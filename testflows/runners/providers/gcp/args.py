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

"""Google Cloud Platform provider argument validators."""

import re
from argparse import ArgumentTypeError


def image_type(v):
    """GCP VM image argument. Example: projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"""
    if not v.startswith("projects/"):
        raise ArgumentTypeError(f"invalid GCP image {v}, must start with projects/")
    return v


def server_type(v):
    """GCP machine type argument. Example: e2-medium"""
    # Basic validation for GCP machine types
    valid_families = ["e2", "n1", "n2", "n2d", "c2", "c2d", "m1", "m2", "f1", "g1"]

    if "-" not in v:
        raise ArgumentTypeError(
            f"invalid GCP machine type {v}, must be in format family-size"
        )

    family = v.split("-")[0]
    if family not in valid_families:
        raise ArgumentTypeError(f"invalid GCP machine family {family}")

    return v


def location_type(v):
    """GCP zone argument. Example: us-central1-a"""
    if not re.match(r"^[a-z]+-[a-z]+\d+-[a-z]$", v):
        raise ArgumentTypeError(
            f"invalid GCP zone {v}, must be in format us-central1-a"
        )
    return v


def add_arguments(parser):
    """Add GCP-specific CLI arguments to parser."""
    gcp_group = parser.add_argument_group("GCP options")

    gcp_group.add_argument(
        "--gcp-project-id",
        metavar="project",
        type=str,
        help="GCP project ID, default: project config or $GCP_PROJECT_ID environment variable",
    )

    gcp_group.add_argument(
        "--gcp-service-account-key",
        metavar="path",
        type=str,
        help="Path to GCP service account key file, default: project config or $GCP_SERVICE_ACCOUNT_KEY environment variable",
    )

    gcp_group.add_argument(
        "--gcp-network",
        metavar="network",
        type=str,
        help="GCP network name, default: project config",
    )

    gcp_group.add_argument(
        "--gcp-subnetwork",
        metavar="subnet",
        type=str,
        help="GCP subnetwork name, default: project config",
    )

    gcp_group.add_argument(
        "--gcp-default-image",
        metavar="image-path",
        type=image_type,
        help="Default GCP VM image (projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts)",
    )

    gcp_group.add_argument(
        "--gcp-default-server-type",
        metavar="machine-type",
        type=server_type,
        help="Default GCP machine type (e2-medium)",
    )

    gcp_group.add_argument(
        "--gcp-default-location",
        metavar="zone",
        type=location_type,
        help="Default GCP zone (us-central1-a)",
    )

    gcp_group.add_argument(
        "--gcp-default-volume-size",
        metavar="GB",
        type=int,
        help="Default GCP disk size in GB (20)",
    )

    gcp_group.add_argument(
        "--gcp-default-volume-type",
        metavar="disk-type",
        type=str,
        help="Default GCP disk type (pd-ssd)",
    )
