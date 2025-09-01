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
import pandas as pd
from datetime import datetime, timedelta
import logging

from .. import metrics
from ..colors import STREAMLIT_COLORS, STATE_COLORS
from .utils import chart, render as render_utils, data
from .utils.metrics import StateMetric, SimpleMetric, CombinedMetric


# Create metric abstractions
runners_states_metric = StateMetric(
    "github_hetzner_runners_runners_total", ["online", "offline"]
)

busy_metric = SimpleMetric("github_hetzner_runners_runners_busy")

# Combine state metrics with busy metric
runners_combined_metric = CombinedMetric(runners_states_metric, [busy_metric])


def render_runners_metrics():
    """Render the runners metrics header in an isolated fragment for optimal performance."""
    try:
        # Get current runners summary
        runners_summary = metrics.get_runners_summary()

        # Get busy runners count
        busy_runners = (
            metrics.get_metric_value("github_hetzner_runners_runners_busy") or 0
        )

        # Build metrics data
        metrics_data = [
            {"label": "Total", "value": runners_summary["total"]},
            {
                "label": "Online",
                "value": runners_summary["by_status"].get("online", 0),
            },
            {
                "label": "Offline",
                "value": runners_summary["by_status"].get("offline", 0),
            },
            {"label": "Busy", "value": int(busy_runners)},
        ]

        render_utils.render_metrics_columns(metrics_data)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering runners metrics: {e}")
        st.error(f"Error rendering runners metrics: {e}")


def render_runners_chart():
    """Render the runners chart using Altair for proper multi-line visualization."""
    try:
        # Get DataFrame using the simple abstraction
        df = runners_combined_metric.get_dataframe()

        # Create color mapping for runner states
        color_domain = ["online", "offline", "busy"]
        color_range = [
            STREAMLIT_COLORS["success"],  # Green for online
            STREAMLIT_COLORS["error"],  # Red for offline
            STREAMLIT_COLORS["warning"],  # Orange for busy
        ]

        def create_chart():
            return chart.create_time_series_chart(
                df=df,
                y_title="Number of Runners",
                color_column="Status",
                color_domain=color_domain,
                color_range=color_range,
                y_type="count",
            )

        chart.render_chart_with_fallback(
            create_chart,
            "No runners data available yet. The chart will appear once data is collected.",
            "Error rendering runners chart",
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering runners chart: {e}")
        st.error(f"Error rendering runners chart: {e}")


def render_runners_details():
    """Render the runners details as a dataframe."""
    try:
        # Get runner information using the same approach as metrics
        runners_summary = metrics.get_runners_summary()
        runners_info = runners_summary["details"]
        total_runners = runners_summary["total"]

        # Prepare runner data for dataframe with all relevant fields
        formatted_runners = []
        for runner in runners_info:
            runner_id = runner.get("runner_id")
            runner_name = runner.get("name")

            # Get runner labels
            runner_labels_info = metrics.get_metric_info(
                "github_hetzner_runners_runner_labels"
            )
            runner_labels_list = []
            for label_dict in runner_labels_info:
                if (
                    label_dict.get("runner_id") == runner_id
                    and label_dict.get("runner_name") == runner_name
                    and "label" in label_dict
                ):
                    runner_labels_list.append(label_dict["label"])

            # Create formatted runner data with all fields
            formatted_runner = {
                "name": runner.get("name", "Unknown"),
                "status": runner.get("status", "unknown"),
                "runner_id": runner.get("runner_id", ""),
                "os": runner.get("os", ""),
                "repository": runner.get("repository", ""),
                "labels": ", ".join(runner_labels_list) if runner_labels_list else "",
                "busy": (
                    "Busy" if runner.get("busy", "false").lower() == "true" else "Idle"
                ),
                "link": (
                    f"https://github.com/{runner.get('repository', '')}/settings/actions/runners/{runner.get('runner_id', '')}"
                    if runner.get("repository") and runner.get("runner_id")
                    else ""
                ),
            }

            # Add any additional fields from the original runner data
            for key, value in runner.items():
                if key not in formatted_runner and value:
                    formatted_runner[key] = str(value)

            formatted_runners.append(formatted_runner)

        render_utils.render_details_dataframe(
            items=formatted_runners,
            title="Runner Details",
            name_key="name",
            status_key="status",
            link_keys=["link"],
        )

        # Add standby runner information
        try:
            # Check for standby runners in the current runners list
            standby_runners = [
                r
                for r in formatted_runners
                if r.get("name", "").startswith("github-hetzner-runner-standby-")
            ]

            if standby_runners:
                st.subheader("Standby Runners")

                # Create standby runner metrics
                standby_runner_metrics = [
                    {"label": "Total Standby Runners", "value": len(standby_runners)},
                    {
                        "label": "Online Standby",
                        "value": len(
                            [r for r in standby_runners if r.get("status") == "online"]
                        ),
                    },
                    {
                        "label": "Idle Standby",
                        "value": len(
                            [r for r in standby_runners if r.get("busy") == "Idle"]
                        ),
                    },
                ]

                render_utils.render_metrics_columns(standby_runner_metrics)

                # Show standby runners by status
                standby_by_status = {}
                for runner in standby_runners:
                    status = runner.get("status", "unknown")
                    standby_by_status[status] = standby_by_status.get(status, 0) + 1

                if standby_by_status:
                    st.write("**Standby Runners by Status:**")
                    for status, count in standby_by_status.items():
                        st.write(f"- {status}: {count}")
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.debug(f"Could not display standby runner summary: {e}")

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering runners details: {e}")
        st.error(f"Error rendering runners details: {e}")


def render():
    """Render the runners panel in Streamlit.

    This function creates a Streamlit-compatible version of the runners panel
    that maintains all the functionality of the original dashboard panel.
    """
    render_utils.render_panel_with_fragments(
        title="Runners",
        metrics_func=render_runners_metrics,
        chart_func=render_runners_chart,
        details_func=render_runners_details,
        error_message="Error rendering runners panel",
    )
