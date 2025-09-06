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

"""Scaleway provider configuration."""


def is_enabled(provider_config):
    """Check if Scaleway provider is enabled (has required credentials)."""
    return (
        provider_config
        and provider_config.access_key
        and provider_config.secret_key
        and provider_config.organization_id
    )


def get_cli_fields():
    """Get list of all CLI field names for Scaleway provider."""
    return [
        "access_key",
        "secret_key",
        "organization_id",
        "default_image",
        "default_server_type",
        "default_location",
        "default_volume_size",
        "default_volume_location",
        "default_volume_type",
    ]


def has_cli_args(args):
    """Check if any Scaleway CLI arguments are provided."""
    return any(
        getattr(args, f"scaleway_{field}", None) is not None
        for field in get_cli_fields()
    )


def update_from_args(provider_config, args):
    """Update Scaleway provider configuration from CLI arguments."""
    if not provider_config:
        return

    # Update credentials
    if getattr(args, "scaleway_access_key", None) is not None:
        provider_config.access_key = args.scaleway_access_key
    if getattr(args, "scaleway_secret_key", None) is not None:
        provider_config.secret_key = args.scaleway_secret_key
    if getattr(args, "scaleway_organization_id", None) is not None:
        provider_config.organization_id = args.scaleway_organization_id

    # Update defaults
    if getattr(args, "scaleway_default_image", None) is not None:
        provider_config.defaults.image = args.scaleway_default_image
    if getattr(args, "scaleway_default_server_type", None) is not None:
        provider_config.defaults.server_type = args.scaleway_default_server_type
    if getattr(args, "scaleway_default_location", None) is not None:
        provider_config.defaults.location = args.scaleway_default_location
    if getattr(args, "scaleway_default_volume_size", None) is not None:
        provider_config.defaults.volume_size = args.scaleway_default_volume_size
    if getattr(args, "scaleway_default_volume_location", None) is not None:
        provider_config.defaults.volume_location = args.scaleway_default_volume_location
    if getattr(args, "scaleway_default_volume_type", None) is not None:
        provider_config.defaults.volume_type = args.scaleway_default_volume_type
