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

import dateutil.parser
from datetime import datetime

from . import get
from . import history
from ..colors import STREAMLIT_COLORS
from ..panels.utils import format


def scale_up_summary():
    """Get scale-up errors summary data.

    Returns:
        dict: Summary of scale-up errors data
    """
    error_count = (
        get.metric_value("github_hetzner_runners_scale_up_failures_last_hour") or 0
    )
    errors_info = get.metric_info("github_hetzner_runners_scale_up_failure_last_hour")

    return {"last_hour": int(error_count), "details": errors_info}


def scale_down_summary():
    """Get scale-down errors summary data.

    Returns:
        dict: Summary of scale-down errors data
    """
    error_count = (
        get.metric_value("github_hetzner_runners_scale_down_failures_last_hour") or 0
    )
    errors_info = get.metric_info("github_hetzner_runners_scale_down_failure_last_hour")

    return {"last_hour": int(error_count), "details": errors_info}


def get_error_color(error_type, error_type_colors):
    """Get color for error type.

    Args:
        error_type: The error type string
        error_type_colors: Dictionary mapping error types to colors

    Returns:
        str: Color code for the error type
    """
    return error_type_colors.get(error_type, STREAMLIT_COLORS["warning"])


def format_error_details(errors_info, error_type_colors):
    """Format error details for display.

    Args:
        errors_info: List of error info dictionaries
        error_type_colors: Dictionary mapping error types to colors

    Returns:
        list: List of formatted error dictionaries
    """
    formatted_errors = []

    if not errors_info:
        return formatted_errors

    # Sort errors by timestamp in descending order
    errors_info.sort(
        key=lambda x: dateutil.parser.parse(
            x.get("timestamp_iso", "1970-01-01T00:00:00Z")
        ),
        reverse=True,
    )

    for info in errors_info:
        try:
            error_type = info.get("error_type", "Unknown")
            server_name = info.get("server_name", "Unknown")
            error_message = info.get("error", "Unknown error")
            server_type = info.get("server_type", "Unknown")
            location = info.get("location", "Unknown") or "Unspecified"
            labels = info.get("labels", "").split(",") if info.get("labels") else []
            time_str = format.format_created_time(info.get("timestamp_iso"))

            # Create formatted error data
            formatted_error = {
                "name": f"Error Type: {error_type}",
                "server_name": server_name,
                "error_type": error_type,
                "error_message": error_message,
                "server_type": server_type,
                "location": location,
                "labels": ", ".join(labels) if labels else "None",
                "time": time_str,
                "color": get_error_color(error_type, error_type_colors),
            }

            formatted_errors.append(formatted_error)

        except (ValueError, KeyError, AttributeError):
            # Skip malformed error entries
            continue

    return formatted_errors


def scale_up_formatted_details():
    """Get formatted scale-up error details.

    Returns:
        list: List of formatted scale-up error dictionaries
    """
    summary_data = scale_up_summary()

    # Map scale-up error types to colors
    error_type_colors = {
        "max_servers_reached": STREAMLIT_COLORS["error"],
        "resource_limit_exceeded": STREAMLIT_COLORS["error"],
        "api_exception": STREAMLIT_COLORS["error"],
        "error": STREAMLIT_COLORS["error"],
    }

    return format_error_details(summary_data["details"], error_type_colors)


def scale_down_formatted_details():
    """Get formatted scale-down error details.

    Returns:
        list: List of formatted scale-down error dictionaries
    """
    summary_data = scale_down_summary()

    # Map scale-down error types to colors
    error_type_colors = {
        "delete_failed": STREAMLIT_COLORS["error"],
        "delete_powered_off_failed": STREAMLIT_COLORS["error"],
        "delete_zombie_failed": STREAMLIT_COLORS["error"],
        "delete_unused_failed": STREAMLIT_COLORS["error"],
        "delete_recyclable_failed": STREAMLIT_COLORS["error"],
        "delete_powered_off_no_ssh_key_failed": STREAMLIT_COLORS["error"],
        "delete_powered_off_wrong_ssh_key_failed": STREAMLIT_COLORS["error"],
        "delete_powered_off_end_of_life_failed": STREAMLIT_COLORS["error"],
        "delete_zombie_no_ssh_key_failed": STREAMLIT_COLORS["error"],
        "delete_zombie_wrong_ssh_key_failed": STREAMLIT_COLORS["error"],
        "delete_zombie_end_of_life_failed": STREAMLIT_COLORS["error"],
        "delete_unused_runner_no_ssh_key_failed": STREAMLIT_COLORS["error"],
        "delete_unused_runner_wrong_ssh_key_failed": STREAMLIT_COLORS["error"],
        "delete_unused_runner_end_of_life_failed": STREAMLIT_COLORS["error"],
        "delete_unused_recyclable_no_ssh_key_failed": STREAMLIT_COLORS["error"],
        "delete_unused_recyclable_wrong_ssh_key_failed": STREAMLIT_COLORS["error"],
        "delete_unused_recyclable_end_of_life_failed": STREAMLIT_COLORS["error"],
        "scale_down_cycle_failed": STREAMLIT_COLORS["error"],
        "error": STREAMLIT_COLORS["error"],
    }

    return format_error_details(summary_data["details"], error_type_colors)


def scale_up_history(cutoff_minutes=60):
    """Update and get history for scale-up error metrics.

    Args:
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        dict: Dictionary with scale-up error history data
    """
    current_time = datetime.now()

    # Update and get scale-up errors history
    timestamps, values, _, _ = history.update_and_get(
        "github_hetzner_runners_scale_up_failures_last_hour",
        timestamp=current_time,
        cutoff_minutes=cutoff_minutes,
        default_value=0,
    )

    return {
        "Scale-up Errors": {
            "timestamps": timestamps,
            "values": values,
        }
    }


def scale_down_history(cutoff_minutes=60):
    """Update and get history for scale-down error metrics.

    Args:
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        dict: Dictionary with scale-down error history data
    """
    current_time = datetime.now()

    # Update and get scale-down errors history
    timestamps, values, _, _ = history.update_and_get(
        "github_hetzner_runners_scale_down_failures_last_hour",
        timestamp=current_time,
        cutoff_minutes=cutoff_minutes,
        default_value=0,
    )

    return {
        "Scale-down Errors": {
            "timestamps": timestamps,
            "values": values,
        }
    }
