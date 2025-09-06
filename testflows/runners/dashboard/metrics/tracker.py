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

import threading
import time
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Callable, Any

from . import history

logger = logging.getLogger(__name__)

tracked_metrics = {}
stop_event = threading.Event()
update_thread = None
running = False
lock = threading.Lock()
default_seconds = 5
cutoff_minutes = 15


def update_simple_metric(metric: Dict[str, Any], timestamp) -> None:
    """Update a simple Prometheus metric."""
    history.update(
        metric_name=metric["metric_name"],
        labels=metric["labels"],
        timestamp=timestamp,
        cutoff_minutes=cutoff_minutes,
    )


def update_states_metric(metric: Dict[str, Any], timestamp) -> None:
    """Update a Prometheus metric with multiple states."""
    history.update_for_states(
        metric_name=metric["metric_name"],
        states=metric["states"],
        labels=metric["labels"],
        timestamp=timestamp,
        cutoff_minutes=cutoff_minutes,
    )


def update_computed_metric(metric: Dict[str, Any], timestamp) -> None:
    """Update a computed metric."""
    compute_func = metric["compute_func"]

    value = compute_func()
    history.update(
        metric_name=metric["metric_name"],
        labels={},
        value=value,
        timestamp=timestamp,
        cutoff_minutes=cutoff_minutes,
    )


def track(
    metric_name: str,
    labels: Dict[str, str] = None,
    states: List[str] = None,
    compute_func: Callable = None,
    interval_seconds: int = default_seconds,
) -> None:
    """Track a metric in history.

    Args:
        metric_name: Name of the metric
        labels: Optional labels dict
        states: Optional list of state values (for metrics with multiple states)
        compute_func: Optional function that returns current value (for computed metrics)
        interval_seconds: How often to update this metric (default: 5 seconds)
    """
    if labels is None:
        labels = {}

    # Check if this metric is already being tracked (idempotent)
    with lock:
        if metric_name in tracked_metrics:
            logger.debug(f"Metric {metric_name} already being tracked, skipping")
            return

    # Determine update function based on parameters
    if compute_func is not None:
        update_func = update_computed_metric
        metric_type = "computed"
    elif states is not None:
        update_func = update_states_metric
        metric_type = "states"
    else:
        update_func = update_simple_metric
        metric_type = "simple"

    metric_info = {
        "metric_name": metric_name,
        "labels": labels,
        "interval_seconds": interval_seconds,
        "last_update": 0,
        "update_func": update_func,
        "states": states,
        "compute_func": compute_func,
    }

    with lock:
        tracked_metrics[metric_name] = metric_info

    logger.debug(
        f"Tracking {metric_type} metric: {metric_name} "
        f"with labels {labels} every {interval_seconds}s"
    )


def start_tracking() -> None:
    """Start the background metric tracking thread."""
    global update_thread, running

    if running:
        logger.warning("Metric tracking is already running")
        return

    stop_event.clear()
    update_thread = threading.Thread(target=update_loop, daemon=True)
    update_thread.start()
    running = True


def stop_tracking() -> None:
    """Stop the background metric tracking thread."""
    global running

    if not running:
        return

    stop_event.set()
    if update_thread and update_thread.is_alive():
        update_thread.join(timeout=10)
    running = False


def is_tracking() -> bool:
    """Check if metric tracking is running."""
    return running and update_thread and update_thread.is_alive()


def tracking_info() -> List[Dict[str, Any]]:
    """Get information about all tracked metrics."""
    with lock:
        return [
            {
                "name": metric["metric_name"],
                "labels": metric["labels"],
                "type": metric["update_func"].__name__,
                "interval": metric["interval_seconds"],
                "last_update": metric["last_update"],
                "states": metric.get("states"),
            }
            for metric in tracked_metrics.values()
        ]


@contextmanager
def tracking():
    """Context manager for metric tracking.

    Usage:
        with tracking():
            track("my_metric")
            # ... do other work ...
        # Tracking automatically stopped when exiting context
    """
    start_tracking()
    try:
        yield
    finally:
        stop_tracking()


def tick() -> int:
    """Update all metrics that are due for update.

    Returns:
        int: Number of metrics that were updated
    """
    current_time = time.time()

    with lock:
        metrics_to_update = [
            metric
            for metric in tracked_metrics.values()
            if current_time - metric["last_update"] >= metric["interval_seconds"]
        ]

    updated_count = 0
    for metric in metrics_to_update:
        try:
            timestamp = datetime.fromtimestamp(current_time)
            metric["update_func"](metric, timestamp)
            metric["last_update"] = current_time
            updated_count += 1
        except Exception as e:
            logger.exception(f"Error updating metric {metric['metric_name']}: {e}")

    return updated_count


def update_loop(frequency: int = 5) -> None:
    """Main update loop that runs in the background thread."""

    while not stop_event.wait(frequency):
        tick()
