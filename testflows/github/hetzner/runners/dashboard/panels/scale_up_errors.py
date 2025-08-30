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
import dateutil.parser
import logging

from ..colors import STREAMLIT_COLORS
from .. import metrics
from .utils import chart, render as render_utils, data, format


def create_panel():
    """Create scale-up errors panel.

    This function maintains API compatibility with the original dashboard.

    Returns:
        dict: Panel configuration dictionary
    """
    return {"title": "Scale-up Errors (Last Hour)", "type": "scale_up_errors"}


def get_scale_up_errors_history_data(cutoff_minutes=60):
    """Get scale-up errors history data for plotting.

    Args:
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        dict: Dictionary with error history data
    """
    timestamps, values = metrics.get_metric_history_data(
        "github_hetzner_runners_scale_up_failures_last_hour",
        cutoff_minutes=cutoff_minutes,
    )
    return {"timestamps": timestamps, "values": values}


def get_current_scale_up_errors_data():
    """Get current scale-up errors data without caching to ensure fresh data."""
    current_time = datetime.now()
    current_value = (
        metrics.get_metric_value("github_hetzner_runners_scale_up_failures_last_hour")
        or 0
    )

    # Update metric history for plotting (this tracks the gauge value over time)
    data.update_simple_metric_history(
        "github_hetzner_runners_scale_up_failures_last_hour",
        current_value,
        current_time,
        cutoff_minutes=60,
    )

    # Get history data for plotting
    history_data = get_scale_up_errors_history_data()

    return history_data, current_value, current_time


def get_scale_up_errors_data():
    """Get scale-up errors data for display and plotting.

    Returns:
        tuple: (error_list_data, error_count, history_data)
    """
    # Get error information from metrics
    errors_info = metrics.get_metric_info(
        "github_hetzner_runners_scale_up_failure_last_hour"
    )

    # Get total number of errors from metrics
    total_errors = (
        metrics.get_metric_value("github_hetzner_runners_scale_up_failures_last_hour")
        or 0
    )

    # Create error list data
    error_items = []

    if errors_info:
        # Sort errors_info by timestamp in descending order
        errors_info.sort(
            key=lambda x: dateutil.parser.parse(
                x.get("timestamp_iso", "1970-01-01T00:00:00Z")
            ),
            reverse=True,
        )

        for info in errors_info:
            try:
                error_type = info.get("error_type", "Unknown")
                server_name = info.get("server_name", "Unknown")
                error_message = info.get("error", "Unknown error")
                server_type = info.get("server_type", "Unknown")
                location = info.get("location", "Unknown") or "Unspecified"
                labels = info.get("labels", "").split(",")
                time_str = (
                    dateutil.parser.parse(info.get("timestamp_iso", "")).strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    )
                    if info.get("timestamp_iso")
                    else "Unknown time"
                )

                # Map error types to colors
                error_colors = {
                    "max_servers_reached": STREAMLIT_COLORS["error"],
                    "resource_limit_exceeded": STREAMLIT_COLORS["error"],
                    "api_exception": STREAMLIT_COLORS["error"],
                    "error": STREAMLIT_COLORS["error"],
                }
                error_color = error_colors.get(error_type, STREAMLIT_COLORS["warning"])

                # Create error item
                error_item = {
                    "name": f"Error Type: {error_type}",
                    "server_name": server_name,
                    "color": error_color,
                    "values": [
                        {"label": "Time", "value": time_str},
                        {"label": "Server Type", "value": server_type},
                        {"label": "Location", "value": location},
                        {"label": "Labels", "value": ", ".join(labels) or "None"},
                        {"label": "Error Message", "value": error_message},
                    ],
                }
                error_items.append(error_item)

            except (ValueError, KeyError, AttributeError) as e:
                logging.exception(f"Error processing error info: {info}")
                continue

    # Create error list data structure
    error_list_data = {
        "name": "errors",
        "count": total_errors,
        "items": error_items,
        "title": (
            "Total errors"
            if total_errors > 0
            else "No scale-up errors in the last hour"
        ),
    }

    # Get history data for plotting
    history_data = get_scale_up_errors_history_data()

    return error_list_data, total_errors, history_data


def create_errors_dataframe(history_data):
    """Create a pandas DataFrame for the errors data with proper time formatting."""
    if not history_data or not history_data.get("timestamps"):
        # Return a DataFrame with a single data point at 0 for the current time
        current_time = pd.Timestamp.now()
        return pd.DataFrame({"Time": [current_time], "Count": [0]})

    timestamps = history_data["timestamps"]
    values = history_data["values"]

    if not timestamps or not values or len(timestamps) != len(values):
        # Return a DataFrame with a single data point at 0 for the current time
        current_time = pd.Timestamp.now()
        return pd.DataFrame({"Time": [current_time], "Count": [0]})

    # Collect all data points
    all_data = []

    for ts, val in zip(timestamps, values):
        try:
            all_data.append({"Time": pd.to_datetime(ts), "Count": int(val)})
        except (ValueError, TypeError):
            continue

    if not all_data:
        # Return a DataFrame with a single data point at 0 for the current time
        current_time = pd.Timestamp.now()
        return pd.DataFrame({"Time": [current_time], "Count": [0]})

    # Create DataFrame and sort by time
    df = pd.DataFrame(all_data)
    df = df.sort_values("Time")

    return df


@st.fragment(run_every=st.session_state.update_interval)
def render_scale_up_errors_metrics():
    """Render the scale-up errors metrics section."""
    try:
        # Get data
        _, total_errors, _ = get_scale_up_errors_data()

        # Build metrics data
        metrics_data = [
            {"label": "Total Errors", "value": int(total_errors)},
        ]

        render_utils.render_metrics_columns(metrics_data)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering scale-up errors metrics: {e}")
        st.error(f"Error rendering scale-up errors metrics: {e}")


@st.fragment(run_every=st.session_state.update_interval)
def render_scale_up_errors_chart():
    """Render the scale-up errors chart section."""
    try:
        # Get fresh data
        history_data, current_value, current_time = get_current_scale_up_errors_data()

        # Create DataFrame for the chart
        df = create_errors_dataframe(history_data)

        def create_chart():
            return chart.create_time_series_chart(
                df=df,
                x_column="Time",
                y_column="Count",
                title="Scale-up Errors Over Time",
                y_title="Number of Errors",
                time_window_minutes=60,
                y_type="count",
            )

        chart.render_chart_with_fallback(
            create_chart,
            "No error data available yet. The chart will appear once data is collected.",
            "Error rendering scale-up errors chart",
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering scale-up errors chart: {e}")
        st.error(f"Error rendering scale-up errors chart: {e}")


@st.fragment(run_every=st.session_state.update_interval)
def render_scale_up_errors_details():
    """Render the scale-up errors details section."""
    try:
        # Get data
        error_list_data, total_errors, _ = get_scale_up_errors_data()

        # Display error details
        if error_list_data["items"]:
            # Prepare error data for dataframe
            formatted_errors = []
            for error_item in error_list_data["items"]:
                # Extract values from the error item
                error_data = {}
                for value_item in error_item["values"]:
                    error_data[value_item["label"].lower().replace(" ", "_")] = (
                        value_item["value"]
                    )

                # Create formatted error data
                formatted_error = {
                    "name": error_item["name"],
                    "server_name": error_item["server_name"],
                    "error_message": error_data.get("error_message", ""),
                    "server_type": error_data.get("server_type", ""),
                    "location": error_data.get("location", ""),
                    "labels": error_data.get("labels", ""),
                }

                formatted_errors.append(formatted_error)

            render_utils.render_details_dataframe(
                items=formatted_errors,
                title="Error Details",
                name_key="name",
                status_key="server_name",
            )
        else:
            if total_errors > 0:
                st.info(f"Total errors: {total_errors} (details not available)")
            else:
                st.info("No errors found")

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering scale-up errors details: {e}")
        st.error(f"Error rendering scale-up errors details: {e}")


def render():
    """Render the scale-up errors panel in Streamlit.

    This function creates a Streamlit-compatible version of the scale-up errors panel
    that maintains all the functionality of the original dashboard panel.
    """
    render_utils.render_panel_with_fragments(
        title="Scale-up Errors (Last Hour)",
        metrics_func=render_scale_up_errors_metrics,
        chart_func=render_scale_up_errors_chart,
        details_func=render_scale_up_errors_details,
        error_message="Error rendering scale-up errors panel",
    )


def render_graph_only():
    """Render only the scale-up errors graph without header and metrics.

    This is useful for embedding the scale-up errors graph in other panels or layouts.
    """
    render_scale_up_errors_chart()
