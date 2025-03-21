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
from datetime import datetime, timedelta
import logging

from ..colors import STATE_COLORS
from .. import metrics
from . import panel


def create_panel():
    """Create servers panel."""
    return panel.create_panel("Servers")


def create_server_list():
    """Create a list of servers with their descriptions."""
    servers_info = metrics.get_metric_info("github_hetzner_runners_server")

    # Get total number of servers from metrics
    total_servers = (
        metrics.get_metric_value("github_hetzner_runners_servers_total_count") or 0
    )

    if not servers_info:
        if total_servers > 0:
            # We have servers but no details
            return panel.create_list("servers", total_servers, [], "Total servers")
        return panel.create_list("servers", 0, [], "No servers")

    server_items = []
    for info in servers_info:
        try:
            server_id = info.get("server_id")
            server_name = info.get("name")
            if not server_id or not server_name:
                continue

            # Get server labels
            server_labels_info = metrics.get_metric_info(
                "github_hetzner_runners_server_labels"
            )
            server_labels_list = []
            for label_dict in server_labels_info:
                if (
                    label_dict.get("server_id") == server_id
                    and label_dict.get("server_name") == server_name
                    and "label" in label_dict
                ):
                    server_labels_list.append(label_dict["label"])

            status = info.get("status", "unknown")
            status_color = STATE_COLORS.get(status, STATE_COLORS["unknown"])

            # Create header
            header = panel.create_item_header(
                f"Server: {server_name}",
                status,
                status_color,
            )

            # Create values
            values = [
                panel.create_item_value("Type", info.get("type", "Unknown")),
                panel.create_item_value("Location", info.get("location", "Unknown")),
                panel.create_item_value("IPv4", info.get("ipv4", "Unknown")),
                panel.create_item_value("IPv6", info.get("ipv6", "Unknown")),
                panel.create_item_value("Created", info.get("created", "Unknown")),
                panel.create_item_value(
                    "Runner Status", info.get("runner_status", "Unknown")
                ),
                panel.create_item_value(
                    "Labels", ", ".join(server_labels_list) or "None"
                ),
            ]

            # Add cost information if available
            if info.get("cost_hourly"):
                cost_text = f"{info['cost_hourly']} {info['cost_currency']}/hour" + (
                    f" (total: {info['cost_total']} {info['cost_currency']})"
                    if info.get("cost_total")
                    else ""
                )
                values.append(panel.create_item_value("Cost", cost_text))

            server_items.append(
                panel.create_list_item("server", status_color, header, values)
            )

        except (ValueError, KeyError, AttributeError) as e:
            logging.exception(f"Error processing server info key: {info}")
            continue

    return panel.create_list("servers", total_servers, server_items, "Total servers")


def update_graph(n):
    """Update servers graph."""
    current_time = datetime.now()
    states = ["running", "off", "initializing", "ready", "busy"]
    current_values = {}

    # Define colors for server states
    server_colors = {
        "running": STATE_COLORS["running"],  # Green for running servers
        "off": STATE_COLORS["off"],  # Red for off servers
        "initializing": STATE_COLORS["initializing"],  # Orange for initializing
        "ready": STATE_COLORS["ready"],  # Cyan for ready
        "busy": STATE_COLORS["busy"],  # Magenta for busy
    }

    # Create traces for each state
    traces = []
    for status in states:
        value = (
            metrics.get_metric_value(
                "github_hetzner_runners_servers_total", {"status": status}
            )
            or 0
        )
        current_values[status] = value

        traces.append(
            panel.create_metric_trace(
                "github_hetzner_runners_servers_total",
                value,
                current_time,
                server_colors[status],
                status,
                {"status": status},
            )
        )

    xaxis = {
        "title": "Time",
        "range": panel.get_time_range(current_time),
        "tickformat": "%H:%M",
    }

    yaxis = {
        "title": "Number of Servers",
        "autorange": True,
        "rangemode": "nonnegative",
        "tickmode": "linear" if max(current_values.values()) < 5 else "auto",
        "nticks": 5,
        "tickformat": "d",
        "automargin": True,
        "showgrid": True,
    }

    return panel.create_graph(traces, "Servers", xaxis, yaxis)
