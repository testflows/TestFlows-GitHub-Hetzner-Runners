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
from .. import chart, renderers
from ..colors import STREAMLIT_COLORS


def render_scale_up_errors_metrics():
    """Render the scale-up errors metrics section."""
    # Get scale-up errors summary
    summary_data = metrics.errors.scale_up_summary()

    # Build metrics data
    metrics_data = [
        {"label": "Total Errors", "value": summary_data["last_hour"]},
    ]

    renderers.render_metrics_columns(metrics_data)


def render_scale_up_errors_chart():
    """Render the scale-up errors chart section."""
    # Get scale-up errors history and create dataframe
    states_history = metrics.errors.scale_up_history(cutoff_minutes=60)
    df = metrics.history.dataframe_for_states(states_history)

    def create_chart():
        return chart.create_time_series_chart(
            chart_id="scale_up_errors",
            df=df,
            group_by="Status",
            y_title="Number of Errors",
            names=["Scale-up Errors"],
            colors=[STREAMLIT_COLORS["error"]],
            y_type="count",
        )

    renderers.render_chart(
        create_chart,
        "No error data available yet. The chart will appear once data is collected.",
        "rendering scale-up errors chart",
    )


def render_scale_up_errors_details():
    """Render the scale-up errors details section."""
    # Get formatted scale-up error details
    formatted_errors = metrics.errors.scale_up_formatted_details()

    renderers.render_details_dataframe(
        items=formatted_errors,
        title="Error Details",
        name_key="name",
        status_key="server_name",
    )


def render():
    """Render the scale-up errors panel in Streamlit.

    This function creates a Streamlit-compatible version of the scale-up errors panel
    that maintains all the functionality of the original dashboard panel.
    """
    renderers.render_panel(
        title="Scale-up Errors",
        title_caption="Last Hour",
        metrics_func=render_scale_up_errors_metrics,
        chart_func=render_scale_up_errors_chart,
        details_func=render_scale_up_errors_details,
        message="rendering scale-up errors panel",
    )
