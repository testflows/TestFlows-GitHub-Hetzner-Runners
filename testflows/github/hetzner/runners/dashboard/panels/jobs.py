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
from ..colors import STREAMLIT_COLORS
from .. import chart, renderers


def render_jobs_metrics():
    """Render the jobs metrics header."""

    # Get current jobs summary
    jobs_summary = metrics.jobs.summary()

    # Build metrics data
    metrics_data = [
        {"label": "Total", "value": jobs_summary["total"]},
        {"label": "Running", "value": jobs_summary["running"]},
        {"label": "Queued", "value": jobs_summary["queued"]},
    ]

    renderers.render_metrics_columns(metrics_data)


def render_job_counts_chart(selected_label_sets):
    """Render job counts chart."""
    # Get jobs history filtered by selected label sets
    states_history = metrics.jobs.jobs_history_filtered_by_label_sets(
        selected_label_sets=selected_label_sets if selected_label_sets else None
    )
    df = metrics.history.dataframe_for_states(states_history)

    # Create color mapping for job states
    color_domain = ["running", "queued"]
    color_range = [
        STREAMLIT_COLORS["success"],  # Green for running
        STREAMLIT_COLORS["warning"],  # Orange for queued
    ]

    def create_jobs_count_chart():
        return chart.create_time_series_chart(
            chart_id="jobs",
            df=df,
            group_by="Status",
            y_title="Number of Jobs",
            names=color_domain,
            colors=color_range,
            y_type="count",
        )

    renderers.render_chart(
        create_jobs_count_chart,
        "No jobs data available yet. The chart will appear once data is collected.",
        "rendering jobs chart",
    )


def render_wait_times_chart(selected_label_sets):
    """Render job wait times chart."""
    # Get timing history filtered by selected label sets
    timing_data = metrics.jobs.job_times_history_filtered_by_label_sets(
        time_type="wait",
        selected_label_sets=selected_label_sets if selected_label_sets else None,
    )

    df = metrics.history.dataframe_for_timing(
        timing_data, value_column="Wait Time (seconds)"
    )

    def create_wait_times_chart():
        return chart.create_time_series_chart(
            chart_id="job_wait_times",
            df=df,
            group_by=None,  # Single series
            y_column="Wait Time (seconds)",
            y_title="Average Wait Time (seconds)",
            names=[],
            colors=None,
            y_type="count",
        )

    renderers.render_chart(
        create_wait_times_chart,
        "No wait time data available yet.",
        "rendering job wait times chart",
    )


def render_run_times_chart(selected_label_sets):
    """Render job run times chart."""
    # Get timing history filtered by selected label sets
    timing_data = metrics.jobs.job_times_history_filtered_by_label_sets(
        time_type="run",
        selected_label_sets=selected_label_sets if selected_label_sets else None,
    )

    df = metrics.history.dataframe_for_timing(
        timing_data, value_column="Run Time (seconds)"
    )

    def create_run_times_chart():
        return chart.create_time_series_chart(
            chart_id="job_run_times",
            df=df,
            group_by=None,  # Single series
            y_column="Run Time (seconds)",
            y_title="Average Run Time (seconds)",
            names=[],
            colors=None,
            y_type="count",
        )

    renderers.render_chart(
        create_run_times_chart,
        "No run time data available yet.",
        "rendering job run times chart",
    )


@st.fragment
def render_jobs_chart():
    """Render all job charts with optional label set filtering."""

    # Get all unique label sets from historical data for filtering
    all_label_sets = metrics.jobs.get_all_historical_label_sets()

    # Convert to list and format for display
    label_set_options = []
    label_set_map = {}
    for label_set in sorted(all_label_sets):
        display_name = ", ".join(label_set)
        label_set_options.append(display_name)
        label_set_map[display_name] = list(label_set)

    # Add label set filter selector
    selected_label_sets = None
    if label_set_options:
        selected_display_names = st.multiselect(
            "Filter by labels (leave empty to show all):",
            label_set_options,
            default=[],
            key="jobs_chart_labels_filter",
        )

        if selected_display_names:
            selected_label_sets = [
                label_set_map[name] for name in selected_display_names
            ]

    # Create tabs for different charts
    tab1, tab2, tab3 = st.tabs(["Job Counts", "Wait Times", "Run Times"])

    with tab1:
        render_job_counts_chart(selected_label_sets)

    with tab2:
        render_wait_times_chart(selected_label_sets)

    with tab3:
        render_run_times_chart(selected_label_sets)


def render_jobs_details():
    """Render the jobs details as a dataframe."""

    # Get formatted job details
    formatted_jobs = metrics.jobs.formatted_details()

    renderers.render_details_dataframe(
        items=formatted_jobs,
        title="Job Details",
        name_key="name",
        status_key="status",
        link_keys=["job", "run", "repository"],
    )


def render():
    """Render the jobs panel."""
    renderers.render_panel(
        title="Jobs",
        metrics_func=render_jobs_metrics,
        chart_func=render_jobs_chart,
        details_func=render_jobs_details,
        message="rendering jobs panel",
    )
