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

import streamlit as st

from .. import metrics
from ..colors import STATE_COLORS
from .utils import chart, renderers


def render_servers_metrics():
    """Render the server metrics header."""

    # Get current server summary
    servers_summary = metrics.servers.summary()

    # Build metrics data
    metrics_data = [
        {"label": "Total", "value": servers_summary["total"]},
        {
            "label": "Running",
            "value": servers_summary["by_status"].get("running", 0),
        },
        {
            "label": "Other",
            "value": sum(
                count
                for status, count in servers_summary["by_status"].items()
                if status != "running"
            ),
        },
    ]

    renderers.render_metrics_columns(metrics_data)


def render_servers_chart():
    """Render the server chart."""

    # Get server states history
    states_history = metrics.servers.states_history()
    df = metrics.history.dataframe_for_states(states_history)

    # Create color mapping for server states
    color_domain = ["running", "off", "initializing", "ready", "busy"]
    color_range = [
        STATE_COLORS["running"],
        STATE_COLORS["off"],
        STATE_COLORS["initializing"],
        STATE_COLORS["ready"],
        STATE_COLORS["busy"],
    ]

    def create_chart():
        return chart.create_time_series_chart(
            df=df,
            y_title="Number of Servers",
            color_column="Status",
            color_domain=color_domain,
            color_range=color_range,
            y_type="count",
        )

    renderers.render_chart(
        create_chart,
        "No server data available yet. The chart will appear once data is collected.",
        "rendering server chart",
    )


def render_health_metrics():
    """Render the health metrics header."""

    # Get health metrics
    zombie_total = metrics.servers.zombie_total_count()
    unused_total = metrics.servers.unused_total_count()
    recycled_total = metrics.servers.recycled_total_count()

    # Build metrics data
    metrics_data = [
        {
            "label": "Zombie",
            "value": zombie_total,
            "color": "red" if zombie_total > 0 else "green",
        },
        {
            "label": "Unused",
            "value": unused_total,
            "color": "orange" if unused_total > 0 else "green",
        },
        {
            "label": "Recycled",
            "value": recycled_total,
            "color": "blue",
        },
    ]

    renderers.render_metrics_columns(metrics_data)


def render_health_chart():
    """Render the health metrics chart using Altair."""

    # Get health metrics history data
    health_history = metrics.servers.health_history()
    df = metrics.history.dataframe_for_states(health_history)

    # Create color mapping for health metrics
    health_color_domain = ["zombie", "unused", "recycled"]
    health_color_range = [
        STATE_COLORS["zombie"],
        STATE_COLORS["unused"],
        STATE_COLORS["recycled"],
    ]

    def create_health_chart():
        return chart.create_time_series_chart(
            df=df,
            y_title="Health Metrics",
            color_column="Status",
            color_domain=health_color_domain,
            color_range=health_color_range,
            y_type="count",
        )

    renderers.render_chart(
        create_health_chart,
        "No health metrics data available yet. The chart will appear once data is collected.",
        "rendering health metrics chart",
    )


def render_health_details():
    """Render the health status details as a dataframe."""

    # FIXME: Finish this function !!!!!!!!

    # Get server information
    servers_summary = metrics.servers.summary()
    servers_info = servers_summary["details"]

    if not servers_info:
        st.info("No servers found")
        return

    # Get individual server health data
    zombie_servers = metrics.get.metric_info(
        "github_hetzner_runners_zombie_server_age_seconds"
    )

    unused_runners = metrics.get.metric_info(
        "github_hetzner_runners_unused_runner_age_seconds"
    )
    unused_server_names = set()
    for runner in unused_runners:
        runner_name = runner.get("runner_name", "")
        if "-" in runner_name:
            server_name = runner_name.rsplit("-", 1)[0]
            unused_server_names.add(server_name)

    # Prepare health data for dataframe
    health_data = []

    # Add zombie servers
    for zombie in zombie_servers:
        server_id = zombie.get("server_id")
        if server_id:
            # Find the corresponding server info
            server_info = next(
                (s for s in servers_info if str(s.get("server_id")) == str(server_id)),
                None,
            )

            age_seconds = metrics.servers.age(server_info.get("created"))
            health_data.append(
                {
                    "server_name": server_info.get("name", "Unknown"),
                    "server_id": server_id,
                    "health_status": "zombie",
                    "age_seconds": age_seconds,
                }
            )

    # Add unused runners
    for runner in unused_runners:
        runner_name = runner.get("runner_name", "")
        if "-" in runner_name:
            server_name = runner_name.rsplit("-", 1)[0]
            if server_name in unused_server_names:
                # Find the corresponding server info to get creation time
                server_info = next(
                    (s for s in servers_info if s.get("name") == server_name), None
                )

                age_seconds = metrics.servers.age(
                    server_info.get("created") if server_info else None
                )
                health_data.append(
                    {
                        "server_name": server_name,
                        "server_id": (
                            server_info.get("server_id", "") if server_info else ""
                        ),
                        "health_status": "unused",
                        "age_seconds": age_seconds,
                    }
                )

    # Add recycled servers
    for server in servers_info:
        server_name = server.get("name", "")
        if server_name.startswith("github-hetzner-runner-recycle-"):
            age_seconds = metrics.servers.age(server.get("created"))
            health_data.append(
                {
                    "server_name": server_name,
                    "server_id": server.get("server_id", ""),
                    "health_status": "recycled",
                    "age_seconds": age_seconds,
                }
            )

    # Sort by health status priority (zombie first, then unused, then recycled)
    status_priority = {"zombie": 1, "unused": 2, "recycled": 3}
    health_data.sort(
        key=lambda x: (status_priority.get(x["health_status"], 4), x["server_name"])
    )

    renderers.render_details_dataframe(
        items=health_data,
        title="Health Status Details",
        name_key="server_name",
        status_key="health_status",
    )


def render_servers_details():
    """Render the server details as a dataframe."""

    # Get server details
    servers_details = metrics.servers.summary()["details"]
    formatted_details = metrics.servers.formatted_details(servers_details)

    renderers.render_details_dataframe(
        items=formatted_details,
        title="Server Details",
        name_key="name",
        status_key="status",
    )


def render():
    """Render the servers panel in Streamlit.

    This function creates a Streamlit-compatible version of the servers panel
    that maintains all the functionality of the original dashboard panel.
    """
    # First section: Servers
    renderers.render_panel(
        title="Servers",
        metrics_func=render_servers_metrics,
        chart_func=render_servers_chart,
        details_func=render_servers_details,
        message="rendering servers panel",
    )

    # Second section: Health Status
    renderers.render_panel(
        title="Health Status",
        metrics_func=render_health_metrics,
        chart_func=render_health_chart,
        details_func=render_health_details,
        message="rendering health status panel",
    )
