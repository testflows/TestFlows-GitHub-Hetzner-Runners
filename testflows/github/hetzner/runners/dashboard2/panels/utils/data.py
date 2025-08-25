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

"""Common data processing utilities for dashboard panels."""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
from ... import metrics


def get_metric_history_for_states(
    metric_name: str,
    states: List[str],
    labels: Dict[str, str] = None,
    cutoff_minutes: int = 15,
) -> Dict[str, Dict[str, List]]:
    """Get metric history data for multiple states.

    Args:
        metric_name: Name of the metric
        states: List of state values to fetch
        labels: Optional labels to filter by
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        Dictionary with state history data
    """
    history_data = {}

    for state in states:
        if labels:
            # Add state to labels
            state_labels = labels.copy()
            state_labels["status"] = state
            timestamps, values = metrics.get_metric_history_data(
                metric_name, state_labels, cutoff_minutes=cutoff_minutes
            )
        else:
            timestamps, values = metrics.get_metric_history_data(
                metric_name, {"status": state}, cutoff_minutes=cutoff_minutes
            )
        history_data[state] = {"timestamps": timestamps, "values": values}

    return history_data


def get_current_metric_values(
    metric_name: str,
    states: List[str],
    labels: Dict[str, str] = None,
) -> Tuple[Dict[str, int], datetime]:
    """Get current metric values for multiple states.

    Args:
        metric_name: Name of the metric
        states: List of state values to fetch
        labels: Optional labels to filter by

    Returns:
        Tuple of (current_values_dict, current_time)
    """
    current_time = datetime.now()
    current_values = {}

    for state in states:
        if labels:
            # Add state to labels
            state_labels = labels.copy()
            state_labels["status"] = state
            value = metrics.get_metric_value(metric_name, state_labels) or 0
        else:
            value = metrics.get_metric_value(metric_name, {"status": state}) or 0

        current_values[state] = value

        # Update metric history
        if labels:
            metrics.update_metric_history(
                metric_name, state_labels, value, current_time, cutoff_minutes=15
            )
        else:
            metrics.update_metric_history(
                metric_name, {"status": state}, value, current_time, cutoff_minutes=15
            )

    return current_values, current_time


def get_simple_metric_history(
    metric_name: str,
    cutoff_minutes: int = 15,
) -> Tuple[List, List]:
    """Get simple metric history data (no labels).

    Args:
        metric_name: Name of the metric
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        Tuple of (timestamps, values)
    """
    return metrics.get_metric_history_data(metric_name, cutoff_minutes=cutoff_minutes)


def get_multiple_metrics_history(
    metric_names: List[str],
    cutoff_minutes: int = 15,
) -> Dict[str, Dict[str, List]]:
    """Get history data for multiple separate metrics.

    Args:
        metric_names: List of metric names
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        Dictionary with metric history data
    """
    history_data = {}

    for metric_name in metric_names:
        timestamps, values = metrics.get_metric_history_data(
            metric_name, cutoff_minutes=cutoff_minutes
        )
        history_data[metric_name] = {"timestamps": timestamps, "values": values}

    return history_data


def get_current_multiple_metrics(
    metric_names: List[str],
) -> Tuple[Dict[str, int], datetime]:
    """Get current values for multiple separate metrics.

    Args:
        metric_names: List of metric names

    Returns:
        Tuple of (current_values_dict, current_time)
    """
    current_time = datetime.now()
    current_values = {}

    for metric_name in metric_names:
        value = metrics.get_metric_value(metric_name) or 0
        current_values[metric_name] = value

        # Update metric history
        metrics.update_metric_history(
            metric_name, {}, value, current_time, cutoff_minutes=15
        )

    return current_values, current_time


def update_simple_metric_history(
    metric_name: str,
    value: float,
    current_time: datetime = None,
    cutoff_minutes: int = 15,
):
    """Update simple metric history (no labels).

    Args:
        metric_name: Name of the metric
        value: Current value
        current_time: Current time (defaults to now)
        cutoff_minutes: Number of minutes to keep in history
    """
    if current_time is None:
        current_time = datetime.now()

    metrics.update_metric_history(
        metric_name, {}, value, current_time, cutoff_minutes=cutoff_minutes
    )


def build_metrics_summary(
    summary_func: callable,
    metric_labels: List[str] = None,
) -> List[Dict[str, Any]]:
    """Build metrics summary for display.

    Args:
        summary_func: Function that returns a summary dictionary
        metric_labels: List of metric labels to extract

    Returns:
        List of metric dictionaries with 'label' and 'value' keys
    """
    try:
        summary = summary_func()

        if not metric_labels:
            # Default to total if available
            return [{"label": "Total", "value": summary.get("total", 0)}]

        metrics_data = []
        for label in metric_labels:
            if label in summary:
                metrics_data.append({"label": label.title(), "value": summary[label]})

        return metrics_data

    except Exception as e:
        return [{"label": "Error", "value": "N/A"}]


def format_server_content(
    info: Dict[str, Any], server_labels_list: List[str]
) -> List[str]:
    """Format server information content for display.

    Args:
        info: Server information dictionary
        server_labels_list: List of server labels

    Returns:
        List of formatted content lines
    """
    content_lines = []

    # Add server details
    content_lines.append(f"**Type:** {info.get('type', 'Unknown')}")
    content_lines.append(f"**Location:** {info.get('location', 'Unknown')}")
    content_lines.append(f"**IPv4:** {info.get('ipv4', 'Unknown')}")
    content_lines.append(f"**Created:** {info.get('created', 'Unknown')}")
    content_lines.append(f"**IPv6:** {info.get('ipv6', 'Unknown')}")
    content_lines.append(f"**Runner Status:** {info.get('runner_status', 'Unknown')}")
    content_lines.append(f"**Labels:** {', '.join(server_labels_list) or 'None'}")

    # Add cost information if available
    if info.get("cost_hourly"):
        cost_text = f"{info['cost_hourly']} {info['cost_currency']}/hour"
        if info.get("cost_total"):
            cost_text += f" (total: {info['cost_total']} {info['cost_currency']})"
        content_lines.append(f"**Cost:** {cost_text}")

    return content_lines


def format_job_content(info: Dict[str, Any], job_labels_list: List[str]) -> List[str]:
    """Format job information content for display.

    Args:
        info: Job information dictionary
        job_labels_list: List of job labels

    Returns:
        List of formatted content lines with HTML links
    """
    content_lines = []

    # Job ID with inline GitHub link
    job_id_text = (
        f"{info.get('job_id', 'Unknown')} (attempt {info.get('run_attempt', '1')})"
    )
    job_url = None
    if info.get("repository"):
        job_url = f"https://github.com/{info.get('repository', '')}/actions/runs/{info.get('run_id', '')}/job/{info.get('job_id', '')}"

    job_line = f"**Job ID:** {job_id_text}"
    if job_url:
        job_line += f" <a href='{job_url}' target='_blank'>(View on GitHub)</a>"
    content_lines.append(job_line)

    # Run ID with inline GitHub link
    run_id_text = info.get("run_id", "Unknown")
    run_url = None
    if info.get("repository"):
        run_url = f"https://github.com/{info.get('repository', '')}/actions/runs/{info.get('run_id', '')}"

    run_line = f"**Run ID:** {run_id_text}"
    if run_url:
        run_line += f" <a href='{run_url}' target='_blank'>(View on GitHub)</a>"
    content_lines.append(run_line)

    # Add regular fields
    content_lines.append(
        f"**Workflow:** {info.get('workflow_name', 'Unknown').strip()}"
    )

    # Add time information
    if info.get("started_at"):
        from .format import format_duration
        import time

        start_time = info.get("started_at")
        current_time = time.time()
        duration = current_time - start_time
        time_str = format_duration(duration)
        time_label = "Duration"
    else:
        time_str = info.get("started_at", "Unknown")
        time_label = "Started At"

    content_lines.append(f"**{time_label}:** {time_str}")
    content_lines.append(f"**Branch:** {info.get('head_branch', 'Unknown')}")
    content_lines.append(f"**Labels:** {', '.join(job_labels_list) or 'None'}")

    # Add repository with link
    repository_text = info.get("repository", "Unknown").strip()
    repo_line = f"**Repository:** {repository_text}"
    if repository_text != "Unknown":
        repo_url = f"https://github.com/{repository_text}"
        repo_line += f" <a href='{repo_url}' target='_blank'>(View on GitHub)</a>"
    content_lines.append(repo_line)

    return content_lines
