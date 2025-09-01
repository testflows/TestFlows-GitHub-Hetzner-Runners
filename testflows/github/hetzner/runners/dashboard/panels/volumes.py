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

from .. import metrics
from .utils import data, chart, render as render_utils
from ..colors import STATE_COLORS


def create_volume_dataframe(history_data):
    """Create DataFrame from volume history data."""
    return chart.create_dataframe_from_history(history_data)


def get_volume_history_data():
    """Get volume history data for plotting."""
    states = ["available", "creating", "attached"]
    return data.get_metric_history_for_states(
        "github_hetzner_runners_volumes_total", states, cutoff_minutes=15
    )


def get_current_volume_data():
    """Get current volume data without caching to ensure fresh data."""
    states = ["available", "creating", "attached"]
    current_values, current_time = data.get_current_metric_values(
        "github_hetzner_runners_volumes_total", states
    )

    # Get history data for plotting
    history_data = get_volume_history_data()

    return history_data, current_values, current_time


def render_volume_metrics():
    """Render the volume metrics header in an isolated fragment for optimal performance."""
    try:
        # Get current volume summary
        volumes_summary = metrics.get_volumes_summary()

        # Build metrics data
        metrics_data = [
            {"label": "Total", "value": volumes_summary["total"]},
            {
                "label": "Available",
                "value": volumes_summary["by_status"].get("available", 0),
            },
            {
                "label": "Attached",
                "value": volumes_summary["by_status"].get("attached", 0),
            },
            {
                "label": "Creating",
                "value": volumes_summary["by_status"].get("creating", 0),
            },
        ]

        render_utils.render_metrics_columns(metrics_data)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering volume metrics: {e}")
        st.error(f"Error rendering volume metrics: {e}")


def render_volume_chart():
    """Render the volume chart using Altair for proper multi-line visualization."""
    try:
        # Get fresh data
        history_data, current_values, current_time = get_current_volume_data()

        # Create DataFrame for the chart
        df = create_volume_dataframe(history_data)

        # Create color mapping for volume states
        color_domain = ["available", "creating", "attached"]
        color_range = [
            STATE_COLORS.get("available", "#00ff00"),
            STATE_COLORS.get("creating", "#ffff00"),
            STATE_COLORS.get("attached", "#0000ff"),
        ]

        def create_chart():
            return chart.create_time_series_chart(
                df=df,
                y_title="Number of Volumes",
                color_column="Status",
                color_domain=color_domain,
                color_range=color_range,
                y_type="count",
            )

        chart.render_chart_with_fallback(
            create_chart,
            "No volume data available yet. The chart will appear once data is collected.",
            "Error rendering volume chart",
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering volume chart: {e}")
        st.error(f"Error rendering volume chart: {e}")


def render_volume_details():
    """Render the volume details as a dataframe."""
    try:
        # Get volume information using the same approach as metrics
        volumes_summary = metrics.get_volumes_summary()
        volumes_info = volumes_summary["details"]
        total_volumes = volumes_summary["total"]

        # Prepare volume data for dataframe with all relevant fields
        formatted_volumes = []
        for volume in volumes_info:
            volume_id = volume.get("volume_id")
            volume_name = volume.get("name")

            # Get volume labels
            volume_labels_info = metrics.get_metric_info(
                "github_hetzner_runners_volume_labels"
            )
            volume_labels_list = []
            for label_dict in volume_labels_info:
                if (
                    label_dict.get("volume_id") == volume_id
                    and label_dict.get("volume_name") == volume_name
                    and "label" in label_dict
                ):
                    volume_labels_list.append(label_dict["label"])

            # Create formatted volume data with all fields
            formatted_volume = {
                "name": volume.get("name", "Unknown"),
                "status": volume.get("status", "unknown"),
                "volume_id": volume.get("volume_id", ""),
                "size": volume.get("size", ""),
                "location": volume.get("location", ""),
                "format": volume.get("format", ""),
                "server_name": volume.get("server_name", ""),
                "server_id": volume.get("server_id", ""),
                "created": volume.get("created", ""),
                "labels": ", ".join(volume_labels_list) if volume_labels_list else "",
            }

            formatted_volumes.append(formatted_volume)

        render_utils.render_details_dataframe(
            items=formatted_volumes,
            title="Volume Details",
            name_key="name",
            status_key="status",
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering volume details: {e}")
        st.error(f"Error rendering volume details: {e}")


def render():
    """Render the volumes panel."""
    st.header("Volumes")

    # Render metrics
    render_volume_metrics()

    # Render chart
    render_volume_chart()

    # Render details
    render_volume_details()
