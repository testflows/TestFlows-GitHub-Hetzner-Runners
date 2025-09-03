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
import pandas as pd

from .. import metrics
from ..colors import STATE_COLORS
from .. import chart, renderers


def render_standby_pool_info(config=None):
    """Render standby pool configuration information."""
    try:
        st.subheader("Pool Configuration")

        if not config or not config.standby_runners:
            st.info("No standby runners configured")
            return

        # Get actual standby runner configuration from config
        config_data = []
        for standby_runner in config.standby_runners:
            config_data.append(
                {
                    "labels": standby_runner.labels,
                    "count": standby_runner.count,
                    "replenish immediately": standby_runner.replenish_immediately,
                }
            )

        df = pd.DataFrame(config_data)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

    except Exception as e:
        st.error(f"Error rendering standby pool info: {e}")


def render_standby_servers_metrics():
    """Render the standby servers metrics header."""
    # Get standby servers summary
    standby_summary = metrics.servers.standby_summary()

    # Build metrics data
    metrics_data = [
        {"label": "Total", "value": standby_summary["total"]},
        {"label": "Running", "value": standby_summary["by_status"].get("running", 0)},
        {"label": "Ready", "value": standby_summary["by_status"].get("ready", 0)},
        {
            "label": "Other",
            "value": sum(
                count
                for status, count in standby_summary["by_status"].items()
                if status not in ["running", "ready"]
            ),
        },
    ]

    renderers.render_metrics_columns(metrics_data)


def render_standby_servers_chart():
    """Render the standby servers chart."""
    # Get standby servers history and create dataframe
    states_history = metrics.servers.standby_states_history()
    df = metrics.history.dataframe_for_states(states_history)

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
            y_title="Number of Standby Servers",
            color_column="Status",
            color_domain=color_domain,
            color_range=color_range,
            y_type="count",
        )

    renderers.render_chart(
        create_chart,
        "No standby server data available yet. The chart will appear once data is collected.",
        "rendering standby servers chart",
    )


def render_standby_servers_details():
    """Render the standby servers details as a dataframe."""
    # Get all servers and filter for standby servers
    servers_summary = metrics.servers.summary()
    all_servers = servers_summary["details"]

    # Filter for standby servers
    standby_servers = [
        server
        for server in all_servers
        if server.get("name", "").startswith("github-hetzner-runner-standby-")
    ]

    # Format using the existing servers formatting function
    formatted_standby_servers = metrics.servers.formatted_details(standby_servers)

    renderers.render_details_dataframe(
        items=formatted_standby_servers,
        title="Standby Server Details",
        name_key="name",
        status_key="status",
    )


def render_standby_runners_metrics():
    """Render standby runners metrics header."""
    # Get standby runners summary
    standby_runners_summary = metrics.runners.standby_summary()

    # Build metrics data
    metrics_data = [
        {"label": "Total", "value": standby_runners_summary["total"]},
        {
            "label": "Online",
            "value": standby_runners_summary["by_status"].get("online", 0),
        },
        {
            "label": "Offline",
            "value": standby_runners_summary["by_status"].get("offline", 0),
        },
    ]

    renderers.render_metrics_columns(metrics_data)


def render_standby_runners_chart():
    """Render the standby runners chart."""
    # Get standby runners history and create dataframe
    states_history = metrics.runners.standby_states_history()
    df = metrics.history.dataframe_for_states(states_history)

    # Create color mapping for runner states
    color_domain = ["online", "offline"]
    color_range = [
        STATE_COLORS["running"],  # Use running color for online
        STATE_COLORS["off"],  # Use off color for offline
    ]

    def create_chart():
        return chart.create_time_series_chart(
            df=df,
            y_title="Number of Standby Runners",
            color_column="Status",
            color_domain=color_domain,
            color_range=color_range,
            y_type="count",
        )

    renderers.render_chart(
        create_chart,
        "No standby runners data available yet. The chart will appear once data is collected.",
        "rendering standby runners chart",
    )


def render_standby_runners_details():
    """Render the standby runners details as a dataframe."""
    # Get standby runners summary
    standby_runners_summary = metrics.runners.standby_summary()
    formatted_standby_runners = metrics.runners.formatted_details(
        standby_runners_summary["details"]
    )

    renderers.render_details_dataframe(
        items=formatted_standby_runners,
        title="Standby Runner Details",
        name_key="name",
        status_key="status",
        link_keys=["link"],
    )


def render(config=None):
    """Render the standby panel in Streamlit.

    This function creates a Streamlit-compatible version of the standby panel
    that maintains all the functionality of the original dashboard panel.
    """
    # Add pool configuration section at the top
    render_standby_pool_info(config)

    renderers.render_panel(
        title="Standby Servers",
        metrics_func=render_standby_servers_metrics,
        chart_func=render_standby_servers_chart,
        details_func=render_standby_servers_details,
        message="rendering standby servers panel",
    )

    # Group standby runners metrics, chart and details together
    renderers.render_panel(
        title="Standby Runners",
        metrics_func=render_standby_runners_metrics,
        chart_func=render_standby_runners_chart,
        details_func=render_standby_runners_details,
        message="rendering standby runners panel",
    )
