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
from datetime import datetime, timedelta
import logging

from .. import metrics
from ..colors import STATE_COLORS
from .utils import chart, render as render_utils
from .utils.metrics import StateMetric, get_metric_history_for_states


# Create metric abstraction
standby_states_metric = StateMetric(
    "github_hetzner_runners_standby_servers_total",
    ["running", "off", "initializing", "ready", "busy"],
)


def render_standby_metrics():
    """Render the standby metrics header in an isolated fragment for optimal performance."""
    try:
        # Get all server information and filter for standby servers
        servers_summary = metrics.get_servers_summary()
        servers_info = servers_summary["details"]

        # Filter for standby servers
        standby_servers = []
        for server in servers_info:
            server_name = server.get("name", "")
            if server_name.startswith("github-hetzner-runner-standby-"):
                standby_servers.append(server)

        # Count by status
        status_counts = {}
        for server in standby_servers:
            status = server.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        total_standby = len(standby_servers)
        running_standby = status_counts.get("running", 0)
        ready_standby = status_counts.get("ready", 0)
        other_states = sum(
            count
            for status, count in status_counts.items()
            if status not in ["running", "ready"]
        )

        # Build metrics data
        metrics_data = [
            {"label": "Total", "value": total_standby},
            {"label": "Running", "value": running_standby},
            {"label": "Ready", "value": ready_standby},
            {"label": "Other", "value": other_states},
        ]

        render_utils.render_metrics_columns(metrics_data)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering standby metrics: {e}")
        st.error(f"Error rendering standby metrics: {e}")


def render_standby_chart():
    """Render the standby chart using Altair for proper multi-line visualization."""
    try:
        # Get DataFrame using the simple abstraction
        df = standby_states_metric.get_dataframe()

        # Create color mapping for standby server states
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

        chart.render_chart_with_fallback(
            create_chart,
            "No standby server data available yet. The chart will appear once data is collected.",
            "Error rendering standby chart",
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering standby chart: {e}")
        st.error(f"Error rendering standby chart: {e}")


def render_standby_details():
    """Render the standby details as a dataframe."""
    try:
        # Get all server information and filter for standby servers
        servers_summary = metrics.get_servers_summary()
        servers_info = servers_summary["details"]

        # Filter for standby servers
        standby_servers = []
        for server in servers_info:
            server_name = server.get("name", "")
            if server_name.startswith("github-hetzner-runner-standby-"):
                standby_servers.append(server)

        total_standby = len(standby_servers)

        # Always continue to show the dataframe, even if empty

        # Prepare standby server data for dataframe with all relevant fields (same as regular servers)
        formatted_standby_servers = []
        for server in standby_servers:
            server_id = server.get("server_id")
            server_name = server.get("name")

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

            # Create formatted standby server data with all fields (same as regular servers)
            formatted_server = {
                "name": server.get("name", "Unknown"),
                "status": server.get("status", "unknown"),
                "server_id": server.get("server_id", ""),
                "server_type": server.get("server_type", ""),
                "location": server.get("location", ""),
                "ipv4": server.get("ipv4", ""),
                "ipv6": server.get("ipv6", ""),
                "created": server.get("created", ""),
                "labels": ", ".join(server_labels_list) if server_labels_list else "",
            }

            # Add any additional fields from the original server data
            for key, value in server.items():
                if key not in formatted_server and value:
                    # Format cost_hourly to 3 decimal points
                    if key == "cost_hourly":
                        try:
                            formatted_value = f"{float(value):.3f}"
                        except (ValueError, TypeError):
                            formatted_value = str(value)
                    else:
                        formatted_value = str(value)
                    formatted_server[key] = formatted_value

            formatted_standby_servers.append(formatted_server)

        # Use the same render_details_dataframe function as regular servers for consistency
        render_utils.render_details_dataframe(
            items=formatted_standby_servers,
            title="Standby Server Details",
            name_key="name",
            status_key="status",
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering standby details: {e}")
        st.error(f"Error rendering standby details: {e}")


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
                    "replenish_immediately": standby_runner.replenish_immediately,
                }
            )

        df = pd.DataFrame(config_data)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering standby pool info: {e}")
        st.error(f"Error rendering standby pool info: {e}")


def render_standby_runners_info():
    """Render standby runners information."""
    try:
        # Get standby runners summary
        standby_runners_summary = metrics.get_standby_runners_summary()

        # Always show metrics, even when there are no standby runners
        standby_runners_metrics = [
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

        render_utils.render_metrics_columns(standby_runners_metrics)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering standby runners info: {e}")
        st.error(f"Error rendering standby runners info: {e}")


def render_standby_runners_chart():
    """Render the standby runners chart using Altair for proper multi-line visualization."""
    try:
        # Get standby runners summary
        standby_runners_summary = metrics.get_standby_runners_summary()

        # Try to get historical data for standby runners
        try:
            # Get history data for online/offline runners and filter for standby
            states = ["online", "offline"]
            runners_history = get_metric_history_for_states(
                "github_hetzner_runners_runners_total", states, cutoff_minutes=15
            )

            # Create DataFrame for the chart with historical data
            df = chart.create_dataframe_from_history(runners_history)

            # Filter for standby runners if we can identify them
            # For now, we'll use current data since historical filtering is complex
            if df.empty:
                # Fallback to current data
                chart_data = []
                for status, count in standby_runners_summary["by_status"].items():
                    chart_data.append(
                        {"Status": status, "Count": count, "Time": pd.Timestamp.now()}
                    )
                df = pd.DataFrame(chart_data)
        except Exception:
            # Fallback to current data
            chart_data = []
            for status, count in standby_runners_summary["by_status"].items():
                chart_data.append(
                    {"Status": status, "Count": count, "Time": pd.Timestamp.now()}
                )
            df = pd.DataFrame(chart_data)

        # If no data, create empty chart with zero values for all states
        if df.empty:
            chart_data = []
            for status in ["online", "offline"]:
                chart_data.append(
                    {"Status": status, "Count": 0, "Time": pd.Timestamp.now()}
                )
            df = pd.DataFrame(chart_data)

        # Create color mapping for standby runner states
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

        chart.render_chart_with_fallback(
            create_chart,
            "No standby runners data available yet. The chart will appear once data is collected.",
            "Error rendering standby runners chart",
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering standby runners chart: {e}")
        st.error(f"Error rendering standby runners chart: {e}")


def render_standby_runners_details():
    """Render the standby runners details as a dataframe."""
    try:
        # Get standby runners summary
        standby_runners_summary = metrics.get_standby_runners_summary()
        standby_runners_info = standby_runners_summary["details"]
        total_standby = standby_runners_summary["total"]

        # Prepare standby runner data for dataframe
        formatted_standby_runners = []
        for runner in standby_runners_info:
            runner_id = runner.get("runner_id")
            runner_name = runner.get("name")

            # Get runner labels
            runner_labels_info = metrics.get_metric_info(
                "github_hetzner_runners_runner_labels"
            )
            runner_labels_list = []
            for label_dict in runner_labels_info:
                if (
                    label_dict.get("runner_id") == runner_id
                    and label_dict.get("runner_name") == runner_name
                    and "label" in label_dict
                ):
                    runner_labels_list.append(label_dict["label"])

            # Create formatted standby runner data
            formatted_runner = {
                "name": runner.get("name", "Unknown"),
                "status": runner.get("status", "unknown"),
                "runner_id": runner.get("runner_id", ""),
                "os": runner.get("os", ""),
                "repository": runner.get("repository", ""),
                "labels": ", ".join(runner_labels_list) if runner_labels_list else "",
                "busy": (
                    "Busy" if runner.get("busy", "false").lower() == "true" else "Idle"
                ),
                "link": (
                    f"https://github.com/{runner.get('repository', '')}/settings/actions/runners/{runner.get('runner_id', '')}"
                    if runner.get("repository") and runner.get("runner_id")
                    else ""
                ),
            }

            # Add any additional fields from the original runner data
            for key, value in runner.items():
                if key not in formatted_runner and value:
                    formatted_runner[key] = str(value)

            formatted_standby_runners.append(formatted_runner)

        # Always render the dataframe, even if empty
        render_utils.render_details_dataframe(
            items=formatted_standby_runners,
            title="Standby Runner Details",
            name_key="name",
            status_key="status",
            link_keys=["link"],
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering standby runners details: {e}")
        st.error(f"Error rendering standby runners details: {e}")


def render(config=None):
    """Render the standby panel in Streamlit.

    This function creates a Streamlit-compatible version of the standby panel
    that maintains all the functionality of the original dashboard panel.
    """
    # Add pool configuration section at the top
    render_standby_pool_info(config)

    render_utils.render_panel_with_fragments(
        title="Servers",
        metrics_func=render_standby_metrics,
        chart_func=render_standby_chart,
        details_func=render_standby_details,
        error_message="Error rendering standby panel",
    )

    # Group standby runners metrics, chart and details together
    render_utils.render_panel_with_fragments(
        title="Runners",
        metrics_func=render_standby_runners_info,
        chart_func=render_standby_runners_chart,
        details_func=render_standby_runners_details,
        error_message="Error rendering standby runners panel",
    )
