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
import pandas as pd
import streamlit as st


def create_time_series_chart(
    chart_id,
    df,
    group_by,
    x_column="Time",
    y_column="Count",
    title="Time Series Chart",
    y_title=None,
    names=None,
    colors=None,
    height=300,
    time_window_minutes=15,
    y_type="count",
):
    """Create a standardized time series chart using Altair.

    Args:
        chart_id: Unique identifier for the chart (required for state management)
        df: Pandas DataFrame with time series data
        x_column: Column name for x-axis (time) or index name if time is in index
        y_column: Column name for y-axis (values)
        group_by: Column name for grouping data into multiple series (required)
        title: Chart title (defaults to "Time Series Chart")
        y_title: Y-axis title (defaults to y_column)
        names: List of series names in the column (optional)
        colors: List of colors for each series name (optional)
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

    # Chart will be created later based on filtered data

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

    # Initialize legend visibility state - ensure all series start as visible
    if f"{chart_id}_legend_visibility" not in st.session_state:
        st.session_state[f"{chart_id}_legend_visibility"] = {}

    # Initialize all names as visible if not already set
    if names:
        for name in names:
            if name not in st.session_state[f"{chart_id}_legend_visibility"]:
                st.session_state[f"{chart_id}_legend_visibility"][name] = True

    # Create series visibility controls
    create_series_selector(names, chart_id)

    # Filter data based on series visibility
    visible_names = [
        name
        for name, visible in st.session_state[f"{chart_id}_legend_visibility"].items()
        if visible
    ]

    if names and visible_names:
        filtered_df = window_df[window_df[group_by].isin(visible_names)].copy()
    elif names and not visible_names:
        filtered_df = window_df.iloc[:0].copy()  # Empty chart if no names visible
    else:
        filtered_df = window_df  # No series names, show all data

    # Build chart encoding
    chart_encoding = {
        "x": x_encoding,
        "y": y_encoding,
        "tooltip": tooltip,
    }

    # Add color encoding if we have multiple series
    if names:
        color_encoding = alt.Color(
            f"{group_by}:N", scale=alt.Scale(domain=names, range=colors)
        )
        chart_encoding["color"] = color_encoding
        tooltip.append(alt.Tooltip(f"{group_by}:N", title=group_by.title()))

    # Create chart once
    chart = alt.Chart(filtered_df).mark_line().encode(**chart_encoding)

    # Configure chart with no zoom/pan interactions
    final_chart = (
        chart.configure_axis(grid=True, gridColor="lightgray", gridOpacity=0.5)
        .properties(
            width="container",
            height=height,
        )
        .resolve_scale(color="independent")
    )

    return final_chart


def create_series_selector(names, chart_id):
    """Create series visibility selector checkboxes."""

    # Only create selector if we have more than one name to select
    if len(names) < 1:
        return

    # Create horizontal container with series selector checkboxes
    with st.container(
        border=False, horizontal=True, gap="small", horizontal_alignment="right"
    ):

        for name in names:
            # Check current visibility state
            is_visible = st.session_state[f"{chart_id}_legend_visibility"].get(
                name, True
            )

            checkbox_key = f"{chart_id}_legend_{name}"

            new_state = st.checkbox(
                name[0].capitalize() + name[1:],
                value=is_visible,
                key=checkbox_key,
                width="content",
            )

            # Update session state if changed
            if new_state != is_visible:
                st.session_state[f"{chart_id}_legend_visibility"][name] = new_state
                st.rerun()
