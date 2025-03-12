import dash
import threading
from dash import dcc, html
from dash.dependencies import Input, Output
from prometheus_client import REGISTRY
from datetime import datetime, timedelta

import plotly.graph_objs as go

from .config import Config

# Initialize the Dash app
app = dash.Dash(__name__)

# Dark theme colors
COLORS = {
    "background": "#111111",
    "text": "#7FDBFF",
    "grid": "#333333",
    "paper": "#222222",
}

# Layout configuration that will be used across all plots
LAYOUT_STYLE = {
    "paper_bgcolor": COLORS["paper"],
    "plot_bgcolor": COLORS["background"],
    "font": {"color": COLORS["text"]},
    "xaxis": {"gridcolor": COLORS["grid"], "showgrid": True},
    "yaxis": {"gridcolor": COLORS["grid"], "showgrid": True},
}

# Create a config instance for the dashboard
config = Config()


# Function to get metric value directly from registry
def get_metric_value(metric_name, labels=None):
    """
    Get metric value directly from Prometheus registry
    Args:
        metric_name: Name of the metric to fetch
        labels: Dictionary of label names and values
    """
    if labels is None:
        labels = {}

    for metric in REGISTRY.collect():
        if metric.name == metric_name:
            for sample in metric.samples:
                # Check if all labels match
                if all(sample.labels.get(k) == v for k, v in labels.items()):
                    return sample.value
    return 0.0


app.layout = html.Div(
    style={"backgroundColor": COLORS["background"], "padding": "20px"},
    children=[
        html.H1(
            "GitHub Hetzner Runners Dashboard",
            style={
                "textAlign": "center",
                "color": COLORS["text"],
                "marginBottom": "30px",
            },
        ),
        # Servers Total Section
        html.Div(
            [
                html.H3(
                    "Servers Total",
                    style={"color": COLORS["text"], "marginBottom": "20px"},
                ),
                dcc.Graph(id="servers-total-graph"),
                dcc.Interval(
                    id="interval-component",
                    interval=30 * 1000,  # Update every 30 seconds
                    n_intervals=0,
                ),
            ]
        ),
    ],
)


@app.callback(
    Output("servers-total-graph", "figure"), Input("interval-component", "n_intervals")
)
def update_servers_total(n):
    # Get current time for the x-axis
    current_time = datetime.now()

    # Fetch data for each status
    statuses = ["running", "off", "initializing", "ready", "busy"]
    traces = []

    for status in statuses:
        value = get_metric_value(
            "github_hetzner_runners_servers_total", {"status": status}
        )

        traces.append(
            go.Scatter(
                x=[current_time],
                y=[value],
                name=status.capitalize(),
                mode="lines+markers",
            )
        )

    return {
        "data": traces,
        "layout": {
            **LAYOUT_STYLE,
            "title": "Servers by Status",
            "height": 400,
            "xaxis": {
                **LAYOUT_STYLE["xaxis"],
                "title": "Time",
                "range": [current_time - timedelta(minutes=15), current_time],
            },
            "yaxis": {**LAYOUT_STYLE["yaxis"], "title": "Number of Servers"},
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
