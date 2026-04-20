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

"""Hetzner Cloud implementation of the CloudProvider interface."""

import base64
import hashlib
import re as _re

_HETZNER_DC_CODE_RE = _re.compile(r"^[a-z]+\d+$")

from hcloud.ssh_keys.domain import SSHKey
from hcloud.servers.client import BoundServer, BoundVolume
from hcloud.servers.domain import Server
from hcloud.images.domain import Image
from hcloud.server_types.domain import ServerType
from hcloud.locations.domain import Location

from ...hclient import HClient
from ...actions import Action
from ...cloud_provider import CloudProvider, ProviderServer, ProviderServerType, ProviderVolume
from . import config as hetzner_config
from ...constants import github_runner_label


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

    # Private IPv4: take the first private network IP if present.
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
        status=volume.status if volume.status else "",
        device_path=volume.linux_device or "",
        _native=volume,
    )


class HetznerCloudProvider(CloudProvider):
    """Hetzner Cloud implementation of CloudProvider.

    Wraps HClient (hcloud.Client subclass) and delegates to the existing
    validation helpers in providers/hetzner/config.py.
    """

    def __init__(self, token: str, ssh_key_path: str = None, default_image=None):
        """Initialise the provider.

        Args:
            token: Hetzner Cloud API token.
            ssh_key_path: Optional path to a public SSH key file.  When
                supplied, ``get_or_create_ssh_key`` can accept ``is_file=True``.
            default_image: Default image to use when no ``image-`` label is
                present.  Accepts a validated hcloud ``Image`` object (from
                ``config.default_image``) or a raw spec string.
        """
        self._token = token
        self._ssh_key_path = ssh_key_path
        self._client = HClient(token=token)
        self._default_image = default_image

    # ---------------------------------------------------------------------------
    # Identity
    # ---------------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "hetzner"

    @property
    def supports_recycling(self) -> bool:
        return True

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
        labels: dict[str, str],
        volumes: list = None,
        automount: bool = False,
        public_net=None,
    ) -> ProviderServer:
        """Create a server and return a ProviderServer wrapping the BoundServer."""
        response = self._client.servers.create(
            name=name,
            # Unwrap ProviderServerType; accept raw ServerType for callers that
            # haven't migrated yet (e.g. recycle_server in scale_up.py).
            server_type=server_type._native if isinstance(server_type, ProviderServerType) else server_type,
            location=location,
            image=image,
            ssh_keys=ssh_keys,
            labels=labels,
            volumes=volumes or [],
            automount=automount,
            public_net=public_net,
        )
        bound_server: BoundServer = response.server
        # Propagate volume attachment bookkeeping the caller expects.
        if volumes:
            bound_server.volumes = volumes
            for vol in volumes:
                vol.server = bound_server
        return _server_to_provider(bound_server)

    def delete_server(self, server: ProviderServer) -> None:
        """Delete the server via its native BoundServer."""
        native: BoundServer = server._native
        native.delete()

    def get_server(self, name: str) -> "ProviderServer | None":
        """Look up a server by name."""
        bound = self._client.servers.get_by_name(name=name)
        if bound is None:
            return None
        return _server_to_provider(bound)

    def list_servers(self, label_selector: str = None) -> list[ProviderServer]:
        """List servers, optionally filtered by label selector."""
        servers = self._client.servers.get_all(label_selector=label_selector)
        return [_server_to_provider(s) for s in servers]

    def power_off_server(self, server: ProviderServer) -> None:
        """Power off the server."""
        native: BoundServer = server._native
        native.power_off()

    def power_on_server(self, server: ProviderServer) -> None:
        """Power on the server."""
        native: BoundServer = server._native
        native.power_on()

    def rebuild_server(self, server: ProviderServer, image_spec) -> None:
        """Rebuild the server with the given image. Blocks until finished."""
        from hcloud import APIException

        native: BoundServer = server._native
        try:
            native.rebuild(image=image_spec).action.wait_until_finished(
                max_retries=300
            )
        except APIException as exc:
            raise APIException(
                code=exc.code,
                message=f"error while rebuilding server {native.name}: {exc.message}",
                details=getattr(exc, "details", None),
            ) from exc

    # ---------------------------------------------------------------------------
    # Runner identification
    # ---------------------------------------------------------------------------

    def list_runner_servers(self) -> list[ProviderServer]:
        """Return all active runner servers using the Hetzner label convention."""
        return self.list_servers(label_selector=f"{github_runner_label}=active")

    # ---------------------------------------------------------------------------
    # Runner label helpers
    # ---------------------------------------------------------------------------

    def get_runner_labels(self, server: ProviderServer) -> set:
        """Return the job labels attached to this runner server.

        Hetzner stores each label value under a numbered key with the prefix
        ``github-hetzner-runner-label``.  This extracts just the values.
        """
        return {
            value.lower()
            for key, value in server.labels.items()
            if key.startswith("github-hetzner-runner-label")
        }

    # ---------------------------------------------------------------------------
    # Server metadata helpers
    # ---------------------------------------------------------------------------

    def build_server_labels(
        self, runner_labels: list[str], ssh_key_name: str = None
    ) -> dict[str, str]:
        """Return Hetzner tag dict for a runner server.

        Each runner label is stored under a numbered ``github-hetzner-runner-label-{i}``
        key so it satisfies Hetzner's label value constraints.
        """
        from ...constants import server_ssh_key_label, github_runner_label

        labels = {
            f"github-hetzner-runner-label-{i}": value
            for i, value in enumerate(runner_labels)
        }
        if ssh_key_name:
            labels[server_ssh_key_label] = ssh_key_name
        labels[github_runner_label] = "active"
        return labels

    def build_volume_labels(
        self, arch: str, os_flavor: str, os_version: str
    ) -> dict[str, str]:
        """Return Hetzner tag dict for a runner volume."""
        return {
            "github-hetzner-runner-volume": "active",
            "github-hetzner-runner-arch": arch,
            "github-hetzner-runner-os": os_flavor,
            "github-hetzner-runner-os-version": os_version,
        }

    def validate_labels(self, labels: dict[str, str]) -> "tuple[bool, str]":
        """Validate labels against Hetzner's label constraints."""
        from hcloud.helpers.labels import LabelValidator

        return LabelValidator.validate_verbose(labels=labels)

    def update_server(
        self, server: ProviderServer, name: str, labels: dict[str, str]
    ) -> ProviderServer:
        """Rename the server and replace its labels atomically."""
        native: BoundServer = server._native
        native.update(name=name, labels=labels)
        # Keep ProviderServer in sync with the updated native state.
        server.name = name
        server.labels = labels
        return server

    # ---------------------------------------------------------------------------
    # Tag / label operations
    # ---------------------------------------------------------------------------

    def get_server_tag(self, server: ProviderServer, key: str) -> "str | None":
        """Return the value of a server label, or None."""
        return server.labels.get(key)

    def set_server_tags(self, server: ProviderServer, tags: dict[str, str]) -> None:
        """Merge *tags* onto the server and update the ProviderServer labels."""
        native: BoundServer = server._native
        updated_labels = dict(native.labels or {})
        updated_labels.update(tags)
        native.update(labels=updated_labels)
        # Keep the ProviderServer in sync.
        server.labels = updated_labels

    # ---------------------------------------------------------------------------
    # SSH key management
    # ---------------------------------------------------------------------------

    def get_or_create_ssh_key(self, public_key: str, is_file: bool = False) -> SSHKey:
        """Ensure an SSH key matching *public_key* exists in Hetzner Cloud.

        Args:
            public_key: The public key string (or path when is_file=True).
            is_file: If True, treat *public_key* as a file path and read it.

        Returns:
            The hcloud SSHKey object (BoundSSHKey).
        """

        def fingerprint(key_str: str) -> str:
            encoded_key = base64.b64decode(key_str.strip().split()[1].encode("utf-8"))
            md5_digest = hashlib.md5(encoded_key).hexdigest()
            return ":".join(a + b for a, b in zip(md5_digest[::2], md5_digest[1::2]))

        if is_file:
            with open(public_key, "r", encoding="utf-8") as fh:
                public_key_str = fh.read()
        else:
            public_key_str = public_key

        key_name = hashlib.md5(public_key_str.encode("utf-8")).hexdigest()
        key_fp = fingerprint(public_key_str)

        existing = self._client.ssh_keys.get_by_fingerprint(fingerprint=key_fp)
        if not existing:
            with Action(
                f"Creating SSH key {key_name} with fingerprint {key_fp}",
                stacklevel=3,
            ):
                ssh_key = self._client.ssh_keys.create(
                    name=key_name, public_key=public_key_str
                )
        else:
            ssh_key = existing

        return ssh_key

    # ---------------------------------------------------------------------------
    # Resource discovery
    # ---------------------------------------------------------------------------

    def get_server_type(self, name) -> ProviderServerType:
        """Validate and return a ProviderServerType for *name*.

        Accepts either a plain string name or a ``ServerType`` object.
        Delegates to the existing ``check_server_type`` helper.
        """
        # Accept a raw ServerType object for backwards compatibility with startup
        # validation code that stores the validated hcloud object back into config.
        native_name = name.name if isinstance(name, ServerType) else name
        native = hetzner_config.check_server_type(self._client, ServerType(name=native_name))
        return ProviderServerType(name=native.name, _native=native)

    def get_server_arch(self, server_type: ProviderServerType) -> str:
        """Return the CPU architecture for *server_type*.

        Hetzner ARM64 types use the ``cax`` prefix (CAX11, CAX21, CAX31, CAX41).
        """
        if server_type.name.lower().startswith("ca"):
            return "arm64"
        return "x64"

    def get_location(self, name, required: bool = False) -> "Location | None":
        """Validate and return the hcloud Location for *name*.

        Accepts either a ``Location`` object, a plain string, or None.
        Delegates to ``check_location``.
        """
        if isinstance(name, Location) or name is None:
            return hetzner_config.check_location(self._client, name, required=required)
        return hetzner_config.check_location(
            self._client, Location(name=name), required=required
        )

    def get_image(self, image_spec) -> Image:
        """Validate and return the hcloud Image for *image_spec*.

        Accepts either:
        - An ``hcloud.images.domain.Image`` descriptor (existing validated object)
        - A raw spec string in ``arch:type:name`` (colon-separated) or
          ``arch-type-name`` (hyphen-separated) format, e.g.
          ``"x86:system:ubuntu-22.04"`` or ``"x86-system-ubuntu-22.04"``.
        """
        if isinstance(image_spec, str):
            from ...args import image_type as _parse_hetzner_image

            sep = ":" if ":" in image_spec else "-"
            image_spec = _parse_hetzner_image(image_spec, separator=sep)
        return hetzner_config.check_image(self._client, image_spec)

    def expand_location_label(self, name: str) -> list[str]:
        """Expand a composite Hetzner DC label into individual DC names.

        A composite label like ``hel1-fsn1-nbg1`` means "any of these
        datacentres" and is split into ``['hel1', 'fsn1', 'nbg1']`` so that
        scale_up tries each location in order.  A simple label like ``nbg1``
        is returned as ``['nbg1']``.
        """
        parts = name.split("-")
        if len(parts) > 1 and all(_HETZNER_DC_CODE_RE.match(p) for p in parts):
            return parts
        return [name]

    # ---------------------------------------------------------------------------
    # Volume operations
    # ---------------------------------------------------------------------------

    def create_volume(
        self,
        name: str,
        size: int,
        location,
        labels: dict[str, str] = None,
        format: str = "ext4",
        automount: bool = False,
    ) -> ProviderVolume:
        """Create a Hetzner volume."""
        response = self._client.volumes.create(
            name=name,
            size=size,
            location=location,
            labels=labels or {},
            format=format,
            automount=automount,
        )
        new_vol = response.volume
        response.action.wait_until_finished()
        new_vol.reload()
        return _volume_to_provider(new_vol)

    def delete_volume(self, volume: ProviderVolume) -> None:
        """Delete a Hetzner volume."""
        native: BoundVolume = volume._native
        native.delete()

    def get_volume(self, name: str) -> "ProviderVolume | None":
        """Look up a volume by name."""
        bound = self._client.volumes.get_by_name(name=name)
        if bound is None:
            return None
        return _volume_to_provider(bound)

    def list_volumes(self, label_selector: str = None) -> list[ProviderVolume]:
        """List Hetzner volumes, optionally filtered by label selector.

        Overrides the base-class stub so Hetzner volumes can be retrieved
        without accessing ``_client`` directly from generic paths.
        """
        vols = self._client.volumes.get_all(label_selector=label_selector)
        return [_volume_to_provider(v) for v in vols]

    def resize_volume(self, volume: ProviderVolume, size: int) -> None:
        """Resize a Hetzner volume."""
        native: BoundVolume = volume._native
        native.resize(size).wait_until_finished()
        native.size = size
        volume.size = size

    # ---------------------------------------------------------------------------
    # Prices (Hetzner-specific convenience — not part of the abstract interface)
    # ---------------------------------------------------------------------------

    def get_prices(self) -> dict[str, dict[str, float]]:
        """Return a mapping of server_type_name -> location_name -> hourly_gross_price."""
        return hetzner_config.check_prices(self._client)
