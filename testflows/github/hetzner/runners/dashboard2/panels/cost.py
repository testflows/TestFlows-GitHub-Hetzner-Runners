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
    return metrics.get_metric_history_data(
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
    key = metrics.update_metric_history(
        "github_hetzner_runners_cost_total",
        {},
        current_value,
        current_time,
        cutoff_minutes=15,
    )

    # Get history data for plotting
    history_data = metrics.metric_history.get(key, {"timestamps": [], "values": []})
    timestamps = history_data["timestamps"]
    values = history_data["values"]

    return timestamps, values, current_value, current_time


# Removed update_cost_data function - no longer needed with st.line_chart


@st.fragment(run_every=st.session_state.get("update_interval", 5))
def render_cost_chart():
    """Render the cost chart using Streamlit's native line chart to prevent flickering."""
    try:
        # Get fresh data
        timestamps, values, current_value, current_time = get_current_cost_data()

        # Create DataFrame for the chart
        df = create_cost_dataframe(timestamps, values)

        # Display the chart using Streamlit's native line chart with proper x-axis scaling
        if not df.empty:
            # Add custom CSS for better chart styling
            st.markdown(
                """
            <style>
            .stLineChart {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
                background-color: #f8f9fa;
            }
            </style>
            """,
                unsafe_allow_html=True,
            )

            # Use Streamlit's native line chart - much more reliable for real-time data
            # Reset index and ensure proper data types
            chart_df = df.reset_index()
            chart_df["Total Cost (€/h)"] = chart_df["Total Cost (€/h)"].astype(float)
            chart_df = chart_df.dropna()
            chart_df = chart_df.sort_values("Time")

            # Use Altair for proper time window and dynamic price range

            # Create proper time window (last 15 minutes)
            current_time = pd.Timestamp.now()
            time_window_start = current_time - pd.Timedelta(minutes=15)

            # Filter data to time window
            window_df = chart_df[chart_df["Time"] >= time_window_start].copy()

            # Calculate dynamic y-axis range
            if len(window_df) > 0:
                min_cost = min(0, window_df["Total Cost (€/h)"].min())
                max_cost = max(1, window_df["Total Cost (€/h)"].max())
                cost_range = max_cost - min_cost

                # Set y-axis range with padding
                if cost_range == 0:
                    y_min = 0
                    y_max = max(max_cost * 1.1, 0.001)  # At least 0.001 for visibility
                else:
                    y_min = max(0, min_cost - cost_range * 0.1)
                    y_max = max_cost + cost_range * 0.1
            else:
                y_min, y_max = 0, 1

            # Create chart with proper time window and dynamic price range
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
                        "Total Cost (€/h):Q",
                        title="Cost (€/h)",
                        scale=alt.Scale(domain=[y_min, y_max]),
                    ),
                    tooltip=[
                        alt.Tooltip("Time:T", title="Time", format="%H:%M:%S"),
                        alt.Tooltip("Total Cost (€/h):Q", title="Cost", format=".3f"),
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
            # Show placeholder when no data
            st.info(
                "No cost data available yet. The chart will appear once data is collected."
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
    logger = logging.getLogger(__name__)

    try:
        with st.container(border=True):
            st.header("Cost (Last 15 Minutes)")

            # Get current cost summary for display
            cost_summary = metrics.get_cost_summary()

            # Display current cost metrics in columns
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    label="Current Hourly Cost",
                    value=f"€{cost_summary['hourly']:.3f}/h",
                )

            with col2:
                st.metric(
                    label="Daily Cost Estimate",
                    value=f"€{cost_summary['daily']:.2f}/day",
                )

            with col3:
                st.metric(
                    label="Monthly Cost Estimate",
                    value=f"€{cost_summary['monthly']:.2f}/month",
                )

            # Render the cost chart with stable updates
            render_cost_chart()

    except Exception as e:
        logger.exception(f"Error rendering cost panel: {e}")
        st.error(f"Error rendering cost panel: {e}")


def render_graph_only():
    """Render only the cost graph without header and metrics.

    This is useful for embedding the cost graph in other panels or layouts.
    """
    render_cost_chart()
