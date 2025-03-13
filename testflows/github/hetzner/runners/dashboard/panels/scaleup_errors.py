from datetime import datetime, timedelta
from dash import html, dcc
import logging

from ..colors import COLORS
from ..metrics import get_metric_value, metric_history, get_metric_info


def create_panel():
    """Create errors panel."""
    return html.Div(
        className="tui-container",
        children=[
            html.H3(
                "Scale-up Errors (Last 60 Minutes)",
                style={
                    "color": COLORS["accent"],
                    "marginBottom": "20px",
                    "borderBottom": f"1px solid {COLORS['accent']}",
                    "paddingBottom": "10px",
                },
            ),
            # Error count graph
            dcc.Graph(
                id="errors-graph",
                style={"height": "300px"},
            ),
            # Error list
            html.Div(
                id="errors-list",
                style={
                    "marginTop": "20px",
                    "borderTop": f"1px solid {COLORS['accent']}",
                    "paddingTop": "20px",
                },
            ),
        ],
    )


def create_error_list():
    """Create a list of scale-up errors with their descriptions."""
    error_count = (
        get_metric_value("github_hetzner_runners_scale_up_failures_total_count_total")
        or 0
    )

    if error_count == 0:
        return html.Div(
            "No scale-up errors",
            style={
                "color": COLORS["text"],
                "padding": "10px",
                "fontFamily": "JetBrains Mono, Fira Code, Consolas, monospace",
            },
        )

    return html.Div(
        f"Total scale-up errors: {error_count}",
        style={
            "color": COLORS["error"],
            "padding": "10px",
            "fontFamily": "JetBrains Mono, Fira Code, Consolas, monospace",
        },
    )


def update_graph(n):
    """Update errors graph."""
    current_time = datetime.now()
    one_hour_ago = current_time - timedelta(hours=1)
    common_style = {
        "gridcolor": COLORS["grid"],
        "zerolinecolor": COLORS["grid"],
        "color": COLORS["text"],
        "font": {"family": "JetBrains Mono, Fira Code, Consolas, monospace"},
    }

    # Get error count
    error_count = (
        get_metric_value("github_hetzner_runners_scale_up_failures_total_count_total")
        or 0
    )

    # Create time points every 2 minutes for the last hour
    time_points = []
    error_counts = []

    # Start from one hour ago and move forward to now in 2-minute intervals
    for i in range(31):  # 30 intervals of 2 minutes = 60 minutes
        time_point = one_hour_ago + timedelta(minutes=i * 2)
        time_points.append(time_point)
        error_counts.append(0)

    # Empty graph layout
    layout = {
        "title": {
            "text": "Scale-up Errors Over Time (Last Hour)",
            "font": {"size": 16, "weight": "bold", **common_style["font"]},
            "x": 0.5,
            "y": 0.95,
        },
        "height": 300,
        "plot_bgcolor": COLORS["background"],
        "paper_bgcolor": COLORS["paper"],
        "font": common_style,
        "xaxis": {
            "title": "Time",
            "tickformat": "%H:%M",
            "dtick": 480000,  # 8 minutes in milliseconds for grid lines
            "tickmode": "linear",
            "gridcolor": COLORS["grid"],
            "autorange": False,
            "range": [one_hour_ago, current_time],
            "type": "date",
            "showgrid": True,  # Ensure grid is visible
            **common_style,
        },
        "yaxis": {
            "title": "Number of Errors",
            "range": [0, 2],  # Start with range [0,2] for empty graph
            "tickformat": "d",  # 'd' format ensures integers only
            "automargin": True,
            "showgrid": True,  # Ensure grid is visible
            "dtick": 1,  # Force integer ticks
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
    }

    if error_count == 0:
        return {
            "data": [],
            "layout": {
                **layout,
                "title": {
                    "text": "No errors in the last hour",
                    "font": {"size": 16, "weight": "bold", **common_style["font"]},
                    "x": 0.5,
                    "y": 0.95,
                },
                "showlegend": False,
            },
            "config": {
                "displayModeBar": False,
                "staticPlot": True,
                "displaylogo": False,
            },
        }

    # Put all errors in the last time slot
    error_counts[-1] = error_count

    # Calculate optimal y-axis range and tick spacing
    max_value = max(2, error_count + 1)

    # Define tick spacing based on the maximum value
    if max_value <= 5:
        dtick = 1
    elif max_value <= 10:
        dtick = 2
    elif max_value <= 20:
        dtick = 5
    elif max_value <= 50:
        dtick = 10
    else:
        dtick = 20

    # Create trace for error count
    trace = {
        "x": time_points,
        "y": error_counts,
        "type": "scatter",
        "mode": "lines+markers",
        "name": "Scale-up Errors",
        "line": {"color": COLORS["error"]},
        "marker": {"color": COLORS["error"]},
    }

    return {
        "data": [trace],
        "layout": {
            **layout,
            "yaxis": {
                **layout["yaxis"],
                "range": [0, max_value],
                "dtick": dtick,
                "tickformat": "d",  # Ensure integer display
            },
        },
        "config": {
            "displayModeBar": False,
            "staticPlot": True,
            "displaylogo": False,
        },
    }
