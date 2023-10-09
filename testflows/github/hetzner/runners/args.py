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
import argparse

from hcloud.images.domain import Image
from hcloud.locations.domain import Location
from hcloud.server_types.domain import ServerType

from argparse import ArgumentTypeError

from traceback import print_exception

file_type = argparse.FileType


class ColumnsType(list):
    pass


def lines_type(v):
    """Log lines type [+]num."""
    offset = 0
    if v.startswith("+"):
        offset = 1
    try:
        assert int(v[offset:]) and int(v[offset:]) >= 0
    except Exception as e:
        raise ArgumentTypeError(f"{v} must be [+]num with num >= 0")
    return v


def columns_type(v):
    """Log columns type name:width,..."""
    columns = ColumnsType()
    columns.value = v
    try:
        for c in v.split(","):
            d = {}
            c = str(c).rsplit(":", 1)
            d["column"] = c[0]
            if len(c) > 1:
                c[1] = int(c[1])
                assert c[1] > 0
                d["width"] = c[1]
            columns.append(d)
    except Exception as e:
        raise ArgumentTypeError(f"invalid format {v}")
    return columns


def end_of_life_type(v):
    """Server end of life type."""
    try:
        v = int(v)
        assert v > 0 and v < 60, f"{v} must be > 0 and < 60"
    except AssertionError as e:
        raise ArgumentTypeError(str(e))
    return v


def switch_type(v):
    """Switch argument type."""
    if v == "on":
        return True
    elif v == "off":
        return False
    raise ArgumentTypeError(f"invalid value {v}")


def path_type(v, check_exists=True):
    """Path argument type."""
    try:
        v = os.path.abspath(os.path.expanduser(v))
        if check_exists:
            os.path.exists(v)
    except Exception as e:
        raise ArgumentTypeError(str(e))
    return v


def count_type(v):
    """Count argument type."""
    v = int(v)
    if not v >= 1:
        raise ArgumentTypeError(f"{v} must be >= 0")
    return v


def image_type(v, separator=":"):
    """Image type argument. Example: system:ubuntu-22.04"""
    try:
        image_architecture, image_type, image_name = v.split(separator, 2)
        assert image_type in ("system", "snapshot", "backup", "app")
    except:
        raise ArgumentTypeError(f"invalid image {v}")

    if image_type in ("system", "app"):
        return Image(type=image_type, architecture=image_architecture, name=image_name)
    else:
        # backup or snapshot uses description
        return Image(
            type=image_type, architecture=image_architecture, description=image_name
        )


def location_type(v):
    """Location type argument. Example: ash"""
    if v is not None:
        return Location(name=v)
    return None


def server_type(v):
    """Server type argument. Example: cx11"""
    return ServerType(name=v)


def config_type(v):
    """Program configuration file type."""
    from .config import parse_config, default_user_config

    if v == "__default_user_config__":
        if os.path.exists(default_user_config):
            v = default_user_config
        else:
            return None

    v = path_type(v)
    try:
        config = parse_config(v)
        config.config_file = v
    except Exception as e:
        if "--debug" in sys.argv:
            print_exception(e)
        raise ArgumentTypeError(str(e))

    return config
