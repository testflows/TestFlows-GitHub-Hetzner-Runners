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

"""AWS cost estimation implementation."""

import json

from github import Github
from github.Repository import Repository

from ...actions import Action
from ...config import Config
from ...utils import get_runner_server_type_and_location


def check_prices(
    region: str, instance_types: list[str] = None, session=None
) -> dict[str, dict[str, float]]:
    """Fetch on-demand Linux prices from the AWS Pricing API.

    Returns a mapping of instance_type -> {region: hourly_usd_price}.
    The Pricing API endpoint is only available in us-east-1 regardless of
    which region the instances actually run in.

    session: optional boto3.Session to use (uses provider credentials);
             falls back to the default session when None.
    """
    import boto3

    if session is None:
        session = boto3.Session()
    client = session.client("pricing", region_name="us-east-1")

    filters = [
        {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
        {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
        {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
        {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
        {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region},
    ]

    prices = {}
    paginator = client.get_paginator("get_products")

    for page in paginator.paginate(ServiceCode="AmazonEC2", Filters=filters):
        for price_item_str in page["PriceList"]:
            data = json.loads(price_item_str)
            attrs = data.get("product", {}).get("attributes", {})
            instance_type = attrs.get("instanceType")

            if not instance_type:
                continue
            if instance_types and instance_type not in instance_types:
                continue

            on_demand = data.get("terms", {}).get("OnDemand", {})
            for term in on_demand.values():
                for pd in term.get("priceDimensions", {}).values():
                    price_usd = float(pd.get("pricePerUnit", {}).get("USD", 0) or 0)
                    if price_usd > 0:
                        prices.setdefault(instance_type, {})[region] = price_usd

    return prices


def get_server_price(
    server_prices: dict[str, dict[str, float]],
    server_type: str,
    server_location: str,
    ipv4_price: float = 0.0,
    ipv6_price: float = 0.0,
) -> float:
    """Get hourly on-demand price for an EC2 instance type in USD.

    ipv4_price and ipv6_price are accepted for interface compatibility but
    ignored — AWS billing for Elastic IPs is separate and outside scope.

    server_location may be an AZ (e.g. 'us-east-1a') or a region ('us-east-1');
    prices are always stored by region so we try both.
    """
    from .provider import _az_to_region

    price = None
    try:
        region_prices = server_prices[server_type]
        price = region_prices.get(server_location) or region_prices.get(
            _az_to_region(server_location)
        )
    except (KeyError, TypeError):
        pass
    return price


def get_runner_server_price_per_second(
    server_prices: dict[str, dict[str, float]],
    runner_name: str,
    ipv4_price: float = 0.0,
    ipv6_price: float = 0.0,
) -> tuple[float, str, str]:
    """Get runner server price per second for AWS."""

    price_per_second = None

    server_type, server_location = get_runner_server_type_and_location(runner_name)
    server_price_per_hour = get_server_price(server_prices, server_type, server_location)

    if server_price_per_hour is not None:
        price_per_second = server_price_per_hour / 3600

    return price_per_second, server_type, server_location


def login_and_get_prices(
    args, config: Config
) -> tuple[Repository, dict[str, dict[str, float]]]:
    """Login to GitHub and fetch on-demand EC2 prices for the configured region."""

    config.check("github_token")
    config.check("github_repository")

    region = getattr(config, "aws_region", None) or "us-east-1"

    with Action("Logging in to GitHub"):
        github_client = Github(login_or_token=config.github_token, per_page=100)

    with Action(f"Getting repository {config.github_repository}"):
        repo: Repository = github_client.get_repo(config.github_repository)

    with Action(f"Getting EC2 on-demand prices for {region}"):
        server_prices = check_prices(region)

    return (repo, server_prices)
