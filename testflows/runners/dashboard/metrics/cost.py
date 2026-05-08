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

from datetime import datetime
from . import get
from . import history
from . import tracker

CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$"}


def servers_cost() -> dict:
    """Return {currency: total_hourly} for all servers."""
    totals = {}
    servers_info = get.metric_info("github_hetzner_runners_server")
    if servers_info:
        for info in servers_info:
            try:
                cost = float(info.get("cost_hourly") or 0)
                if cost > 0:
                    currency = info.get("cost_currency") or "EUR"
                    totals[currency] = totals.get(currency, 0) + cost
            except (ValueError, TypeError):
                continue
    return totals


def volumes_cost() -> dict:
    """Return {currency: total_hourly} for all volumes (always EUR)."""
    total = 0
    volumes_info = get.metric_info("github_hetzner_runners_volume")
    if volumes_info:
        for info in volumes_info:
            try:
                cost = float(info.get("cost_hourly") or 0)
                total += cost
            except (ValueError, TypeError):
                continue
    return {"EUR": total} if total > 0 else {}


def total_cost() -> dict:
    """Return {currency: total_hourly} combining servers and volumes."""
    totals = {}
    for currency, amount in servers_cost().items():
        totals[currency] = totals.get(currency, 0) + amount
    for currency, amount in volumes_cost().items():
        totals[currency] = totals.get(currency, 0) + amount
    return totals


def _servers_cost_scalar() -> float:
    return sum(servers_cost().values())


def _volumes_cost_scalar() -> float:
    return sum(volumes_cost().values())


def _total_cost_scalar() -> float:
    return sum(total_cost().values())


# Register cost metrics for tracking (scalar sums for history)
tracker.track("github_hetzner_runners_cost_total", compute_func=lambda: _total_cost_scalar())
tracker.track(
    "github_hetzner_runners_cost_servers", compute_func=lambda: _servers_cost_scalar()
)
tracker.track(
    "github_hetzner_runners_cost_volumes", compute_func=lambda: _volumes_cost_scalar()
)


def summary() -> dict:
    """Return {currency: {hourly, daily, monthly}}."""
    result = {}
    for currency, hourly in total_cost().items():
        result[currency] = {
            "hourly": hourly,
            "daily": hourly * 24,
            "monthly": hourly * 24 * 30,
        }
    return result


def servers_cost_history(cutoff_minutes=15):
    """Get servers cost history data."""
    return history.data(
        "github_hetzner_runners_cost_servers", cutoff_minutes=cutoff_minutes
    )


def volumes_cost_history(cutoff_minutes=15):
    """Get volumes cost history data."""
    return history.data(
        "github_hetzner_runners_cost_volumes", cutoff_minutes=cutoff_minutes
    )


def formatted_details():
    """Get formatted cost details grouped by currency."""
    cost_details = []

    totals = total_cost()
    for currency, total_hourly in totals.items():
        sym = CURRENCY_SYMBOLS.get(currency, currency)
        cost_details.append(
            {
                "name": f"Total ({currency})",
                "cost hourly": f"{sym}{total_hourly:.4f}/h",
                "cost daily": f"{sym}{total_hourly * 24:.3f}/day",
                "cost monthly": f"{sym}{total_hourly * 24 * 30:.2f}/month",
            }
        )

    sc = servers_cost()
    for currency, servers_hourly in sc.items():
        sym = CURRENCY_SYMBOLS.get(currency, currency)
        cost_details.append(
            {
                "name": f"Servers ({currency})",
                "cost hourly": f"{sym}{servers_hourly:.4f}/h",
                "cost daily": f"{sym}{servers_hourly * 24:.3f}/day",
                "cost monthly": f"{sym}{servers_hourly * 24 * 30:.2f}/month",
            }
        )

    vc_total = _volumes_cost_scalar()
    if vc_total > 0:
        sym = CURRENCY_SYMBOLS.get("EUR", "€")
        cost_details.append(
            {
                "name": "Volumes (EUR)",
                "cost hourly": f"{sym}{vc_total:.4f}/h",
                "cost daily": f"{sym}{vc_total * 24:.3f}/day",
                "cost monthly": f"{sym}{vc_total * 24 * 30:.2f}/month",
            }
        )

    return cost_details


def total_cost_history(cutoff_minutes=15):
    """Get total cost history data."""
    return history.data(
        "github_hetzner_runners_cost_total", cutoff_minutes=cutoff_minutes
    )
