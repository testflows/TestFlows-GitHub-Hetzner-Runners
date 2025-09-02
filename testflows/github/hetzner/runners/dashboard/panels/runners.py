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

import streamlit as st
from .. import metrics
from ..colors import STREAMLIT_COLORS
from .utils import chart, renderers


def render_runners_metrics():
    """Render the runners metrics header."""

    # Get current runners summary
    runners_summary = metrics.runners.summary()

    # Get busy runners count
    busy_runners = metrics.get.metric_value("github_hetzner_runners_runners_busy") or 0

    # Build metrics data
    metrics_data = [
        {"label": "Total", "value": runners_summary["total"]},
        {
            "label": "Online",
            "value": runners_summary["by_status"].get("online", 0),
        },
        {
            "label": "Offline",
            "value": runners_summary["by_status"].get("offline", 0),
        },
        {"label": "Busy", "value": int(busy_runners)},
    ]

    renderers.render_metrics_columns(metrics_data)


def render_runners_chart():
    """Render the runners chart."""

    # Get runners history and create dataframe
    states_history = metrics.runners.runners_history()
    df = metrics.history.dataframe_for_states(states_history)

    # Create color mapping for runner states
    color_domain = ["online", "offline", "busy", "total"]
    color_range = [
        STREAMLIT_COLORS["success"],  # Green for online
        STREAMLIT_COLORS["error"],  # Red for offline
        STREAMLIT_COLORS["warning"],  # Orange for busy
        STREAMLIT_COLORS["info"],  # Blue for total
    ]

    def create_chart():
        return chart.create_time_series_chart(
            df=df,
            y_title="Number of Runners",
            color_column="Status",
            color_domain=color_domain,
            color_range=color_range,
            y_type="count",
        )

    renderers.render_chart(
        create_chart,
        "No runners data available yet. The chart will appear once data is collected.",
        "rendering runners chart",
    )


def render_runners_details():
    """Render the runners details as a dataframe."""

    # Get runners summary and format details
    runners_summary = metrics.runners.summary()
    formatted_runners = metrics.runners.formatted_details(runners_summary["details"])

    renderers.render_details_dataframe(
        items=formatted_runners,
        title="Runner Details",
        name_key="name",
        status_key="status",
        link_keys=["link"],
    )


def render():
    """Render the runners panel in Streamlit.

    This function creates a Streamlit-compatible version of the runners panel
    that maintains all the functionality of the original dashboard panel.
    """
    renderers.render_panel(
        title="Runners",
        metrics_func=render_runners_metrics,
        chart_func=render_runners_chart,
        details_func=render_runners_details,
        message="rendering runners panel",
    )
