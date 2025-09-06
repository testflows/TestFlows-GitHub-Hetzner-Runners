# Copyright 2023-2025 Katteli Inc.
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


def meta_label_type(v):
    """Meta labels type argument."""
    try:
        return {l[0]: set(l[1].split(",") if l[1] else []) for l in v}
    except Exception as e:
        raise ArgumentTypeError(str(e))


def config_type(v):
    """Program configuration file type."""
    from .config import default_user_config
    from .config.parse import parse_config

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
        if "unexpected keyword argument" in str(e):
            e = str(e).replace(".__init__()", "") + ", please remove it"
        raise ArgumentTypeError(str(e))

    return config


def max_runners_for_label_type(value: str) -> tuple[set[str], int]:
    """Parse max runners for label specification.

    Format: label1,label2:count
    Example: windows,gpu:3

    Returns:
        tuple[set[str], int]: Tuple of (set of labels, count)
    """
    try:
        labels_str, count_str = value.rsplit(":", 1)
        labels = [label.strip().lower() for label in labels_str.split(",")]
        count = int(count_str)
        if not labels or not count > 0:
            raise ValueError
        return (set(labels), count)
    except (ValueError, TypeError):
        raise ArgumentTypeError(
            f"invalid max runners for label specification: {value}, "
            "expected format: label1,label2:count"
        )


def provider_type(value: str) -> list[str]:
    """Parse provider argument supporting comma-separated values.

    Args:
        value: Provider string, can be comma-separated (e.g., "hetzner,aws")

    Returns:
        list[str]: List of valid provider names

    Raises:
        ArgumentTypeError: If any provider is invalid
    """
    valid_providers = {"hetzner", "aws", "azure", "gcp", "scaleway"}

    # Split by comma and strip whitespace
    providers = [p.strip() for p in value.split(",")]
    parsed = []

    for provider in providers:
        if provider in valid_providers:
            if provider not in parsed:  # Avoid duplicates
                parsed.append(provider)
        else:
            raise ArgumentTypeError(
                f"Unknown provider '{provider}'. Valid providers: {', '.join(sorted(valid_providers))}"
            )

    return parsed
