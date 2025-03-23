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

from ..colors import STATE_COLORS
from .. import metrics
from . import panel


def create_panel():
    """Create cost panel."""
    return panel.create_panel("Cost")


def update_graph(n):
    """Update cost graph."""
    current_time = datetime.now()
    current_value = 0

    # Get all server info metrics
    servers_info = metrics.get_metric_info("github_hetzner_runners_server")

    if servers_info:
        for info in servers_info:
            try:
                # Get cost per hour from server info
                cost_hourly = float(info.get("cost_hourly", 0))
                current_value += cost_hourly
            except (ValueError, TypeError):
                continue

    # Create trace for total cost
    trace = panel.create_metric_trace(
        "github_hetzner_runners_cost_total",
        current_value,
        current_time,
        STATE_COLORS["running"],  # Use green color for cost
        "Total Cost",
        {},
    )

    xaxis = {
        "title": "Time",
        "range": panel.get_time_range(current_time),
        "tickformat": "%H:%M",
    }

    yaxis = {
        "title": "Cost per Hour (EUR)",
        "autorange": True,
        "rangemode": "nonnegative",
        "tickmode": "auto",
        "nticks": 5,
        "tickformat": ".3f",
        "automargin": True,
        "showgrid": True,
    }

    return panel.create_graph([trace], "Cost", xaxis, yaxis)
