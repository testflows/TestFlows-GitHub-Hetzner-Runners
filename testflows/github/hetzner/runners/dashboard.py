import dash
import threading
from dash import dcc, html
from dash.dependencies import Input, Output
from prometheus_client import REGISTRY
from datetime import datetime, timedelta
from collections import defaultdict

import plotly.graph_objs as go

from .config import Config

# Initialize the Dash app
app = dash.Dash(__name__)

# Dark theme colors
COLORS = {
    "background": "#000000",  # Pure black
    "text": "#7FDBFF",  # Cyan blue
    "grid": "#333333",  # Dark gray
    "paper": "#111111",  # Very dark gray
    "nav": "#000000",  # Pure black
    "accent": "#008080",  # Teal
    "border": "#008080",  # Teal
    "title": "#008080",  # Teal
}

# State colors
STATE_COLORS = {
    "off": "#FF69B4",  # Hot pink
    "running": "#008080",  # Teal
    "initializing": "#FFD700",  # Gold
    "ready": "#20B2AA",  # Light Sea Green
    "busy": "#FF4500",  # Orange red
}

# Layout configuration that will be used across all plots
LAYOUT_STYLE = {
    "paper_bgcolor": COLORS["paper"],
    "plot_bgcolor": COLORS["background"],
    "font": {
        "color": COLORS["text"],
        "family": "JetBrains Mono, Fira Code, Consolas, monospace",
        "size": 11,
    },
    "xaxis": {
        "gridcolor": COLORS["grid"],
        "showgrid": True,
        "title_font": {
            "family": "JetBrains Mono, Fira Code, Consolas, monospace",
            "size": 12,
        },
        "tickfont": {
            "family": "JetBrains Mono, Fira Code, Consolas, monospace",
            "size": 10,
        },
    },
    "yaxis": {
        "gridcolor": COLORS["grid"],
        "showgrid": True,
        "title_font": {
            "family": "JetBrains Mono, Fira Code, Consolas, monospace",
            "size": 12,
        },
        "tickfont": {
            "family": "JetBrains Mono, Fira Code, Consolas, monospace",
            "size": 10,
        },
    },
}

# Create a config instance for the dashboard
config = Config()

# Store metric history
metric_history = defaultdict(lambda: {"timestamps": [], "values": []})


# Function to get metric value directly from registry
def get_metric_value(metric_name, labels=None):
    """
    Get metric value directly from Prometheus registry
    Args:
        metric_name: Name of the metric to fetch
        labels: Dictionary of label names and values
    Returns:
        int: The metric value as an integer, guaranteed to be non-negative
    """
    if labels is None:
        labels = {}

    try:
        for metric in REGISTRY.collect():
            if metric.name == metric_name:
                # Print all samples for debugging
                print(f"\nAll samples for {metric_name}:")
                for sample in metric.samples:
                    print(f"  Labels: {sample.labels}, Value: {sample.value}")

                # Get the exact matching sample
                matching_samples = [
                    sample
                    for sample in metric.samples
                    if all(sample.labels.get(k) == v for k, v in labels.items())
                ]

                if matching_samples:
                    if len(matching_samples) > 1:
                        print(
                            f"Warning: Multiple matches found for {metric_name} with labels {labels}"
                        )
                    # Take the first match
                    return int(float(matching_samples[0].value))
    except (ValueError, TypeError) as e:
        print(f"Error getting metric value: {e}")

    return 0  # Default to 0 if not found


def update_metric_history(metric_name, labels, value, timestamp):
    """Update metric history with new value"""
    key = f"{metric_name}_{','.join(f'{k}={v}' for k, v in sorted(labels.items()))}"

    # Initialize if not exists
    if key not in metric_history:
        metric_history[key] = {"timestamps": [], "values": []}

    # Keep only last 15 minutes of data
    cutoff_time = timestamp - timedelta(minutes=15)

    # Remove old data points
    while (
        metric_history[key]["timestamps"]
        and metric_history[key]["timestamps"][0] < cutoff_time
    ):
        metric_history[key]["timestamps"].pop(0)
        metric_history[key]["values"].pop(0)

    # Simply append the new value
    metric_history[key]["timestamps"].append(timestamp)
    metric_history[key]["values"].append(value)


# Set the app's background color using CSS
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                background-color: #000000;
                margin: 0;
                padding: 0;
                font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
            }
            h2, h3 {
                font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
                font-weight: 700;
                letter-spacing: -0.5px;
            }
            .title-container {
                display: flex;
                align-items: center;
                gap: 15px;
            }
            .title-logo {
                height: 32px;
                width: auto;
                margin-right: 10px;
                filter: brightness(1);
            }
            .title-logo svg {
                height: 100%;
                width: auto;
                fill: currentColor;
            }
            .title-text {
                color: #008080;
                white-space: nowrap;
            }
            @media (max-width: 768px) {
                .nav-content {
                    flex-direction: column;
                    gap: 15px;
                }
                .title-container {
                    justify-content: center;
                }
                .controls-container {
                    width: 100%;
                    justify-content: center;
                }
                .title-text {
                    font-size: 1.5em;
                }
                .title-logo {
                    height: 24px;
                }
            }
            /* TUI-style container borders */
            .tui-container {
                border: 1px solid #008080;
                border-radius: 0;
                padding: 15px;
                margin-bottom: 20px;
                position: relative;
            }
            /* Navigation bar styling */
            .nav-bar {
                border-bottom: 1px solid #008080;
                position: relative;
            }
            .nav-bar::after {
                content: "";
                position: absolute;
                bottom: -2px;
                left: 0;
                right: 0;
                height: 1px;
                border-bottom: 1px solid #008080;
            }
            /* Dropdown styling */
            .Select-control {
                background-color: #111111 !important;
                border: 1px solid #008080 !important;
                border-radius: 0 !important;
                font-family: "JetBrains Mono, Fira Code, Consolas, monospace" !important;
            }
            .Select-menu-outer {
                background-color: #111111 !important;
                border: 1px solid #008080 !important;
                border-radius: 0 !important;
                font-family: "JetBrains Mono, Fira Code, Consolas, monospace" !important;
                margin-top: -1px !important;
            }
            .Select-value-label {
                color: #008080 !important;
                font-family: "JetBrains Mono, Fira Code, Consolas, monospace" !important;
            }
            .Select-menu-outer .Select-option {
                background-color: #111111 !important;
                color: #008080 !important;
                font-family: "JetBrains Mono, Fira Code, Consolas, monospace" !important;
            }
            .Select-menu-outer .Select-option:hover {
                background-color: #008080 !important;
                color: #000000 !important;
            }
            .Select-menu-outer .Select-option.is-selected {
                background-color: #008080 !important;
                color: #000000 !important;
            }
            .Select-menu-outer .Select-option.is-focused {
                background-color: #008080 !important;
                color: #000000 !important;
            }
            .Select-placeholder {
                color: #008080 !important;
                font-family: "JetBrains Mono, Fira Code, Consolas, monospace" !important;
            }
            .Select-input > input {
                color: #008080 !important;
                font-family: "JetBrains Mono, Fira Code, Consolas, monospace" !important;
            }
            .Select.is-focused > .Select-control {
                border-color: #008080 !important;
                box-shadow: none !important;
            }
            .Select-arrow-zone {
                color: #008080 !important;
            }
            .VirtualizedSelectOption {
                background-color: #111111 !important;
                color: #008080 !important;
                font-family: "JetBrains Mono, Fira Code, Consolas, monospace" !important;
            }
            .VirtualizedSelectFocusedOption {
                background-color: #008080 !important;
                color: #000000 !important;
            }
            .Select--single > .Select-control .Select-value {
                background-color: #111111 !important;
                color: #008080 !important;
                font-family: "JetBrains Mono, Fira Code, Consolas, monospace" !important;
            }
            /* Labels styling */
            .label {
                color: #008080 !important;
                font-size: 0.9em;
                letter-spacing: 0.5px;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""

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
                                    "GitHub Hetzner runners",
                                    className="title-text",
                                    style={
                                        "margin": 0,
                                        "padding": 0,
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
                                    value=30,
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
                # Servers Total Section
                html.Div(
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
                ),
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
    Output("servers-total-graph", "figure"), Input("interval-component", "n_intervals")
)
def update_servers_total(n):
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


if __name__ == "__main__":
    start_http_server(port=config.dashboard_port)
