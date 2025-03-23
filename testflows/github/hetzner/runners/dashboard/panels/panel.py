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
from dash import html, dcc
from datetime import datetime, timedelta

from ..colors import COLORS
from ..metrics import update_metric_history, metric_history


def create_list(name, count, items, no_details):
    """Create a list of items with their descriptions.

    Args:
        name: Name of the list
        count: Number of items
        items: List of items to display
        no_details: Message to show when details are not available
    """
    if count == 0:
        return html.Div(
            f"No {name}",
            style={
                "color": COLORS["text"],
                "padding": "10px",
                "fontFamily": "JetBrains Mono, Fira Code, Consolas, monospace",
            },
        )

    if count > 0 and not items:
        items.append(
            html.Div(
                f"{no_details} (details not available)",
                style={
                    "color": COLORS["warning"],
                    "padding": "10px",
                    "fontFamily": "JetBrains Mono, Fira Code, Consolas, monospace",
                },
            )
        )

    return html.Div(
        children=items,
        style={
            "height": "400px",
            "overflowY": "auto",
            "backgroundColor": COLORS["background"],
            "border": f"1px solid {COLORS['grid']}",
            "borderRadius": "4px",
            "padding": "4px",
            # Custom scrollbar styling
            "scrollbarWidth": "thin",
            "scrollbarColor": f"{COLORS['accent']} {COLORS['background']}",
            # Add custom class for scrollbar styling
            "WebkitOverflowScrolling": "touch",
        },
        className="custom-scrollbar",
    )


def create_list_item(name, color, header, values):
    """Create a list item with its name, header and values."""
    children = []

    if header:
        children.append(header)
    if values:
        children.extend(values)

    return html.Div(
        className=f"{name}-item",
        style={
            "borderLeft": f"4px solid {color}",
            "padding": "10px",
            "marginBottom": "10px",
            "backgroundColor": COLORS["paper"],
            "wordWrap": "break-word",
        },
        children=children,
    )


def create_item_header(label, value, value_color, extra_span=None):
    """Create a header with label and value.

    Args:
        label (str): label
        value (str): value
        value_color (str): value color
        extra_span (dict, optional): Extra span configuration with 'text' and 'color' keys
    """
    spans = [
        html.Span(
            f"{label}",
            style={
                "color": COLORS["accent"],
                "fontWeight": "bold",
            },
        ),
        html.Span(
            f" ({value})",
            style={
                "color": value_color,
                "marginLeft": "10px",
            },
        ),
    ]

    if extra_span:
        spans.append(
            html.Span(
                extra_span["text"],
                style={
                    "color": extra_span["color"],
                    "marginLeft": "10px",
                },
            )
        )

    return html.Div(
        spans,
        style={"marginBottom": "5px"},
    )


def create_item_value(label, value, value_color=COLORS["warning"], link=None):
    """Create a labeled value with optional link.

    Args:
        label (str): Label text
        value (str): Value text
        value_color (str, optional): Color for the value text. Defaults to COLORS["warning"]
        link (dict, optional): Link configuration with 'text' and 'href' keys
    """
    value_color = value_color or COLORS["warning"]

    children = [
        html.Span(
            f"{label}: ",
            style={"color": COLORS["text"]},
        ),
        html.Span(
            value,
            style={"color": value_color},
        ),
    ]

    if link:
        children.append(
            html.A(
                f" ({link['text']})",
                href=link["href"],
                target="_blank",
                style={
                    "color": COLORS["accent"],
                    "marginLeft": "10px",
                    "textDecoration": "none",
                },
            )
        )

    return html.Div(
        children,
        style={"marginBottom": "2px"},
    )


def create_panel(title, with_header=True, with_graph=True, with_list=True):
    """Create panel that contains a graph and a list of items."""
    children = []
    panel_id = title.lower().replace(" ", "-")

    header = (
        html.H3(
            title,
            style={
                "color": COLORS["accent"],
                "marginBottom": "20px",
                "borderBottom": f"1px solid {COLORS['accent']}",
                "paddingBottom": "10px",
            },
        )
        if with_header
        else None
    )

    graph = (
        dcc.Graph(
            id=f"{panel_id}-graph",
        )
        if with_graph
        else None
    )

    list = (
        html.Div(
            id=f"{panel_id}-list",
            style=(
                {
                    "marginTop": "20px",
                    "borderTop": f"1px solid {COLORS['accent']}",
                    "paddingTop": "20px",
                }
                if with_graph
                else None
            ),
        )
        if with_list
        else None
    )

    if with_header:
        children.append(header)

    if with_graph:
        children.append(graph)

    if with_list:
        children.append(list)

    return html.Div(
        id=panel_id,
        className="tui-container",
        children=children,
    )


def create_trace(x, y, name, text, color):
    """Create a trace for the graph."""
    return {
        "type": "scatter",
        "x": x,
        "y": y,
        "name": name,
        "mode": "lines",
        "line": {"width": 2, "shape": "hv", "color": color},
        "text": text,
        "hoverinfo": "y+text",
    }


def create_graph(traces, title, xaxis, yaxis, height=400):
    """Create a scatter plot graph.

    Args:
        traces: List of traces to plot
        title: Graph title
        xaxis: X-axis configuration
        yaxis: Y-axis configuration
        height: Graph height in pixels
    """
    common_style = {
        "font": {
            "family": "JetBrains Mono, Fira Code, Consolas, monospace",
            "color": COLORS["text"],
        },
        "gridcolor": COLORS["grid"],
        "showgrid": True,
        "fixedrange": True,
    }

    # Safely merge common_style with existing axis configurations
    for key, value in common_style.items():
        if key not in xaxis:
            xaxis[key] = value
        if key not in yaxis:
            yaxis[key] = value

    return {
        "data": traces,
        "layout": {
            "title": {
                "text": f"{title.capitalize()}",
                "font": {"size": 16, "weight": "bold", **common_style["font"]},
                "x": 0.5,
                "y": 0.95,
            },
            "height": height,
            "plot_bgcolor": COLORS["background"],
            "paper_bgcolor": COLORS["paper"],
            "font": common_style["font"],
            "xaxis": xaxis,
            "yaxis": yaxis,
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


def create_metric_trace(
    metric_name, value, current_time, color, status=None, labels=None, cutoff_minutes=15
):
    """Helper function to create metric history and create a trace.

    Args:
        metric_name: Name of the metric
        value: Current value of the metric
        current_time: Current timestamp
        color: Color for the trace
        status: Optional status text for the trace name
        labels: Optional dictionary of labels for the metric
        cutoff_minutes: Optional number of minutes to keep in history. Defaults to 15 minutes.

    Returns:
        dict: A trace dictionary ready to be used in a graph
    """
    # Update metric history and get the key
    key = update_metric_history(
        metric_name, labels or {}, value, current_time, cutoff_minutes
    )

    # Format value based on metric type
    if "cost" in metric_name.lower():
        formatted_value = f"{value:.3f}"
    else:
        formatted_value = f"{int(value)}"

    # Create trace name
    name = (
        f"{status} ({formatted_value})"
        if status
        else f"{metric_name} ({formatted_value})"
    )

    return create_trace(
        metric_history[key]["timestamps"],
        metric_history[key]["values"],
        name,
        status or metric_name,
        color,
    )


def get_time_range(current_time, cutoff_minutes=15):
    """Get the time range for graphs based on history cutoff.

    Args:
        current_time: Current timestamp
        cutoff_minutes: Optional number of minutes to keep in history

    Returns:
        list: List containing [start_time, end_time]
    """

    return [current_time - timedelta(minutes=cutoff_minutes), current_time]
