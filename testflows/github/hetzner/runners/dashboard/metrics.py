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
