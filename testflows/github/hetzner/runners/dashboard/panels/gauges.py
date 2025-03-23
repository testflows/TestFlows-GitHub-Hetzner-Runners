from dash import html
from ..colors import COLORS


def create_gauge(title, gauge_id, color=COLORS["warning"], clickable=False):
    """Create a gauge component with consistent styling.

    Args:
        title: The title text for the gauge
        gauge_id: The ID for the gauge div
        color: The color for the gauge value (defaults to warning color)
        clickable: Whether the gauge should be clickable (defaults to False)

    Returns:
        html.Div: A styled gauge component
    """
    return html.Div(
        style={
            "textAlign": "center",
            "padding": "15px",
            "backgroundColor": COLORS["paper"],
            "borderRadius": "4px",
            "minWidth": "100px",
            "flex": "0 1 auto",
            "cursor": "pointer" if clickable else "default",
            "transition": "background-color 0.2s ease",
        },
        id=f"{gauge_id}-container",
        children=[
            html.Div(
                title,
                style={
                    "color": COLORS["accent"],
                    "fontSize": "1.1em",
                    "marginBottom": "5px",
                },
            ),
            html.Div(
                id=gauge_id,
                style={
                    "fontSize": "2em",
                    "fontWeight": "bold",
                    "color": color,
                },
            ),
        ],
    )


def create_panel():
    """Create the top panel containing various gauges."""
    return html.Div(
        style={
            "display": "flex",
            "gap": "20px",
            "marginBottom": "20px",
            "justifyContent": "center",
            "flexWrap": "wrap",
        },
        children=[
            create_gauge("Heartbeat", "heartbeat-gauge"),
            create_gauge("Cost (€/h)", "cost-gauge", clickable=True),
            create_gauge("Servers", "total-servers-gauge", clickable=True),
            create_gauge("Runners", "total-runners-gauge", clickable=True),
            create_gauge("Queued Jobs", "queued-jobs-gauge", clickable=True),
            create_gauge("Running Jobs", "running-jobs-gauge", clickable=True),
            create_gauge("Scale Up Errors", "scale-up-errors-gauge", clickable=True),
        ],
    )
