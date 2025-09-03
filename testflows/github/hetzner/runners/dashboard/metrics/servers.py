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
from .. import format
from . import history
from . import tracker
from ...constants import standby_server_name_prefix, recycle_server_name_prefix

# Server status constants
states = ["running", "off", "initializing", "ready", "busy"]

# Register server metrics for tracking
tracker.track("github_hetzner_runners_servers_total", states=states)
tracker.track("github_hetzner_runners_zombie_servers_total_count")
tracker.track("github_hetzner_runners_unused_runners_total_count")
tracker.track("github_hetzner_runners_recycled_servers_total")
# Register individual standby server status metrics
for status in states:
    tracker.track(
        f"standby_servers_{status}",
        compute_func=lambda s=status: standby_count_for_status(s),
    )


def standby_count_for_status(status):
    """Helper function to get count of standby servers for a specific status."""
    servers_summary = summary()
    all_servers = servers_summary["details"]

    count = 0
    for server in all_servers:
        if (
            server.get("name", "").startswith(standby_server_name_prefix)
            and server.get("status", "unknown") == status
        ):
            count += 1

    return count


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
    # Get all servers and filter for standby servers
    servers_summary = summary()
    all_servers = servers_summary["details"]

    # Filter for standby servers
    standby_servers = [
        server
        for server in all_servers
        if server.get("name", "").startswith(standby_server_name_prefix)
    ]

    # Calculate totals by status
    standby_by_status = defaultdict(int)
    for server in standby_servers:
        status = server.get("status", "unknown")
        standby_by_status[status] += 1

    return {
        "total": len(standby_servers),
        "details": standby_servers,
        "by_status": dict(standby_by_status),
    }


def recycled_summary():
    """Get summary of recycled servers.

    Returns:
        dict: Summary of recycled servers
    """
    # Get all servers and filter for recycled servers
    servers_summary = summary()
    all_servers = servers_summary["details"]

    # Filter for recycled servers
    recycled_servers = [
        server
        for server in all_servers
        if server.get("name", "").startswith(recycle_server_name_prefix)
    ]

    # Calculate totals by status
    recycled_by_status = defaultdict(int)
    for server in recycled_servers:
        status = server.get("status", "unknown")
        recycled_by_status[status] += 1

    return {
        "total": len(recycled_servers),
        "details": recycled_servers,
        "by_status": dict(recycled_by_status),
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
    if server_name.startswith(standby_server_name_prefix):
        pool = "standby"
    elif server_name.startswith(recycle_server_name_prefix):
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
        server_id = server.get("id")
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
            "id": server.get("id", ""),
            "type": server.get("type", ""),
            "image": server.get("image", ""),
            "architecture": server.get("architecture", ""),
            "location": server.get("location", ""),
            "ipv4": server.get("ipv4", ""),
            "ipv6": server.get("ipv6", ""),
            "created": format.format_created_time(server.get("created", "")),
            "labels": server_labels if server_labels else [],
        }

        # Add any additional fields from the original server data
        # Skip Prometheus metric labels that are not part of the actual server info
        prometheus_labels = {"server_id", "server_name"}
        for key, value in server.items():
            if key not in formatted_server and key not in prometheus_labels and value:
                # Format cost_hourly to 3 decimal points
                if key == "cost_hourly":
                    try:
                        formatted_value = f"{float(value):.3f}"
                    except (ValueError, TypeError):
                        formatted_value = str(value)
                else:
                    formatted_value = str(value)
                formatted_server[key.replace("_", " ")] = formatted_value

        formatted_servers.append(formatted_server)

    return formatted_servers


def states_history(cutoff_minutes=15):
    """Get history for server states."""
    return history.data_for_states(
        "github_hetzner_runners_servers_total",
        states=states,
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
                "id": item.get("server_id", "unknown"),
                "health status": "zombie",
                "status": item.get("status", "unknown"),
                "type": item.get("server_type", "unknown"),
                "location": item.get("location", "unknown"),
                "created": format.format_created_time(item.get("created", "")),
            }
        )

    # Add unused runners
    unused_runners = get.metric_info("github_hetzner_runners_unused_runner")
    for item in unused_runners:
        health_data.append(
            {
                "server_name": item.get("server_name", "Unknown"),
                "name": item.get("runner_name", "Unknown"),
                "server id": item.get("server_id", "unknown"),
                "id": item.get("runner_id", "unknown"),
                "health status": "unused",
                "status": item.get("status", "unknown"),
                "server type": item.get("server_type", "unknown"),
                "location": item.get("location", "unknown"),
                "created": format.format_created_time(item.get("created", "")),
            }
        )

    # Add recycled servers
    recycled_servers = [
        server
        for server in summary()["details"]
        if server.get("name", "").startswith(recycle_server_name_prefix)
    ]
    for item in recycled_servers:
        health_data.append(
            {
                "name": item.get("name", "Unknown"),
                "id": item.get("id", "unknown"),
                "health status": "recycled",
                "status": item.get("status", "unknown"),
                "type": item.get("type", "unknown"),
                "location": item.get("location", "unknown"),
                "created": format.format_created_time(item.get("created", "")),
            }
        )

    # Sort by health status priority (zombie first, then unused, then recycled)
    status_priority = {"zombie": 1, "unused": 2, "recycled": 3}
    health_data.sort(
        key=lambda x: (status_priority.get(x["health status"], 4), x["name"])
    )

    return health_data


def health_history(cutoff_minutes=15):
    """Get health metrics history.

    Args:
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        dict: Dictionary with health metrics history data
    """
    health_metrics = {}

    # Get zombie servers total count history
    zombie_timestamps, zombie_values = history.data(
        "github_hetzner_runners_zombie_servers_total_count",
        cutoff_minutes=cutoff_minutes,
    )
    health_metrics["zombie"] = {
        "timestamps": zombie_timestamps,
        "values": zombie_values,
    }

    # Get unused runners total count history
    unused_timestamps, unused_values = history.data(
        "github_hetzner_runners_unused_runners_total_count",
        cutoff_minutes=cutoff_minutes,
    )
    health_metrics["unused"] = {
        "timestamps": unused_timestamps,
        "values": unused_values,
    }

    # Get recycled servers total count history
    recycled_timestamps, recycled_values = history.data(
        "github_hetzner_runners_recycled_servers_total",
        cutoff_minutes=cutoff_minutes,
    )
    health_metrics["recycled"] = {
        "timestamps": recycled_timestamps,
        "values": recycled_values,
    }

    return health_metrics


def standby_states_history(cutoff_minutes=15):
    """Get history for standby server states.

    Args:
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        dict: Dictionary with standby server states history data
    """
    standby_history = {}

    for status in states:
        # Get history for this specific status
        timestamps, values = history.data(
            f"standby_servers_{status}",
            cutoff_minutes=cutoff_minutes,
        )
        standby_history[status] = {
            "timestamps": timestamps,
            "values": values,
        }

    return standby_history
