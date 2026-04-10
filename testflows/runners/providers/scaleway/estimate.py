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

"""Scaleway cost estimation implementation."""

from github.Repository import Repository
from ...config import Config


def get_server_price(
    server_prices: dict[str, dict[str, float]],
    server_type: str,
    server_location: str,
    ipv4_price: float,
    ipv6_price: float,
) -> float:
    """Get server price for Scaleway."""
    raise NotImplementedError("Scaleway cost estimation is not yet implemented")


def get_runner_server_price_per_second(
    server_prices: dict[str, dict[str, float]],
    runner_name: str,
    ipv4_price: float,
    ipv6_price: float,
) -> tuple[float, str, str]:
    """Get runner server price per second for Scaleway."""
    raise NotImplementedError("Scaleway cost estimation is not yet implemented")


def login_and_get_prices(
    args, config: Config
) -> tuple[Repository, dict[str, dict[str, float]]]:
    """Login and get prices for Scaleway."""
    raise NotImplementedError("Scaleway cost estimation is not yet implemented")
