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

import socket
import psutil
import pandas as pd
from datetime import datetime
from . import get
from . import history
from . import tracker

# Register system health metrics for tracking
tracker.track("github_hetzner_runners_system_cpu_percent")
tracker.track("github_hetzner_runners_system_memory_percent")
tracker.track("github_hetzner_runners_process_cpu_percent")
tracker.track("github_hetzner_runners_process_memory_percent")
tracker.track("github_hetzner_runners_system_root_disk_percent")


def summary():
    """Get system health summary data.

    Returns:
        dict: Summary of system health metrics
    """
    # Get system metrics
    system_cpu = get.metric_value("github_hetzner_runners_system_cpu_percent") or 0
    system_memory_percent = (
        get.metric_value("github_hetzner_runners_system_memory_percent") or 0
    )
    system_memory_total = (
        get.metric_value("github_hetzner_runners_system_memory_total_bytes") or 0
    )
    system_memory_used = (
        get.metric_value("github_hetzner_runners_system_memory_used_bytes") or 0
    )
    system_memory_available = (
        get.metric_value("github_hetzner_runners_system_memory_available_bytes") or 0
    )

    # Get process metrics
    process_cpu = get.metric_value("github_hetzner_runners_process_cpu_percent") or 0
    process_memory_percent = (
        get.metric_value("github_hetzner_runners_process_memory_percent") or 0
    )
    process_memory_rss = (
        get.metric_value("github_hetzner_runners_process_memory_rss_bytes") or 0
    )
    process_memory_vms = (
        get.metric_value("github_hetzner_runners_process_memory_vms_bytes") or 0
    )
    process_threads = (
        get.metric_value("github_hetzner_runners_process_num_threads") or 0
    )
    process_fds = get.metric_value("github_hetzner_runners_process_num_fds") or 0

    # Get system load averages
    load_1m = get.metric_value("github_hetzner_runners_system_load_average_1m") or 0
    load_5m = get.metric_value("github_hetzner_runners_system_load_average_5m") or 0
    load_15m = get.metric_value("github_hetzner_runners_system_load_average_15m") or 0

    # Get system info
    num_cpus = get.metric_value("github_hetzner_runners_system_num_cpus") or 0
    boot_time = get.metric_value("github_hetzner_runners_system_boot_time") or 0

    # Get disk metrics for root filesystem
    root_disk_percent = (
        get.metric_value(
            "github_hetzner_runners_system_disk_percent", {"mountpoint": "/"}
        )
        or 0
    )
    root_disk_used = (
        get.metric_value(
            "github_hetzner_runners_system_disk_used_bytes", {"mountpoint": "/"}
        )
        or 0
    )
    root_disk_total = (
        get.metric_value(
            "github_hetzner_runners_system_disk_total_bytes", {"mountpoint": "/"}
        )
        or 0
    )

    # Calculate uptime
    current_time = datetime.now()
    uptime_seconds = current_time.timestamp() - boot_time if boot_time > 0 else 0
    uptime_days = int(uptime_seconds // 86400)
    uptime_hours = int((uptime_seconds % 86400) // 3600)
    uptime_minutes = int((uptime_seconds % 3600) // 60)
    uptime_str = f"{uptime_days}d {uptime_hours}h {uptime_minutes}m"

    return {
        "timestamp": current_time,
        "system": {
            "cpu_percent": system_cpu,
            "memory_percent": system_memory_percent,
            "memory_total": system_memory_total,
            "memory_used": system_memory_used,
            "memory_available": system_memory_available,
            "load_1m": load_1m,
            "load_5m": load_5m,
            "load_15m": load_15m,
            "num_cpus": int(num_cpus),
            "uptime": uptime_str,
        },
        "process": {
            "cpu_percent": process_cpu,
            "memory_percent": process_memory_percent,
            "memory_rss": process_memory_rss,
            "memory_vms": process_memory_vms,
            "threads": int(process_threads),
            "file_descriptors": int(process_fds),
        },
        "disk": {
            "root_percent": root_disk_percent,
            "root_used": root_disk_used,
            "root_total": root_disk_total,
        },
    }


def network_info():
    """Get hostname and network interface information as dataframe.

    Returns:
        tuple: (hostname, network_dataframe)
    """
    try:
        # Get hostname
        hostname = socket.gethostname()

        # Create network data
        network_data = []

        # Get network interfaces
        for interface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:  # IPv4
                    # Skip loopback and internal addresses
                    if not addr.address.startswith(
                        "127."
                    ) and not addr.address.startswith("169.254."):
                        network_data.append(
                            {
                                "Type": "IPv4",
                                "Interface": interface,
                                "Address": addr.address,
                            }
                        )
                elif addr.family == socket.AF_INET6:  # IPv6
                    # Skip loopback and link-local addresses
                    if not addr.address.startswith(
                        "::1"
                    ) and not addr.address.startswith("fe80:"):
                        network_data.append(
                            {
                                "Type": "IPv6",
                                "Interface": interface,
                                "Address": addr.address,
                            }
                        )

        # If no IPv4/IPv6 found, add None entries
        if not any(item["Type"] == "IPv4" for item in network_data):
            network_data.append({"Type": "IPv4", "Interface": "-", "Address": "None"})
        if not any(item["Type"] == "IPv6" for item in network_data):
            network_data.append({"Type": "IPv6", "Interface": "-", "Address": "None"})

        return hostname, pd.DataFrame(network_data)

    except Exception:
        return "unknown", pd.DataFrame(
            [
                {"Type": "IPv4", "Interface": "-", "Address": "None"},
                {"Type": "IPv6", "Interface": "-", "Address": "None"},
            ]
        )


def format_bytes(bytes_value):
    """Format bytes value to human readable string.

    Args:
        bytes_value: Number of bytes

    Returns:
        str: Formatted bytes string
    """
    if bytes_value == 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def formatted_details():
    """Get formatted system health details.

    Returns:
        list: List of formatted system health detail dictionaries
    """
    health_data = summary()

    # Create detailed dataframe
    system_info = [
        {
            "Category": "System",
            "Metric": "CPU Usage",
            "Value": f"{health_data['system']['cpu_percent']:.1f}%",
        },
        {
            "Category": "System",
            "Metric": "Memory Usage",
            "Value": f"{health_data['system']['memory_percent']:.1f}%",
        },
        {
            "Category": "System",
            "Metric": "Memory Total",
            "Value": format_bytes(health_data["system"]["memory_total"]),
        },
        {
            "Category": "System",
            "Metric": "Memory Used",
            "Value": format_bytes(health_data["system"]["memory_used"]),
        },
        {
            "Category": "System",
            "Metric": "Memory Available",
            "Value": format_bytes(health_data["system"]["memory_available"]),
        },
        {
            "Category": "System",
            "Metric": "Load Average (1m)",
            "Value": f"{health_data['system']['load_1m']:.2f}",
        },
        {
            "Category": "System",
            "Metric": "Load Average (5m)",
            "Value": f"{health_data['system']['load_5m']:.2f}",
        },
        {
            "Category": "System",
            "Metric": "Load Average (15m)",
            "Value": f"{health_data['system']['load_15m']:.2f}",
        },
        {
            "Category": "System",
            "Metric": "CPU Cores",
            "Value": health_data["system"]["num_cpus"],
        },
        {
            "Category": "System",
            "Metric": "Uptime",
            "Value": health_data["system"]["uptime"],
        },
        {
            "Category": "Process",
            "Metric": "CPU Usage",
            "Value": f"{health_data['process']['cpu_percent']:.1f}%",
        },
        {
            "Category": "Process",
            "Metric": "Memory Usage",
            "Value": f"{health_data['process']['memory_percent']:.1f}%",
        },
        {
            "Category": "Process",
            "Metric": "Memory RSS",
            "Value": format_bytes(health_data["process"]["memory_rss"]),
        },
        {
            "Category": "Process",
            "Metric": "Memory VMS",
            "Value": format_bytes(health_data["process"]["memory_vms"]),
        },
        {
            "Category": "Process",
            "Metric": "Threads",
            "Value": health_data["process"]["threads"],
        },
        {
            "Category": "Process",
            "Metric": "File Descriptors",
            "Value": health_data["process"]["file_descriptors"],
        },
        {
            "Category": "Disk",
            "Metric": "Root Usage",
            "Value": f"{health_data['disk']['root_percent']:.1f}%",
        },
        {
            "Category": "Disk",
            "Metric": "Root Used",
            "Value": format_bytes(health_data["disk"]["root_used"]),
        },
        {
            "Category": "Disk",
            "Metric": "Root Total",
            "Value": format_bytes(health_data["disk"]["root_total"]),
        },
    ]

    return system_info


def system_health_history(cutoff_minutes=15):
    """Get history for system health metrics.

    Args:
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        dict: Dictionary with system health metrics history data
    """
    # Get system CPU history
    system_cpu_timestamps, system_cpu_values = history.data(
        "github_hetzner_runners_system_cpu_percent",
        cutoff_minutes=cutoff_minutes,
    )

    # Get system memory history
    system_memory_timestamps, system_memory_values = history.data(
        "github_hetzner_runners_system_memory_percent",
        cutoff_minutes=cutoff_minutes,
    )

    # Get process CPU history
    process_cpu_timestamps, process_cpu_values = history.data(
        "github_hetzner_runners_process_cpu_percent",
        cutoff_minutes=cutoff_minutes,
    )

    # Get process memory history
    process_memory_timestamps, process_memory_values = history.data(
        "github_hetzner_runners_process_memory_percent",
        cutoff_minutes=cutoff_minutes,
    )

    # Get root disk history
    root_disk_timestamps, root_disk_values = history.data(
        "github_hetzner_runners_system_root_disk_percent",
        cutoff_minutes=cutoff_minutes,
    )

    return {
        "System CPU": {
            "timestamps": system_cpu_timestamps,
            "values": system_cpu_values,
        },
        "System Memory": {
            "timestamps": system_memory_timestamps,
            "values": system_memory_values,
        },
        "Process CPU": {
            "timestamps": process_cpu_timestamps,
            "values": process_cpu_values,
        },
        "Process Memory": {
            "timestamps": process_memory_timestamps,
            "values": process_memory_values,
        },
        "Root Disk": {
            "timestamps": root_disk_timestamps,
            "values": root_disk_values,
        },
    }
