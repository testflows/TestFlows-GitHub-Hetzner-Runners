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
import plotly.graph_objs as go
from dash import html, dcc

from ..colors import COLORS, STATE_COLORS
from ..metrics import get_metric_value, metric_history


def create_panel():
    """Create servers total panel."""
    return html.Div(
        className="tui-container",
        children=[
            html.H3(
                "servers by status",
                style={
                    "color": COLORS["accent"],
                    "marginBottom": "20px",
                    "borderBottom": f"1px solid {COLORS['accent']}",
                    "paddingBottom": "10px",
                },
            ),
            dcc.Graph(id="servers-total-graph"),
            dcc.Interval(
                id="interval-component",
                interval=30 * 1000,
                n_intervals=0,
            ),
        ],
    )


def update_graph(n):
    """Update servers total graph."""
    current_time = datetime.now()
    states = ["running", "off", "initializing", "ready", "busy"]
    current_values = {}
    total_servers = 0

    print("\nCurrent server states:")
    for status in states:
        value = get_metric_value(
            "github_hetzner_runners_servers_total", {"status": status}
        )
        current_values[status] = value if value is not None else 0
        total_servers += current_values[status]
        print(f"  {status}: {current_values[status]}")
    print(f"Total servers: {total_servers}")

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
                "text": "servers by status",
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
                "range": [0, max(2, total_servers + 1)],
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
