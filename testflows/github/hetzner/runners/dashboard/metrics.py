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
        print(f"Error getting metric {metric_name}: {str(e)}")
        return None


def get_metric_info(metric_name, job_id=None):
    """Get the current info for a metric from Prometheus.

    Args:
        metric_name: Name of the metric
        job_id: Optional job ID to filter by

    Returns:
        dict: Dictionary of metric info, or empty dict if not found
    """
    try:
        metrics = {}
        print(f"\nGetting metric info for {metric_name}")

        # First, let's see what metrics we have in the registry
        all_metrics = list(REGISTRY.collect())
        print(f"Total metrics in registry: {len(all_metrics)}")
        print("Available metrics:")
        for m in all_metrics:
            print(f"  - {m.name}")

        for metric in all_metrics:
            if metric.name == metric_name:
                print(f"\nFound metric {metric_name}")
                print(f"Metric type: {metric.type}")
                print(f"Metric documentation: {metric.documentation}")

                samples = list(metric.samples)
                print(f"Number of samples: {len(samples)}")

                for i, sample in enumerate(samples):
                    print(f"\nSample {i + 1}:")
                    print(f"  Name: {sample.name}")
                    print(f"  Labels: {sample.labels}")
                    print(f"  Value: {sample.value}")

                    # If job_id is provided, only return metrics for that job
                    if job_id:
                        sample_job_id = f"{sample.labels.get('job_id', '')},{sample.labels.get('run_id', '')}"
                        if sample_job_id != job_id:
                            print(f"  Skipping - job_id mismatch")
                            continue

                    # For Info metrics, store all labels
                    if metric_name.endswith("_info"):
                        key = f"{sample.labels.get('job_id', '')},{sample.labels.get('run_id', '')}"
                        print(f"  Info metric - using key: {key}")
                        # Store all labels except internal ones
                        labels = {
                            k: v
                            for k, v in sample.labels.items()
                            if k not in ("__name__", "instance", "job")
                        }
                        if key not in metrics:
                            metrics[key] = labels
                        else:
                            metrics[key].update(labels)
                        print(f"  Stored labels: {metrics[key]}")
                    else:
                        # Use all labels as the key
                        key = ",".join(
                            f"{k}={v}" for k, v in sorted(sample.labels.items())
                        )
                        print(f"  Regular metric - using key: {key}")
                        metrics[key] = sample.value
                        print(f"  Stored value: {metrics[key]}")

        print(f"\nFinal metrics dictionary: {metrics}")
        return metrics
    except Exception as e:
        print(f"Error getting metric info {metric_name}: {str(e)}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return {}


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
