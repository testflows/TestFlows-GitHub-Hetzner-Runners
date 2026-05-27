"""Hetzner Cloud API adapter utilities: server/volume converters."""

import re as _re

from hcloud.servers.client import BoundServer, BoundVolume
from hcloud.servers.domain import Server

from ...cloud_provider import CloudProvider, ProviderServer, ProviderVolume


_HETZNER_DC_CODE_RE = _re.compile(r"^[a-z]+\d+$")

# Map hcloud status strings to the abstract status constants.
_STATUS_MAP = {
    Server.STATUS_RUNNING: CloudProvider.STATUS_RUNNING,
    Server.STATUS_OFF: CloudProvider.STATUS_OFF,
    Server.STATUS_STARTING: CloudProvider.STATUS_STARTING,
    Server.STATUS_STOPPING: CloudProvider.STATUS_STOPPING,
    Server.STATUS_REBUILDING: CloudProvider.STATUS_REBUILDING,
    Server.STATUS_MIGRATING: CloudProvider.STATUS_MIGRATING,
    Server.STATUS_DELETING: CloudProvider.STATUS_DELETING,
    Server.STATUS_UNKNOWN: CloudProvider.STATUS_UNKNOWN,
}


def _server_to_provider(server: BoundServer) -> ProviderServer:
    """Convert an hcloud BoundServer to a ProviderServer."""
    ipv4 = None
    if server.public_net and server.public_net.ipv4:
        ipv4 = server.public_net.ipv4.ip

    ipv6 = None
    if server.public_net and server.public_net.primary_ipv6:
        ipv6 = server.public_net.primary_ipv6.ip

    private_ipv4 = None
    if server.private_net:
        for net in server.private_net:
            if net.ip:
                private_ipv4 = net.ip
                break

    return ProviderServer(
        id=server.id,
        name=server.name,
        status=_STATUS_MAP.get(server.status, CloudProvider.STATUS_UNKNOWN),
        public_ipv4=ipv4,
        private_ipv4=private_ipv4,
        public_ipv6=ipv6,
        labels=dict(server.labels) if server.labels else {},
        server_type=server.server_type.name if server.server_type else "",
        location=(
            server.datacenter.location.name
            if server.datacenter and server.datacenter.location
            else ""
        ),
        created=server.created,
        volumes=[_volume_to_provider(v) for v in (server.volumes or [])],
        _native=server,
    )


def _volume_to_provider(volume: BoundVolume) -> ProviderVolume:
    """Convert an hcloud BoundVolume to a ProviderVolume."""
    return ProviderVolume(
        id=volume.id,
        name=volume.name,
        size=volume.size,
        location=volume.location.name if volume.location else "",
        labels=dict(volume.labels) if volume.labels else {},
        status="attached" if volume.server is not None else (volume.status or ""),
        device_path=volume.linux_device or "",
        _native=volume,
    )
