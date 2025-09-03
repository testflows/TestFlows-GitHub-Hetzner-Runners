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

from . import get
from . import history
from . import tracker
from .. import format

# Register job metrics for tracking
tracker.track("github_hetzner_runners_queued_jobs")
tracker.track("github_hetzner_runners_running_jobs")


def summary():
    """Get jobs summary data.

    Returns:
        dict: Summary of jobs data
    """
    queued_jobs = get.metric_value("github_hetzner_runners_queued_jobs") or 0
    running_jobs = get.metric_value("github_hetzner_runners_running_jobs") or 0

    return {
        "queued": int(queued_jobs),
        "running": int(running_jobs),
        "total": int(queued_jobs + running_jobs),
    }


def jobs_history(cutoff_minutes=15):
    """Get history for jobs metrics."""

    # Get queued jobs history
    queued_timestamps, queued_values = history.data(
        "github_hetzner_runners_queued_jobs",
        cutoff_minutes=cutoff_minutes,
    )

    # Get running jobs history
    running_timestamps, running_values = history.data(
        "github_hetzner_runners_running_jobs",
        cutoff_minutes=cutoff_minutes,
    )

    return {
        "queued": {
            "timestamps": queued_timestamps,
            "values": queued_values,
        },
        "running": {
            "timestamps": running_timestamps,
            "values": running_values,
        },
    }


def labels_info(is_running=False):
    """Get all job label information from metrics.

    Args:
        is_running: If True, get running job labels, else get queued job labels

    Returns:
        list: List of label dictionaries containing job_id, run_id, and label data
    """
    metric_name = (
        "github_hetzner_runners_running_job_labels"
        if is_running
        else "github_hetzner_runners_queued_job_labels"
    )
    return get.metric_info(metric_name)


def labels(labels_info, job_id, run_id):
    """Extract labels for a specific job from labels info.

    Args:
        labels_info: List of label dictionaries from labels_info()
        job_id: Job ID to filter by
        run_id: Run ID to filter by

    Returns:
        list: List of labels associated with the specified job
    """
    labels = []
    for label_dict in labels_info:
        if (
            label_dict.get("job_id") == job_id
            and label_dict.get("run_id") == run_id
            and "label" in label_dict
        ):
            labels.append(label_dict["label"])
    return labels


def formatted_details():
    """Format jobs information with enhanced data including labels and timing.

    Returns:
        list: List of formatted job dictionaries with enhanced fields including
              name, status, job_id, labels, timing, and links
    """
    # Get job information
    queued_jobs_info = get.metric_info("github_hetzner_runners_queued_job")
    running_jobs_info = get.metric_info("github_hetzner_runners_running_job")

    # Get labels info once for each type
    queued_labels_info = labels_info(is_running=False)
    running_labels_info = labels_info(is_running=True)

    formatted_jobs = []

    # Process both queued and running jobs
    for jobs_info, is_running, job_labels_info in [
        (queued_jobs_info, False, queued_labels_info),
        (running_jobs_info, True, running_labels_info),
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
                time_value = get.metric_value(
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
                job_labels = labels(job_labels_info, job_id, run_id)

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
                    "status": status_text.lower(),
                    "job id": f"{info.get('job_id', 'Unknown')}",
                    "run id": info.get("run_id", ""),
                    "workflow": info.get("workflow_name", "").strip(),
                    "repository": info.get("repository", "").strip(),
                    "branch": info.get("head_branch", ""),
                    "sha": info.get("head_sha", ""),
                    "labels": job_labels if job_labels else [],
                    time_label.lower(): time_str,
                    "job": job_url,
                    "run": run_url,
                    "repository": repo_url,
                    "queued at": format.format_created_time(info.get("queued_at", "")),
                }

                # Add any additional fields from the original job data
                for key, value in info.items():
                    if key in ("head_branch", "workflow_name", "head_sha", "queued_at"):
                        continue
                    if key not in formatted_job and value:
                        formatted_job[key.replace("_", " ")] = str(value)

                formatted_jobs.append(formatted_job)

            except (ValueError, KeyError, AttributeError):
                continue

    return formatted_jobs
