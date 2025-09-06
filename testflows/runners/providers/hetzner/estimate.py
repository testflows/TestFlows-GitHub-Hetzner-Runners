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

"""Hetzner Cloud cost estimation implementation."""

from github import Github
from github.Repository import Repository

from ...actions import Action
from ...config import Config
from ...hclient import HClient as Client
from ...utils import get_runner_server_type_and_location


def get_server_price(
    server_prices: dict[str, dict[str, float]],
    server_type: str,
    server_location: str,
    ipv4_price: float,
    ipv6_price: float,
) -> float:
    """Get server price for Hetzner Cloud."""
    price = None
    if ipv4_price is None:
        ipv4_price = 0
    try:
        price = server_prices[server_type][server_location] + ipv4_price + ipv6_price
    except KeyError:
        pass
    return price


def get_runner_server_price_per_second(
    server_prices: dict[str, dict[str, float]],
    runner_name: str,
    ipv4_price: float,
    ipv6_price: float,
) -> tuple[float, str, str]:
    """Get runner server price per second for Hetzner Cloud."""

    price_per_second = None

    server_type, server_location = get_runner_server_type_and_location(runner_name)
    server_price_per_hour = get_server_price(
        server_prices, server_type, server_location, ipv4_price, ipv6_price
    )

    if server_price_per_hour is not None:
        price_per_second = server_price_per_hour / 3600

    return price_per_second, server_type, server_location


def login_and_get_prices(
    args, config: Config
) -> tuple[Repository, dict[str, dict[str, float]]]:
    """Login and get prices for Hetzner Cloud."""

    config.check("github_token")
    config.check("github_repository")
    config.check("hetzner_token")

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action("Logging in to GitHub"):
        github_client = Github(login_or_token=config.github_token, per_page=100)

    with Action(f"Getting repository {config.github_repository}"):
        repo: Repository = github_client.get_repo(config.github_repository)

    with Action("Getting current server prices"):
        server_prices = check_prices(client)

    return (repo, server_prices)
