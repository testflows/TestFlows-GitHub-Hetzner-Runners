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

import logging
import streamlit as st
import pandas as pd
from datetime import datetime
import socket
import psutil
from datetime import datetime, timedelta

from .. import metrics
from .utils import render as render_utils, data, chart
from ..colors import COLORS, STREAMLIT_COLORS


def get_network_info():
    """Get hostname and network interface information as dataframe."""
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

    except Exception as e:
        logging.exception(f"Error getting network info: {e}")
        return "unknown", pd.DataFrame(
            [
                {"Type": "IPv4", "Interface": "-", "Address": "None"},
                {"Type": "IPv6", "Interface": "-", "Address": "None"},
            ]
        )


def get_system_health_data():
    """Get current system health data for display."""
    current_time = datetime.now()

    # Get system metrics
    system_cpu = (
        metrics.get_metric_value("github_hetzner_runners_system_cpu_percent") or 0
    )
    system_memory_percent = (
        metrics.get_metric_value("github_hetzner_runners_system_memory_percent") or 0
    )
    system_memory_total = (
        metrics.get_metric_value("github_hetzner_runners_system_memory_total_bytes")
        or 0
    )
    system_memory_used = (
        metrics.get_metric_value("github_hetzner_runners_system_memory_used_bytes") or 0
    )
    system_memory_available = (
        metrics.get_metric_value("github_hetzner_runners_system_memory_available_bytes")
        or 0
    )

    # Get process metrics
    process_cpu = (
        metrics.get_metric_value("github_hetzner_runners_process_cpu_percent") or 0
    )
    process_memory_percent = (
        metrics.get_metric_value("github_hetzner_runners_process_memory_percent") or 0
    )
    process_memory_rss = (
        metrics.get_metric_value("github_hetzner_runners_process_memory_rss_bytes") or 0
    )
    process_memory_vms = (
        metrics.get_metric_value("github_hetzner_runners_process_memory_vms_bytes") or 0
    )
    process_threads = (
        metrics.get_metric_value("github_hetzner_runners_process_num_threads") or 0
    )
    process_fds = (
        metrics.get_metric_value("github_hetzner_runners_process_num_fds") or 0
    )

    # Get system load averages
    load_1m = (
        metrics.get_metric_value("github_hetzner_runners_system_load_average_1m") or 0
    )
    load_5m = (
        metrics.get_metric_value("github_hetzner_runners_system_load_average_5m") or 0
    )
    load_15m = (
        metrics.get_metric_value("github_hetzner_runners_system_load_average_15m") or 0
    )

    # Get system info
    num_cpus = metrics.get_metric_value("github_hetzner_runners_system_num_cpus") or 0
    boot_time = metrics.get_metric_value("github_hetzner_runners_system_boot_time") or 0

    # Get disk metrics for root filesystem
    root_disk_percent = (
        metrics.get_metric_value(
            "github_hetzner_runners_system_disk_percent", {"mountpoint": "/"}
        )
        or 0
    )
    root_disk_used = (
        metrics.get_metric_value(
            "github_hetzner_runners_system_disk_used_bytes", {"mountpoint": "/"}
        )
        or 0
    )
    root_disk_total = (
        metrics.get_metric_value(
            "github_hetzner_runners_system_disk_total_bytes", {"mountpoint": "/"}
        )
        or 0
    )

    # Calculate uptime
    uptime_seconds = current_time.timestamp() - boot_time if boot_time > 0 else 0
    uptime_days = int(uptime_seconds // 86400)
    uptime_hours = int((uptime_seconds % 86400) // 3600)
    uptime_minutes = int((uptime_seconds % 3600) // 60)
    uptime_str = f"{uptime_days}d {uptime_hours}h {uptime_minutes}m"

    # Format memory sizes
    def format_bytes(bytes_value):
        if bytes_value == 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"

    return {
        "timestamp": current_time,
        "system": {
            "cpu_percent": system_cpu,
            "memory_percent": system_memory_percent,
            "memory_total": format_bytes(system_memory_total),
            "memory_used": format_bytes(system_memory_used),
            "memory_available": format_bytes(system_memory_available),
            "load_1m": load_1m,
            "load_5m": load_5m,
            "load_15m": load_15m,
            "num_cpus": int(num_cpus),
            "uptime": uptime_str,
        },
        "process": {
            "cpu_percent": process_cpu,
            "memory_percent": process_memory_percent,
            "memory_rss": format_bytes(process_memory_rss),
            "memory_vms": format_bytes(process_memory_vms),
            "threads": int(process_threads),
            "file_descriptors": int(process_fds),
        },
        "disk": {
            "root_percent": root_disk_percent,
            "root_used": format_bytes(root_disk_used),
            "root_total": format_bytes(root_disk_total),
        },
    }


def get_system_health_history_data(cutoff_minutes=15):
    """Get system health history data for plotting.

    Args:
        cutoff_minutes: Number of minutes to keep in history

    Returns:
        dict: Dictionary with system health metrics history data
    """
    metric_names = [
        "github_hetzner_runners_system_cpu_percent",
        "github_hetzner_runners_system_memory_percent",
        "github_hetzner_runners_process_cpu_percent",
        "github_hetzner_runners_process_memory_percent",
        "github_hetzner_runners_system_root_disk_percent",
    ]

    # Update system health metrics and store in history
    data.get_current_multiple_metrics(metric_names)

    return data.get_multiple_metrics_history(metric_names, cutoff_minutes)


def create_system_health_dataframe(history_data):
    """Create a pandas DataFrame for the system health data with proper time formatting."""
    if not history_data:
        return pd.DataFrame({"Time": pd.to_datetime([]), "Metric": [], "Value": []})

    # Map metric names to display names
    metric_to_display = {
        "github_hetzner_runners_system_cpu_percent": "System CPU",
        "github_hetzner_runners_system_memory_percent": "System Memory",
        "github_hetzner_runners_process_cpu_percent": "Process CPU",
        "github_hetzner_runners_process_memory_percent": "Process Memory",
        "github_hetzner_runners_system_root_disk_percent": "Root Disk",
    }

    # Collect all data points
    all_data = []

    for metric_name, data in history_data.items():
        display_name = metric_to_display.get(metric_name, metric_name)
        timestamps = data.get("timestamps", [])
        values = data.get("values", [])

        if timestamps and values and len(timestamps) == len(values):
            for ts, val in zip(timestamps, values):
                try:
                    all_data.append(
                        {
                            "Time": pd.to_datetime(ts),
                            "Metric": display_name,
                            "Value": float(val),
                        }
                    )
                except (ValueError, TypeError):
                    continue

    if not all_data:
        return pd.DataFrame({"Time": pd.to_datetime([]), "Metric": [], "Value": []})

    # Create DataFrame and sort by time
    df = pd.DataFrame(all_data)
    df = df.sort_values("Time")

    return df


def render_system_health_metrics():
    """Render the system health metrics header."""
    try:
        # Get current system health data
        health_data = get_system_health_data()
        network_info = get_network_info()

        # Build metrics data
        metrics_data = [
            {
                "label": "System CPU",
                "value": f"{health_data['system']['cpu_percent']:.1f}%",
            },
            {
                "label": "System Memory",
                "value": f"{health_data['system']['memory_percent']:.1f}%",
            },
            {
                "label": "Process CPU",
                "value": f"{health_data['process']['cpu_percent']:.1f}%",
            },
            {
                "label": "Process Memory",
                "value": f"{health_data['process']['memory_percent']:.1f}%",
            },
            {
                "label": "Root Disk",
                "value": f"{health_data['disk']['root_percent']:.1f}%",
            },
            {"label": "Load (1m)", "value": f"{health_data['system']['load_1m']:.2f}"},
        ]

        render_utils.render_metrics_columns(metrics_data)

        # Display network info
        hostname, network_df = get_network_info()
        st.write(f"**Hostname:** {hostname}")
        st.write("**Network Interfaces:**")
        st.dataframe(
            network_df,
            hide_index=True,
            use_container_width=False,
            column_config={
                "Type": st.column_config.TextColumn("Type", width="small"),
                "Interface": st.column_config.TextColumn("Interface", width="small"),
                "Address": st.column_config.TextColumn("Address", width="medium"),
            },
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering system health metrics: {e}")
        st.error(f"Error rendering system health metrics: {e}")


def render_system_health_chart():
    """Render the system health chart using Altair for proper multi-line visualization."""
    try:
        # Get fresh data
        history_data = get_system_health_history_data()

        # Create DataFrame for the chart
        df = create_system_health_dataframe(history_data)

        # Create color mapping for metrics
        color_domain = [
            "System CPU",
            "System Memory",
            "Process CPU",
            "Process Memory",
            "Root Disk",
        ]
        color_range = [
            STREAMLIT_COLORS["primary"],  # Blue for system CPU
            STREAMLIT_COLORS["secondary"],  # Orange for system memory
            STREAMLIT_COLORS["success"],  # Green for process CPU
            STREAMLIT_COLORS["info"],  # Light blue for process memory
            STREAMLIT_COLORS["warning"],  # Yellow for root disk
        ]

        # Always create a chart, even with empty data
        if df.empty:
            # Create empty chart with proper structure
            empty_df = pd.DataFrame(
                {
                    "Time": pd.to_datetime([pd.Timestamp.now()]),
                    "Metric": ["System CPU"],
                    "Count": [0.0],
                }
            )
            chart_obj = chart.create_time_series_chart(
                df=empty_df,
                y_title="Percentage (%)",
                color_column="Metric",
                color_domain=color_domain,
                color_range=color_range,
                y_type="value",
            )
        else:
            # Rename "Value" column to "Count" to match expected column name
            df_chart = df.copy()
            df_chart = df_chart.rename(columns={"Value": "Count"})

            chart_obj = chart.create_time_series_chart(
                df=df_chart,
                y_title="Percentage (%)",
                color_column="Metric",
                color_domain=color_domain,
                color_range=color_range,
                y_type="value",
            )

        if chart_obj is not None:
            st.altair_chart(chart_obj, use_container_width=True)
        else:
            st.info(
                "No system health data available yet. The chart will appear once data is collected."
            )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering system health chart: {e}")
        st.error(f"Error rendering system health chart: {e}")


def render_system_health_dataframe():
    """Render the system health detailed dataframe."""
    try:
        # Get current system health data
        health_data = get_system_health_data()

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
                "Value": health_data["system"]["memory_total"],
            },
            {
                "Category": "System",
                "Metric": "Memory Used",
                "Value": health_data["system"]["memory_used"],
            },
            {
                "Category": "System",
                "Metric": "Memory Available",
                "Value": health_data["system"]["memory_available"],
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
                "Value": health_data["process"]["memory_rss"],
            },
            {
                "Category": "Process",
                "Metric": "Memory VMS",
                "Value": health_data["process"]["memory_vms"],
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
                "Value": health_data["disk"]["root_used"],
            },
            {
                "Category": "Disk",
                "Metric": "Root Total",
                "Value": health_data["disk"]["root_total"],
            },
        ]

        df = pd.DataFrame(system_info)

        # Display the dataframe
        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Category": st.column_config.TextColumn("Category", width="medium"),
                "Metric": st.column_config.TextColumn("Metric", width="large"),
                "Value": st.column_config.TextColumn("Value", width="medium"),
            },
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering system health dataframe: {e}")
        st.error(f"Error rendering system health dataframe: {e}")


def render():
    """Render the system health panel."""
    st.header("System Health")

    # Render metrics header
    render_system_health_metrics()

    # Render chart
    st.subheader("System Health Trends")
    render_system_health_chart()

    # Render detailed dataframe
    st.subheader("System Health Details")
    render_system_health_dataframe()
