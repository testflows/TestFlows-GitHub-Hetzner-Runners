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
from .utils import chart, render as render_utils, data


def create_panel():
    """Create cost panel.

    This function maintains API compatibility with the original dashboard.

    Returns:
        dict: Panel configuration dictionary
    """
    return {"title": "Cost", "type": "cost"}


def get_cost_history_data(cutoff_minutes=15):
    """Get cost history data for plotting.

    Args:
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        tuple: (timestamps, values) for plotting
    """
    return data.get_simple_metric_history(
        "github_hetzner_runners_cost_total", cutoff_minutes=cutoff_minutes
    )


def create_cost_dataframe(timestamps, values):
    """Create a pandas DataFrame for the cost data with proper time formatting."""
    if not timestamps or not values:
        # Return empty DataFrame with proper structure
        return pd.DataFrame({"Time": pd.to_datetime([]), "Total Cost (€/h)": []})

    # Ensure we have valid data
    if len(timestamps) != len(values):
        return pd.DataFrame({"Time": pd.to_datetime([]), "Total Cost (€/h)": []})

    # Create DataFrame from the data with proper time formatting
    df = pd.DataFrame(
        {
            "Time": pd.to_datetime(timestamps),
            "Total Cost (€/h)": [float(v) for v in values],  # Ensure values are floats
        }
    )

    # Remove any NaN values
    df = df.dropna()

    # Convert time to proper datetime and set as index
    df["Time"] = pd.to_datetime(df["Time"])
    df.set_index("Time", inplace=True)

    # Sort by time to ensure proper line chart
    df = df.sort_index()

    return df


def get_current_cost_data():
    """Get current cost data without caching to ensure fresh data."""
    current_time = datetime.now()
    current_value = 0

    # Get all server info metrics (exact same logic as original)
    servers_info = metrics.get_metric_info("github_hetzner_runners_server")

    if servers_info:
        for info in servers_info:
            try:
                # Get cost per hour from server info
                cost_hourly = float(info.get("cost_hourly", 0))
                current_value += cost_hourly
            except (ValueError, TypeError):
                continue

    # Update metric history (same as original)
    data.update_simple_metric_history(
        "github_hetzner_runners_cost_total",
        current_value,
        current_time,
        cutoff_minutes=15,
    )

    # Get history data for plotting
    timestamps, values = get_cost_history_data()

    return timestamps, values, current_value, current_time


# Removed update_cost_data function - no longer needed with st.line_chart


@st.fragment(run_every=st.session_state.update_interval)
def render_cost_metrics():
    """Render the cost metrics header in an isolated fragment for optimal performance.

    This fragment updates independently from the main dashboard using the same
    refresh interval selected by the user in the header dropdown.
    """
    try:
        # Get current cost summary for display
        cost_summary = metrics.get_cost_summary()

        # Build metrics data
        metrics_data = [
            {
                "label": "Current Hourly Cost",
                "value": f"€{cost_summary['hourly']:.3f}/h",
            },
            {
                "label": "Daily Cost Estimate",
                "value": f"€{cost_summary['daily']:.2f}/day",
            },
            {
                "label": "Monthly Cost Estimate",
                "value": f"€{cost_summary['monthly']:.2f}/month",
            },
        ]

        render_utils.render_metrics_columns(metrics_data)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering cost metrics: {e}")
        st.error(f"Error rendering cost metrics: {e}")


@st.fragment(run_every=st.session_state.update_interval)
def render_cost_chart():
    """Render the cost chart using Altair for proper time series visualization."""
    try:
        # Get fresh data
        timestamps, values, current_value, current_time = get_current_cost_data()

        # Create DataFrame for the chart
        df = create_cost_dataframe(timestamps, values)

        def create_chart():
            return chart.create_time_series_chart(
                df=df,
                y_column="Total Cost (€/h)",
                y_title="Cost (€/h)",
                y_type="price",
            )

        chart.render_chart_with_fallback(
            create_chart,
            "No cost data available yet. The chart will appear once data is collected.",
            "Error rendering cost chart",
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering cost chart: {e}")
        st.error(f"Error rendering cost chart: {e}")


def render():
    """Render the cost panel in Streamlit.

    This function creates a Streamlit-compatible version of the cost panel
    that maintains all the functionality of the original dashboard panel.
    """
    render_utils.render_panel_with_fragments(
        title="Cost",
        metrics_func=render_cost_metrics,
        chart_func=render_cost_chart,
        error_message="Error rendering cost panel",
    )


def render_graph_only():
    """Render only the cost graph without header and metrics.

    This is useful for embedding the cost graph in other panels or layouts.
    """
    render_cost_chart()
