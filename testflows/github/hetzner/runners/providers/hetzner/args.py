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

"""Hetzner Cloud provider argument validators."""

from hcloud.images.domain import Image
from hcloud.locations.domain import Location
from hcloud.server_types.domain import ServerType
from argparse import ArgumentTypeError


def image_type(v, separator=":"):
    """Hetzner image type argument. Example: x86:system:ubuntu-22.04"""
    try:
        image_architecture, image_type, image_name = v.split(separator, 2)
        assert image_type in ("system", "snapshot", "backup", "app")
    except:
        raise ArgumentTypeError(f"invalid Hetzner image {v}")

    if image_architecture in ("aarch64", "arm64"):
        # support aarch64, arm64 alias for arm
        image_architecture = "arm"

    if image_type in ("system", "app"):
        return Image(type=image_type, architecture=image_architecture, name=image_name)
    else:
        # backup or snapshot uses description
        return Image(
            type=image_type, architecture=image_architecture, description=image_name
        )


def server_type(v):
    """Hetzner server type argument. Example: cx31"""
    return ServerType(name=v)


def location_type(v):
    """Hetzner location type argument. Example: nbg1"""
    if v is not None:
        return Location(name=v)
    return None


def add_arguments(parser):
    """Add Hetzner-specific CLI arguments to parser."""
    hetzner_group = parser.add_argument_group("Hetzner options")

    hetzner_group.add_argument(
        "--hetzner-token",
        metavar="token",
        type=str,
        help="Hetzner Cloud token, default: project config or $HETZNER_TOKEN environment variable",
    )

    hetzner_group.add_argument(
        "--hetzner-default-image",
        metavar="architecture:type:name_or_description",
        type=image_type,
        help="Default Hetzner runner server image (x86:system:ubuntu-22.04)",
    )

    hetzner_group.add_argument(
        "--hetzner-default-server-type",
        metavar="name",
        type=server_type,
        help="Default Hetzner runner server type (cx31)",
    )

    hetzner_group.add_argument(
        "--hetzner-default-location",
        metavar="name",
        type=location_type,
        help="Default Hetzner runner server location (nbg1)",
    )

    hetzner_group.add_argument(
        "--hetzner-default-volume-size",
        metavar="GB",
        type=int,
        help="Default Hetzner volume size in GB (20)",
    )

    hetzner_group.add_argument(
        "--hetzner-default-volume-location",
        metavar="name",
        type=location_type,
        help="Default Hetzner volume location (nbg1)",
    )
