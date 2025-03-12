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

from ..colors import COLORS
from ..metrics import get_metric_value, metric_history


def create_panel():
    """Create servers total count panel."""
    return html.Div(
        className="tui-container",
        children=[
            html.H3(
                "servers total count",
                style={
                    "color": COLORS["accent"],
                    "marginBottom": "20px",
                    "borderBottom": f"1px solid {COLORS['accent']}",
                    "paddingBottom": "10px",
                },
            ),
            dcc.Graph(id="servers-total-count-graph"),
            dcc.Interval(
                id="interval-component-total-count",
                interval=30 * 1000,
                n_intervals=0,
            ),
        ],
    )


def update_graph(n):
    """Update servers total count graph."""
    total_count = get_metric_value("github_hetzner_runners_servers_total_count")
    metric_time = datetime.now()
    print(f"\nTotal servers count: {total_count}")

    key = "github_hetzner_runners_servers_total_count"
    if key not in metric_history:
        metric_history[key] = {"timestamps": [], "values": []}

    metric_history[key]["timestamps"].append(metric_time)
    metric_history[key]["values"].append(total_count)

    cutoff_time = metric_time - timedelta(minutes=15)
    while (
        metric_history[key]["timestamps"]
        and metric_history[key]["timestamps"][0] < cutoff_time
    ):
        metric_history[key]["timestamps"].pop(0)
        metric_history[key]["values"].pop(0)

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
        "data": [
            go.Scatter(
                x=metric_history[key]["timestamps"],
                y=metric_history[key]["values"],
                name=f"total ({total_count})",
                mode="lines",
                line={"width": 2, "shape": "hv", "color": COLORS["accent"]},
                hovertemplate="%{y:.0f} servers<extra></extra>",
            )
        ],
        "layout": {
            "title": {
                "text": "servers total count",
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
                "range": [metric_time - timedelta(minutes=15), metric_time],
                "tickformat": "%H:%M",
                **common_style,
            },
            "yaxis": {
                "title": "Number of Servers",
                "range": [0, max(2, total_count + 1)],
                "tickformat": "d",
                "dtick": 1,
                **common_style,
            },
            "margin": {"t": 60, "b": 50, "l": 50, "r": 50},
            "showlegend": False,
            "dragmode": False,
        },
        "config": {
            "displayModeBar": False,
            "staticPlot": True,
            "displaylogo": False,
        },
    }
