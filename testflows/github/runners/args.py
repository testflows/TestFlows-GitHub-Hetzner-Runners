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

from importlib.machinery import SourceFileLoader

from hcloud.images.domain import Image
from hcloud.locations.domain import Location
from hcloud.server_types.domain import ServerType

from argparse import ArgumentTypeError


def path_type(v):
    """Path argument type."""
    try:
        v = os.path.abspath(os.path.expanduser(v))
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
        image_type, image_name = v.split(separator, 1)
        assert image_type in ("system", "snapshot", "backup", "app")
    except:
        raise ArgumentTypeError(f"invalid image {v}")

    if image_type in ("system", "app"):
        return Image(type=image_type, name=image_name)
    else:
        # backup or snapshot uses description
        return Image(type=image_type, description=image_name)


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
    from .config import Config

    v = path_type(v)
    try:
        config_module = SourceFileLoader("config", v).load_module()
        assert hasattr(config_module, "config"), "config not defined"
        assert isinstance(config_module.config, Config), "invalid config type"
    except Exception as e:
        raise ArgumentTypeError(str(e))

    config_module.config.config_file = v
    return config_module.config
