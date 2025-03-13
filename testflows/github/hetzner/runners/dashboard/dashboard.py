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

from dash import html, dcc
from dash.dependencies import Input, Output
from flask import send_from_directory

from .colors import COLORS
from .panels import servers, jobs
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
                html.Div(
                    style={
                        "display": "flex",
                        "gap": "20px",
                        "marginBottom": "20px",
                        "justifyContent": "center",
                        "flexWrap": "wrap",
                    },
                    children=[
                        # Servers Gauge
                        html.Div(
                            style={
                                "textAlign": "center",
                                "padding": "15px",
                                "backgroundColor": COLORS["paper"],
                                "borderRadius": "4px",
                                "minWidth": "150px",
                                "flex": "0 1 auto",
                            },
                            children=[
                                html.Div(
                                    "Servers",
                                    style={
                                        "color": COLORS["accent"],
                                        "fontSize": "1.1em",
                                        "marginBottom": "5px",
                                    },
                                ),
                                html.Div(
                                    id="total-servers-gauge",
                                    style={
                                        "fontSize": "2em",
                                        "fontWeight": "bold",
                                        "color": COLORS["warning"],
                                    },
                                ),
                            ],
                        ),
                        # Queued Jobs Gauge
                        html.Div(
                            style={
                                "textAlign": "center",
                                "padding": "15px",
                                "backgroundColor": COLORS["paper"],
                                "borderRadius": "4px",
                                "minWidth": "150px",
                                "flex": "0 1 auto",
                            },
                            children=[
                                html.Div(
                                    "Queued Jobs",
                                    style={
                                        "color": COLORS["accent"],
                                        "fontSize": "1.1em",
                                        "marginBottom": "5px",
                                    },
                                ),
                                html.Div(
                                    id="queued-jobs-gauge",
                                    style={
                                        "fontSize": "2em",
                                        "fontWeight": "bold",
                                        "color": COLORS["warning"],
                                    },
                                ),
                            ],
                        ),
                        # Running Jobs Gauge
                        html.Div(
                            style={
                                "textAlign": "center",
                                "padding": "15px",
                                "backgroundColor": COLORS["paper"],
                                "borderRadius": "4px",
                                "minWidth": "150px",
                                "flex": "0 1 auto",
                            },
                            children=[
                                html.Div(
                                    "Running Jobs",
                                    style={
                                        "color": COLORS["accent"],
                                        "fontSize": "1.1em",
                                        "marginBottom": "5px",
                                    },
                                ),
                                html.Div(
                                    id="running-jobs-gauge",
                                    style={
                                        "fontSize": "2em",
                                        "fontWeight": "bold",
                                        "color": COLORS["warning"],
                                    },
                                ),
                            ],
                        ),
                    ],
                ),
                # Jobs Panel
                jobs.create_panel(),
                # Servers Panel
                servers.create_panel(),
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
    Output("servers-graph", "figure"), Input("interval-component", "n_intervals")
)
def update_servers_graph(n):
    """Update servers graph."""
    return servers.update_graph(n)


@app.callback(
    Output("total-servers-gauge", "children"),
    Input("interval-component", "n_intervals"),
)
def update_total_servers_gauge(n):
    """Update total servers gauge."""
    total_servers = get_metric_value("github_hetzner_runners_servers_total_count") or 0
    return str(int(total_servers))


@app.callback(
    Output("servers-list", "children"),
    Input("interval-component", "n_intervals"),
)
def update_servers_list(n):
    """Update servers list."""
    return servers.create_server_list()


@app.callback(
    Output("interval-component-jobs", "interval"),
    Input("interval-dropdown", "value"),
)
def update_jobs_interval(value):
    """Update the interval time for jobs panel based on dropdown selection"""
    return value * 1000  # Convert seconds to milliseconds


@app.callback(
    Output("jobs-graph", "figure"),
    Input("interval-component-jobs", "n_intervals"),
)
def update_jobs_graph(n):
    """Update jobs graph."""
    return jobs.update_graph(n)


@app.callback(
    Output("jobs-list", "children"),
    Input("interval-component-jobs", "n_intervals"),
)
def update_jobs_list(n):
    """Update jobs list."""
    return jobs.create_job_list()


@app.callback(
    Output("queued-jobs-gauge", "children"),
    Input("interval-component", "n_intervals"),
)
def update_queued_jobs_gauge(n):
    """Update queued jobs gauge."""
    queued_jobs = get_metric_value("github_hetzner_runners_queued_jobs") or 0
    return str(int(queued_jobs))


@app.callback(
    Output("running-jobs-gauge", "children"),
    Input("interval-component", "n_intervals"),
)
def update_running_jobs_gauge(n):
    """Update running jobs gauge."""
    running_jobs = get_metric_value("github_hetzner_runners_running_jobs") or 0
    return str(int(running_jobs))


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
