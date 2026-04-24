# Copyright 2025 Katteli Inc.
# TestFlows.com Open-Source Software Testing Framework (http://testflows.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""AWS EC2 implementation of the CloudProvider interface."""

import re
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from ...cloud_provider import CloudProvider, ProviderServer, ProviderServerType
from ...errors import ServerTypeError, ImageError, ImageSpecFormatError, LocationError


# AWS-specific tag keys used to identify and annotate runner instances.
# These are internal to AWSCloudProvider and not shared with other providers.
_RUNNER_TAG = "github-runner"
_RUNNER_LABEL_TAG_PREFIX = "github-runner-label"
_SSH_KEY_TAG = "github-runner-ssh-key"

# EC2 instance states considered "active" (included in server listings).
_ACTIVE_STATES = ["pending", "running", "stopping", "stopped"]

# Map EC2 instance state names to abstract CloudProvider status constants.
_STATE_MAP = {
    "pending": CloudProvider.STATUS_STARTING,
    "running": CloudProvider.STATUS_RUNNING,
    "stopping": CloudProvider.STATUS_STOPPING,
    "stopped": CloudProvider.STATUS_OFF,
    "shutting-down": CloudProvider.STATUS_DELETING,
    "terminated": CloudProvider.STATUS_DELETING,
    "rebooting": CloudProvider.STATUS_STARTING,
}

# ARM64 (Graviton) instance family pattern.
# Covers: t4g, m6g/m7g/m6gd/m7gd, c6g/c7g/c6gd/c6gn, r6g/r7g/r6gd, a1, im4gn, is4gen.
_ARM64_RE = re.compile(r"^(t4g|[mcr]\d+g[a-z]*|a1|im4gn|is4gen)\.")


@dataclass
class AWSKeyPair:
    """Minimal key-pair descriptor returned by ``get_or_create_ssh_key``."""

    name: str


def _tags_to_dict(tags) -> dict:
    """Convert boto3 ``Tags`` list to a plain ``{key: value}`` dict."""
    return {t["Key"]: t["Value"] for t in (tags or [])}


def _instance_to_provider(instance: dict, ssh_user: str = "ubuntu") -> ProviderServer:
    """Convert a boto3 EC2 instance dict to a ProviderServer."""
    tags = _tags_to_dict(instance.get("Tags"))
    name = tags.get("Name", instance["InstanceId"])

    public_ipv6 = None
    for iface in instance.get("NetworkInterfaces", []):
        for addr in iface.get("Ipv6Addresses", []):
            public_ipv6 = addr.get("Ipv6Address")
            break
        if public_ipv6:
            break

    return ProviderServer(
        id=instance["InstanceId"],
        name=name,
        status=_STATE_MAP.get(
            instance.get("State", {}).get("Name", "unknown"),
            CloudProvider.STATUS_UNKNOWN,
        ),
        public_ipv4=instance.get("PublicIpAddress"),
        private_ipv4=instance.get("PrivateIpAddress"),
        public_ipv6=public_ipv6,
        labels=tags,
        server_type=instance.get("InstanceType", ""),
        location=instance.get("Placement", {}).get("AvailabilityZone", ""),
        created=instance.get("LaunchTime") or datetime.now(timezone.utc),
        volumes=[],
        ssh_user=ssh_user,
        _native=instance,
    )


def _az_to_region(az: str) -> str:
    """Derive AWS region name from an availability zone by stripping trailing letter.

    Example: ``us-east-1a`` → ``us-east-1``.
    """
    return re.sub(r"[a-z]$", "", az) if az else "us-east-1"


class AWSCloudProvider(CloudProvider):
    """AWS EC2 implementation of CloudProvider.

    Uses ``boto3`` (optional dependency: ``pip install testflows.runners[aws]``).
    Recycling is not supported (``supports_recycling = False``).
    Volume operations raise ``NotImplementedError`` (inherited from base class).
    """

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        region: str,
        security_group: str = None,
        subnet: str = None,
        default_image_spec: str = None,
        default_location_spec: str = None,
        ssh_user: str = "ubuntu",
        root_volume_size: int = 20,
        root_volume_type: str = "gp3",
    ):
        """Initialise the provider.

        Args:
            access_key_id: AWS access key ID.
            secret_access_key: AWS secret access key.
            region: AWS region (e.g. ``us-east-1``).
            security_group: Security group ID to attach to new instances.
            subnet: Subnet ID to launch instances into.
            default_image_spec: Default AMI ID or SSM parameter path used when
                no ``image-`` label is present on the job.
            default_location_spec: Default availability zone (e.g. ``us-east-1a``)
                used when no ``in-`` label is present on the job.
        """
        import boto3

        self._session = boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )
        self._ec2 = self._session.client("ec2")
        self._region = region
        self._security_group = security_group
        self._subnet = subnet
        self._default_image = default_image_spec
        self._default_location = default_location_spec
        self._ssh_user = ssh_user
        self._root_volume_size = root_volume_size
        self._root_volume_type = root_volume_type

    # ---------------------------------------------------------------------------
    # Identity
    # ---------------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "aws"

    @property
    def supports_recycling(self) -> bool:
        return False

    # ---------------------------------------------------------------------------
    # Server lifecycle
    # ---------------------------------------------------------------------------

    def create_server(
        self,
        name: str,
        server_type: ProviderServerType,
        location,
        image,
        ssh_keys: list,
        labels: dict,
        volumes: list = None,
        automount: bool = False,
        public_net=None,
    ) -> ProviderServer:
        """Launch an EC2 instance and return a ProviderServer wrapping it.

        ``public_net`` and ``volumes`` are ignored for AWS.
        """
        tag_specs = [{"Key": "Name", "Value": name}] + [
            {"Key": k, "Value": v} for k, v in labels.items()
        ]
        kwargs = {
            "ImageId": image,
            "InstanceType": server_type.name,
            "MinCount": 1,
            "MaxCount": 1,
            "TagSpecifications": [
                {"ResourceType": "instance", "Tags": tag_specs}
            ],
        }
        if ssh_keys:
            kwargs["KeyName"] = ssh_keys[0].name
        if self._subnet:
            # Use NetworkInterfaces to explicitly request a public IP.
            # SubnetId and SecurityGroupIds must live inside the interface
            # spec when NetworkInterfaces is used — they cannot be top-level.
            iface = {
                "DeviceIndex": 0,
                "SubnetId": self._subnet,
                "AssociatePublicIpAddress": True,
            }
            if self._security_group:
                iface["Groups"] = [self._security_group]
            kwargs["NetworkInterfaces"] = [iface]
        else:
            if self._security_group:
                kwargs["SecurityGroupIds"] = [self._security_group]
        if location:
            kwargs["Placement"] = {"AvailabilityZone": location}

        ebs = {"VolumeSize": self._root_volume_size, "DeleteOnTermination": True}
        if self._root_volume_type:
            ebs["VolumeType"] = self._root_volume_type
        kwargs["BlockDeviceMappings"] = [{"DeviceName": "/dev/sda1", "Ebs": ebs}]

        response = self._ec2.run_instances(**kwargs)
        instance_id = response["Instances"][0]["InstanceId"]

        # RunInstances returns the instance before IP assignment completes.
        # Wait for "running" state, then re-describe to capture PublicIpAddress.
        waiter = self._ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id])

        describe = self._ec2.describe_instances(InstanceIds=[instance_id])
        instance = describe["Reservations"][0]["Instances"][0]
        return _instance_to_provider(instance, ssh_user=self._ssh_user)

    def delete_server(self, server: ProviderServer) -> None:
        self._ec2.terminate_instances(InstanceIds=[server.id])

    def get_server(self, name: str) -> ProviderServer | None:
        response = self._ec2.describe_instances(
            Filters=[
                {"Name": "tag:Name", "Values": [name]},
                {"Name": "instance-state-name", "Values": _ACTIVE_STATES},
            ]
        )
        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                return _instance_to_provider(instance, ssh_user=self._ssh_user)
        return None

    def list_servers(self, label_selector: str = None) -> list[ProviderServer]:
        """List EC2 instances in active states, optionally filtered by a tag selector.

        Accepts the ``key=value`` selector format used across all providers.
        """
        filters = [
            {"Name": "instance-state-name", "Values": _ACTIVE_STATES}
        ]
        if label_selector and "=" in label_selector:
            key, value = label_selector.split("=", 1)
            filters.append({"Name": f"tag:{key}", "Values": [value]})

        response = self._ec2.describe_instances(Filters=filters)
        servers = []
        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                servers.append(_instance_to_provider(instance, ssh_user=self._ssh_user))
        return servers

    def power_off_server(self, server: ProviderServer) -> None:
        self._ec2.stop_instances(InstanceIds=[server.id])

    def power_on_server(self, server: ProviderServer) -> None:
        self._ec2.start_instances(InstanceIds=[server.id])

    def rebuild_server(self, server: ProviderServer, image_spec) -> None:
        raise NotImplementedError("AWS provider does not support server recycling")

    # ---------------------------------------------------------------------------
    # Runner identification
    # ---------------------------------------------------------------------------

    def list_runner_servers(self) -> list[ProviderServer]:
        return self.list_servers(label_selector=f"{_RUNNER_TAG}=active")

    # ---------------------------------------------------------------------------
    # Runner label helpers
    # ---------------------------------------------------------------------------

    def get_runner_labels(self, server: ProviderServer) -> set:
        return {
            value.lower()
            for key, value in server.labels.items()
            if key.startswith(_RUNNER_LABEL_TAG_PREFIX)
        }

    # ---------------------------------------------------------------------------
    # Tag / label operations
    # ---------------------------------------------------------------------------

    def get_server_tag(self, server: ProviderServer, key: str) -> str | None:
        return server.labels.get(key)

    def set_server_tags(self, server: ProviderServer, tags: dict) -> None:
        self._ec2.create_tags(
            Resources=[server.id],
            Tags=[{"Key": k, "Value": v} for k, v in tags.items()],
        )
        server.labels = {**server.labels, **tags}

    # ---------------------------------------------------------------------------
    # SSH key management
    # ---------------------------------------------------------------------------

    def get_or_create_ssh_key(self, public_key: str, is_file: bool = False) -> AWSKeyPair:
        """Ensure an EC2 key pair matching *public_key* exists.

        The key pair name is derived from the MD5 hash of the public key,
        matching the convention used by ``HetznerCloudProvider``.

        Args:
            public_key: Public key string or file path when ``is_file=True``.
            is_file: If True, treat *public_key* as a file path and read it.

        Returns:
            ``AWSKeyPair`` with the key pair name.
        """
        from botocore.exceptions import ClientError

        if is_file:
            with open(public_key, "r", encoding="utf-8") as fh:
                public_key_str = fh.read().strip()
        else:
            public_key_str = public_key.strip()

        key_name = hashlib.md5(public_key_str.encode("utf-8")).hexdigest()

        try:
            self._ec2.describe_key_pairs(KeyNames=[key_name])
            return AWSKeyPair(name=key_name)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "InvalidKeyPair.NotFound":
                pass  # doesn't exist yet — import it below
            else:
                raise

        self._ec2.import_key_pair(
            KeyName=key_name,
            PublicKeyMaterial=public_key_str.encode("utf-8"),
        )
        return AWSKeyPair(name=key_name)

    # ---------------------------------------------------------------------------
    # Server metadata helpers
    # ---------------------------------------------------------------------------

    def build_server_labels(
        self, runner_labels: list, ssh_key_name: str = None
    ) -> dict:
        """Return EC2 tag dict for a runner instance."""
        labels = {
            f"{_RUNNER_LABEL_TAG_PREFIX}-{i}": value
            for i, value in enumerate(runner_labels)
        }
        if ssh_key_name:
            labels[_SSH_KEY_TAG] = ssh_key_name
        labels[_RUNNER_TAG] = "active"
        return labels

    def build_volume_labels(self, arch: str, os_flavor: str, os_version: str) -> dict:
        """Return EC2 tag dict for a runner volume (for future EBS support)."""
        return {
            "github-runner-volume": "active",
            "github-runner-arch": arch,
            "github-runner-os": os_flavor,
            "github-runner-os-version": os_version,
        }

    def validate_labels(self, labels: dict) -> tuple[bool, str]:
        """Validate AWS EC2 tag key/value constraints.

        Enforces: key ≤ 128 chars, value ≤ 256 chars, key must not start with ``aws:``.
        """
        for key, value in labels.items():
            if len(key) > 128:
                return False, f"tag key '{key}' exceeds 128 characters"
            if len(str(value)) > 256:
                return False, f"tag value for key '{key}' exceeds 256 characters"
            if key.lower().startswith("aws:"):
                return False, f"tag key '{key}' uses the reserved prefix 'aws:'"
        return True, ""

    def update_server(
        self, server: ProviderServer, name: str, labels: dict
    ) -> ProviderServer:
        """Rename the instance (via Name tag) and replace its labels.

        EC2 has no atomic "replace all tags" operation.  We approximate the
        contract by first removing tags that are absent from the new set, then
        writing the new ones.  The window between the two calls is not atomic,
        but the end state matches the caller's intent.
        """
        new_tag_dict = {"Name": name, **labels}

        # Use EC2 as the source of truth for currently attached tags so stale
        # keys are removed even if the local ProviderServer snapshot is old.
        current_tags = {}
        describe = self._ec2.describe_instances(InstanceIds=[server.id])
        reservations = describe.get("Reservations", []) if isinstance(describe, dict) else []
        for reservation in reservations:
            for instance in reservation.get("Instances", []):
                if instance.get("InstanceId") == server.id:
                    current_tags = _tags_to_dict(instance.get("Tags"))
                    break
            if current_tags:
                break
        if not current_tags:
            current_tags = dict(server.labels or {})

        keys_to_remove = [
            {"Key": k}
            for k in current_tags
            if k not in new_tag_dict and not k.lower().startswith("aws:")
        ]
        if keys_to_remove:
            self._ec2.delete_tags(Resources=[server.id], Tags=keys_to_remove)
        self._ec2.create_tags(
            Resources=[server.id],
            Tags=[{"Key": k, "Value": v} for k, v in new_tag_dict.items()],
        )
        server.name = name
        server.labels = new_tag_dict
        return server

    # ---------------------------------------------------------------------------
    # Resource discovery
    # ---------------------------------------------------------------------------

    def get_server_type(self, name: str) -> ProviderServerType:
        """Validate and return a ProviderServerType for the given EC2 instance type."""
        from botocore.exceptions import ClientError

        try:
            response = self._ec2.describe_instance_types(InstanceTypes=[name])
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if "InvalidInstanceType" in code or "InvalidParameterValue" in code:
                raise ServerTypeError(
                    f"AWS instance type '{name}' not found"
                ) from exc
            raise
        if response.get("InstanceTypes"):
            it = response["InstanceTypes"][0]
            return ProviderServerType(name=it["InstanceType"], _native=it)
        raise ServerTypeError(f"AWS instance type '{name}' not found")

    def get_server_arch(self, server_type: ProviderServerType) -> str:
        """Return CPU architecture for *server_type*.

        AWS Graviton (ARM64) families match the pattern
        ``t4g``, ``m*g``, ``c*g``, ``r*g``, ``a1``, ``im4gn``, ``is4gen``.
        """
        if _ARM64_RE.match(server_type.name.lower()):
            return "arm64"
        return "x64"

    def get_location(self, name, required: bool = False) -> str | None:
        """Validate and return the AWS availability zone name for *name*."""
        if name is None:
            if required:
                raise LocationError("AWS availability zone is not defined")
            return None
        from botocore.exceptions import ClientError

        try:
            response = self._ec2.describe_availability_zones(ZoneNames=[name])
        except ClientError as exc:
            raise LocationError(
                f"AWS availability zone '{name}' not found"
            ) from exc
        if response.get("AvailabilityZones"):
            return response["AvailabilityZones"][0]["ZoneName"]
        raise LocationError(f"AWS availability zone '{name}' not found")

    def get_image(self, image_spec) -> str:
        """Resolve and validate an AWS image spec. Returns the AMI ID string.

        Accepted formats:

        - ``"ami-{id}"`` — direct AMI ID; validated against EC2.
        - ``"resolve:ssm:{path}"`` — SSM Parameter Store path that resolves to
          an AMI ID (e.g. ``resolve:ssm:/aws/service/canonical/ubuntu/...``).
        """
        from botocore.exceptions import ClientError

        if image_spec is None:
            raise ImageError("AWS image spec is required")

        spec = str(image_spec)

        if spec.startswith("resolve:ssm:"):
            path = spec[len("resolve:ssm:"):]
            try:
                ssm = self._session.client("ssm", region_name=self._region)
                response = ssm.get_parameter(Name=path)
                ami_id = response["Parameter"]["Value"]
            except Exception as exc:
                raise ImageError(
                    f"failed to resolve SSM parameter '{path}': {exc}"
                ) from exc
        elif spec.startswith("ami-"):
            ami_id = spec
        else:
            raise ImageSpecFormatError(
                f"unsupported AWS image spec '{spec}'; "
                "expected 'ami-{{id}}' or 'resolve:ssm:{{path}}'"
            )

        # Validate that the AMI exists and is available in this region.
        try:
            response = self._ec2.describe_images(
                ImageIds=[ami_id],
                Filters=[{"Name": "state", "Values": ["available"]}],
            )
        except ClientError as exc:
            raise ImageError(f"AWS AMI '{ami_id}' not found: {exc}") from exc
        if not response.get("Images"):
            raise ImageError(f"AWS AMI '{ami_id}' not found or not available")
        return ami_id
