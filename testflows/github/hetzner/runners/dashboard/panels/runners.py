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
import logging

from ..colors import COLORS, STATE_COLORS
from .. import metrics
from . import panel


def create_runner_list():
    """Create a list of runners with their descriptions."""
    runners_info = metrics.get_metric_info("github_hetzner_runners_runner")
    total_runners = (
        metrics.get_metric_value("github_hetzner_runners_runners_total_count") or 0
    )

    if not runners_info:
        if total_runners > 0:
            return panel.create_list("runners", total_runners, [], "Total runners")
        return panel.create_list("runners", 0, [], "No runners")

    runner_items = []
    for info in runners_info:
        try:
            runner_id = info.get("runner_id")
            runner_name = info.get("name")
            if not runner_id or not runner_name:
                continue

            # Get runner labels
            runner_labels_info = metrics.get_metric_info(
                "github_hetzner_runners_runner_labels"
            )
            runner_labels_list = []
            for label_dict in runner_labels_info:
                if (
                    label_dict.get("runner_id") == runner_id
                    and label_dict.get("runner_name") == runner_name
                    and "label" in label_dict
                ):
                    runner_labels_list.append(label_dict["label"])

            status = info.get("status", "unknown")
            busy = info.get("busy", "false").lower() == "true"
            status_color = STATE_COLORS.get(status, STATE_COLORS["unknown"])

            # Create header with status and busy state
            header = panel.create_item_header(
                f"Runner: {runner_name}",
                status,
                status_color,
                extra_span={
                    "text": " [busy]" if busy else " [idle]",
                    "color": COLORS["warning"] if busy else COLORS["success"],
                },
            )

            # Create values
            values = [
                panel.create_item_value("OS", info.get("os", "Unknown")),
                panel.create_item_value(
                    "Repository", info.get("repository", "Unknown")
                ),
                panel.create_item_value(
                    "Labels", ", ".join(runner_labels_list) or "None"
                ),
            ]

            runner_items.append(
                panel.create_list_item("runner", status_color, header, values)
            )

        except (ValueError, KeyError, AttributeError) as e:
            logging.exception(f"Error processing runner info key: {info}")
            continue

    return panel.create_list("runners", total_runners, runner_items, "Total runners")


def update_graph(n):
    """Update runners graph."""
    current_time = datetime.now()
    states = ["online", "offline"]
    current_values = {}

    # Define colors for runner states
    runner_colors = {
        "online": COLORS["success"],  # Green for online runners
        "offline": STATE_COLORS["off"],  # Red for offline runners
    }

    # Create traces for each state
    traces = []
    for status in states:
        value = (
            metrics.get_metric_value(
                "github_hetzner_runners_runners_total", {"status": status}
            )
            or 0
        )
        current_values[status] = value

        traces.append(
            panel.create_metric_trace(
                "github_hetzner_runners_runners_total",
                value,
                current_time,
                runner_colors[status],
                status,
                {"status": status},
            )
        )

    # Add busy runners trace
    busy_runners = metrics.get_metric_value("github_hetzner_runners_runners_busy") or 0
    traces.append(
        panel.create_metric_trace(
            "github_hetzner_runners_runners_busy",
            busy_runners,
            current_time,
            COLORS["warning"],
            "busy",
        )
    )

    xaxis = {
        "title": "Time",
        "range": panel.get_time_range(current_time),
        "tickformat": "%H:%M",
    }

    yaxis = {
        "title": "Number of Runners",
        "autorange": True,
        "rangemode": "nonnegative",
        "tickmode": "linear" if max(current_values.values()) < 5 else "auto",
        "nticks": 5,
        "tickformat": "d",
        "automargin": True,
        "showgrid": True,
    }

    return panel.create_graph(traces, "Runners", xaxis, yaxis)


def create_panel():
    """Create runners panel."""
    return panel.create_panel("Runners")
