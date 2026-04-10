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
from ..colors import STATE_COLORS


def render_volume_metrics():
    """Render the volume metrics header."""

    # Get current volume summary
    volumes_summary = metrics.volumes.summary()

    # Build metrics data
    metrics_data = [
        {"label": "Total", "value": volumes_summary["total"]},
        {
            "label": "Available",
            "value": volumes_summary["by_status"].get("available", 0),
        },
        {
            "label": "Attached",
            "value": volumes_summary["by_status"].get("attached", 0),
        },
        {
            "label": "Creating",
            "value": volumes_summary["by_status"].get("creating", 0),
        },
    ]

    renderers.render_metrics_columns(metrics_data)


def render_volume_chart():
    """Render the volume chart."""

    # Get volume states history
    states_history = metrics.volumes.states_history()
    df = metrics.history.dataframe_for_states(states_history)

    # Create color mapping for volume states
    color_domain = ["available", "creating", "attached"]
    color_range = [
        STATE_COLORS.get("available", "#00ff00"),
        STATE_COLORS.get("creating", "#ffff00"),
        STATE_COLORS.get("attached", "#0000ff"),
    ]

    def create_chart():
        return chart.create_time_series_chart(
            chart_id="volumes",
            df=df,
            group_by="Status",
            y_title="Number of Volumes",
            names=color_domain,
            colors=color_range,
            y_type="count",
        )

    renderers.render_chart(
        create_chart,
        "No volume data available yet. The chart will appear once data is collected.",
        "rendering volume chart",
    )


def render_volume_details():
    """Render the volume details as a dataframe."""

    # Get volume details
    volumes_details = metrics.volumes.summary()["details"]
    formatted_details = metrics.volumes.formatted_details(volumes_details)

    renderers.render_details_dataframe(
        items=formatted_details,
        title="Volume Details",
        name_key="name",
        status_key="status",
    )


def render():
    """Render the volumes panel."""
    renderers.render_panel(
        title="Volumes",
        metrics_func=render_volume_metrics,
        chart_func=render_volume_chart,
        details_func=render_volume_details,
        message="rendering volumes panel",
    )
