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

from .. import metrics
from ..colors import STREAMLIT_COLORS
from .. import chart, renderers


def render_cost_metrics():
    """Render the cost metrics header."""

    cost_summary = metrics.cost.summary()

    metrics_data = []
    for currency, data in cost_summary.items():
        sym = metrics.cost.CURRENCY_SYMBOLS.get(currency, currency)
        metrics_data.extend(
            [
                {"label": f"Hourly ({currency})", "value": f"{sym}{data['hourly']:.3f}/h"},
                {"label": f"Daily ({currency})", "value": f"{sym}{data['daily']:.2f}/day"},
                {"label": f"Monthly ({currency})", "value": f"{sym}{data['monthly']:.2f}/month"},
            ]
        )

    if not metrics_data:
        metrics_data = [
            {"label": "Hourly", "value": "0.000/h"},
            {"label": "Daily", "value": "0.00/day"},
            {"label": "Monthly", "value": "0.00/month"},
        ]

    renderers.render_metrics(metrics_data)


def render_cost_chart():
    """Render the cost breakdown chart showing total, servers, and volumes costs."""

    # Get cost history data for all three metrics
    total_timestamps, total_values = metrics.cost.total_cost_history()
    servers_timestamps, servers_values = metrics.cost.servers_cost_history()
    volumes_timestamps, volumes_values = metrics.cost.volumes_cost_history()

    # Create data structure compatible with dataframe_for_states
    cost_data = {
        "total": {"timestamps": total_timestamps, "values": total_values},
        "servers": {"timestamps": servers_timestamps, "values": servers_values},
        "volumes": {"timestamps": volumes_timestamps, "values": volumes_values},
    }

    # Use dataframe_for_states to create the DataFrame
    df = metrics.history.dataframe_for_states(
        cost_data,
        time_column="Time",
        value_column="Cost/h",
        status_column="Type",
        value_type=float,
    )

    # Convert values to float for price display
    if not df.empty:
        df["Cost/h"] = df["Cost/h"].astype(float)

    # Create color mapping for cost types
    color_domain = ["total", "servers", "volumes"]
    color_range = [
        STREAMLIT_COLORS["primary"],  # Red for total
        STREAMLIT_COLORS["success"],  # Green for servers
        STREAMLIT_COLORS["info"],  # Cyan for volumes
    ]

    mixed = len(metrics.cost.total_cost()) > 1
    y_title = "Cost/h (mixed currencies)" if mixed else "Cost/h"

    def create_chart():
        return chart.create_time_series_chart(
            chart_id="cost",
            df=df,
            group_by="Type",
            y_column="Cost/h",
            y_title=y_title,
            names=color_domain,
            colors=color_range,
            y_type="price",
        )

    renderers.render_chart(
        create_chart,
        "No cost data available yet. The chart will appear once data is collected.",
        "rendering cost breakdown chart",
    )


def render_cost_details():
    """Render cost details showing servers and volumes with hourly, daily, and monthly costs."""

    # Get formatted cost details
    formatted_costs = metrics.cost.formatted_details()

    renderers.render_details_dataframe(
        items=formatted_costs,
        title="Cost Details",
        name_key="name",
        status_key="status",
    )


def render():
    """Render the cost panel in Streamlit.

    This function creates a Streamlit-compatible version of the cost panel
    that maintains all the functionality of the original dashboard panel.
    """
    renderers.render_panel(
        title="Cost",
        title_caption="Estimated",
        metrics_func=render_cost_metrics,
        chart_func=render_cost_chart,
        details_func=render_cost_details,
        message="rendering cost panel",
    )
