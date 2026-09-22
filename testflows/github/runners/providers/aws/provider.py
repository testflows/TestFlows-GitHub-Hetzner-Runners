"""AWS EC2 implementation of the CloudProvider interface."""

import hashlib

from ...cloud_provider import CloudProvider, ProviderServer, ProviderServerType
from ...errors import ServerTypeError, ImageError, ImageSpecFormatError, LocationError
from ...constants import github_runner_label
from ...utils import derive_runner_tag
from . import estimate
from .utils import (
    _RUNNER_LABEL_TAG_PREFIX,
    _SSH_KEY_TAG,
    _ACTIVE_STATES,
    _STATE_MAP,
    _ARM64_RE,
    AWSKeyPair,
    _tags_to_dict,
    _instance_to_provider,
    _az_to_region,
)


class AWSCloudProvider(CloudProvider):
    """AWS EC2 implementation of CloudProvider.

    Uses ``boto3`` (optional dependency: ``pip install testflows.github.runners[aws]``).
    Recycling uses the default create/delete lifecycle (no reusable pool).
    Volume operations raise ``NotImplementedError`` (inherited from base class).
    """

    config_key = "aws"
    precedence = 2

    @classmethod
    def from_config(cls, config) -> "AWSCloudProvider | None":
        """Construct from Config, or None if AWS is not configured."""
        cfg = config.providers.aws
        if not (cfg and cfg.access_key_id and cfg.secret_access_key):
            return None
        location = cfg.defaults.location or "us-east-1a"
        region = _az_to_region(location)
        provider = cls(
            access_key_id=cfg.access_key_id,
            secret_access_key=cfg.secret_access_key,
            region=region,
            security_group=cfg.security_group,
            subnets=cfg.subnets,
            default_image_spec=cfg.defaults.image,
            default_location_spec=location,
            default_server_type_spec=cfg.defaults.server_type,
            ssh_user=cfg.ssh_user,
            root_disk_size=cfg.defaults.disk_size,
            root_disk_type=cfg.defaults.disk_type,
            max_runners=cfg.max_runners,
            end_of_life=cfg.end_of_life,
            recycle=cfg.recycle,
            recycle_grace_period=cfg.recycle_grace_period,
        )
        provider._runner_tag = derive_runner_tag(
            config.github_repository, config.with_label
        )
        return provider

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        region: str,
        security_group: str = None,
        subnets: list[str] = None,
        default_image_spec: str = None,
        default_location_spec: str = None,
        default_server_type_spec: str = None,
        ssh_user: str = "ubuntu",
        root_disk_size: int = 20,
        root_disk_type: str = "gp3",
        max_runners: int = None,
        end_of_life: int = None,
        recycle: bool = None,
        recycle_grace_period: int = None,
    ):
        """Initialise the provider.

        Args:
            access_key_id: AWS access key ID.
            secret_access_key: AWS secret access key.
            region: AWS region (e.g. ``us-east-1``).
            security_group: Security group ID to attach to new instances.
            subnets: Subnet IDs to launch instances into.  Each subnet belongs
                to exactly one AZ; the provider maps subnet → AZ at init time
                and uses this to expand location labels and select the right
                subnet for each create_server call.  When multiple subnets are
                provided the scale-up loop will try each AZ in turn, giving
                automatic fallback when one AZ has insufficient capacity.
            default_image_spec: Default AMI ID or SSM parameter path used when
                no ``image-`` label is present on the job.
            default_location_spec: Default availability zone (e.g. ``us-east-1a``)
                used when no ``in-`` label is present on the job.  When None,
                all configured subnet AZs are tried.
            max_runners: Per-provider runner cap (overrides global max_runners).
            end_of_life: Per-provider end-of-life in minutes (overrides global).
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
        self._default_image = default_image_spec
        self._default_location = default_location_spec
        self._default_server_type = default_server_type_spec
        self._ssh_user = ssh_user
        self._root_disk_size = root_disk_size
        self._root_disk_type = root_disk_type
        self._max_runners = max_runners
        self._end_of_life = end_of_life
        self._recycle = recycle
        self._recycle_grace_period = recycle_grace_period
        self._runner_tag = "active"

        # Build subnet → AZ mapping from describe_subnets.
        # This is a single API call at init time; the result is cached for the
        # lifetime of the provider instance.
        self._subnet_az_map: dict[str, str] = {}  # subnet_id → az
        if subnets:
            import botocore.exceptions

            # from_config resolves an unset location to "us-east-1a", so a
            # default can't be told from an explicit value here. Note the
            # default whenever the value matches -- true either way, and
            # the only case the message would name a value the user never
            # wrote.
            _location_note = (
                " (the default)" if default_location_spec == "us-east-1a" else ""
            )

            requested = list(subnets)
            try:
                response = self._ec2.describe_subnets(SubnetIds=requested)
            except botocore.exceptions.ClientError as exc:
                raise LocationError(
                    f"failed to look up subnet(s) {requested} in region "
                    f"'{self._region}' from "
                    f"providers.aws.defaults.location={default_location_spec!r}"
                    f"{_location_note}. Subnets are region-scoped -- set "
                    "providers.aws.defaults.location to an AZ in their "
                    f"region. Original error: {exc}"
                ) from exc
            for s in response.get("Subnets", []):
                self._subnet_az_map[s["SubnetId"]] = s["AvailabilityZone"]

            missing = [sid for sid in requested if sid not in self._subnet_az_map]
            if missing:
                raise LocationError(
                    f"describe_subnets did not return subnet(s) {missing} "
                    f"in region '{self._region}' from "
                    f"providers.aws.defaults.location={default_location_spec!r}"
                    f"{_location_note}. Check those subnet ids exist in "
                    "that region."
                )

    # ---------------------------------------------------------------------------
    # Identity
    # ---------------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "aws"

    @property
    def currency(self) -> str:
        return "USD"

    def get_prices(self) -> dict[str, dict[str, float]]:
        return estimate.check_prices(self._region, session=self._session)

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
        public_net=None,
        root_disk_size: int = None,
    ) -> ProviderServer:
        """Launch an EC2 instance and return a ProviderServer wrapping it.

        ``public_net`` and ``volumes`` are ignored for AWS. ``root_disk_size``
        (GB), when given, sizes the EBS root volume for this instance instead of
        the provider's configured default.
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

        # Pick the subnet for the requested AZ (if subnets are configured).
        # The subnet implicitly pins the AZ, so no separate Placement kwarg
        # is needed — and mixing SubnetId with Placement.AvailabilityZone
        # causes an AWS error if they disagree.
        subnet = None
        if self._subnet_az_map:
            if location:
                # Find the first subnet in the requested AZ.
                subnet = next(
                    (sid for sid, az in self._subnet_az_map.items() if az == location),
                    None,
                )
                if subnet is None:
                    raise LocationError(
                        f"No configured subnet found for availability zone '{location}'"
                    )
            else:
                # No location preference — use the first configured subnet.
                subnet = next(iter(self._subnet_az_map))

        if subnet:
            # Use NetworkInterfaces to explicitly request a public IP.
            # SubnetId and SecurityGroupIds must live inside the interface
            # spec when NetworkInterfaces is used — they cannot be top-level.
            iface = {
                "DeviceIndex": 0,
                "SubnetId": subnet,
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

        ebs = {
            "VolumeSize": root_disk_size or self._root_disk_size,
            "DeleteOnTermination": True,
        }
        if self._root_disk_type:
            ebs["VolumeType"] = self._root_disk_type
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

    def power_on_server(
        self, server: ProviderServer, timeout: int | None = None
    ) -> None:
        self._ec2.start_instances(InstanceIds=[server.id])

    def rebuild_server(self, server: ProviderServer, image_spec) -> None:
        raise NotImplementedError("AWS provider does not support server recycling")

    # ---------------------------------------------------------------------------
    # Runner identification
    # ---------------------------------------------------------------------------
    # Runner label helpers
    # ---------------------------------------------------------------------------

    def get_runner_labels(self, server: ProviderServer) -> set:
        return {
            value.lower()
            for key, value in server.labels.items()
            if key.startswith(_RUNNER_LABEL_TAG_PREFIX)
        }

    def is_runner_label_tag(self, key: str) -> bool:
        return key.startswith(_RUNNER_LABEL_TAG_PREFIX)

    # ---------------------------------------------------------------------------
    # Tag / label operations
    # ---------------------------------------------------------------------------

    def get_server_tag(self, server: ProviderServer, key: str) -> str | None:
        return server.labels.get(key)

    def set_server_tags(self, server: ProviderServer, tags: dict) -> None:
        """Set/merge tags; a tag with value ``None`` is deleted."""
        to_set = {k: v for k, v in tags.items() if v is not None}
        to_delete = [k for k, v in tags.items() if v is None]
        if to_set:
            self._ec2.create_tags(
                Resources=[server.id],
                Tags=[{"Key": k, "Value": v} for k, v in to_set.items()],
            )
        if to_delete:
            self._ec2.delete_tags(
                Resources=[server.id],
                Tags=[{"Key": k} for k in to_delete],
            )
        new_labels = {**server.labels, **to_set}
        for k in to_delete:
            new_labels.pop(k, None)
        server.labels = new_labels

    def has_matching_ssh_key(
        self, server: ProviderServer, ssh_key_names: set[str]
    ) -> bool:
        key_name = server.labels.get(_SSH_KEY_TAG)
        return key_name in ssh_key_names if key_name is not None else False

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
        labels[github_runner_label] = self._runner_tag
        return labels

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

    def expand_location_label(self, name: str) -> list[str]:
        """Expand a location label into a list of AZs to try.

        If subnets are configured and *name* is None (no ``in-`` label on the
        job), return all AZs covered by the configured subnets so the scale-up
        loop tries each in turn.  Otherwise return ``[name]`` (the base class
        behaviour).
        """
        if name is None and self._subnet_az_map:
            # Deduplicate while preserving subnet order.
            seen = {}
            for az in self._subnet_az_map.values():
                seen[az] = None
            return list(seen)
        return [name]

    def get_location(self, name, required: bool = False) -> str | None:
        """Validate and return the AWS availability zone name for *name*."""
        if name is None:
            if required:
                raise LocationError("AWS availability zone is not defined")
            return None
        # Accept AZs that we have a subnet for without an extra API call.
        if name in self._subnet_az_map.values():
            return name
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

    # Canonical's AWS account id; owns the official Ubuntu AMIs.
    _CANONICAL_OWNER_ID = "099720109477"

    def _resolve_canonical_ubuntu(self, version: str, arch: str = "amd64") -> str:
        """Newest Canonical Ubuntu <version> AMI in this region, via
        DescribeImages (needs ec2:DescribeImages, not ssm:GetParameter)."""
        from botocore.exceptions import ClientError

        name = f"ubuntu/images/hvm-ssd*/ubuntu-*-{version}-{arch}-server-*"
        try:
            response = self._ec2.describe_images(
                Owners=[self._CANONICAL_OWNER_ID],
                Filters=[
                    {"Name": "name", "Values": [name]},
                    {"Name": "state", "Values": ["available"]},
                ],
            )
        except ClientError as exc:
            raise ImageError(
                f"failed to resolve Ubuntu {version} ({arch}) AMI: {exc}"
            ) from exc
        images = response.get("Images") or []
        if not images:
            raise ImageError(
                f"no Canonical Ubuntu {version} {arch} AMI available in this region"
            )
        return max(images, key=lambda i: i["CreationDate"])["ImageId"]

    def get_image(self, image_spec) -> str:
        """Resolve and validate an AWS image spec. Returns the AMI ID string.

        Accepted formats:

        - ``"ami-{id}"`` — direct AMI ID; validated against EC2.
        - ``"ubuntu-{version}"`` — newest Canonical Ubuntu release (e.g.
          ``ubuntu-22.04``, amd64), resolved via EC2 DescribeImages.
        - ``"resolve:ssm:{path}"`` — SSM Parameter Store path that resolves to
          an AMI ID (needs ``ssm:GetParameter``).
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
        elif spec.startswith("ubuntu-"):
            ami_id = self._resolve_canonical_ubuntu(spec[len("ubuntu-"):])
        else:
            raise ImageSpecFormatError(
                f"unsupported AWS image spec '{spec}'; expected 'ami-{{id}}', "
                "'ubuntu-{{version}}' (e.g. ubuntu-22.04), or 'resolve:ssm:{{path}}'"
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
