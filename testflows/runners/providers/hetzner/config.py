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

"""Hetzner Cloud provider configuration."""

import base64
import hashlib

from hcloud.images.domain import Image
from hcloud.server_types.domain import ServerType
from hcloud.locations.domain import Location
from hcloud.ssh_keys.domain import SSHKey

from ...hclient import HClient as Client
from ...actions import Action
from ...config.config import ImageError, LocationError, ServerTypeError


def is_enabled(provider_config):
    """Check if Hetzner provider is enabled (has required credentials)."""
    return provider_config and provider_config.token


def get_cli_fields():
    """Get list of all CLI field names for Hetzner provider."""
    return [
        "token",
        "default_image",
        "default_server_type",
        "default_location",
        "default_volume_size",
        "default_volume_location",
    ]


def has_cli_args(args):
    """Check if any Hetzner CLI arguments are provided."""
    return any(
        getattr(args, f"hetzner_{field}", None) is not None
        for field in get_cli_fields()
    )


def update_from_args(provider_config, args):
    """Update Hetzner provider configuration from CLI arguments."""
    if not provider_config:
        return

    # Update credentials
    if getattr(args, "hetzner_token", None) is not None:
        provider_config.token = args.hetzner_token

    # Update defaults
    if getattr(args, "hetzner_default_image", None) is not None:
        provider_config.defaults.image = args.hetzner_default_image
    if getattr(args, "hetzner_default_server_type", None) is not None:
        provider_config.defaults.server_type = args.hetzner_default_server_type
    if getattr(args, "hetzner_default_location", None) is not None:
        provider_config.defaults.location = args.hetzner_default_location
    if getattr(args, "hetzner_default_volume_size", None) is not None:
        provider_config.defaults.volume_size = args.hetzner_default_volume_size
    if getattr(args, "hetzner_default_volume_location", None) is not None:
        provider_config.defaults.volume_location = args.hetzner_default_volume_location


# Hetzner-specific validation functions


def check_ssh_key(client: Client, ssh_key: str, is_file=True):
    """Check that ssh key exists if not create it."""

    def fingerprint(ssh_key):
        """Calculate fingerprint of a public SSH key."""
        encoded_key = base64.b64decode(ssh_key.strip().split()[1].encode("utf-8"))
        md5_digest = hashlib.md5(encoded_key).hexdigest()

        return ":".join(a + b for a, b in zip(md5_digest[::2], md5_digest[1::2]))

    if is_file:
        with open(ssh_key, "r", encoding="utf-8") as ssh_key_file:
            public_key = ssh_key_file.read()
    else:
        public_key = ssh_key

    name = hashlib.md5(public_key.encode("utf-8")).hexdigest()
    ssh_key: SSHKey = SSHKey(
        name=name, public_key=public_key, fingerprint=fingerprint(public_key)
    )

    existing_ssh_key = client.ssh_keys.get_by_fingerprint(
        fingerprint=ssh_key.fingerprint
    )

    if not existing_ssh_key:
        with Action(
            f"Creating SSH key {ssh_key.name} with fingerprint {ssh_key.fingerprint}",
            stacklevel=3,
        ):
            ssh_key = client.ssh_keys.create(
                name=ssh_key.name, public_key=ssh_key.public_key
            )
    else:
        ssh_key = existing_ssh_key

    return ssh_key


def check_image(client: Client, image: Image):
    """Check if image exists.
    If image type is not 'system' then use image description to find it.
    """

    if image.type in ("system", "app"):
        _image = client.images.get_by_name_and_architecture(
            name=image.name, architecture=image.architecture
        )
        if not _image:
            raise ImageError(
                f"image type:'{image.type}' name:'{image.name}' architecture:'{image.architecture}' not found"
            )
        return _image
    else:
        # backup or snapshot
        try:
            return [
                i
                for i in client.images.get_all(
                    type=image.type, architecture=image.architecture
                )
                if i.description == image.description
            ][0]
        except IndexError:
            raise ImageError(
                f"image type:'{image.type}' name:'{image.description}' architecture:'{image.architecture}' not found"
            )


def check_location(client: Client, location: Location, required=False):
    """Check if location exists."""
    if location is None:
        if required:
            raise LocationError(f"location is not defined")
        return None
    _location = client.locations.get_by_name(location.name)
    if not _location:
        raise LocationError(f"location '{location.name}' not found")
    return _location


def check_server_type(client: Client, server_type: ServerType):
    """Check if server type exists."""
    _type: ServerType = client.server_types.get_by_name(server_type.name)
    if not _type:
        raise ServerTypeError(f"server type '{server_type.name}' not found")
    return _type


def check_prices(client: Client):
    """Check server prices."""
    server_types: list[ServerType] = client.server_types.get_all()
    return {
        t.name.lower(): {
            price["location"]: float(price["price_hourly"]["gross"])
            for price in t.prices
        }
        for t in server_types
    }
