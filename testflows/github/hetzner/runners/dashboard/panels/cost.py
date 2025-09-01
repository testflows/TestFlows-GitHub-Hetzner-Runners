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
from .utils import chart, render as render_utils
from .utils.metrics import ComputedMetric


def compute_total_cost():
    """Compute total cost from all servers."""
    total_cost = 0
    servers_info = metrics.get_metric_info("github_hetzner_runners_server")

    if servers_info:
        for info in servers_info:
            try:
                cost_hourly = float(info.get("cost_hourly", 0))
                total_cost += cost_hourly
            except (ValueError, TypeError):
                continue

    return total_cost


# Create the cost metric abstraction
cost_metric = ComputedMetric("github_hetzner_runners_cost_total", compute_total_cost)


def render_cost_metrics():
    """Render the cost metrics header in an isolated fragment for optimal performance.

    This fragment updates independently from the main dashboard using the same
    refresh interval selected by the user in the header dropdown.
    """
    try:
        # Get current cost summary for display
        cost_summary = metrics.get_cost_summary()

        # Build metrics data
        metrics_data = [
            {
                "label": "Hourly",
                "value": f"€{cost_summary['hourly']:.3f}/h",
            },
            {
                "label": "Daily",
                "value": f"€{cost_summary['daily']:.2f}/day",
            },
            {
                "label": "Monthly",
                "value": f"€{cost_summary['monthly']:.2f}/month",
            },
        ]

        render_utils.render_metrics_columns(metrics_data)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering cost metrics: {e}")
        st.error(f"Error rendering cost metrics: {e}")


def render_cost_chart():
    """Render the cost chart using Altair for proper time series visualization."""
    try:
        # Get DataFrame using the simple abstraction
        df = cost_metric.get_dataframe()

        # Rename column for display
        if not df.empty:
            df = df.rename(columns={"Value": "Total Cost (€/h)"})

        def create_chart():
            return chart.create_time_series_chart(
                df=df,
                y_column="Total Cost (€/h)",
                y_title="Cost (€/h)",
                y_type="price",
            )

        chart.render_chart_with_fallback(
            create_chart,
            "No cost data available yet. The chart will appear once data is collected.",
            "Error rendering cost chart",
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"Error rendering cost chart: {e}")
        st.error(f"Error rendering cost chart: {e}")


def render():
    """Render the cost panel in Streamlit.

    This function creates a Streamlit-compatible version of the cost panel
    that maintains all the functionality of the original dashboard panel.
    """
    render_utils.render_panel_with_fragments(
        title="Estimated Cost",
        metrics_func=render_cost_metrics,
        chart_func=render_cost_chart,
        error_message="Error rendering cost panel",
    )
