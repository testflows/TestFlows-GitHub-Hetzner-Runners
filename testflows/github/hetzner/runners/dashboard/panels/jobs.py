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

from .. import metrics
from ..colors import STREAMLIT_COLORS
from .utils import chart, renderers


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


def render_jobs_chart():
    """Render the jobs chart."""

    # Get jobs history and create dataframe
    states_history = metrics.jobs.jobs_history()
    df = metrics.history.dataframe_for_states(states_history)

    # Create color mapping for job states
    color_domain = ["running", "queued"]
    color_range = [
        STREAMLIT_COLORS["success"],  # Green for running
        STREAMLIT_COLORS["warning"],  # Orange for queued
    ]

    def create_chart():
        return chart.create_time_series_chart(
            df=df,
            y_title="Number of Jobs",
            color_column="Status",
            color_domain=color_domain,
            color_range=color_range,
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
