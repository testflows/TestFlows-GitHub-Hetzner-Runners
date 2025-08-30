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
from ..colors import STREAMLIT_COLORS, STATE_COLORS
from .utils import chart, render as render_utils, data


def create_panel():
    """Create runners panel.

    This function maintains API compatibility with the original dashboard.

    Returns:
        dict: Panel configuration dictionary
    """
    return {"title": "Runners", "type": "runners"}


def get_runners_history_data(cutoff_minutes=15):
    """Get runners history data for plotting.

    Args:
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        dict: Dictionary with runner status history data
    """
    # Get online/offline runners history
    states = ["online", "offline"]
    runners_history = data.get_metric_history_for_states(
        "github_hetzner_runners_runners_total", states, cutoff_minutes=cutoff_minutes
    )

    # Get busy runners history
    busy_timestamps, busy_values = data.get_simple_metric_history(
        "github_hetzner_runners_runners_busy", cutoff_minutes=cutoff_minutes
    )

    # Add busy runners to the history data
    if busy_timestamps and busy_values:
        runners_history["github_hetzner_runners_runners_busy"] = {
            "timestamps": busy_timestamps,
            "values": busy_values,
        }

    return runners_history


def create_runners_dataframe(history_data):
    """Create a pandas DataFrame for the runners data with proper time formatting."""
    if not history_data:
        return pd.DataFrame({"Time": pd.to_datetime([]), "Status": [], "Count": []})

    # Map metric names to status names
    metric_to_status = {
        "github_hetzner_runners_runners_total": "online",  # This will be overridden by the actual status
        "github_hetzner_runners_runners_busy": "busy",
    }

    # Collect all data points
    all_data = []

    for metric_name, data in history_data.items():
        if metric_name == "github_hetzner_runners_runners_busy":
            status = "busy"
        else:
            # For the runners_total metric, we need to check the status label
            continue  # Skip this as it's handled by create_dataframe_from_history

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

    # Get the online/offline data using the existing function
    df_online_offline = chart.create_dataframe_from_history(
        {
            k: v
            for k, v in history_data.items()
            if k != "github_hetzner_runners_runners_busy"
        }
    )

    # Create DataFrame for busy runners
    if all_data:
        df_busy = pd.DataFrame(all_data)
        # Combine the dataframes
        df = pd.concat([df_online_offline, df_busy], ignore_index=True)
        df = df.sort_values("Time")
    else:
        df = df_online_offline

    return df


def get_current_runners_data():
    """Get current runners data without caching to ensure fresh data."""
    states = ["online", "offline"]
    current_values, current_time = data.get_current_metric_values(
        "github_hetzner_runners_runners_total", states
    )

    # Get history data for plotting
    history_data = get_runners_history_data()

    return history_data, current_values, current_time


@st.fragment(run_every=st.session_state.update_interval)
def render_runners_metrics():
    """Render the runners metrics header in an isolated fragment for optimal performance."""
    try:
        # Get current runners summary
        runners_summary = metrics.get_runners_summary()

        # Get busy runners count
        busy_runners = (
            metrics.get_metric_value("github_hetzner_runners_runners_busy") or 0
        )

        # Build metrics data
        metrics_data = [
            {"label": "Total Runners", "value": runners_summary["total"]},
            {
                "label": "Online Runners",
                "value": runners_summary["by_status"].get("online", 0),
            },
            {
                "label": "Offline Runners",
                "value": runners_summary["by_status"].get("offline", 0),
            },
            {"label": "Busy Runners", "value": int(busy_runners)},
        ]

        render_utils.render_metrics_columns(metrics_data)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering runners metrics: {e}")
        st.error(f"Error rendering runners metrics: {e}")


@st.fragment(run_every=st.session_state.update_interval)
def render_runners_chart():
    """Render the runners chart using Altair for proper multi-line visualization."""
    try:
        # Get fresh data
        history_data, current_values, current_time = get_current_runners_data()

        # Create DataFrame for the chart
        df = create_runners_dataframe(history_data)

        # Create color mapping for runner states
        color_domain = ["online", "offline", "busy"]
        color_range = [
            STREAMLIT_COLORS["success"],  # Green for online
            STREAMLIT_COLORS["error"],  # Red for offline
            STREAMLIT_COLORS["warning"],  # Orange for busy
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

        chart.render_chart_with_fallback(
            create_chart,
            "No runners data available yet. The chart will appear once data is collected.",
            "Error rendering runners chart",
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering runners chart: {e}")
        st.error(f"Error rendering runners chart: {e}")


@st.fragment(run_every=st.session_state.update_interval)
def render_runners_details():
    """Render the runners details as a dataframe."""
    try:
        # Get runner information using the same approach as metrics
        runners_summary = metrics.get_runners_summary()
        runners_info = runners_summary["details"]
        total_runners = runners_summary["total"]

        if not runners_info:
            if total_runners > 0:
                st.info(f"Total runners: {total_runners} (details not available)")
            else:
                st.info("No runners found")
            return

        # Prepare runner data for dataframe with all relevant fields
        formatted_runners = []
        for runner in runners_info:
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

            # Create formatted runner data with all fields
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

            formatted_runners.append(formatted_runner)

        render_utils.render_details_dataframe(
            items=formatted_runners,
            title="Runner Details",
            name_key="name",
            status_key="status",
            link_keys=["link"],
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering runners details: {e}")
        st.error(f"Error rendering runners details: {e}")


def render():
    """Render the runners panel in Streamlit.

    This function creates a Streamlit-compatible version of the runners panel
    that maintains all the functionality of the original dashboard panel.
    """
    render_utils.render_panel_with_fragments(
        title="Runners",
        metrics_func=render_runners_metrics,
        chart_func=render_runners_chart,
        details_func=render_runners_details,
        error_message="Error rendering runners panel",
    )


def render_graph_only():
    """Render only the runners graph without header and metrics.

    This is useful for embedding the runners graph in other panels or layouts.
    """
    render_runners_chart()
