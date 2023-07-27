# Copyright 2023 Katteli Inc.
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
import os
import sys

from hcloud import Client
from hcloud.images.domain import Image
from hcloud.locations.domain import Location
from hcloud.server_types.domain import ServerType


class ImageNotFoundError(Exception):
    pass


def path_type(v):
    """Path argument type."""
    v = os.path.abspath(os.path.expanduser(v))
    os.path.exists(v)
    return v


def count_type(v):
    """Count argument type."""
    v = int(v)
    assert v >= 1
    return v


def env_var_type(name):
    """Environment variable type."""

    def option(v):
        v = v if v else os.getenv(name)
        return v

    return option


def image_type(v, separator=":"):
    """Image type argument."""
    try:
        image_type, image_name = v.split(separator, 1)
        assert image_type in ("system", "snapshot", "backup", "app")
    except:
        raise ValueError(f"invalid image value {v}")

    if image_type in ("system", "app"):
        return Image(type=image_type, name=image_name)
    else:
        # backup or snapshot uses description
        return Image(type=image_type, description=image_name)


def location_type(v):
    """Location type argument."""
    if v is not None:
        return Location(name=v)
    return None


def server_type(v):
    """Server type argument."""
    return ServerType(name=v)


def check(args):
    """Check mandatory arguments."""

    def _check(name, value):
        if value:
            return
        value = "is not defined"
        print(
            f"argument error: --{name.lower().replace('_','-')} {value}",
            file=sys.stderr,
        )
        sys.exit(1)

    _check("GITHUB_TOKEN", args.github_token)
    _check("GITHUB_REPOSITORY", args.github_repository)
    _check("HETZNER_TOKEN", args.hetzner_token)


def check_image(client: Client, image: Image):
    """Check if image exists.
    If image type is not 'system' then use image description to find it.
    """

    if image.type in ("system", "app"):
        return client.images.get_by_name(image.name)
    else:
        # backup or snapshot
        try:
            return [
                i
                for i in client.images.get_all(type=image.type)
                if i.description == image.description
            ][0]
        except IndexError:
            raise ImageNotFoundError(f"{image.type}:{image.description} not found")
