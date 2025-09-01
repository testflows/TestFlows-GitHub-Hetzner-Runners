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
