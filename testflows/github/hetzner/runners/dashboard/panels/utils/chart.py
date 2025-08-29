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

"""Common chart creation utilities for dashboard panels."""

import altair as alt
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging


def create_time_series_chart(
    df,
    x_column="Time",
    y_column="Count",
    color_column=None,
    title="Time Series Chart",
    y_title=None,
    color_domain=None,
    color_range=None,
    height=300,
    time_window_minutes=15,
    y_type="count",
):
    """Create a standardized time series chart using Altair.

    Args:
        df: Pandas DataFrame with time series data
        x_column: Column name for x-axis (time) or index name if time is in index
        y_column: Column name for y-axis (values)
        color_column: Column name for color encoding (optional)
        title: Chart title
        y_title: Y-axis title (defaults to y_column)
        color_domain: List of color domain values
        color_range: List of color range values
        height: Chart height in pixels
        time_window_minutes: Time window to display in minutes
        y_type: Type of y-axis data ("count" for integers, "price" for floats)

    Returns:
        alt.Chart: Configured Altair chart
    """
    if df.empty:
        return None

    # Handle case where time is in the index
    if x_column in df.index.names or (df.index.name == x_column):
        # Reset index to make time a column
        df = df.reset_index()

    # Create proper time window
    # Check if DataFrame has timezone-aware timestamps
    if not df.empty and df[x_column].dt.tz is not None:
        current_time = pd.Timestamp.now(tz=df[x_column].dt.tz)
    else:
        current_time = pd.Timestamp.now()

    time_window_start = current_time - pd.Timedelta(minutes=time_window_minutes)

    # Filter data to time window
    window_df = df[df[x_column] >= time_window_start].copy()

    if window_df.empty:
        return None

    # Calculate dynamic y-axis range based on data type
    max_value = window_df[y_column].max()
    if y_type == "price":
        y_max = max(max_value * 1.1, 0.01)  # At least 0.01 for price visibility
    else:  # count
        y_max = max(max_value * 1.1, 1)  # At least 1 for count visibility

    # Base chart configuration
    chart = alt.Chart(window_df).mark_line()

    # X-axis encoding
    x_encoding = alt.X(
        f"{x_column}:T",
        title="Time",
        axis=alt.Axis(format="%H:%M", tickCount=15),
        scale=alt.Scale(domain=[time_window_start, current_time]),
    )

    # Y-axis encoding
    if y_type == "price":
        y_encoding = alt.Y(
            f"{y_column}:Q",
            title=y_title or y_column,
            scale=alt.Scale(domain=[0, y_max]),
            axis=alt.Axis(format=".3f", tickCount=6),
        )
    else:  # count

        y_encoding = alt.Y(
            f"{y_column}:Q",
            title=y_title or y_column,
            scale=alt.Scale(domain=[0, y_max]),
            axis=alt.Axis(
                values=list(range(0, int(y_max) + 1)), format="d", tickCount=6
            ),
        )

    # Tooltip configuration
    tooltip = [
        alt.Tooltip(f"{x_column}:T", title="Time", format="%H:%M:%S"),
        alt.Tooltip(
            f"{y_column}:Q",
            title=y_title or y_column,
            format=".3f" if y_type == "price" else "d",
        ),
    ]

    # Add color encoding if specified
    if color_column and color_domain and color_range:
        color_encoding = alt.Color(
            f"{color_column}:N",
            scale=alt.Scale(domain=color_domain, range=color_range),
            legend=alt.Legend(title=f"{color_column.title()}"),
        )
        tooltip.append(alt.Tooltip(f"{color_column}:N", title=color_column.title()))

        chart = chart.encode(
            x=x_encoding,
            y=y_encoding,
            color=color_encoding,
            tooltip=tooltip,
        )
    else:
        chart = chart.encode(
            x=x_encoding,
            y=y_encoding,
            tooltip=tooltip,
        )

    # Configure and return chart
    return chart.configure_axis(
        grid=True, gridColor="lightgray", gridOpacity=0.5
    ).properties(
        width="container",
        height=height,
    )


def render_chart_with_fallback(
    chart_func,
    no_data_message="No data available yet. The chart will appear once data is collected.",
    error_message="Error rendering chart",
):
    """Render a chart with standardized error handling and fallback messages.

    Args:
        chart_func: Function that returns an Altair chart
        no_data_message: Message to show when no data is available
        error_message: Base error message for exceptions
    """
    try:
        chart = chart_func()

        if chart is not None:
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info(no_data_message)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"{error_message}: {e}")
        st.error(f"{error_message}: {e}")


def create_dataframe_from_history(
    history_data, time_column="Time", value_column="Count", status_column="Status"
):
    """Create a standardized DataFrame from history data.

    Args:
        history_data: Dictionary with history data
        time_column: Name for the time column
        value_column: Name for the value column
        status_column: Name for the status column (if applicable)

    Returns:
        pd.DataFrame: Formatted DataFrame
    """
    if not history_data:
        return pd.DataFrame(
            {time_column: pd.to_datetime([]), value_column: [], status_column: []}
        )

    all_data = []

    for status, data in history_data.items():
        timestamps = data.get("timestamps", [])
        values = data.get("values", [])

        if timestamps and values and len(timestamps) == len(values):
            for ts, val in zip(timestamps, values):
                try:
                    data_point = {
                        time_column: pd.to_datetime(ts),
                        value_column: int(val),
                    }
                    if status_column:
                        data_point[status_column] = status
                    all_data.append(data_point)
                except (ValueError, TypeError):
                    continue

    if not all_data:
        return pd.DataFrame(
            {time_column: pd.to_datetime([]), value_column: [], status_column: []}
        )

    df = pd.DataFrame(all_data)
    return df.sort_values(time_column)
