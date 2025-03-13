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
from dash import html, dcc
import logging
import ast

from ..colors import COLORS, STATE_COLORS
from ..metrics import get_metric_value, metric_history, get_metric_info


def create_panel():
    """Create runners panel."""
    return html.Div(
        className="tui-container",
        children=[
            html.H3(
                "Runners",
                style={
                    "color": COLORS["accent"],
                    "marginBottom": "20px",
                    "borderBottom": f"1px solid {COLORS['accent']}",
                    "paddingBottom": "10px",
                },
            ),
            dcc.Graph(id="runners-graph"),
            # Runner list
            html.Div(
                id="runners-list",
                style={
                    "marginTop": "20px",
                    "borderTop": f"1px solid {COLORS['accent']}",
                    "paddingTop": "20px",
                },
            ),
        ],
    )


def create_runner_list():
    """Create a list of runners with their descriptions."""
    runners_info = get_metric_info("github_hetzner_runners_runner")

    # Get total number of runners from metrics
    total_runners = get_metric_value("github_hetzner_runners_runners_total_count") or 0

    if not runners_info:
        if total_runners > 0:
            # We have runners but no details
            return html.Div(
                f"Total runners: {int(total_runners)} (details not available)",
                style={
                    "color": COLORS["warning"],
                    "padding": "10px",
                    "fontFamily": "JetBrains Mono, Fira Code, Consolas, monospace",
                },
            )
        return html.Div(
            "No runners",
            style={
                "color": COLORS["text"],
                "padding": "10px",
                "fontFamily": "JetBrains Mono, Fira Code, Consolas, monospace",
            },
        )

    runner_items = []
    for key, info in runners_info.items():
        try:
            # Parse the runner info from the key
            runner_dict = {}
            for item in key.split(","):
                if "=" in item:
                    k, v = item.split("=", 1)
                    runner_dict[k] = v

            runner_id = runner_dict.get("runner_id")
            runner_name = runner_dict.get("name")
            if not runner_id or not runner_name:
                continue

            # Get runner labels
            runner_labels_info = get_metric_info("github_hetzner_runners_runner_labels")
            runner_labels_list = []
            for label_key, label_value in runner_labels_info.items():
                if (
                    label_value == 1.0
                    and runner_id in label_key
                    and runner_name in label_key
                ):
                    # Parse the raw key-value pairs
                    label_dict = {}
                    for item in label_key.split(","):
                        if "=" in item:
                            k, v = item.split("=", 1)
                            label_dict[k] = v
                    if "label" in label_dict:
                        runner_labels_list.append(label_dict["label"])

            status = runner_dict.get("status", "unknown")
            busy = runner_dict.get("busy", "false").lower() == "true"
            status_color = STATE_COLORS.get(status, STATE_COLORS["unknown"])

            runner_items.append(
                html.Div(
                    className="runner-item",
                    style={
                        "borderLeft": f"4px solid {status_color}",
                        "padding": "10px",
                        "marginBottom": "10px",
                        "backgroundColor": COLORS["paper"],
                    },
                    children=[
                        html.Div(
                            [
                                html.Span(
                                    f"Runner: {runner_name}",
                                    style={
                                        "color": COLORS["accent"],
                                        "fontWeight": "bold",
                                    },
                                ),
                                html.Span(
                                    f" ({status})",
                                    style={
                                        "color": status_color,
                                        "marginLeft": "10px",
                                    },
                                ),
                                html.Span(
                                    " [busy]" if busy else " [idle]",
                                    style={
                                        "color": (
                                            COLORS["warning"]
                                            if busy
                                            else COLORS["success"]
                                        ),
                                        "marginLeft": "10px",
                                    },
                                ),
                            ],
                            style={"marginBottom": "5px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "OS: ",
                                    style={"color": COLORS["text"]},
                                ),
                                html.Span(
                                    runner_dict.get("os", "Unknown"),
                                    style={"color": COLORS["warning"]},
                                ),
                            ],
                            style={"marginBottom": "2px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "Repository: ",
                                    style={"color": COLORS["text"]},
                                ),
                                html.Span(
                                    runner_dict.get("repository", "Unknown"),
                                    style={"color": COLORS["warning"]},
                                ),
                            ],
                            style={"marginBottom": "2px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "Labels: ",
                                    style={"color": COLORS["text"]},
                                ),
                                html.Span(
                                    ", ".join(runner_labels_list) or "None",
                                    style={"color": COLORS["warning"]},
                                ),
                            ],
                        ),
                    ],
                )
            )
        except (ValueError, KeyError, AttributeError) as e:
            logging.exception(f"Error processing runner info key: {key}")
            continue

    return html.Div(
        children=runner_items,
        style={
            "maxHeight": "400px",
            "overflowY": "auto",
            "marginTop": "20px",
            "paddingRight": "4px",
            "backgroundColor": COLORS["background"],
            "border": f"1px solid {COLORS['grid']}",
            "borderRadius": "4px",
        },
    )


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

    for status in states:
        value = get_metric_value(
            "github_hetzner_runners_runners_total", {"status": status}
        )
        current_values[status] = value if value is not None else 0

    traces = []
    for status in states:
        key = f"github_hetzner_runners_runners_total_status={status}"
        if key not in metric_history:
            metric_history[key] = {"timestamps": [], "values": []}

        metric_history[key]["timestamps"].append(current_time)
        metric_history[key]["values"].append(current_values[status])

        cutoff_time = current_time - timedelta(minutes=15)
        while (
            metric_history[key]["timestamps"]
            and metric_history[key]["timestamps"][0] < cutoff_time
        ):
            metric_history[key]["timestamps"].pop(0)
            metric_history[key]["values"].pop(0)

        traces.append(
            {
                "type": "scatter",
                "x": metric_history[key]["timestamps"],
                "y": metric_history[key]["values"],
                "name": f"{status} ({int(current_values[status] or 0)})",
                "mode": "lines",
                "line": {"width": 2, "shape": "hv", "color": runner_colors[status]},
                "text": status,
                "hoverinfo": "y+text",
            }
        )

    # Add busy runners trace
    busy_runners = get_metric_value("github_hetzner_runners_runners_busy") or 0
    key = "github_hetzner_runners_runners_busy"
    if key not in metric_history:
        metric_history[key] = {"timestamps": [], "values": []}

    metric_history[key]["timestamps"].append(current_time)
    metric_history[key]["values"].append(busy_runners)

    while (
        metric_history[key]["timestamps"]
        and metric_history[key]["timestamps"][0] < cutoff_time
    ):
        metric_history[key]["timestamps"].pop(0)
        metric_history[key]["values"].pop(0)

    traces.append(
        {
            "type": "scatter",
            "x": metric_history[key]["timestamps"],
            "y": metric_history[key]["values"],
            "name": f"busy ({int(busy_runners)})",
            "mode": "lines",
            "line": {"width": 2, "shape": "hv", "color": COLORS["warning"]},
            "text": "busy",
            "hoverinfo": "y+text",
        }
    )

    common_style = {
        "font": {
            "family": "JetBrains Mono, Fira Code, Consolas, monospace",
            "color": COLORS["text"],
        },
        "gridcolor": COLORS["grid"],
        "showgrid": True,
        "fixedrange": True,
    }

    return {
        "data": traces,
        "layout": {
            "title": {
                "text": "Runners",
                "font": {"size": 16, "weight": "bold", **common_style["font"]},
                "x": 0.5,
                "y": 0.95,
            },
            "height": 300,  # Match jobs panel height
            "plot_bgcolor": COLORS["background"],
            "paper_bgcolor": COLORS["paper"],
            "font": common_style["font"],
            "xaxis": {
                "title": "Time",
                "range": [current_time - timedelta(minutes=15), current_time],
                "tickformat": "%H:%M",
                **common_style,
            },
            "yaxis": {
                "title": "Number of Runners",
                "range": [
                    0,
                    max(
                        2,
                        max(
                            max(
                                metric_history[
                                    f"github_hetzner_runners_runners_total_status={status}"
                                ]["values"]
                            )
                            for status in states
                        )
                        + 1,
                    ),
                ],
                "tickformat": "d",
                "dtick": 1,
                **common_style,
            },
            "margin": {"t": 60, "b": 50, "l": 50, "r": 50},
            "showlegend": True,
            "legend": {
                "x": 0,
                "y": 1,
                "xanchor": "left",
                "yanchor": "top",
                "bgcolor": COLORS["paper"],
                "font": {"size": 10},
            },
            "dragmode": False,
        },
        "config": {
            "displayModeBar": False,
            "staticPlot": True,
            "displaylogo": False,
        },
    }
