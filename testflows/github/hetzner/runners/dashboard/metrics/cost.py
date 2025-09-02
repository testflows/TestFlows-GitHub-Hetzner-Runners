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

from . import get
from . import history


def servers_cost():
    """Compute total cost from all servers."""
    total_cost = 0

    # Add server costs
    servers_info = get.metric_info("github_hetzner_runners_server")
    if servers_info:
        for info in servers_info:
            try:
                cost_hourly = float(info.get("cost_hourly", 0))
                total_cost += cost_hourly
            except (ValueError, TypeError):
                continue

    return total_cost


def volumes_cost():
    """Compute total cost from all volumes."""
    total_cost = 0

    # Add volume costs
    volumes_info = get.metric_info("github_hetzner_runners_volume")
    if volumes_info:
        for info in volumes_info:
            try:
                cost_hourly = float(info.get("cost_hourly", 0))
                total_cost += cost_hourly
            except (ValueError, TypeError):
                continue

    return total_cost


def total_cost():
    """Compute total cost from all servers and volumes."""
    return servers_cost() + volumes_cost()


def summary():
    """Get cost summary data.

    Returns:
        dict: Summary of cost data
    """
    current_hourly_cost = total_cost()

    return {
        "hourly": current_hourly_cost,
        "daily": current_hourly_cost * 24,
        "monthly": current_hourly_cost * 24 * 30,
    }


def servers_cost_history(cutoff_minutes=15):
    """Update and get servers cost history data.

    Updates the servers cost history with the current servers cost value and returns
    the historical data for the last 15 minutes.

    Returns:
        tuple: (timestamps, values, current_value, current_time)
    """
    return history.update_and_get(
        "github_hetzner_runners_cost_servers",
        labels={},
        value=servers_cost(),
        cutoff_minutes=cutoff_minutes,
    )


def volumes_cost_history(cutoff_minutes=15):
    """Update and get volumes cost history data.

    Updates the volumes cost history with the current volumes cost value and returns
    the historical data for the last 15 minutes.

    Returns:
        tuple: (timestamps, values, current_value, current_time)
    """
    return history.update_and_get(
        "github_hetzner_runners_cost_volumes",
        labels={},
        value=volumes_cost(),
        cutoff_minutes=cutoff_minutes,
    )


def formatted_details():
    """Get formatted cost details for servers and volumes.

    Returns:
        list: List of dictionaries with cost details for each server and volume
    """
    cost_details = []

    # Get total costs for summary
    total_cost_value = total_cost()
    total_servers_cost = servers_cost()
    total_volumes_cost = volumes_cost()

    # Add total cost summary
    if total_cost_value > 0:
        cost_details.append(
            {
                "name": "Total",
                "cost hourly": f"€{total_cost_value:.4f}/h",
                "cost daily": f"€{total_cost_value * 24:.3f}/day",
                "cost monthly": f"€{total_cost_value * 24 * 30:.2f}/month",
            }
        )

    # Add servers summary if there are any servers with cost
    if total_servers_cost > 0:
        cost_details.append(
            {
                "name": "Servers",
                "cost hourly": f"€{total_servers_cost:.4f}/h",
                "cost daily": f"€{total_servers_cost * 24:.3f}/day",
                "cost monthly": f"€{total_servers_cost * 24 * 30:.2f}/month",
            }
        )

    # Add volumes summary if there are any volumes with cost
    if total_volumes_cost > 0:
        cost_details.append(
            {
                "name": "Volumes",
                "cost hourly": f"€{total_volumes_cost:.4f}/h",
                "cost daily": f"€{total_volumes_cost * 24:.3f}/day",
                "cost monthly": f"€{total_volumes_cost * 24 * 30:.2f}/month",
            }
        )

    return cost_details


def total_cost_history(cutoff_minutes=15):
    """Update and get total cost history data.

    Updates the cost history with the current total cost value and returns
    the historical data for the last 15 minutes.

    Returns:
        tuple: (timestamps, values, current_value, current_time)
    """
    return history.update_and_get(
        "github_hetzner_runners_cost_total",
        labels={},
        value=total_cost(),
        cutoff_minutes=cutoff_minutes,
    )
