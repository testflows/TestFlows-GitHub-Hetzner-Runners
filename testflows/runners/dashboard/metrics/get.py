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
from typing import List, Dict
from prometheus_client import REGISTRY

logger = logging.getLogger(__name__)


def metric_value(metric_name, labels=None):
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


def metric_info(metric_name, job_id=None):
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


def metric_value_for_states(
    metric_name: str,
    states: List[str],
    labels: Dict[str, str] = None,
) -> Dict[str, int]:
    """Get current metric value for multiple states.

    Args:
        metric_name: Name of the metric
        states: List of state values to fetch
        labels: Optional labels to filter by

    Returns:
        Dictionary mapping states to their current value
    """
    current_values = {}

    for state in states:
        if labels:
            # Add state to labels
            state_labels = labels.copy()
            state_labels["status"] = state
            value = metric_value(metric_name, state_labels) or 0
        else:
            value = metric_value(metric_name, {"status": state}) or 0

        current_values[state] = value

    return current_values
