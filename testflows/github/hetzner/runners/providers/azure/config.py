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

"""Azure provider configuration."""


def is_enabled(provider_config):
    """Check if Azure provider is enabled (has required credentials)."""
    return (
        provider_config
        and provider_config.subscription_id
        and provider_config.tenant_id
        and provider_config.client_id
        and provider_config.client_secret
    )


def get_cli_fields():
    """Get list of all CLI field names for Azure provider."""
    return [
        "subscription_id",
        "tenant_id",
        "client_id",
        "client_secret",
        "resource_group",
        "default_image",
        "default_server_type",
        "default_location",
        "default_volume_size",
        "default_volume_location",
        "default_volume_type",
    ]


def has_cli_args(args):
    """Check if any Azure CLI arguments are provided."""
    return any(
        getattr(args, f"azure_{field}", None) is not None for field in get_cli_fields()
    )


def update_from_args(provider_config, args):
    """Update Azure provider configuration from CLI arguments."""
    if not provider_config:
        return

    # Update credentials
    if getattr(args, "azure_subscription_id", None) is not None:
        provider_config.subscription_id = args.azure_subscription_id
    if getattr(args, "azure_tenant_id", None) is not None:
        provider_config.tenant_id = args.azure_tenant_id
    if getattr(args, "azure_client_id", None) is not None:
        provider_config.client_id = args.azure_client_id
    if getattr(args, "azure_client_secret", None) is not None:
        provider_config.client_secret = args.azure_client_secret
    if getattr(args, "azure_resource_group", None) is not None:
        provider_config.resource_group = args.azure_resource_group

    # Update defaults
    if getattr(args, "azure_default_image", None) is not None:
        provider_config.defaults.image = args.azure_default_image
    if getattr(args, "azure_default_server_type", None) is not None:
        provider_config.defaults.server_type = args.azure_default_server_type
    if getattr(args, "azure_default_location", None) is not None:
        provider_config.defaults.location = args.azure_default_location
    if getattr(args, "azure_default_volume_size", None) is not None:
        provider_config.defaults.volume_size = args.azure_default_volume_size
    if getattr(args, "azure_default_volume_location", None) is not None:
        provider_config.defaults.volume_location = args.azure_default_volume_location
    if getattr(args, "azure_default_volume_type", None) is not None:
        provider_config.defaults.volume_type = args.azure_default_volume_type
