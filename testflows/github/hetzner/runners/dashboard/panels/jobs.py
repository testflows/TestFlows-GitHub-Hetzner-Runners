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
from ..colors import STREAMLIT_COLORS
from .utils import chart, render as render_utils, data, format


def create_panel():
    """Create jobs panel.

    This function maintains API compatibility with the original dashboard.

    Returns:
        dict: Panel configuration dictionary
    """
    return {"title": "Jobs", "type": "jobs"}


def get_jobs_history_data(cutoff_minutes=15):
    """Get jobs history data for plotting.

    Args:
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        dict: Dictionary with job status history data
    """
    job_types = ["queued", "running"]
    metric_names = [f"github_hetzner_runners_{job_type}_jobs" for job_type in job_types]
    return data.get_multiple_metrics_history(metric_names, cutoff_minutes)


def create_jobs_dataframe(history_data):
    """Create a pandas DataFrame for the jobs data with proper time formatting."""
    if not history_data:
        return pd.DataFrame({"Time": pd.to_datetime([]), "Status": [], "Count": []})

    # Map metric names to status names
    metric_to_status = {
        "github_hetzner_runners_queued_jobs": "queued",
        "github_hetzner_runners_running_jobs": "running",
    }

    # Collect all data points
    all_data = []

    for metric_name, data in history_data.items():
        status = metric_to_status.get(metric_name, metric_name)
        timestamps = data.get("timestamps", [])
        values = data.get("values", [])

        if timestamps and values and len(timestamps) == len(values):
            for ts, val in zip(timestamps, values):
                try:
                    all_data.append(
                        {
                            "Time": pd.to_datetime(ts),
                            "Status": status,
                            "Count": int(val),
                        }
                    )
                except (ValueError, TypeError):
                    continue

    if not all_data:
        return pd.DataFrame({"Time": pd.to_datetime([]), "Status": [], "Count": []})

    # Create DataFrame and sort by time
    df = pd.DataFrame(all_data)
    df = df.sort_values("Time")

    return df


def get_current_jobs_data():
    """Get current jobs data without caching to ensure fresh data."""
    job_types = ["queued", "running"]
    metric_names = [f"github_hetzner_runners_{job_type}_jobs" for job_type in job_types]
    current_values, current_time = data.get_current_multiple_metrics(metric_names)

    # Get history data for plotting
    history_data = get_jobs_history_data()

    return history_data, current_values, current_time


@st.fragment(run_every=st.session_state.update_interval)
def render_jobs_metrics():
    """Render the jobs metrics header in an isolated fragment for optimal performance."""
    try:
        # Get current jobs summary
        jobs_summary = metrics.get_jobs_summary()

        # Build metrics data
        metrics_data = [
            {"label": "Total Jobs", "value": jobs_summary["total"]},
            {"label": "Running Jobs", "value": jobs_summary["running"]},
            {"label": "Queued Jobs", "value": jobs_summary["queued"]},
        ]

        render_utils.render_metrics_columns(metrics_data)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering jobs metrics: {e}")
        st.error(f"Error rendering jobs metrics: {e}")


@st.fragment(run_every=st.session_state.update_interval)
def render_jobs_chart():
    """Render the jobs chart using Altair for proper multi-line visualization."""
    try:
        # Get fresh data
        history_data, current_values, current_time = get_current_jobs_data()

        # Create DataFrame for the chart
        df = create_jobs_dataframe(history_data)

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

        chart.render_chart_with_fallback(
            create_chart,
            "No jobs data available yet. The chart will appear once data is collected.",
            "Error rendering jobs chart",
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering jobs chart: {e}")
        st.error(f"Error rendering jobs chart: {e}")


@st.fragment(run_every=st.session_state.update_interval)
def render_jobs_details():
    """Render the jobs details as a dataframe."""
    try:
        # Get job information
        queued_jobs_info = metrics.get_metric_info("github_hetzner_runners_queued_job")
        running_jobs_info = metrics.get_metric_info(
            "github_hetzner_runners_running_job"
        )
        jobs_summary = metrics.get_jobs_summary()

        total_jobs = jobs_summary["total"]

        if not queued_jobs_info and not running_jobs_info:
            if total_jobs > 0:
                st.info(f"Total jobs: {total_jobs} (details not available)")
            else:
                st.info("No jobs found")
            return

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

        render_utils.render_details_dataframe(
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
    render_utils.render_panel_with_fragments(
        title="Jobs",
        metrics_func=render_jobs_metrics,
        chart_func=render_jobs_chart,
        details_func=render_jobs_details,
        error_message="Error rendering jobs panel",
    )


def render_graph_only():
    """Render only the jobs graph without header and metrics.

    This is useful for embedding the jobs graph in other panels or layouts.
    """
    render_jobs_chart()
