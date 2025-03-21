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
import logging
import dateutil.parser

from ..colors import COLORS
from .. import metrics
from . import panel


def create_panel():
    """Create errors panel."""
    return panel.create_panel("Scale-up Errors (Last Hour)")


def create_error_list():
    """Create a list of errors with their descriptions."""
    errors_info = metrics.get_metric_info(
        "github_hetzner_runners_scale_up_failure_last_hour"
    )
    # Get total number of errors from metrics
    total_errors = (
        metrics.get_metric_value("github_hetzner_runners_scale_up_failures_last_hour")
        or 0
    )

    if not errors_info:
        if total_errors > 0:
            # We have errors but no details
            return panel.create_list("errors", total_errors, [], "Total errors")
        return panel.create_list("errors", 0, [], "No scale-up errors in the last hour")

    # Sort errors_info by timestamp in descending order
    errors_info.sort(
        key=lambda x: dateutil.parser.parse(
            x.get("timestamp_iso", "1970-01-01T00:00:00Z")
        ),
        reverse=True,
    )

    error_items = []
    for info in errors_info:
        try:
            error_type = info.get("error_type", "Unknown")
            server_name = info.get("server_name", "Unknown")
            error_message = info.get("error", "Unknown error")
            server_type = info.get("server_type", "Unknown")
            location = info.get("location", "Unknown") or "Unspecified"
            labels = info.get("labels", "").split(",")
            time_str = (
                dateutil.parser.parse(info.get("timestamp_iso", "")).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                )
                if info.get("timestamp_iso")
                else "Unknown time"
            )

            # Map error types to colors
            error_colors = {
                "max_servers_reached": COLORS["error"],
                "resource_limit_exceeded": COLORS["error"],
                "api_exception": COLORS["error"],
                "error": COLORS["error"],
            }
            error_color = error_colors.get(error_type, COLORS["warning"])

            # Create header
            header = panel.create_item_header(
                f"Error Type: {error_type}",
                server_name,
                error_color,
            )

            # Create values
            values = [
                panel.create_item_value("Time", time_str),
                panel.create_item_value("Server Type", server_type),
                panel.create_item_value("Location", location),
                panel.create_item_value("Labels", ", ".join(labels) or "None"),
                panel.create_item_value("Error Message", error_message),
            ]

            error_items.append(
                panel.create_list_item("error", error_color, header, values)
            )

        except (ValueError, KeyError, AttributeError) as e:
            logging.exception(f"Error processing error info: {info}")
            continue

    return panel.create_list("errors", total_errors, error_items, "Total errors")


def update_graph(n, cache=[]):
    """Update errors graph."""
    current_time = datetime.now()
    one_hour_ago = current_time - timedelta(hours=1)

    # Get current error count
    error_count = (
        metrics.get_metric_value("github_hetzner_runners_scale_up_failures_last_hour")
        or 0
    )

    # Add current state to cache
    cache.append((current_time.timestamp(), error_count))

    # Clean up old entries and sort by timestamp
    cache[:] = [(ts, count) for ts, count in cache if ts >= one_hour_ago.timestamp()]
    cache.sort()

    # Create points for plotting
    time_points = []
    error_counts = []

    # Add all points as they come in
    for ts, count in cache:
        time_points.append(datetime.fromtimestamp(ts))
        error_counts.append(count)

    # Create trace for error count
    traces = [
        panel.create_trace(
            time_points,
            error_counts,
            f"errors ({int(error_count)})",
            "errors",
            COLORS["error"],
        )
    ]

    xaxis = {
        "title": "Time",
        "range": panel.get_time_range(
            current_time, cutoff_minutes=60
        ),  # Use 60 minutes for scale-up errors
        "tickformat": "%H:%M",
    }

    yaxis = {
        "title": "Number of Errors",
        "autorange": True,
        "rangemode": "nonnegative",
        "tickmode": "linear" if error_count < 5 else "auto",
        "nticks": 5,
        "tickformat": "d",  # Display as integers
        "automargin": True,
        "showgrid": True,
    }

    return panel.create_graph(traces, "Scale-up Errors", xaxis, yaxis)
