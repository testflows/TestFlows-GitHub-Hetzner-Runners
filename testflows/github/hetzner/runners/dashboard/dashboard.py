# Copyright 2023 Katteli Inc.
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
import os
import dash
import threading
from datetime import datetime, timedelta
import logging

from dash import html, dcc
from dash.dependencies import Input, Output
from flask import send_from_directory

from .colors import COLORS
from .panels import servers, jobs, runners, scaleup_errors, gauges
from .metrics import get_metric_value

# Get the directory containing this file
current_dir = os.path.dirname(os.path.abspath(__file__))

# Initialize the Dash app with static assets configuration
app = dash.Dash(
    __name__,
    assets_folder=os.path.join(current_dir, "css"),
    assets_url_path="/css",
)

app.title = "GitHub Hetzner Runners Dashboard"


# Set up routes for serving static files
@app.server.route("/css/<path:path>")
def serve_static(path):
    """Serve static files from the css directory."""
    return send_from_directory(os.path.join(current_dir, "css"), path)


# Set the app's template
with open(os.path.join(current_dir, "html", "template.html"), "r") as f:
    app.index_string = f.read()

app.layout = html.Div(
    style={
        "backgroundColor": COLORS["background"],
        "minHeight": "100vh",
        "margin": 0,
        "padding": 0,
    },
    children=[
        # Single interval component for all updates
        dcc.Interval(
            id="interval-component",
            interval=60 * 1000,  # Default to 1 minute
            n_intervals=0,
        ),
        # Navigation/Control Bar
        html.Div(
            style={
                "backgroundColor": COLORS["nav"],
                "padding": "15px 20px",
                "marginBottom": "20px",
            },
            className="nav-bar",
            children=[
                html.Div(
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "justifyContent": "space-between",
                        "maxWidth": "1200px",
                        "margin": "0 auto",
                    },
                    className="nav-content",
                    children=[
                        # Left side - Logo and Title
                        html.Div(
                            className="title-container",
                            children=[
                                html.Img(
                                    src="https://raw.githubusercontent.com/testflows/TestFlows-ArtWork/refs/heads/master/images/logo_white.svg",
                                    className="title-logo",
                                    style={
                                        "height": "32px",
                                        "width": "auto",
                                        "filter": "brightness(1)",
                                    },
                                ),
                                html.H2(
                                    "GitHub Hetzner Runners Dashboard",
                                    className="title-text",
                                    style={
                                        "margin": 0,
                                        "padding": 0,
                                        "color": COLORS["warning"],
                                    },
                                ),
                            ],
                        ),
                        # Right side - Controls
                        html.Div(
                            className="controls-container",
                            style={
                                "display": "flex",
                                "alignItems": "center",
                                "gap": "15px",
                            },
                            children=[
                                html.Label(
                                    "update interval:",
                                    style={
                                        "color": COLORS["accent"],
                                        "marginRight": "5px",
                                    },
                                    className="label",
                                ),
                                dcc.Dropdown(
                                    id="interval-dropdown",
                                    options=[
                                        {"label": "5 seconds", "value": 5},
                                        {"label": "10 seconds", "value": 10},
                                        {"label": "30 seconds", "value": 30},
                                        {"label": "1 minute", "value": 60},
                                        {"label": "5 minutes", "value": 300},
                                    ],
                                    value=5,
                                    style={
                                        "width": "150px",
                                    },
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        # Main Content
        html.Div(
            style={
                "padding": "0 20px",
                "maxWidth": "1200px",
                "margin": "0 auto",
            },
            children=[
                # Top Gauges Section
                gauges.create_panel(),
                # Rest of the panels
                servers.create_panel(),
                jobs.create_panel(),
                runners.create_panel(),
                scaleup_errors.create_panel(),
            ],
        ),
    ],
)


@app.callback(
    Output("interval-component", "interval"), Input("interval-dropdown", "value")
)
def update_interval(value):
    """Update the interval time based on dropdown selection"""
    return value * 1000  # Convert seconds to milliseconds


@app.callback(
    [
        # Servers components
        Output("servers-graph", "figure"),
        Output("total-servers-gauge", "children"),
        Output("servers-list", "children"),
        # Jobs components
        Output("jobs-graph", "figure"),
        Output("jobs-list", "children"),
        Output("queued-jobs-gauge", "children"),
        Output("running-jobs-gauge", "children"),
        # Runners components
        Output("runners-graph", "figure"),
        Output("total-runners-gauge", "children"),
        Output("runners-list", "children"),
        # Errors components
        Output("errors-graph", "figure"),
        Output("errors-list", "children"),
        Output("scale-up-errors-gauge", "children"),
        # Heartbeat components
        Output("heartbeat-gauge", "children"),
        Output("heartbeat-gauge", "style"),
    ],
    Input("interval-component", "n_intervals"),
)
def update_all_components(n):
    """Update all dashboard components in a single callback."""
    # Get all metric values at once
    total_servers = get_metric_value("github_hetzner_runners_servers_total_count") or 0
    queued_jobs = get_metric_value("github_hetzner_runners_queued_jobs") or 0
    running_jobs = get_metric_value("github_hetzner_runners_running_jobs") or 0
    total_runners = get_metric_value("github_hetzner_runners_runners_total_count") or 0
    error_count = (
        get_metric_value("github_hetzner_runners_scale_up_failures_total_count_total")
        or 0
    )
    heartbeat = get_metric_value("github_hetzner_runners_heartbeat_timestamp") or 0

    # Heartbeat styling
    heartbeat_icon = "◉"
    if heartbeat == 0:
        heartbeat_style = {
            "fontSize": "2em",
            "fontWeight": "bold",
            "color": COLORS["warning"],
        }
    else:
        heartbeat_style = {
            "fontSize": "2em",
            "fontWeight": "bold",
            "color": COLORS["success"],
            "opacity": "1",
            "transition": "opacity 0.5s ease-in-out",
        }

    return (
        # Servers components
        servers.update_graph(n),
        str(int(total_servers)),
        servers.create_server_list(),
        # Jobs components
        jobs.update_graph(n),
        jobs.create_job_list(),
        str(int(queued_jobs)),
        str(int(running_jobs)),
        # Runners components
        runners.update_graph(n),
        str(int(total_runners)),
        runners.create_runner_list(),
        # Errors components
        scaleup_errors.update_graph(n),
        scaleup_errors.create_error_list(),
        str(int(error_count)),
        # Heartbeat components
        heartbeat_icon,
        heartbeat_style,
    )


def start_http_server(
    port: int = 8090, host: str = "0.0.0.0", debug: bool = False
) -> threading.Thread:
    """Start the dashboard HTTP server in a daemon thread.

    Args:
        port: The port to listen on, default: 8050
        host: The host to bind to, default: '0.0.0.0'
        debug: Whether to run in debug mode, default: False

    Returns:
        threading.Thread: The thread running the dashboard server
    """
    thread = threading.Thread(
        target=lambda: app.run_server(host=host, port=port, debug=debug), daemon=True
    )
    thread.start()
    return thread
