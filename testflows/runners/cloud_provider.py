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

"""Abstract cloud provider interface for multi-cloud runner support."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ProviderServerType:
    """Provider-agnostic server type descriptor."""

    name: str
    # Underlying provider object (e.g. hcloud ServerType). Internal use only.
    _native: Any = field(default=None, repr=False)

    def __str__(self) -> str:
        return self.name


@dataclass
class ProviderVolume:
    """Provider-agnostic volume descriptor."""

    id: Any
    name: str
    size: int
    location: str
    labels: dict[str, str]
    status: str = ""
    # Block device path on the server (e.g. /dev/disk/by-id/...). Provider-specific.
    device_path: str = ""
    # Underlying provider object. Internal use only.
    _native: Any = field(default=None, repr=False)


@dataclass
class ProviderServer:
    """Provider-agnostic server descriptor."""

    id: Any
    name: str
    status: str
    public_ipv4: str | None
    private_ipv4: str | None
    labels: dict[str, str]
    server_type: str
    location: str
    created: datetime
    volumes: list["ProviderVolume"] = field(default_factory=list)
    public_ipv6: str | None = None
    # SSH login user for this server. Defaults to 'root' (Hetzner); override
    # for providers whose AMIs use a different default user (e.g. 'ubuntu' on AWS).
    ssh_user: str = "root"
    # Underlying provider object (e.g. hcloud BoundServer). Internal use only.
    _native: Any = field(default=None, repr=False)


class CloudProvider(ABC):
    """Abstract base class for cloud provider implementations.

    Each provider must implement all abstract methods. Volume operations are
    optional per provider and the base class raises NotImplementedError — providers
    that do not support volumes should leave the base implementation in place.
    """

    # Status constants — providers must map their own status strings to these.
    STATUS_RUNNING = "running"
    STATUS_OFF = "off"
    STATUS_STARTING = "initializing"
    STATUS_STOPPING = "stopping"
    STATUS_REBUILDING = "rebuilding"
    STATUS_MIGRATING = "migrating"
    STATUS_DELETING = "deleting"
    STATUS_UNKNOWN = "unknown"

    # ---------------------------------------------------------------------------
    # Identity
    # ---------------------------------------------------------------------------

    @property
    def default_image(self) -> Any:
        """Default image spec for this provider (set in __init__, None if not configured).

        Used by scale_up when no ``image-`` label is present on the job.  Each
        provider stores its own native format (e.g. a validated hcloud Image for
        Hetzner, an AMI ID string for AWS).
        """
        return getattr(self, "_default_image", None)

    @property
    def default_location(self) -> Any:
        """Default location spec for this provider (set in __init__, None if not configured).

        Used by scale_up when no ``in-`` label is present on the job.  The
        format is provider-specific (e.g. an hcloud Location for Hetzner, an
        availability-zone string for AWS).
        """
        return getattr(self, "_default_location", None)

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name, e.g. 'hetzner' or 'aws'."""

    @property
    @abstractmethod
    def supports_recycling(self) -> bool:
        """True if this provider supports server recycling (rebuild/repurpose)."""

    @property
    def supports_volumes(self) -> bool:
        """True if this provider supports persistent volume operations.

        Defaults to False. Providers that implement create/get/list_volume
        should override this to return True.
        """
        return False

    @property
    def max_runners(self) -> int | None:
        """Per-provider runner cap, or None to use the global limit."""
        return getattr(self, "_max_runners", None)

    @property
    def end_of_life(self) -> int | None:
        """Per-provider end-of-life in minutes, or None to use the global setting."""
        return getattr(self, "_end_of_life", None)

    @property
    def currency(self) -> str:
        """ISO 4217 currency code for this provider's prices (e.g. 'EUR', 'USD')."""
        return "EUR"

    def get_prices(self) -> dict[str, dict[str, float]]:
        """Fetch current prices for this provider's server types.

        Returns a dict of {server_type: {location: hourly_price}}.
        Providers that don't support price fetching return an empty dict.
        """
        return {}

    # ---------------------------------------------------------------------------
    # Server lifecycle
    # ---------------------------------------------------------------------------

    @abstractmethod
    def create_server(
        self,
        name: str,
        server_type: Any,
        location: Any,
        image: Any,
        ssh_keys: list,
        labels: dict[str, str],
        volumes: list = None,
        automount: bool = False,
        public_net: Any = None,
    ) -> ProviderServer:
        """Create a new server and return a ProviderServer descriptor.

        The call should block until the server object is created (though not
        necessarily until it is running). The caller is responsible for waiting
        for SSH availability.
        """

    @abstractmethod
    def delete_server(self, server: ProviderServer) -> None:
        """Delete the given server."""

    @abstractmethod
    def get_server(self, name: str) -> ProviderServer | None:
        """Look up a server by name. Returns None if not found."""

    @abstractmethod
    def list_servers(self, label_selector: str = None) -> list[ProviderServer]:
        """Return all servers, optionally filtered by a label selector string."""

    @abstractmethod
    def power_off_server(self, server: ProviderServer) -> None:
        """Power off (stop) the given server."""

    @abstractmethod
    def power_on_server(self, server: ProviderServer) -> None:
        """Power on (start) the given server."""

    @abstractmethod
    def rebuild_server(self, server: ProviderServer, image_spec: Any) -> None:
        """Rebuild the server from the given image. Blocks until finished."""

    # ---------------------------------------------------------------------------
    # Runner identification
    # ---------------------------------------------------------------------------

    @abstractmethod
    def list_runner_servers(self) -> list[ProviderServer]:
        """Return all servers managed by this provider for runner usage.

        The provider is responsible for filtering by its own internal tag/label
        convention (e.g. Hetzner uses ``github-hetzner-runner=active``).
        """

    # ---------------------------------------------------------------------------
    # Runner label helpers
    # ---------------------------------------------------------------------------

    @abstractmethod
    def get_runner_labels(self, server: ProviderServer) -> set:
        """Return the set of job labels attached to a runner server.

        Each provider stores runner labels in its own tag/key scheme.  This
        method hides that scheme and returns a plain set of lowercase label
        value strings (e.g. ``{"self-hosted", "linux", "arm64"}``).
        """

    # ---------------------------------------------------------------------------
    # Tag / label operations
    # ---------------------------------------------------------------------------

    @abstractmethod
    def get_server_tag(self, server: ProviderServer, key: str) -> str | None:
        """Return the value of a server tag/label, or None if not present."""

    @abstractmethod
    def set_server_tags(self, server: ProviderServer, tags: dict[str, str]) -> None:
        """Update (merge) the given tags onto the server.

        Existing tags not in *tags* are preserved. The implementation should
        also update ``server.labels`` to reflect the new state.
        """

    # ---------------------------------------------------------------------------
    # SSH key management
    # ---------------------------------------------------------------------------

    @abstractmethod
    def get_or_create_ssh_key(self, public_key: str) -> Any:
        """Ensure a key pair matching *public_key* exists in the provider.

        Returns the provider key object (e.g. hcloud SSHKey) whose name/id can
        be used when creating servers.
        """

    # ---------------------------------------------------------------------------
    # Server metadata helpers
    # ---------------------------------------------------------------------------

    @abstractmethod
    def build_server_labels(
        self, runner_labels: list[str], ssh_key_name: str = None
    ) -> dict[str, str]:
        """Return the tag/label dict to apply to a new (or recycled) runner server.

        The provider owns its own tag key naming scheme (e.g. Hetzner uses
        ``github-hetzner-runner-label-{i}``).  The returned dict should include
        both the per-label entries and the ``github_runner_label = "active"``
        marker used for server discovery.
        """

    @abstractmethod
    def build_volume_labels(
        self, arch: str, os_flavor: str, os_version: str
    ) -> dict[str, str]:
        """Return the tag/label dict to apply to a new runner volume."""

    @abstractmethod
    def validate_labels(self, labels: dict[str, str]) -> tuple[bool, str]:
        """Validate that *labels* satisfy provider-specific constraints.

        Returns ``(True, "")`` if valid, ``(False, error_message)`` otherwise.
        """

    @abstractmethod
    def update_server(
        self, server: ProviderServer, name: str, labels: dict[str, str]
    ) -> ProviderServer:
        """Rename *server* and replace its labels atomically.

        Updates ``server.name`` and ``server.labels`` in-place and returns the
        same (updated) ProviderServer for convenience.
        """

    # ---------------------------------------------------------------------------
    # Resource discovery
    # ---------------------------------------------------------------------------

    @abstractmethod
    def get_server_type(self, name: str) -> ProviderServerType:
        """Validate and return a ProviderServerType for *name*.

        Raises an appropriate error if the type does not exist.
        """

    @abstractmethod
    def get_server_arch(self, server_type: ProviderServerType) -> str:
        """Return the CPU architecture for *server_type* (``'x64'`` or ``'arm64'``)."""

    @abstractmethod
    def get_location(self, name: str, required: bool = False) -> Any:
        """Validate and return the provider location object for *name*.

        If *name* is None and *required* is False, returns None.
        Raises an appropriate error if *required* is True and name is None or
        the location does not exist.
        """

    @abstractmethod
    def get_image(self, image_spec: Any) -> Any:
        """Validate and return the provider image object for *image_spec*.

        The format of *image_spec* is provider-specific. For Hetzner this is an
        ``hcloud.images.domain.Image`` descriptor; for AWS it may be an AMI id
        string.

        Raises an appropriate error if the image does not exist.
        """

    def expand_location_label(self, name: str) -> list[str]:
        """Expand a (possibly composite) location label into individual location names.

        The default implementation treats every label as a single location and
        returns ``[name]``.  Providers that support composite location labels
        (e.g. Hetzner's ``hel1-fsn1-nbg1`` shorthand for "any of these DCs")
        should override this method to split the composite into its component
        parts so that scale_up can try each location in preference order.

        Args:
            name: Raw location string extracted from an ``in-<name>`` job label.

        Returns:
            List of individual location name strings.  For simple labels this
            is always a one-element list.
        """
        return [name]

    # ---------------------------------------------------------------------------
    # Volume operations (optional — providers that don't support volumes leave
    # the base NotImplementedError in place)
    # ---------------------------------------------------------------------------

    def create_volume(
        self,
        name: str,
        size: int,
        location: Any,
        labels: dict[str, str] = None,
        format: str = "ext4",
        automount: bool = False,
    ) -> ProviderVolume:
        """Create a new volume. Optional per provider."""
        raise NotImplementedError(
            f"Provider '{self.name}' does not support volume creation"
        )

    def delete_volume(self, volume: ProviderVolume) -> None:
        """Delete a volume. Optional per provider."""
        raise NotImplementedError(
            f"Provider '{self.name}' does not support volume deletion"
        )

    def get_volume(self, name: str) -> ProviderVolume | None:
        """Look up a volume by name. Optional per provider."""
        raise NotImplementedError(
            f"Provider '{self.name}' does not support volume lookup"
        )

    def list_volumes(self, label_selector: str = None) -> list[ProviderVolume]:
        """Return volumes, optionally filtered by label selector. Optional per provider."""
        raise NotImplementedError(
            f"Provider '{self.name}' does not support listing volumes"
        )

    def resize_volume(self, volume: ProviderVolume, size: int) -> None:
        """Resize a volume to *size* GB. Optional per provider."""
        raise NotImplementedError(
            f"Provider '{self.name}' does not support volume resize"
        )
