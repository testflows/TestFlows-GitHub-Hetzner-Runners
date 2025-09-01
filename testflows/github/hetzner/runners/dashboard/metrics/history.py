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

from datetime import datetime, timedelta
from collections import defaultdict

# Store metric history
metric_history = defaultdict(lambda: {"timestamps": [], "values": []})


def update(metric_name, labels, value, timestamp, cutoff_minutes=15):
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


def data(metric_name, labels=None, cutoff_minutes=15):
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

    # Apply cutoff filtering to the retrieved data
    current_time = datetime.now()
    cutoff_time = current_time - timedelta(minutes=cutoff_minutes)

    timestamps = []
    values = []

    for i, timestamp in enumerate(history["timestamps"]):
        if timestamp >= cutoff_time:
            timestamps.append(timestamp)
            values.append(history["values"][i])

    return timestamps, values
