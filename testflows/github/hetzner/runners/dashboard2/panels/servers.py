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

import altair as alt
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging

from .. import metrics
from ..colors import STATE_COLORS
from .utils import chart, render as render_utils, data


def create_panel():
    """Create servers panel.

    This function maintains API compatibility with the original dashboard.

    Returns:
        dict: Panel configuration dictionary
    """
    return {"title": "Servers", "type": "servers"}


def get_server_history_data(cutoff_minutes=15):
    """Get server history data for plotting.

    Args:
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        dict: Dictionary with server status history data
    """
    states = ["running", "off", "initializing", "ready", "busy"]
    return data.get_metric_history_for_states(
        "github_hetzner_runners_servers_total", states, cutoff_minutes=cutoff_minutes
    )


def create_server_dataframe(history_data):
    """Create a pandas DataFrame for the server data with proper time formatting."""
    return chart.create_dataframe_from_history(history_data)


def get_current_server_data():
    """Get current server data without caching to ensure fresh data."""
    states = ["running", "off", "initializing", "ready", "busy"]
    current_values, current_time = data.get_current_metric_values(
        "github_hetzner_runners_servers_total", states
    )

    # Get history data for plotting
    history_data = get_server_history_data()

    return history_data, current_values, current_time


@st.fragment(run_every=st.session_state.get("update_interval", 5))
def render_server_metrics():
    """Render the server metrics header in an isolated fragment for optimal performance."""
    try:
        # Get current server summary
        servers_summary = metrics.get_servers_summary()

        # Build metrics data
        metrics_data = [
            {"label": "Total Servers", "value": servers_summary["total"]},
            {
                "label": "Running Servers",
                "value": servers_summary["by_status"].get("running", 0),
            },
            {
                "label": "Other States",
                "value": sum(
                    count
                    for status, count in servers_summary["by_status"].items()
                    if status != "running"
                ),
            },
        ]

        render_utils.render_metrics_columns(metrics_data)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering server metrics: {e}")
        st.error(f"Error rendering server metrics: {e}")


@st.fragment(run_every=st.session_state.get("update_interval", 5))
def render_server_chart():
    """Render the server chart using Altair for proper multi-line visualization."""
    try:
        # Get fresh data
        history_data, current_values, current_time = get_current_server_data()

        # Create DataFrame for the chart
        df = create_server_dataframe(history_data)

        # Create color mapping for server states
        color_domain = ["running", "off", "initializing", "ready", "busy"]
        color_range = [
            STATE_COLORS["running"],
            STATE_COLORS["off"],
            STATE_COLORS["initializing"],
            STATE_COLORS["ready"],
            STATE_COLORS["busy"],
        ]

        def create_chart():
            return chart.create_time_series_chart(
                df=df,
                y_title="Number of Servers",
                color_column="Status",
                color_domain=color_domain,
                color_range=color_range,
                y_type="count",
            )

        chart.render_chart_with_fallback(
            create_chart,
            "No server data available yet. The chart will appear once data is collected.",
            "Error rendering server chart",
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering server chart: {e}")
        st.error(f"Error rendering server chart: {e}")


@st.fragment(run_every=st.session_state.get("update_interval", 5))
def render_server_details():
    """Render the server details list."""
    try:
        # Get server information using the same approach as metrics
        servers_summary = metrics.get_servers_summary()
        servers_info = servers_summary["details"]
        total_servers = servers_summary["total"]

        if not servers_info:
            if total_servers > 0:
                st.info(f"Total servers: {total_servers} (details not available)")
            else:
                st.info("No servers found")
            return

        def build_server_content(info):
            server_id = info.get("server_id")
            server_name = info.get("name")

            # Get server labels
            server_labels_info = metrics.get_metric_info(
                "github_hetzner_runners_server_labels"
            )
            server_labels_list = []
            for label_dict in server_labels_info:
                if (
                    label_dict.get("server_id") == server_id
                    and label_dict.get("server_name") == server_name
                    and "label" in label_dict
                ):
                    server_labels_list.append(label_dict["label"])

            content_lines = data.format_server_content(info, server_labels_list)
            st.markdown("  \n".join(content_lines))

        render_utils.render_expandable_details(
            items=servers_info,
            title_prefix="Server",
            status_key="status",
            name_key="name",
            content_builder=build_server_content,
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering server details: {e}")
        st.error(f"Error rendering server details: {e}")


def render():
    """Render the servers panel in Streamlit.

    This function creates a Streamlit-compatible version of the servers panel
    that maintains all the functionality of the original dashboard panel.
    """
    render_utils.render_panel_with_fragments(
        title="Servers",
        metrics_func=render_server_metrics,
        chart_func=render_server_chart,
        details_func=render_server_details,
        error_message="Error rendering servers panel",
    )


def render_graph_only():
    """Render only the servers graph without header and metrics.

    This is useful for embedding the servers graph in other panels or layouts.
    """
    render_server_chart()
