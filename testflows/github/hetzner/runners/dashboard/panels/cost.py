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
from .utils import chart, renderers


def render_cost_metrics():
    """Render the cost metrics header."""

    # Get current cost summary for display
    cost_summary = metrics.cost.summary()

    # Build metrics data
    metrics_data = [
        {
            "label": "Hourly",
            "value": f"€{cost_summary['hourly']:.3f}/h",
        },
        {
            "label": "Daily",
            "value": f"€{cost_summary['daily']:.2f}/day",
        },
        {
            "label": "Monthly",
            "value": f"€{cost_summary['monthly']:.2f}/month",
        },
    ]

    renderers.render_metrics(metrics_data)


def render_cost_chart():
    """Render the cost chart using Altair for proper time series visualization."""

    timestamps, values, _, _ = metrics.cost.total_cost_history()
    df = metrics.history.dataframe(timestamps, values)

    # Rename column for display
    if not df.empty:
        df = df.rename(columns={"Value": "Total Cost (€/h)"})

    def create_chart():
        return chart.create_time_series_chart(
            df=df,
            y_column="Total Cost (€/h)",
            y_title="Cost (€/h)",
            y_type="price",
        )

    renderers.render_chart(
        create_chart,
        "No cost data available yet. The chart will appear once data is collected.",
        "rendering cost chart",
    )


def render():
    """Render the cost panel in Streamlit.

    This function creates a Streamlit-compatible version of the cost panel
    that maintains all the functionality of the original dashboard panel.
    """
    renderers.render_panel(
        title="Estimated Cost",
        metrics_func=render_cost_metrics,
        chart_func=render_cost_chart,
        message="rendering cost panel",
    )
