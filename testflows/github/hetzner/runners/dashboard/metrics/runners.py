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

from collections import defaultdict
from datetime import datetime
from . import get
from . import history
from . import utils


def summary():
    """Get runners summary data.

    Returns:
        dict: Summary of runners data
    """
    total_runners = get.metric_value("github_hetzner_runners_runners_total_count") or 0
    runners_info = get.metric_info("github_hetzner_runners_runner")

    return {
        "total": int(total_runners),
        "details": runners_info,
        "by_status": utils.count_by_status(runners_info, "status"),
    }


def standby_summary():
    """Get standby runners summary data.

    Returns:
        dict: Summary of standby runners data
    """
    runners_info = get.metric_info("github_hetzner_runners_runner")

    # Filter for standby runners
    standby_runners = [
        r
        for r in runners_info
        if r.get("name", "").startswith("github-hetzner-runner-standby-")
    ]

    # Calculate totals by status
    standby_by_status = defaultdict(int)
    total_standby = len(standby_runners)

    for runner in standby_runners:
        status = runner.get("status", "unknown")
        standby_by_status[status] += 1

    return {
        "total": total_standby,
        "details": standby_runners,
        "by_status": dict(standby_by_status),
    }


def runners_history(cutoff_minutes=15):
    """Update and get history for runners metrics."""

    # Get history for total runners and busy runners
    current_time = datetime.now()

    # Update and get total runners history
    total_timestamps, total_values, _, _ = history.update_and_get(
        "github_hetzner_runners_runners_total_count",
        timestamp=current_time,
        cutoff_minutes=cutoff_minutes,
        default_value=0,
    )

    # Update and get busy runners history
    busy_timestamps, busy_values, _, _ = history.update_and_get(
        "github_hetzner_runners_runners_busy",
        timestamp=current_time,
        cutoff_minutes=cutoff_minutes,
        default_value=0,
    )

    # Update and get online runners history
    online_timestamps, online_values, _, _ = history.update_and_get(
        "github_hetzner_runners_runners_total",
        timestamp=current_time,
        cutoff_minutes=cutoff_minutes,
        default_value=0,
        labels={"status": "online"},
    )

    # Update and get offline runners history
    offline_timestamps, offline_values, _, _ = history.update_and_get(
        "github_hetzner_runners_runners_total",
        timestamp=current_time,
        cutoff_minutes=cutoff_minutes,
        default_value=0,
        labels={"status": "offline"},
    )

    return {
        "total": {
            "timestamps": total_timestamps,
            "values": total_values,
        },
        "busy": {
            "timestamps": busy_timestamps,
            "values": busy_values,
        },
        "online": {
            "timestamps": online_timestamps,
            "values": online_values,
        },
        "offline": {
            "timestamps": offline_timestamps,
            "values": offline_values,
        },
    }


def labels_info():
    """Get all runner label information from metrics."""
    return get.metric_info("github_hetzner_runners_runner_labels")


def labels(labels_info, runner_id, runner_name):
    """Extract labels for a specific runner from labels info."""
    labels = []
    for label_dict in labels_info:
        if (
            label_dict.get("runner_id") == runner_id
            and label_dict.get("runner_name") == runner_name
            and "label" in label_dict
        ):
            labels.append(label_dict["label"])
    return labels


def formatted_details():
    """Get formatted runner details with labels and links."""
    # Get runner information
    runners_summary = summary()
    runners_info = runners_summary["details"]

    # Get all runner labels once
    runner_labels_info = labels_info()

    # Prepare runner data for dataframe
    formatted_runners = []
    for runner in runners_info:
        runner_id = runner.get("runner_id")
        runner_name = runner.get("name")

        # Get runner labels
        runner_labels_list = labels(runner_labels_info, runner_id, runner_name)

        # Create formatted runner data
        formatted_runner = {
            "name": runner.get("name", "Unknown"),
            "status": runner.get("status", "unknown"),
            "runner_id": runner.get("runner_id", ""),
            "os": runner.get("os", ""),
            "repository": runner.get("repository", ""),
            "labels": ", ".join(runner_labels_list) if runner_labels_list else "",
            "busy": (
                "Busy" if runner.get("busy", "false").lower() == "true" else "Idle"
            ),
            "link": (
                f"https://github.com/{runner.get('repository', '')}/settings/actions/runners/{runner.get('runner_id', '')}"
                if runner.get("repository") and runner.get("runner_id")
                else ""
            ),
        }

        # Add any additional fields from the original runner data
        for key, value in runner.items():
            if key not in formatted_runner and value:
                formatted_runner[key] = str(value)

        formatted_runners.append(formatted_runner)

    return formatted_runners
