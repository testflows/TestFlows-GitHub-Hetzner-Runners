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
    """Create servers panel."""
    return html.Div(
        className="tui-container",
        children=[
            html.H3(
                "Servers",
                style={
                    "color": COLORS["accent"],
                    "marginBottom": "20px",
                    "borderBottom": f"1px solid {COLORS['accent']}",
                    "paddingBottom": "10px",
                },
            ),
            dcc.Graph(id="servers-graph"),
            # Server list
            html.Div(
                id="servers-list",
                style={
                    "marginTop": "20px",
                    "borderTop": f"1px solid {COLORS['accent']}",
                    "paddingTop": "20px",
                },
            ),
        ],
    )


def create_server_list():
    """Create a list of servers with their descriptions."""
    servers_info = get_metric_info("github_hetzner_runners_server")

    # Get total number of servers from metrics
    total_servers = get_metric_value("github_hetzner_runners_servers_total_count") or 0

    if not servers_info:
        if total_servers > 0:
            # We have servers but no details
            return html.Div(
                f"Total servers: {int(total_servers)} (details not available)",
                style={
                    "color": COLORS["warning"],
                    "padding": "10px",
                    "fontFamily": "JetBrains Mono, Fira Code, Consolas, monospace",
                },
            )
        return html.Div(
            "No servers",
            style={
                "color": COLORS["text"],
                "padding": "10px",
                "fontFamily": "JetBrains Mono, Fira Code, Consolas, monospace",
            },
        )

    server_items = []
    for info in servers_info:
        try:
            server_id = info.get("server_id")
            server_name = info.get("name")
            if not server_id or not server_name:
                continue

            # Get server labels
            server_labels_info = get_metric_info("github_hetzner_runners_server_labels")
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

            server_items.append(
                html.Div(
                    className="server-item",
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
                                    f"Server: {server_name}",
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
                            ],
                            style={"marginBottom": "5px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "Type: ",
                                    style={"color": COLORS["text"]},
                                ),
                                html.Span(
                                    info.get("type", "Unknown"),
                                    style={"color": COLORS["warning"]},
                                ),
                            ],
                            style={"marginBottom": "2px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "Location: ",
                                    style={"color": COLORS["text"]},
                                ),
                                html.Span(
                                    info.get("location", "Unknown"),
                                    style={"color": COLORS["warning"]},
                                ),
                            ],
                            style={"marginBottom": "2px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "IPv4: ",
                                    style={"color": COLORS["text"]},
                                ),
                                html.Span(
                                    info.get("ipv4", "Unknown"),
                                    style={"color": COLORS["warning"]},
                                ),
                            ],
                            style={"marginBottom": "2px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "IPv6: ",
                                    style={"color": COLORS["text"]},
                                ),
                                html.Span(
                                    info.get("ipv6", "Unknown"),
                                    style={"color": COLORS["warning"]},
                                ),
                            ],
                            style={"marginBottom": "2px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "Created: ",
                                    style={"color": COLORS["text"]},
                                ),
                                html.Span(
                                    info.get("created", "Unknown"),
                                    style={"color": COLORS["warning"]},
                                ),
                            ],
                            style={"marginBottom": "2px"},
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "Runner Status: ",
                                    style={"color": COLORS["text"]},
                                ),
                                html.Span(
                                    info.get("runner_status", "Unknown"),
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
                                    ", ".join(server_labels_list) or "None",
                                    style={"color": COLORS["warning"]},
                                ),
                            ],
                        ),
                        # Add cost information if available
                        (
                            html.Div(
                                [
                                    html.Span(
                                        "Cost: ",
                                        style={"color": COLORS["text"]},
                                    ),
                                    html.Span(
                                        (
                                            f"{info['cost_hourly']} {info['cost_currency']}/hour"
                                            + (
                                                f" (total: {info['cost_total']} {info['cost_currency']})"
                                                if info.get("cost_total")
                                                else ""
                                            )
                                            if info.get("cost_hourly")
                                            else "Unknown"
                                        ),
                                        style={"color": COLORS["warning"]},
                                    ),
                                ],
                                style={"marginBottom": "2px"},
                            )
                            if info.get("cost_hourly")
                            else None
                        ),
                    ],
                )
            )
        except (ValueError, KeyError, AttributeError) as e:
            logging.exception(f"Error processing server info key: {info}")
            continue

    return html.Div(
        children=server_items,
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
    """Update servers graph."""
    current_time = datetime.now()
    states = ["running", "off", "initializing", "ready", "busy"]
    current_values = {}
    total_servers = 0

    for status in states:
        value = get_metric_value(
            "github_hetzner_runners_servers_total", {"status": status}
        )
        current_values[status] = value if value is not None else 0
        total_servers += current_values[status]

    traces = []
    for status in states:
        key = f"github_hetzner_runners_servers_total_status={status}"
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
                "name": f"{status} ({int(current_values[status])})",
                "mode": "lines",
                "line": {"width": 2, "shape": "hv", "color": STATE_COLORS[status]},
                "text": status,
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
                "text": "Servers",
                "font": {"size": 16, "weight": "bold", **common_style["font"]},
                "x": 0.5,
                "y": 0.95,
            },
            "height": 400,
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
                "title": "Number of Servers",
                "range": [
                    0,
                    max(
                        2,
                        max(
                            max(
                                metric_history[
                                    f"github_hetzner_runners_servers_total_status={status}"
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
