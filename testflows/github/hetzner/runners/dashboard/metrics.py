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
from datetime import datetime, timedelta
from prometheus_client import REGISTRY

# Store metric history
metric_history = defaultdict(lambda: {"timestamps": [], "values": []})


def get_metric_value(metric_name, labels=None):
    """
    Get metric value directly from Prometheus registry
    Args:
        metric_name: Name of the metric to fetch
        labels: Dictionary of label names and values
    Returns:
        int: The metric value as an integer, guaranteed to be non-negative
    """
    if labels is None:
        labels = {}

    try:
        for metric in REGISTRY.collect():
            if metric.name == metric_name:
                # Print all samples for debugging
                print(f"\nAll samples for {metric_name}:")
                for sample in metric.samples:
                    print(f"  Labels: {sample.labels}, Value: {sample.value}")

                # Get the exact matching sample
                matching_samples = [
                    sample
                    for sample in metric.samples
                    if all(sample.labels.get(k) == v for k, v in labels.items())
                ]

                if matching_samples:
                    if len(matching_samples) > 1:
                        print(
                            f"Warning: Multiple matches found for {metric_name} with labels {labels}"
                        )
                    # Take the first match
                    return int(float(matching_samples[0].value))
    except (ValueError, TypeError) as e:
        print(f"Error getting metric value: {e}")

    return 0  # Default to 0 if not found


def update_metric_history(metric_name, labels, value, timestamp):
    """Update metric history with new value"""
    key = f"{metric_name}_{','.join(f'{k}={v}' for k, v in sorted(labels.items()))}"

    # Initialize if not exists
    if key not in metric_history:
        metric_history[key] = {"timestamps": [], "values": []}

    # Keep only last 15 minutes of data
    cutoff_time = timestamp - timedelta(minutes=15)

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
