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

"""Scaleway provider argument validators."""

from argparse import ArgumentTypeError


def image_type(v):
    """Scaleway instance image argument. Example: ubuntu_jammy"""
    # Basic validation - Scaleway images are typically lowercase with underscores
    if not v.replace("_", "").replace("-", "").isalnum():
        raise ArgumentTypeError(f"invalid Scaleway image {v}")
    return v


def server_type(v):
    """Scaleway instance type argument. Example: DEV1-M"""
    # Basic validation for Scaleway instance types
    valid_families = ["DEV1", "GP1", "RENDER", "C2S", "C2M", "C2L"]
    valid_sizes = ["XS", "S", "M", "L", "XL"]

    if "-" not in v:
        raise ArgumentTypeError(
            f"invalid Scaleway instance type {v}, must be in format FAMILY-SIZE"
        )

    family, size = v.split("-", 1)
    if family not in valid_families:
        raise ArgumentTypeError(f"invalid Scaleway instance family {family}")
    if size not in valid_sizes:
        raise ArgumentTypeError(f"invalid Scaleway instance size {size}")

    return v


def location_type(v):
    """Scaleway zone argument. Example: par1"""
    # Basic validation for Scaleway zones
    valid_zones = [
        "par1",
        "par2",
        "ams1",
        "war1",
        "fr-par-1",
        "fr-par-2",
        "nl-ams-1",
        "pl-waw-1",
    ]
    if v not in valid_zones:
        raise ArgumentTypeError(
            f"invalid Scaleway zone {v}, must be one of: {', '.join(valid_zones)}"
        )
    return v


def add_arguments(parser):
    """Add Scaleway-specific CLI arguments to parser."""
    scaleway_group = parser.add_argument_group("Scaleway options")

    scaleway_group.add_argument(
        "--scaleway-access-key",
        metavar="key",
        type=str,
        help="Scaleway access key, default: project config or $SCALEWAY_ACCESS_KEY environment variable",
    )

    scaleway_group.add_argument(
        "--scaleway-secret-key",
        metavar="secret",
        type=str,
        help="Scaleway secret key, default: project config or $SCALEWAY_SECRET_KEY environment variable",
    )

    scaleway_group.add_argument(
        "--scaleway-organization-id",
        metavar="id",
        type=str,
        help="Scaleway organization ID, default: project config or $SCALEWAY_ORGANIZATION_ID environment variable",
    )

    scaleway_group.add_argument(
        "--scaleway-default-image",
        metavar="image-name",
        type=image_type,
        help="Default Scaleway instance image (ubuntu_jammy)",
    )

    scaleway_group.add_argument(
        "--scaleway-default-server-type",
        metavar="instance-type",
        type=server_type,
        help="Default Scaleway instance type (DEV1-M)",
    )

    scaleway_group.add_argument(
        "--scaleway-default-location",
        metavar="zone",
        type=location_type,
        help="Default Scaleway zone (par1)",
    )

    scaleway_group.add_argument(
        "--scaleway-default-volume-size",
        metavar="GB",
        type=int,
        help="Default Scaleway volume size in GB (20)",
    )

    scaleway_group.add_argument(
        "--scaleway-default-volume-type",
        metavar="volume-type",
        type=str,
        help="Default Scaleway volume type (b_ssd)",
    )
