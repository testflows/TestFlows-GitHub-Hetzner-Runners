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

"""GCP provider configuration."""


def is_enabled(provider_config):
    """Check if GCP provider is enabled (has required credentials)."""
    return (
        provider_config
        and provider_config.project_id
        and provider_config.service_account_key
    )


def get_cli_fields():
    """Get list of all CLI field names for GCP provider."""
    return [
        "project_id",
        "service_account_key",
        "network",
        "subnetwork",
        "default_image",
        "default_server_type",
        "default_location",
        "default_volume_size",
        "default_volume_location",
        "default_volume_type",
    ]


def has_cli_args(args):
    """Check if any GCP CLI arguments are provided."""
    return any(
        getattr(args, f"gcp_{field}", None) is not None for field in get_cli_fields()
    )


def update_from_args(provider_config, args):
    """Update GCP provider configuration from CLI arguments."""
    if not provider_config:
        return

    # Update credentials
    if getattr(args, "gcp_project_id", None) is not None:
        provider_config.project_id = args.gcp_project_id
    if getattr(args, "gcp_service_account_key", None) is not None:
        provider_config.service_account_key = args.gcp_service_account_key
    if getattr(args, "gcp_network", None) is not None:
        provider_config.network = args.gcp_network
    if getattr(args, "gcp_subnetwork", None) is not None:
        provider_config.subnetwork = args.gcp_subnetwork

    # Update defaults
    if getattr(args, "gcp_default_image", None) is not None:
        provider_config.defaults.image = args.gcp_default_image
    if getattr(args, "gcp_default_server_type", None) is not None:
        provider_config.defaults.server_type = args.gcp_default_server_type
    if getattr(args, "gcp_default_location", None) is not None:
        provider_config.defaults.location = args.gcp_default_location
    if getattr(args, "gcp_default_volume_size", None) is not None:
        provider_config.defaults.volume_size = args.gcp_default_volume_size
    if getattr(args, "gcp_default_volume_location", None) is not None:
        provider_config.defaults.volume_location = args.gcp_default_volume_location
    if getattr(args, "gcp_default_volume_type", None) is not None:
        provider_config.defaults.volume_type = args.gcp_default_volume_type
