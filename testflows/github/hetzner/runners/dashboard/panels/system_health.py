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

from .. import metrics
from .utils import renderers, chart
from ..colors import STREAMLIT_COLORS


def render_system_health_metrics():
    """Render the system health metrics header."""
    # Get current system health data
    health_data = metrics.system_health.summary()

    # Build metrics data
    metrics_data = [
        {
            "label": "System CPU",
            "value": f"{health_data['system']['cpu_percent']:.1f}%",
        },
        {
            "label": "System Memory",
            "value": f"{health_data['system']['memory_percent']:.1f}%",
        },
        {
            "label": "Process CPU",
            "value": f"{health_data['process']['cpu_percent']:.1f}%",
        },
        {
            "label": "Process Memory",
            "value": f"{health_data['process']['memory_percent']:.1f}%",
        },
        {
            "label": "Root Disk",
            "value": f"{health_data['disk']['root_percent']:.1f}%",
        },
        {"label": "Load (1m)", "value": f"{health_data['system']['load_1m']:.2f}"},
    ]

    renderers.render_metrics_columns(metrics_data)

    # Display network info
    hostname, network_df = metrics.system_health.network_info()

    st.write(f"**Hostname:** {hostname}")
    st.write("**Network Interfaces:**")

    st.dataframe(
        network_df,
        hide_index=True,
        use_container_width=False,
        column_config={
            "Type": st.column_config.TextColumn("Type", width="small"),
            "Interface": st.column_config.TextColumn("Interface", width="small"),
            "Address": st.column_config.TextColumn("Address", width="medium"),
        },
    )


def render_system_health_chart():
    """Render the system health chart."""
    # Get system health history and create dataframe
    states_history = metrics.system_health.system_health_history()
    df = metrics.history.dataframe_for_states(states_history)

    # Create color mapping for metrics
    color_domain = [
        "System CPU",
        "System Memory",
        "Process CPU",
        "Process Memory",
        "Root Disk",
    ]
    color_range = [
        STREAMLIT_COLORS["primary"],  # Blue for system CPU
        STREAMLIT_COLORS["secondary"],  # Orange for system memory
        STREAMLIT_COLORS["success"],  # Green for process CPU
        STREAMLIT_COLORS["info"],  # Light blue for process memory
        STREAMLIT_COLORS["warning"],  # Yellow for root disk
    ]

    def create_chart():
        return chart.create_time_series_chart(
            df=df,
            y_title="Percentage (%)",
            color_column="Status",
            color_domain=color_domain,
            color_range=color_range,
            y_type="value",
        )

    renderers.render_chart(
        create_chart,
        "No system health data available yet. The chart will appear once data is collected.",
        "rendering system health chart",
    )


def render_system_health_details():
    """Render the system health details as a dataframe."""
    # Get formatted system health details
    formatted_details = metrics.system_health.formatted_details()

    renderers.render_details_dataframe(
        items=formatted_details,
        title="System Health Details",
        name_key="Metric",
        status_key="Category",
    )


def render():
    """Render the system health panel."""
    renderers.render_panel(
        title="System Health",
        metrics_func=render_system_health_metrics,
        chart_func=render_system_health_chart,
        details_func=render_system_health_details,
        message="rendering system health panel",
    )
