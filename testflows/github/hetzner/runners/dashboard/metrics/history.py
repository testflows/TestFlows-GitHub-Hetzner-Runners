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

import pandas as pd

from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Tuple

# Store metric history
metric_history = defaultdict(lambda: {"timestamps": [], "values": []})

from . import get


def update(metric_name, labels, value=None, timestamp=None, cutoff_minutes=15):
    """Update metric history with new value.

    Args:
        metric_name: Name of the metric
        labels: Dictionary of labels
        value: Current value (if None, gets automatically from Prometheus)
        timestamp: Current timestamp (defaults to now)
        cutoff_minutes: Number of minutes to keep in history. Defaults to 15 minutes.

    Returns:
        str: The key used for the metric history
    """
    if timestamp is None:
        timestamp = datetime.now()

    if value is None:
        value = get.metric_value(metric_name, labels) or 0

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


def update_for_states(
    metric_name: str,
    states: List[str],
    values: Dict[str, float] = None,
    labels: Dict[str, str] = None,
    timestamp: datetime = None,
    cutoff_minutes: int = 15,
) -> None:
    """Update metric history for multiple states.

    Args:
        metric_name: Name of the metric
        states: List of state values to update
        values: Dictionary mapping states to their values (if None, gets automatically from Prometheus)
        labels: Optional labels to filter by
        timestamp: Current timestamp (defaults to now)
        cutoff_minutes: Number of minutes to keep in history
    """
    if timestamp is None:
        timestamp = datetime.now()

    if values is None:
        values = get.metric_value_for_states(metric_name, states, labels)

    for state in states:
        value = values.get(state, 0)
        if labels:
            # Add state to labels
            state_labels = labels.copy()
            state_labels["status"] = state
            update(metric_name, state_labels, value, timestamp, cutoff_minutes)
        else:
            update(metric_name, {"status": state}, value, timestamp, cutoff_minutes)


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


def data_for_states(
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
            timestamps, values = data(
                metric_name, state_labels, cutoff_minutes=cutoff_minutes
            )
        else:
            timestamps, values = data(
                metric_name, {"status": state}, cutoff_minutes=cutoff_minutes
            )
        history_data[state] = {"timestamps": timestamps, "values": values}

    return history_data


def update_and_get(
    metric_name,
    labels={},
    value=None,
    timestamp=None,
    cutoff_minutes=15,
    default_value=None,
) -> Tuple[List, List, float, datetime]:
    """Update and get history for metric with labels,
    and using given value and timestamp.

    If value is not provided, use current value.
    If timestamp is not provided, use current time.

    return (timestamps, values, value, timestamp).
    """
    if timestamp is None:
        timestamp = datetime.now()

    if value is None:
        value = get.metric_value(metric_name)

    if default_value is not None:
        value = value if value is not None else default_value

    # Update history
    update(
        metric_name,
        labels,
        value,
        timestamp,
        cutoff_minutes=cutoff_minutes,
    )

    # Get history
    timestamps, values = data(metric_name, cutoff_minutes=cutoff_minutes)

    return timestamps, values, value, timestamp


def update_and_get_for_states(
    metric_name: str,
    states: List[str],
    values: Dict[str, float] = None,
    labels: Dict[str, str] = None,
    timestamp: datetime = None,
    cutoff_minutes: int = 15,
) -> Dict[str, Dict[str, List]]:
    """Update metric history for multiple states and get their historical data.

    Args:
        metric_name: Name of the metric
        states: List of state values to update and fetch
        values: Dictionary mapping states to their current values (if None, fetches from metrics)
        labels: Optional labels to filter by
        timestamp: Current timestamp (defaults to now)
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        Dictionary with state history data including current values
    """
    if timestamp is None:
        timestamp = datetime.now()

    # Get current values if not provided
    if values is None:
        values = get.metric_value_for_states(metric_name, states, labels)

    # Update history for all states
    update_for_states(metric_name, states, values, labels, timestamp, cutoff_minutes)

    # Get historical data for all states
    return data_for_states(metric_name, states, labels, cutoff_minutes)


def dataframe(timestamps, values) -> pd.DataFrame:
    """Get a pandas DataFrame for history data."""

    if not timestamps or not values:
        return pd.DataFrame({"Time": pd.to_datetime([]), "Value": []})

    if len(timestamps) != len(values):
        return pd.DataFrame({"Time": pd.to_datetime([]), "Value": []})

    df = pd.DataFrame(
        {
            "Time": pd.to_datetime(timestamps),
            "Value": [float(v) for v in values],
        }
    )

    df = df.dropna()
    df = df.sort_values("Time")

    return df


def dataframe_for_states(
    data_for_states,
    time_column="Time",
    value_column="Count",
    status_column="Status",
    value_type=int,
):
    """Create a standardized DataFrame from history data.

    Args:
        history_data: Dictionary with history data
        time_column: Name for the time column
        value_column: Name for the value column
        status_column: Name for the status column (if applicable)

    Returns:
        pd.DataFrame: Formatted DataFrame
    """
    if not data_for_states:
        return pd.DataFrame(
            {time_column: pd.to_datetime([]), value_column: [], status_column: []}
        )

    all_data = []

    for status, data in data_for_states.items():
        timestamps = data.get("timestamps", [])
        values = data.get("values", [])

        if timestamps and values and len(timestamps) == len(values):
            for ts, val in zip(timestamps, values):
                try:
                    data_point = {
                        time_column: pd.to_datetime(ts),
                        value_column: value_type(val),
                    }
                    if status_column:
                        data_point[status_column] = status
                    all_data.append(data_point)
                except (ValueError, TypeError):
                    continue

    if not all_data:
        return pd.DataFrame(
            {time_column: pd.to_datetime([]), value_column: [], status_column: []}
        )

    df = pd.DataFrame(all_data)
    return df.sort_values(time_column)
