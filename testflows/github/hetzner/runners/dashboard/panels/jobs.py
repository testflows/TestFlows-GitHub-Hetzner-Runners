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
import logging

from datetime import datetime

from ..colors import COLORS
from .. import metrics
from . import panel


def create_job_list():
    """Create a list of jobs with their descriptions."""
    queued_jobs_info = metrics.get_metric_info("github_hetzner_runners_queued_job")
    running_jobs_info = metrics.get_metric_info("github_hetzner_runners_running_job")
    queued_count = metrics.get_metric_value("github_hetzner_runners_queued_jobs") or 0
    running_count = metrics.get_metric_value("github_hetzner_runners_running_jobs") or 0

    job_items = []
    # Process both queued and running jobs
    for jobs_info, is_running in [(queued_jobs_info, False), (running_jobs_info, True)]:
        if not jobs_info:
            continue

        for info in jobs_info:
            try:
                job_id = info.get("job_id")
                run_id = info.get("run_id")
                if not job_id or not run_id:
                    continue

                # Get wait time for this job
                metric_name = (
                    "github_hetzner_runners_running_job_time_seconds"
                    if is_running
                    else "github_hetzner_runners_queued_job_wait_time_seconds"
                )
                time_value = metrics.get_metric_value(
                    metric_name,
                    {"job_id": job_id, "run_id": run_id},
                )
                time_str = f"{int(time_value)} seconds" if time_value else "unknown"
                time_label = "Run time: " if is_running else "Wait time: "

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

                logging.info(f"Final labels list for job {job_id}: {job_labels_list}")

                status_color = COLORS["success"] if is_running else COLORS["warning"]
                status_text = "Running" if is_running else "Queued"

                # Create job item header
                header = panel.create_item_header(
                    f"Job: {info.get('name', 'Unknown')}",
                    status_text,
                    status_color,
                )

                # Create job item values
                values = [
                    panel.create_item_value(
                        "Job ID",
                        f"{info.get('job_id', 'Unknown')} (attempt {info.get('run_attempt', '1')})",
                        link={
                            "text": "View on GitHub",
                            "href": f"https://github.com/{info.get('repository', '')}/actions/runs/{info.get('run_id', '')}/job/{info.get('job_id', '')}",
                        },
                    ),
                    panel.create_item_value(
                        "Run ID",
                        info.get("run_id", "Unknown"),
                        link={
                            "text": "View on GitHub",
                            "href": f"https://github.com/{info.get('repository', '')}/actions/runs/{info.get('run_id', '')}",
                        },
                    ),
                    panel.create_item_value(
                        "Workflow", info.get("workflow_name", "Unknown")
                    ),
                    panel.create_item_value(
                        "Repository", info.get("repository", "Unknown")
                    ),
                    panel.create_item_value(
                        "Branch", info.get("head_branch", "Unknown")
                    ),
                    panel.create_item_value(time_label, time_str, status_color),
                    panel.create_item_value(
                        "Labels", ", ".join(job_labels_list) or "None"
                    ),
                ]

                # Create job item
                job_items.append(
                    panel.create_list_item("job", status_color, header, values)
                )

            except (ValueError, KeyError, AttributeError) as e:
                logging.exception(f"Error processing job info {info}")
                continue

    return panel.create_list(
        "jobs",
        queued_count + running_count,
        job_items,
        f"Jobs: {int(queued_count + running_count)}",
    )


def create_panel():
    """Create jobs panel."""
    return panel.create_panel("jobs")


def update_graph(n):
    """Update jobs graph."""
    current_time = datetime.now()
    queued_jobs = metrics.get_metric_value("github_hetzner_runners_queued_jobs") or 0
    running_jobs = metrics.get_metric_value("github_hetzner_runners_running_jobs") or 0

    # Create traces using the helper function
    traces = [
        panel.create_metric_trace(
            "github_hetzner_runners_queued_jobs",
            queued_jobs,
            current_time,
            COLORS["warning"],
            "queued",
        ),
        panel.create_metric_trace(
            "github_hetzner_runners_running_jobs",
            running_jobs,
            current_time,
            COLORS["success"],
            "running",
        ),
    ]

    xaxis = {
        "title": "Time",
        "range": panel.get_time_range(current_time),
        "tickformat": "%H:%M",
    }

    yaxis = {
        "title": "Number of Jobs",
        "autorange": True,
        "rangemode": "nonnegative",
        "tickmode": "linear" if max(queued_jobs, running_jobs) < 5 else "auto",
        "nticks": 5,
        "tickformat": "d",
        "automargin": True,
        "showgrid": True,
    }

    return panel.create_graph(traces, "Jobs", xaxis, yaxis)
