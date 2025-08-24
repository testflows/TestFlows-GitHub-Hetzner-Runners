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
from .utils import format_duration


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
    history_data = {}

    for job_type in job_types:
        metric_name = f"github_hetzner_runners_{job_type}_jobs"
        timestamps, values = metrics.get_metric_history_data(
            metric_name, cutoff_minutes=cutoff_minutes
        )
        history_data[job_type] = {"timestamps": timestamps, "values": values}

    return history_data


def create_jobs_dataframe(history_data):
    """Create a pandas DataFrame for the jobs data with proper time formatting."""
    if not history_data:
        return pd.DataFrame({"Time": pd.to_datetime([]), "Status": [], "Count": []})

    # Collect all data points
    all_data = []

    for job_type, data in history_data.items():
        timestamps = data.get("timestamps", [])
        values = data.get("values", [])

        if timestamps and values and len(timestamps) == len(values):
            for ts, val in zip(timestamps, values):
                try:
                    all_data.append(
                        {
                            "Time": pd.to_datetime(ts),
                            "Status": job_type,
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
    current_time = datetime.now()
    job_types = ["queued", "running"]
    current_values = {}

    # Get current values for each job type
    for job_type in job_types:
        metric_name = f"github_hetzner_runners_{job_type}_jobs"
        value = metrics.get_metric_value(metric_name) or 0
        current_values[job_type] = value

        # Update metric history
        metrics.update_metric_history(
            metric_name,
            {},
            value,
            current_time,
            cutoff_minutes=15,
        )

    # Get history data for plotting
    history_data = get_jobs_history_data()

    return history_data, current_values, current_time


@st.fragment(run_every=st.session_state.get("update_interval", 5))
def render_jobs_metrics():
    """Render the jobs metrics header in an isolated fragment for optimal performance."""
    try:
        # Get current jobs summary
        jobs_summary = metrics.get_jobs_summary()

        # Display current jobs metrics in columns
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="Total Jobs",
                value=jobs_summary["total"],
            )

        with col2:
            st.metric(
                label="Running Jobs",
                value=jobs_summary["running"],
            )

        with col3:
            st.metric(
                label="Queued Jobs",
                value=jobs_summary["queued"],
            )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering jobs metrics: {e}")
        st.error(f"Error rendering jobs metrics: {e}")


@st.fragment(run_every=st.session_state.get("update_interval", 5))
def render_jobs_chart():
    """Render the jobs chart using Altair for proper multi-line visualization."""
    try:
        # Get fresh data
        history_data, current_values, current_time = get_current_jobs_data()

        # Create DataFrame for the chart
        df = create_jobs_dataframe(history_data)

        # Display the chart using Altair for multi-line visualization
        if not df.empty:
            # Create proper time window (last 15 minutes)
            current_time = pd.Timestamp.now()
            time_window_start = current_time - pd.Timedelta(minutes=15)

            # Filter data to time window
            window_df = df[df["Time"] >= time_window_start].copy()

            if not window_df.empty:
                # Calculate dynamic y-axis range and tick count
                max_count = window_df["Count"].max()
                y_max = max(max_count * 1.1, 1)  # At least 1 for visibility

                # Create color mapping for job states
                color_domain = ["running", "queued"]
                color_range = [
                    STREAMLIT_COLORS["success"],  # Green for running
                    STREAMLIT_COLORS["warning"],  # Orange for queued
                ]

                # Create chart with proper time window and dynamic count range
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
                            "Count:Q",
                            title="Number of Jobs",
                            scale=alt.Scale(domain=[0, y_max]),
                            axis=alt.Axis(
                                values=list(range(0, int(y_max) + 1)), format="d"
                            ),
                        ),
                        color=alt.Color(
                            "Status:N",
                            scale=alt.Scale(domain=color_domain, range=color_range),
                            legend=alt.Legend(title="Job Status"),
                        ),
                        tooltip=[
                            alt.Tooltip("Time:T", title="Time", format="%H:%M:%S"),
                            alt.Tooltip("Status:N", title="Status"),
                            alt.Tooltip("Count:Q", title="Count"),
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
                st.info("No jobs data available in the current time window.")

        else:
            # Show placeholder when no data
            st.info(
                "No jobs data available yet. The chart will appear once data is collected."
            )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering jobs chart: {e}")
        st.error(f"Error rendering jobs chart: {e}")


@st.fragment(run_every=st.session_state.get("update_interval", 5))
def render_jobs_details():
    """Render the jobs details list."""
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

        # Display job details
        st.subheader("Job Details")

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
                            format_duration(time_value)
                            if time_value is not None
                            else "unknown"
                        )
                    except (ValueError, TypeError):
                        time_str = "unknown"
                    time_label = "Run time:" if is_running else "Wait time:"

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
                    status_color = (
                        STREAMLIT_COLORS["success"]
                        if is_running
                        else STREAMLIT_COLORS["warning"]
                    )

                    # Create expander for each job
                    with st.expander(
                        f"Job: {info.get('name', 'Unknown')} ({status_text})",
                        expanded=False,
                    ):
                        # Use single column layout to avoid auto-sizing issues
                        # Job ID with inline GitHub link
                        job_id_text = f"{info.get('job_id', 'Unknown')} (attempt {info.get('run_attempt', '1')})"
                        job_url = None
                        if info.get("repository"):
                            job_url = f"https://github.com/{info.get('repository', '')}/actions/runs/{info.get('run_id', '')}/job/{info.get('job_id', '')}"

                        # Run ID with inline GitHub link
                        run_id_text = info.get("run_id", "Unknown")
                        run_url = None
                        if info.get("repository"):
                            run_url = f"https://github.com/{info.get('repository', '')}/actions/runs/{info.get('run_id', '')}"
                        # Build all content as a single markdown string to avoid spacing issues
                        content_lines = []

                        # Add fields with links
                        job_line = f"**Job ID:** {job_id_text}"
                        if job_url:
                            job_line += f" <a href='{job_url}' target='_blank'>(View on GitHub)</a>"
                        content_lines.append(job_line)

                        run_line = f"**Run ID:** {run_id_text}"
                        if run_url:
                            run_line += f" <a href='{run_url}' target='_blank'>(View on GitHub)</a>"
                        content_lines.append(run_line)

                        # Add regular fields
                        content_lines.append(
                            f"**Workflow:** {info.get('workflow_name', 'Unknown').strip()}"
                        )
                        content_lines.append(f"**{time_label}** {time_str}")
                        content_lines.append(
                            f"**Branch:** {info.get('head_branch', 'Unknown')}"
                        )
                        content_lines.append(
                            f"**Labels:** {', '.join(job_labels_list) or 'None'}"
                        )

                        # Add repository with link
                        repository_text = info.get("repository", "Unknown").strip()
                        repo_line = f"**Repository:** {repository_text}"
                        if repository_text != "Unknown":
                            repo_url = f"https://github.com/{repository_text}"
                            repo_line += f" <a href='{repo_url}' target='_blank'>(View on GitHub)</a>"
                        content_lines.append(repo_line)

                        # Render all content in a single markdown call
                        st.markdown("  \n".join(content_lines), unsafe_allow_html=True)

                except (ValueError, KeyError, AttributeError) as e:
                    logging.exception(f"Error processing job info: {info}")
                    continue

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering jobs details: {e}")
        st.error(f"Error rendering jobs details: {e}")


def render():
    """Render the jobs panel in Streamlit.

    This function creates a Streamlit-compatible version of the jobs panel
    that maintains all the functionality of the original dashboard panel.
    """
    logger = logging.getLogger(__name__)

    try:
        with st.container(border=True):
            st.header("Jobs")

            # Render the jobs metrics header with stable updates
            render_jobs_metrics()

            # Render the jobs chart with stable updates
            render_jobs_chart()

            # Render jobs details
            render_jobs_details()

    except Exception as e:
        logger.exception(f"Error rendering jobs panel: {e}")
        st.error(f"Error rendering jobs panel: {e}")


def render_graph_only():
    """Render only the jobs graph without header and metrics.

    This is useful for embedding the jobs graph in other panels or layouts.
    """
    render_jobs_chart()
