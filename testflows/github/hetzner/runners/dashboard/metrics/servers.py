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
from datetime import datetime
from collections import defaultdict
from . import get
from . import utils
from . import history


def summary():
    """Get servers summary data.

    Returns:
        dict: Summary of servers data
    """
    total_servers = get.metric_value("github_hetzner_runners_servers_total_count") or 0
    servers_info = get.metric_info("github_hetzner_runners_server")

    return {
        "total": int(total_servers),
        "details": servers_info,
        "by_status": utils.count_by_status(servers_info, "status"),
    }


def standby_summary():
    """Get standby servers summary data.

    Returns:
        dict: Summary of standby servers data
    """
    standby_servers_info = get.metric_info(
        "github_hetzner_runners_standby_servers_total"
    )
    standby_servers_labels = get.metric_info(
        "github_hetzner_runners_standby_servers_labels"
    )

    # Calculate totals by status, server_type, and location
    standby_by_status = defaultdict(int)
    standby_by_type_location = defaultdict(int)
    total_standby = 0

    for server in standby_servers_info:
        status = server.get("status", "unknown")
        server_type = server.get("server_type", "unknown")
        location = server.get("location", "unknown")
        count = int(server.get("value", 0))

        standby_by_status[status] += count
        standby_by_type_location[f"{server_type}-{location}"] += count
        total_standby += count

    return {
        "total": total_standby,
        "details": standby_servers_info,
        "labels": standby_servers_labels,
        "by_status": dict(standby_by_status),
        "by_type_location": dict(standby_by_type_location),
    }


def recycled_summary():
    """Get summary of recycled servers.

    Returns:
        dict: Summary of recycled servers
    """
    recycled_metrics = get.metric_info("github_hetzner_runners_recycled_servers_total")

    total = 0
    by_status = {}
    by_type_location = {}

    for metric in recycled_metrics:
        status = metric.get("status", "unknown")
        server_type = metric.get("server_type", "unknown")
        location = metric.get("location", "unknown")
        value = metric.get("value", 0)

        if value > 0:
            total += value
            by_status[status] = by_status.get(status, 0) + value
            type_location = f"{server_type}-{location}"
            by_type_location[type_location] = (
                by_type_location.get(type_location, 0) + value
            )

    return {
        "total": total,
        "by_status": by_status,
        "by_type_location": by_type_location,
    }


def zombie_total_count():
    """Get the total count of zombie servers.

    Returns:
        int: Number of zombie servers, or 0 if metric not available
    """
    return int(
        get.metric_value("github_hetzner_runners_zombie_servers_total_count") or 0
    )


def unused_total_count():
    """Get the total count of unused runners.

    Returns:
        int: Number of unused runners, or 0 if metric not available
    """
    return int(
        get.metric_value("github_hetzner_runners_unused_runners_total_count") or 0
    )


def recycled_total_count():
    """Get the total count of recycled servers.

    Returns:
        int: Number of recycled servers, or 0 if metric not available
    """
    return int(recycled_summary()["total"] or 0)


def labels_info():
    """Get all server label information from metrics.

    Returns:
        list: List of label dictionaries containing server_id, server_name, and label data
    """
    return get.metric_info("github_hetzner_runners_server_labels")


def labels(labels_info, server_id, server_name):
    """Extract labels for a specific server from labels info.

    Args:
        labels_info: List of label dictionaries from labels_info()
        server_id: Server ID to filter by
        server_name: Server name to filter by

    Returns:
        list: List of labels associated with the specified server
    """
    labels = []
    for label_dict in labels_info:
        if (
            label_dict.get("server_id") == server_id
            and label_dict.get("server_name") == server_name
            and "label" in label_dict
        ):
            labels.append(label_dict["label"])
    return labels


def age(created_time):
    """Calculate server age in seconds from creation time.

    Args:
        created_time: ISO format timestamp string

    Returns:
        int: Age in seconds, or 0 if parsing fails
    """
    if not created_time:
        return 0

    try:
        created_dt = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
        return int((datetime.now(created_dt.tzinfo) - created_dt).total_seconds())
    except (ValueError, TypeError):
        return 0


def pool_name(server_name):
    """Determine the pool type based on server name pattern.

    Args:
        server_name: Name of the server

    Returns:
        str: Pool type - 'standby', 'recycled', or 'regular'
    """
    pool = "regular"
    if server_name.startswith("github-hetzner-runner-standby-"):
        pool = "standby"
    elif server_name.startswith("github-hetzner-runner-recycle-"):
        pool = "recycled"
    return pool


def formatted_details(servers_info):
    """Format servers information with enhanced data including labels and pool assignment.

    Takes raw server information and enriches it with:
    - Server labels from metrics
    - Pool assignment based on naming patterns
    - Formatted cost values
    - Standardized field structure

    Args:
        servers_info: List of raw server dictionaries from server metrics

    Returns:
        list: List of formatted server dictionaries with enhanced fields including
              name, status, pool, server_id, labels, and formatted cost_hourly
    """
    server_labels_info = labels_info()

    formatted_servers = []

    for server in servers_info:
        server_id = server.get("server_id")
        server_name = server.get("name", "")
        # Get server labels
        server_labels = labels(server_labels_info, server_id, server_name)
        # Determine server pool based on name prefix
        pool = pool_name(server_name)

        # Create formatted server data with all fields
        formatted_server = {
            "name": server.get("name", "Unknown"),
            "status": server.get("status", "unknown"),
            "pool": pool,
            "server_id": server.get("server_id", ""),
            "server_type": server.get("server_type", ""),
            "location": server.get("location", ""),
            "ipv4": server.get("ipv4", ""),
            "ipv6": server.get("ipv6", ""),
            "created": server.get("created", ""),
            "labels": ", ".join(server_labels) if server_labels else "",
        }

        # Add any additional fields from the original server data
        for key, value in server.items():
            if key not in formatted_server and value:
                # Format cost_hourly to 3 decimal points
                if key == "cost_hourly":
                    try:
                        formatted_value = f"{float(value):.3f}"
                    except (ValueError, TypeError):
                        formatted_value = str(value)
                else:
                    formatted_value = str(value)
                formatted_server[key] = formatted_value

        formatted_servers.append(formatted_server)

    return formatted_servers


def states_history(cutoff_minutes=15):
    """Update and get history for server states."""

    return history.update_and_get_for_states(
        "github_hetzner_runners_servers_total",
        states=["running", "off", "initializing", "ready", "busy"],
        cutoff_minutes=cutoff_minutes,
    )


def health_details():
    """Get detailed health status information for all problematic servers.

    Returns:
        list: List of dictionaries with server health details, each containing:
              name, server_id, health_status, age_seconds, and other server fields
    """
    health_data = []

    # Add zombie servers
    zombie_servers = get.metric_info("github_hetzner_runners_zombie_server")
    for item in zombie_servers:
        health_data.append(
            {
                "name": item.get("server_name", "Unknown"),
                "server_id": item.get("server_id", "unknown"),
                "health_status": "zombie",
                "age_seconds": age(item.get("created", "")),
                "status": item.get("status", "unknown"),
                "server_type": item.get("server_type", "unknown"),
                "location": item.get("location", "unknown"),
                "created": item.get("created", ""),
            }
        )

    # Add unused runners
    unused_runners = get.metric_info("github_hetzner_runners_unused_runner")
    for item in unused_runners:
        health_data.append(
            {
                "name": item.get("server_name", "Unknown"),
                "server_id": item.get("server_id", "unknown"),
                "health_status": "unused",
                "age_seconds": age(item.get("created", "")),
                "status": item.get("status", "unknown"),
                "server_type": item.get("server_type", "unknown"),
                "location": item.get("location", "unknown"),
                "created": item.get("created", ""),
            }
        )

    # Add recycled servers
    recycled_servers = [
        server
        for server in summary()["details"]
        if server.get("server_name", "").startswith("github-hetzner-runner-recycle-")
    ]
    for item in recycled_servers:
        health_data.append(
            {
                "name": item.get("server_name", "Unknown"),
                "server_id": item.get("server_id", "unknown"),
                "health_status": "recycled",
                "age_seconds": age(item.get("created", "")),
                "status": item.get("status", "unknown"),
                "server_type": item.get("server_type", "unknown"),
                "location": item.get("location", "unknown"),
                "created": item.get("created", ""),
            }
        )

    # Sort by health status priority (zombie first, then unused, then recycled)
    status_priority = {"zombie": 1, "unused": 2, "recycled": 3}
    health_data.sort(
        key=lambda x: (status_priority.get(x["health_status"], 4), x["name"])
    )

    return health_data


def health_history(cutoff_minutes=15):
    """Update and get health metrics history.

    Args:
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        dict: Dictionary with health metrics history data
    """
    # First, ensure health metrics are updated in history
    current_time = datetime.now()

    # Now get the history data
    health_metrics = {}

    # Update and get zombie servers total count history
    zombie_timestamps, zombie_values, _, _ = history.update_and_get(
        "github_hetzner_runners_zombie_servers_total_count",
        timestamp=current_time,
        cutoff_minutes=cutoff_minutes,
        default_value=0,
    )
    health_metrics["zombie"] = {
        "timestamps": zombie_timestamps,
        "values": zombie_values,
    }

    # Update and get unused runners total count history
    unused_timestamps, unused_values, _, _ = history.update_and_get(
        "github_hetzner_runners_unused_runners_total_count",
        timestamp=current_time,
        cutoff_minutes=cutoff_minutes,
        default_value=0,
    )
    health_metrics["unused"] = {
        "timestamps": unused_timestamps,
        "values": unused_values,
    }

    # Update and get recycled servers total count history
    recycled_timestamps, recycled_values, _, _ = history.update_and_get(
        "github_hetzner_runners_recycled_servers_total",
        timestamp=current_time,
        cutoff_minutes=cutoff_minutes,
        default_value=0,
    )
    health_metrics["recycled"] = {
        "timestamps": recycled_timestamps,
        "values": recycled_values,
    }

    return health_metrics
