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
from .utils import format_duration


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
    history_data = {}

    for status in states:
        timestamps, values = metrics.get_metric_history_data(
            "github_hetzner_runners_servers_total",
            {"status": status},
            cutoff_minutes=cutoff_minutes,
        )
        history_data[status] = {"timestamps": timestamps, "values": values}

    return history_data


def create_server_dataframe(history_data):
    """Create a pandas DataFrame for the server data with proper time formatting."""
    if not history_data:
        return pd.DataFrame({"Time": pd.to_datetime([]), "Status": [], "Count": []})

    # Collect all data points
    all_data = []

    for status, data in history_data.items():
        timestamps = data.get("timestamps", [])
        values = data.get("values", [])

        if timestamps and values and len(timestamps) == len(values):
            for ts, val in zip(timestamps, values):
                try:
                    all_data.append(
                        {
                            "Time": pd.to_datetime(ts),
                            "Status": status,
                            "Count": int(val),
                        }
                    )
                except (ValueError, TypeError):
                    continue

    if not all_data:
        return pd.DataFrame({"Time": pd.to_datetime([]), "Status": [], "Count": []})

    # Create DataFrame and sort by time
    df = pd.DataFrame(all_data)
    df = df.sort_values("Time")

    return df


def get_current_server_data():
    """Get current server data without caching to ensure fresh data."""
    current_time = datetime.now()
    states = ["running", "off", "initializing", "ready", "busy"]
    current_values = {}

    # Get current values for each state
    for status in states:
        value = (
            metrics.get_metric_value(
                "github_hetzner_runners_servers_total", {"status": status}
            )
            or 0
        )
        current_values[status] = value

        # Update metric history
        metrics.update_metric_history(
            "github_hetzner_runners_servers_total",
            {"status": status},
            value,
            current_time,
            cutoff_minutes=15,
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

        # Display current server metrics in columns
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="Total Servers",
                value=servers_summary["total"],
            )

        with col2:
            # Count running servers
            running_count = servers_summary["by_status"].get("running", 0)
            st.metric(
                label="Running Servers",
                value=running_count,
            )

        with col3:
            # Count servers in other states
            other_states = sum(
                count
                for status, count in servers_summary["by_status"].items()
                if status != "running"
            )
            st.metric(
                label="Other States",
                value=other_states,
            )

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

        # Display the chart using Altair for multi-line visualization
        if not df.empty:
            # Create proper time window (last 15 minutes)
            current_time = pd.Timestamp.now()
            time_window_start = current_time - pd.Timedelta(minutes=15)

            # Filter data to time window
            window_df = df[df["Time"] >= time_window_start].copy()

            if not window_df.empty:
                # Calculate dynamic y-axis range and tick count
                max_count = window_df["Count"].max()
                y_max = max(max_count * 1.1, 1)  # At least 1 for visibility

                # Create color mapping for server states
                color_domain = ["running", "off", "initializing", "ready", "busy"]
                color_range = [
                    STATE_COLORS["running"],
                    STATE_COLORS["off"],
                    STATE_COLORS["initializing"],
                    STATE_COLORS["ready"],
                    STATE_COLORS["busy"],
                ]

                # Create chart with proper time window and dynamic count range
                chart = (
                    alt.Chart(window_df)
                    .mark_line()
                    .encode(
                        x=alt.X(
                            "Time:T",
                            title="Time",
                            axis=alt.Axis(format="%H:%M", tickCount=15),
                            scale=alt.Scale(domain=[time_window_start, current_time]),
                        ),
                        y=alt.Y(
                            "Count:Q",
                            title="Number of Servers",
                            scale=alt.Scale(domain=[0, y_max]),
                            axis=alt.Axis(
                                values=list(range(0, int(y_max) + 1)), format="d"
                            ),
                        ),
                        color=alt.Color(
                            "Status:N",
                            scale=alt.Scale(domain=color_domain, range=color_range),
                            legend=alt.Legend(title="Server Status"),
                        ),
                        tooltip=[
                            alt.Tooltip("Time:T", title="Time", format="%H:%M:%S"),
                            alt.Tooltip("Status:N", title="Status"),
                            alt.Tooltip("Count:Q", title="Count"),
                        ],
                    )
                    .configure_axis(grid=True, gridColor="lightgray", gridOpacity=0.5)
                    .properties(
                        width="container",
                        height=300,
                    )
                )

                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No server data available in the current time window.")

        else:
            # Show placeholder when no data
            st.info(
                "No server data available yet. The chart will appear once data is collected."
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

        # Display server details
        st.subheader("Server Details")

        for info in servers_info:
            try:
                server_id = info.get("server_id")
                server_name = info.get("name")
                if not server_id or not server_name:
                    continue

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

                status = info.get("status", "unknown")
                status_color = STATE_COLORS.get(status, STATE_COLORS["unknown"])

                # Create expander for each server
                with st.expander(f"Server: {server_name} ({status})", expanded=False):
                    # Build all content as a single markdown string to avoid spacing issues
                    content_lines = []

                    # Add server details
                    content_lines.append(f"**Type:** {info.get('type', 'Unknown')}")
                    content_lines.append(
                        f"**Location:** {info.get('location', 'Unknown')}"
                    )
                    content_lines.append(f"**IPv4:** {info.get('ipv4', 'Unknown')}")
                    content_lines.append(
                        f"**Created:** {info.get('created', 'Unknown')}"
                    )
                    content_lines.append(f"**IPv6:** {info.get('ipv6', 'Unknown')}")
                    content_lines.append(
                        f"**Runner Status:** {info.get('runner_status', 'Unknown')}"
                    )
                    content_lines.append(
                        f"**Labels:** {', '.join(server_labels_list) or 'None'}"
                    )

                    # Add cost information if available
                    if info.get("cost_hourly"):
                        cost_text = (
                            f"{info['cost_hourly']} {info['cost_currency']}/hour"
                        )
                        if info.get("cost_total"):
                            cost_text += f" (total: {info['cost_total']} {info['cost_currency']})"
                        content_lines.append(f"**Cost:** {cost_text}")

                    # Render all content in a single markdown call
                    st.markdown("  \n".join(content_lines))

            except (ValueError, KeyError, AttributeError) as e:
                logging.exception(f"Error processing server info: {info}")
                continue

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering server details: {e}")
        st.error(f"Error rendering server details: {e}")


def render():
    """Render the servers panel in Streamlit.

    This function creates a Streamlit-compatible version of the servers panel
    that maintains all the functionality of the original dashboard panel.
    """
    logger = logging.getLogger(__name__)

    try:
        with st.container(border=True):
            st.header("Servers")

            # Render the server metrics header with stable updates
            render_server_metrics()

            # Render the server chart with stable updates
            render_server_chart()

            # Render server details
            render_server_details()

    except Exception as e:
        logger.exception(f"Error rendering servers panel: {e}")
        st.error(f"Error rendering servers panel: {e}")


def render_graph_only():
    """Render only the servers graph without header and metrics.

    This is useful for embedding the servers graph in other panels or layouts.
    """
    render_server_chart()
