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
from collections import defaultdict
from datetime import timedelta
from prometheus_client import REGISTRY

# Store metric history
metric_history = defaultdict(lambda: {"timestamps": [], "values": []})
logger = logging.getLogger(__name__)


def get_metric_value(metric_name, labels=None):
    """Get the current value of a metric from Prometheus.

    Args:
        metric_name: Name of the metric
        labels: Optional dictionary of label names and values

    Returns:
        float or None: The current value of the metric, or None if not found
    """
    try:
        if labels:
            return REGISTRY.get_sample_value(metric_name, labels)
        return REGISTRY.get_sample_value(metric_name)
    except Exception as e:
        logging.exception(f"Error getting metric {metric_name}")
        return None


def get_metric_info(metric_name, job_id=None):
    """Get the current info for a metric from Prometheus.

    Args:
        metric_name: Name of the metric
        job_id: Optional job ID to filter by

    Returns:
        list: List of parsed metric info dictionaries, or empty list if not found
    """
    try:
        metrics = []

        for metric in REGISTRY.collect():
            if metric.name == metric_name:
                samples = list(metric.samples)

                for sample in samples:
                    # If job_id is provided, only return metrics for that job
                    if job_id:
                        sample_job_id = f"{sample.labels.get('job_id', '')},{sample.labels.get('run_id', '')}"
                        if sample_job_id != job_id:
                            continue

                    # Store all labels except internal ones
                    labels = {
                        k: v
                        for k, v in sample.labels.items()
                        if k not in ("__name__", "instance", "job")
                    }
                    metrics.append(labels)

        return metrics
    except Exception as e:
        logging.exception(f"Error getting metric info {metric_name}")
        return []


def update_metric_history(metric_name, labels, value, timestamp, cutoff_minutes=15):
    """Update metric history with new value.

    Args:
        metric_name: Name of the metric
        labels: Dictionary of labels
        value: Current value
        timestamp: Current timestamp
        cutoff_minutes: Number of minutes to keep in history. Defaults to 15 minutes.

    Returns:
        str: The key used for the metric history
    """
    # Only add labels to key if there are any
    if labels:
        key = f"{metric_name}_{','.join(f'{k}={v}' for k, v in sorted(labels.items()))}"
    else:
        key = metric_name

    # Initialize if not exists
    if key not in metric_history:
        metric_history[key] = {"timestamps": [], "values": []}

    # Calculate cutoff time
    cutoff_time = timestamp - timedelta(minutes=cutoff_minutes)

    # Remove old data points
    while (
        metric_history[key]["timestamps"]
        and metric_history[key]["timestamps"][0] < cutoff_time
    ):
        metric_history[key]["timestamps"].pop(0)
        metric_history[key]["values"].pop(0)

    # Simply append the new value
    metric_history[key]["timestamps"].append(timestamp)
    metric_history[key]["values"].append(value)

    return key


def get_metric_history_data(metric_name, labels=None, cutoff_minutes=15):
    """Get metric history data for plotting.

    Args:
        metric_name: Name of the metric
        labels: Optional dictionary of labels
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        tuple: (timestamps, values) for plotting
    """
    if labels:
        key = f"{metric_name}_{','.join(f'{k}={v}' for k, v in sorted(labels.items()))}"
    else:
        key = metric_name

    history = metric_history.get(key, {"timestamps": [], "values": []})
    return history["timestamps"], history["values"]


def get_heartbeat_status():
    """Get heartbeat status for display.

    Returns:
        tuple: (is_alive, last_heartbeat_timestamp)
    """
    heartbeat = get_metric_value("github_hetzner_runners_heartbeat_timestamp") or 0

    return heartbeat > 0, heartbeat


def get_servers_summary():
    """Get servers summary data.

    Returns:
        dict: Summary of servers data
    """
    total_servers = get_metric_value("github_hetzner_runners_servers_total_count") or 0
    servers_info = get_metric_info("github_hetzner_runners_server")

    return {
        "total": int(total_servers),
        "details": servers_info,
        "by_status": _count_by_status(servers_info, "status"),
    }


def get_jobs_summary():
    """Get jobs summary data.

    Returns:
        dict: Summary of jobs data
    """
    queued_jobs = get_metric_value("github_hetzner_runners_queued_jobs") or 0
    running_jobs = get_metric_value("github_hetzner_runners_running_jobs") or 0

    return {
        "queued": int(queued_jobs),
        "running": int(running_jobs),
        "total": int(queued_jobs + running_jobs),
    }


def get_runners_summary():
    """Get runners summary data.

    Returns:
        dict: Summary of runners data
    """
    total_runners = get_metric_value("github_hetzner_runners_runners_total_count") or 0
    runners_info = get_metric_info("github_hetzner_runners_runner")

    return {
        "total": int(total_runners),
        "details": runners_info,
        "by_status": _count_by_status(runners_info, "status"),
    }


def get_errors_summary():
    """Get errors summary data.

    Returns:
        dict: Summary of errors data
    """
    error_count = (
        get_metric_value("github_hetzner_runners_scale_up_failures_last_hour") or 0
    )
    errors_info = get_metric_info("github_hetzner_runners_scale_up_failure")

    return {"last_hour": int(error_count), "details": errors_info}


def get_cost_summary():
    """Get cost summary data.

    Returns:
        dict: Summary of cost data
    """
    servers_info = get_metric_info("github_hetzner_runners_server")
    current_hourly_cost = 0.0

    if servers_info:
        for info in servers_info:
            try:
                cost_hourly = float(info.get("cost_hourly", 0))
                current_hourly_cost += cost_hourly
            except (ValueError, TypeError):
                continue

    return {
        "hourly": current_hourly_cost,
        "daily": current_hourly_cost * 24,
        "monthly": current_hourly_cost * 24 * 30,
    }


def _count_by_status(items, status_field):
    """Count items by status.

    Args:
        items: List of items with status information
        status_field: Field name containing status

    Returns:
        dict: Count by status
    """
    counts = defaultdict(int)
    for item in items:
        status = item.get(status_field, "unknown")
        counts[status] += 1
    return dict(counts)
