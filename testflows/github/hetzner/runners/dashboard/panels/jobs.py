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


@st.fragment
def render_jobs_chart():
    """Render the jobs chart with optional label set filtering."""

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

    def create_chart():
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
        create_chart,
        "No jobs data available yet. The chart will appear once data is collected.",
        "rendering jobs chart",
    )


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
