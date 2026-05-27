"""AWS API adapter utilities: tag helpers, instance/AZ converters."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from ...cloud_provider import CloudProvider, ProviderServer


# AWS-specific tag keys used to identify and annotate runner instances.
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
