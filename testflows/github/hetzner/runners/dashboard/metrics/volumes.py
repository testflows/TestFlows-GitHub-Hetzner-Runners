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

from . import get
from . import utils
from . import history
from ..panels.utils import format


def summary():
    """Get volumes summary data.

    Returns:
        dict: Summary of volumes data
    """
    total_volumes = get.metric_value("github_hetzner_runners_volumes_total_count") or 0
    volumes_info = get.metric_info("github_hetzner_runners_volume")

    return {
        "total": int(total_volumes),
        "details": volumes_info,
        "by_status": utils.count_by_status(volumes_info, "status"),
    }


def labels_info():
    """Get all volume label information from metrics.

    Returns:
        list: List of label dictionaries containing volume_id, volume_name, and label data
    """
    return get.metric_info("github_hetzner_runners_volume_labels")


def labels(labels_info, volume_id, volume_name):
    """Extract labels for a specific volume from labels info.

    Args:
        labels_info: List of label dictionaries from labels_info()
        volume_id: Volume ID to filter by
        volume_name: Volume name to filter by

    Returns:
        list: List of labels associated with the specified volume
    """
    labels = []
    for label_dict in labels_info:
        if (
            label_dict.get("volume_id") == volume_id
            and label_dict.get("volume_name") == volume_name
            and "label" in label_dict
        ):
            labels.append(label_dict["label"])
    return labels


def formatted_details(volumes_info):
    """Format volumes information with enhanced data including labels.

    Takes raw volume information and enriches it with:
    - Volume labels from metrics
    - Standardized field structure

    Args:
        volumes_info: List of raw volume dictionaries from volume metrics

    Returns:
        list: List of formatted volume dictionaries with enhanced fields including
              name, status, volume_id, labels, and other volume metadata
    """
    volume_labels_info = labels_info()

    formatted_volumes = []

    for volume in volumes_info:
        volume_id = volume.get("volume_id")
        volume_name = volume.get("name", "")
        # Get volume labels
        volume_labels = labels(volume_labels_info, volume_id, volume_name)

        # Create formatted volume data with all fields
        formatted_volume = {
            "name": volume.get("name", "Unknown"),
            "status": volume.get("status", "unknown"),
            "id": volume.get("volume_id", ""),
            "size": volume.get("size", ""),
            "location": volume.get("location", ""),
            "format": volume.get("format", ""),
            "server_name": volume.get("server_name", ""),
            "server_id": volume.get("server_id", ""),
            "created": format.format_created_time(volume.get("created", "")),
            "labels": ", ".join(volume_labels) if volume_labels else "",
        }

        # Add any additional fields from the original volume data
        # Skip Prometheus metric labels that are not part of the actual volume info
        prometheus_labels = {"volume_id", "volume_name"}
        for key, value in volume.items():
            if key not in formatted_volume and key not in prometheus_labels and value:
                formatted_volume[key] = str(value)

        formatted_volumes.append(formatted_volume)

    return formatted_volumes


def states_history(cutoff_minutes=15):
    """Update and get history for volume states."""

    return history.update_and_get_for_states(
        "github_hetzner_runners_volumes_total",
        states=["available", "creating", "attached"],
        cutoff_minutes=cutoff_minutes,
    )
