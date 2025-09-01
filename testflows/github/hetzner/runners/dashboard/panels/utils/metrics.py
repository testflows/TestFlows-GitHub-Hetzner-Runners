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
from datetime import datetime
from typing import List, Dict, Any, Tuple

from ... import metrics
from . import data


class SimpleMetric:
    """Simple abstraction for a single metric that gets tracked over time."""

    def __init__(self, metric_name: str, cutoff_minutes: int = 15):
        self.metric_name = metric_name
        self.cutoff_minutes = cutoff_minutes

    def get_current_value(self) -> float:
        """Get current value of the metric."""
        return metrics.get_metric_value(self.metric_name) or 0

    def update_and_get_history(self) -> Tuple[List, List, float, datetime]:
        """Update history with current value and return (timestamps, values, current_value, current_time)."""
        current_time = datetime.now()
        current_value = self.get_current_value()

        # Update history
        data.update_simple_metric_history(
            self.metric_name,
            current_value,
            current_time,
            cutoff_minutes=self.cutoff_minutes,
        )

        # Get history
        timestamps, values = data.get_simple_metric_history(
            self.metric_name, cutoff_minutes=self.cutoff_minutes
        )

        return timestamps, values, current_value, current_time

    def get_dataframe(self) -> pd.DataFrame:
        """Get a pandas DataFrame ready for charting."""
        timestamps, values, _, _ = self.update_and_get_history()

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


class ComputedMetric(SimpleMetric):
    """A metric that's computed from other metrics rather than stored directly."""

    def __init__(self, metric_name: str, compute_func, cutoff_minutes: int = 15):
        super().__init__(metric_name, cutoff_minutes)
        self.compute_func = compute_func

    def get_current_value(self) -> float:
        """Compute current value using the provided function."""
        return self.compute_func()


class StateMetric:
    """Abstraction for metrics that have multiple states (e.g., running, off, ready)."""

    def __init__(self, metric_name: str, states: List[str], cutoff_minutes: int = 15):
        self.metric_name = metric_name
        self.states = states
        self.cutoff_minutes = cutoff_minutes

    def get_current_values(self) -> Dict[str, int]:
        """Get current values for all states."""
        current_values, _ = data.get_current_metric_values(
            self.metric_name, self.states
        )
        return current_values

    def get_dataframe(self) -> pd.DataFrame:
        """Get a pandas DataFrame ready for charting with multiple state lines."""
        # Update current values (this also updates history)
        self.get_current_values()

        # Get history data
        history_data = data.get_metric_history_for_states(
            self.metric_name, self.states, cutoff_minutes=self.cutoff_minutes
        )

        # Use existing chart utility to create DataFrame
        from . import chart

        return chart.create_dataframe_from_history(history_data)


class CombinedMetric:
    """Abstraction for metrics that combine state-based and individual metrics."""

    def __init__(
        self, base_metric: StateMetric, additional_metrics: List[SimpleMetric]
    ):
        self.base_metric = base_metric
        self.additional_metrics = additional_metrics

    def get_dataframe(self) -> pd.DataFrame:
        """Get a combined DataFrame with all metrics."""
        # Get the base state metric DataFrame
        base_df = self.base_metric.get_dataframe()

        # Get additional metrics and combine them
        for simple_metric in self.additional_metrics:
            # Update the metric and get its history
            timestamps, values, _, _ = simple_metric.update_and_get_history()

            if timestamps and values and len(timestamps) == len(values):
                # Create simple DataFrame for this metric
                metric_df = pd.DataFrame(
                    {
                        "Time": pd.to_datetime(timestamps),
                        "Status": simple_metric.metric_name.split("_")[
                            -1
                        ],  # Extract last part as status
                        "Count": [int(v) for v in values],
                    }
                )

                # Combine with base DataFrame
                if not base_df.empty:
                    base_df = pd.concat([base_df, metric_df], ignore_index=True)
                else:
                    base_df = metric_df

        return base_df.sort_values("Time") if not base_df.empty else base_df


class MultipleSimpleMetrics:
    """Abstraction for tracking multiple individual metrics that should be combined."""

    def __init__(self, metrics_config: List[dict], cutoff_minutes: int = 15):
        """
        Initialize with a list of metric configurations.

        Args:
            metrics_config: List of dicts with 'metric_name' and 'status_name' keys
            cutoff_minutes: History cutoff in minutes
        """
        self.metrics_config = metrics_config
        self.cutoff_minutes = cutoff_minutes
        self.simple_metrics = {
            config["status_name"]: SimpleMetric(config["metric_name"], cutoff_minutes)
            for config in metrics_config
        }

    def get_dataframe(self) -> pd.DataFrame:
        """Get a combined DataFrame with all metrics."""
        all_data = []

        for status_name, simple_metric in self.simple_metrics.items():
            # Update history and get data in one call
            timestamps, values, _, _ = simple_metric.update_and_get_history()

            if timestamps and values and len(timestamps) == len(values):
                for ts, val in zip(timestamps, values):
                    try:
                        all_data.append(
                            {
                                "Time": pd.to_datetime(ts),
                                "Status": status_name,
                                "Count": int(val),
                            }
                        )
                    except (ValueError, TypeError):
                        continue

        if not all_data:
            return pd.DataFrame({"Time": pd.to_datetime([]), "Status": [], "Count": []})

        # Create DataFrame and sort by time
        df = pd.DataFrame(all_data)
        return df.sort_values("Time")
