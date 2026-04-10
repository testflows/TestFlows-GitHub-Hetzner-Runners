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

"""Azure provider argument validators."""

from argparse import ArgumentTypeError


def image_type(v):
    """Azure VM image URN argument. Example: Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest"""
    parts = v.split(":")
    if len(parts) != 4:
        raise ArgumentTypeError(
            f"invalid Azure image URN {v}, must be in format Publisher:Offer:Sku:Version"
        )
    return v


def server_type(v):
    """Azure VM size argument. Example: Standard_B2s"""
    if not v.startswith("Standard_") and not v.startswith("Basic_"):
        raise ArgumentTypeError(
            f"invalid Azure VM size {v}, must start with Standard_ or Basic_"
        )
    return v


def location_type(v):
    """Azure region argument. Example: East US"""
    # Basic validation - Azure regions are typically title case with spaces
    if not v.replace(" ", "").replace("-", "").isalnum():
        raise ArgumentTypeError(f"invalid Azure region {v}")
    return v


def add_arguments(parser):
    """Add Azure-specific CLI arguments to parser."""
    azure_group = parser.add_argument_group("Azure options")

    azure_group.add_argument(
        "--azure-subscription-id",
        metavar="id",
        type=str,
        help="Azure subscription ID, default: project config or $AZURE_SUBSCRIPTION_ID environment variable",
    )

    azure_group.add_argument(
        "--azure-tenant-id",
        metavar="id",
        type=str,
        help="Azure tenant ID, default: project config or $AZURE_TENANT_ID environment variable",
    )

    azure_group.add_argument(
        "--azure-client-id",
        metavar="id",
        type=str,
        help="Azure client ID, default: project config or $AZURE_CLIENT_ID environment variable",
    )

    azure_group.add_argument(
        "--azure-client-secret",
        metavar="secret",
        type=str,
        help="Azure client secret, default: project config or $AZURE_CLIENT_SECRET environment variable",
    )

    azure_group.add_argument(
        "--azure-resource-group",
        metavar="name",
        type=str,
        help="Azure resource group name, default: project config",
    )

    azure_group.add_argument(
        "--azure-default-image",
        metavar="image-urn",
        type=image_type,
        help="Default Azure VM image URN (Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest)",
    )

    azure_group.add_argument(
        "--azure-default-server-type",
        metavar="vm-size",
        type=server_type,
        help="Default Azure VM size (Standard_B2s)",
    )

    azure_group.add_argument(
        "--azure-default-location",
        metavar="region",
        type=location_type,
        help="Default Azure region (East US)",
    )

    azure_group.add_argument(
        "--azure-default-volume-size",
        metavar="GB",
        type=int,
        help="Default Azure disk size in GB (20)",
    )

    azure_group.add_argument(
        "--azure-default-volume-type",
        metavar="tier",
        type=str,
        help="Default Azure disk tier (Premium_LRS)",
    )
