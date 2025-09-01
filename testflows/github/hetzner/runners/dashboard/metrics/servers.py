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
from . import get
from . import utils


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
    try:
        recycled_metrics = get.metric_info(
            "github_hetzner_runners_recycled_servers_total"
        )

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
    except Exception as e:
        logger.exception(f"Error getting recycled servers summary: {e}")
        return {"total": 0, "by_status": {}, "by_type_location": {}}
