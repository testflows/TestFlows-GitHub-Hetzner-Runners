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
from ..layout import LAYOUT_STYLE
from ..metrics import get_metric_value, update_metric_history, metric_history


def create_panel():
    """Create servers total panel."""
    return html.Div(
        className="tui-container",
        children=[
            html.H3(
                "servers total",
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

    # Define all possible states - must match metrics.py
    states = ["running", "off", "initializing", "ready", "busy"]
    current_values = {}
    total_servers = 0

    # Collect all values first
    print("\nCurrent server states:")
    for status in states:
        value = get_metric_value(
            "github_hetzner_runners_servers_total", {"status": status}
        )
        # Ensure we always have a value, defaulting to 0
        current_values[status] = value if value is not None else 0
        total_servers += current_values[status]
        print(f"  {status}: {current_values[status]}")
    print(f"Total servers: {total_servers}")

    # Update history for all states
    for status in states:
        update_metric_history(
            "github_hetzner_runners_servers_total",
            {"status": status},
            current_values[status],
            current_time,
        )

    # Create traces for all states
    traces = []
    for status in states:
        key = f"github_hetzner_runners_servers_total_status={status}"
        current_value = current_values[status]

        traces.append(
            go.Scatter(
                x=metric_history[key]["timestamps"],
                y=metric_history[key]["values"],
                name=f"{status} ({current_value})",
                mode="lines",
                line={"width": 2, "shape": "hv", "color": STATE_COLORS[status]},
                hovertemplate="%{y:.0f} %{fullData.name}<extra></extra>",
            )
        )

    # Calculate y-axis range with integer steps and padding
    y_max = max(
        2, total_servers + 1
    )  # Ensure at least 2 units high and add 1 unit padding
    y_range = [0, y_max]

    return {
        "data": traces,
        "layout": {
            **LAYOUT_STYLE,
            "title": {
                "text": "servers by status",
                "font": {
                    "family": "JetBrains Mono, Fira Code, Consolas, monospace",
                    "size": 16,
                    "weight": "bold",
                },
            },
            "height": 400,
            "xaxis": {
                **LAYOUT_STYLE["xaxis"],
                "title": "Time",
                "range": [current_time - timedelta(minutes=15), current_time],
                "domain": [0, 0.92],
            },
            "yaxis": {
                **LAYOUT_STYLE["yaxis"],
                "title": "Number of Servers",
                "range": y_range,
                "tickformat": "d",  # Force integer ticks
                "dtick": 1,  # Force integer steps between ticks
            },
            "hovermode": "x unified",
            "showlegend": True,
            "legend": {
                "x": 0.95,
                "y": 1,
                "xanchor": "left",
                "yanchor": "top",
                "bgcolor": COLORS["paper"],
                "bordercolor": COLORS["grid"],
                "borderwidth": 1,
                "orientation": "v",
                "font": {
                    "family": "JetBrains Mono, Fira Code, Consolas, monospace",
                    "size": 10,
                },
            },
            "margin": {"r": 100},
        },
    }
