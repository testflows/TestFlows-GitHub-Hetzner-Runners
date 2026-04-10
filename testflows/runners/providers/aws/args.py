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

"""AWS provider argument validators."""

import re
from argparse import ArgumentTypeError


def image_type(v):
    """AWS AMI ID argument. Example: ami-0abcdef1234567890"""
    if not v.startswith("ami-") or len(v) != 21:
        raise ArgumentTypeError(
            f"invalid AWS AMI ID {v}, must be in format ami-xxxxxxxxxxxxxxxxx"
        )
    return v


def server_type(v):
    """AWS instance type argument. Example: t3.medium"""
    # Basic validation for AWS instance types
    valid_families = [
        "t2",
        "t3",
        "t3a",
        "t4g",
        "m5",
        "m5a",
        "m5n",
        "m6i",
        "c5",
        "c5a",
        "c5n",
        "c6i",
        "r5",
        "r5a",
        "r5n",
        "r6i",
        "x1e",
        "z1d",
        "i3",
        "i3en",
        "i4i",
        "d2",
        "d3",
        "h1",
    ]
    valid_sizes = [
        "nano",
        "micro",
        "small",
        "medium",
        "large",
        "xlarge",
        "2xlarge",
        "3xlarge",
        "4xlarge",
        "6xlarge",
        "8xlarge",
        "9xlarge",
        "10xlarge",
        "12xlarge",
        "16xlarge",
        "18xlarge",
        "24xlarge",
        "32xlarge",
    ]

    parts = v.split(".")
    if len(parts) != 2:
        raise ArgumentTypeError(
            f"invalid AWS instance type {v}, must be in format family.size"
        )

    family, size = parts
    if family not in valid_families:
        raise ArgumentTypeError(f"invalid AWS instance family {family}")
    if size not in valid_sizes:
        raise ArgumentTypeError(f"invalid AWS instance size {size}")

    return v


def location_type(v):
    """AWS availability zone argument. Example: us-east-1a"""
    # Basic validation for AWS AZ format
    if not re.match(r"^[a-z]{2}-[a-z]+-\d+[a-z]$", v):
        raise ArgumentTypeError(
            f"invalid AWS availability zone {v}, must be in format us-east-1a"
        )
    return v


def add_arguments(parser):
    """Add AWS-specific CLI arguments to parser."""
    aws_group = parser.add_argument_group("AWS options")

    aws_group.add_argument(
        "--aws-access-key-id",
        metavar="key",
        type=str,
        help="AWS access key ID, default: project config or $AWS_ACCESS_KEY_ID environment variable",
    )

    aws_group.add_argument(
        "--aws-secret-access-key",
        metavar="secret",
        type=str,
        help="AWS secret access key, default: project config or $AWS_SECRET_ACCESS_KEY environment variable",
    )

    aws_group.add_argument(
        "--aws-security-group",
        metavar="sg-id",
        type=str,
        help="AWS security group ID, default: project config",
    )

    aws_group.add_argument(
        "--aws-subnet",
        metavar="subnet-id",
        type=str,
        help="AWS subnet ID, default: project config",
    )

    aws_group.add_argument(
        "--aws-key-name",
        metavar="keypair",
        type=str,
        help="AWS EC2 key pair name, default: project config",
    )

    aws_group.add_argument(
        "--aws-default-image",
        metavar="ami-id",
        type=image_type,
        help="Default AWS AMI ID or SSM parameter path (resolve:ssm:/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp3/ami-id)",
    )

    aws_group.add_argument(
        "--aws-default-server-type",
        metavar="instance-type",
        type=server_type,
        help="Default AWS EC2 instance type (t3.medium)",
    )

    aws_group.add_argument(
        "--aws-default-location",
        metavar="availability-zone",
        type=location_type,
        help="Default AWS availability zone (us-east-1a)",
    )

    aws_group.add_argument(
        "--aws-default-volume-size",
        metavar="GB",
        type=int,
        help="Default AWS EBS volume size in GB (20)",
    )

    aws_group.add_argument(
        "--aws-default-volume-type",
        metavar="type",
        type=str,
        help="Default AWS EBS volume type (gp3)",
    )
