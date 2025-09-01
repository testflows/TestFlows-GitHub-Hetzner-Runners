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
import logging

from .. import metrics
from ..colors import STREAMLIT_COLORS
from .utils import chart, renderers, format
from .utils.metrics import MultipleSimpleMetrics


# Create metric abstraction
jobs_metrics = MultipleSimpleMetrics(
    [
        {"metric_name": "github_hetzner_runners_queued_jobs", "status_name": "queued"},
        {
            "metric_name": "github_hetzner_runners_running_jobs",
            "status_name": "running",
        },
    ]
)


def render_jobs_metrics():
    """Render the jobs metrics header in an isolated fragment for optimal performance."""
    try:
        # Get current jobs summary
        jobs_summary = metrics.jobs.summary()

        # Build metrics data
        metrics_data = [
            {"label": "Total", "value": jobs_summary["total"]},
            {"label": "Running", "value": jobs_summary["running"]},
            {"label": "Queued", "value": jobs_summary["queued"]},
        ]

        renderers.render_metrics_columns(metrics_data)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering jobs metrics: {e}")
        st.error(f"Error rendering jobs metrics: {e}")


def render_jobs_chart():
    """Render the jobs chart using Altair for proper multi-line visualization."""
    try:
        # Get DataFrame using the simple abstraction
        df = jobs_metrics.get_dataframe()

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

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering jobs chart: {e}")
        st.error(f"Error rendering jobs chart: {e}")


def render_jobs_details():
    """Render the jobs details as a dataframe."""
    try:
        # Get job information
        queued_jobs_info = metrics.get.metric_info("github_hetzner_runners_queued_job")
        running_jobs_info = metrics.get.metric_info(
            "github_hetzner_runners_running_job"
        )
        jobs_summary = metrics.jobs.summary()

        # Prepare job data for dataframe
        formatted_jobs = []

        # Process both queued and running jobs
        for jobs_info, is_running in [
            (queued_jobs_info, False),
            (running_jobs_info, True),
        ]:
            if not jobs_info:
                continue

            for info in jobs_info:
                try:
                    job_id = info.get("job_id")
                    run_id = info.get("run_id")
                    if not job_id or not run_id:
                        continue

                    # Get wait/run time for this job
                    metric_name = (
                        "github_hetzner_runners_running_job_time_seconds"
                        if is_running
                        else "github_hetzner_runners_queued_job_wait_time_seconds"
                    )
                    time_value = metrics.get_metric_value(
                        metric_name,
                        {"job_id": job_id, "run_id": run_id},
                    )
                    try:
                        time_str = (
                            format.format_duration(time_value)
                            if time_value is not None
                            else "unknown"
                        )
                    except (ValueError, TypeError):
                        time_str = "unknown"
                    time_label = "Run time" if is_running else "Wait time"

                    # Get labels for this job
                    job_labels_info = metrics.get_metric_info(
                        "github_hetzner_runners_queued_job_labels"
                        if not is_running
                        else "github_hetzner_runners_running_job_labels"
                    )

                    job_labels_list = []
                    for label_dict in job_labels_info:
                        if (
                            label_dict.get("job_id") == job_id
                            and label_dict.get("run_id") == run_id
                            and "label" in label_dict
                        ):
                            job_labels_list.append(label_dict["label"])

                    status_text = "Running" if is_running else "Queued"

                    # Create job links
                    job_url = ""
                    run_url = ""
                    repo_url = ""

                    if info.get("repository"):
                        job_url = f"https://github.com/{info.get('repository', '')}/actions/runs/{info.get('run_id', '')}/job/{info.get('job_id', '')}"
                        run_url = f"https://github.com/{info.get('repository', '')}/actions/runs/{info.get('run_id', '')}"
                        repo_url = f"https://github.com/{info.get('repository', '')}"

                    # Create formatted job data
                    formatted_job = {
                        "name": info.get("name", "Unknown"),
                        "status": status_text,
                        "job_id": f"{info.get('job_id', 'Unknown')} (attempt {info.get('run_attempt', '1')})",
                        "run_id": info.get("run_id", ""),
                        "workflow": info.get("workflow_name", "").strip(),
                        "repository": info.get("repository", "").strip(),
                        "branch": info.get("head_branch", ""),
                        "labels": ", ".join(job_labels_list) if job_labels_list else "",
                        time_label.lower().replace(" ", "_"): time_str,
                        "job_link": job_url,
                        "run_link": run_url,
                        "repo_link": repo_url,
                    }

                    # Add any additional fields from the original job data
                    for key, value in info.items():
                        if key not in formatted_job and value:
                            formatted_job[key] = str(value)

                    formatted_jobs.append(formatted_job)

                except (ValueError, KeyError, AttributeError) as e:
                    logging.exception(f"Error processing job info: {info}")
                    continue

        renderers.render_details_dataframe(
            items=formatted_jobs,
            title="Job Details",
            name_key="name",
            status_key="status",
            link_keys=["job_link", "run_link", "repo_link"],
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering jobs details: {e}")
        st.error(f"Error rendering jobs details: {e}")


def render():
    """Render the jobs panel in Streamlit.

    This function creates a Streamlit-compatible version of the jobs panel
    that maintains all the functionality of the original dashboard panel.
    """
    renderers.render_panel(
        title="Jobs",
        metrics_func=render_jobs_metrics,
        chart_func=render_jobs_chart,
        details_func=render_jobs_details,
        message="rendering jobs panel",
    )
