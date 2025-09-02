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

"""Common rendering utilities for dashboard panels."""

import streamlit as st
import pandas as pd
import logging
from contextlib import contextmanager
from typing import Callable, List, Dict, Any

logger = logging.getLogger(__name__)


@contextmanager
def errors(name: str, _logger: logging.Logger = None):
    """Context manager for consistent error handling in dashboard panels.

    Args:
        name: Descriptive name for the operation (e.g., "rendering cost metrics")
        logger: Logger instance to use. If None, logging is disabled.

    Usage:
        with renderers.errors("rendering cost metrics", logger):
            # Your code here
            pass
    """
    _logger = _logger if _logger is not None else logger
    try:
        yield
    except Exception as e:
        error_msg = f"Error {name}: {e}"
        _logger.exception(error_msg)
        st.error(error_msg)


def render_panel(
    title: str,
    metrics_func: Callable = None,
    chart_func: Callable = None,
    details_func: Callable = None,
    message: str = "rendering panel",
):
    """Render a panel with standardized structure and error handling.

    Args:
        title: Panel title
        metrics_func: Function to render metrics section
        chart_func: Function to render chart section
        details_func: Function to render details section
        message: message for exceptions
    """

    with errors(message):
        with st.container(border=True):
            st.header(title)

            # Render metrics if provided
            if metrics_func:
                with errors(f"rendering {title} metrics"):
                    metrics_func()

            # Render chart if provided
            if chart_func:
                with errors(f"rendering {title} chart"):
                    chart_func()

            # Render details if provided
            if details_func:
                with errors(f"rendering {title} details"):
                    details_func()


def render_metrics(metrics_data: List[Dict[str, Any]]):
    """Render summary header with key values in columns.

    Args:
        metrics_data: List of dictionaries with 'label' and 'value' keys
    """
    if not metrics_data:
        return

    # Create columns based on number of metrics
    cols = st.columns(len(metrics_data))

    for i, metric in enumerate(metrics_data):
        with cols[i]:
            st.metric(
                label=metric.get("label", ""),
                value=metric.get("value", 0),
                delta=metric.get("delta", None),
            )


def render_metrics_columns(metrics_data: List[Dict[str, Any]]):
    """Render summary header with key values in columns.

    Args:
        metrics_data: List of dictionaries with 'label' and 'value' keys
    """
    # FIXME: Deprecated, use render_metrics instead
    render_metrics(metrics_data)


def render_details_dataframe(
    items: List[Dict[str, Any]],
    title: str = "Details",
    name_key: str = "name",
    status_key: str = "status",
    link_keys: List[str] = None,
    additional_columns: Dict[str, str] = None,
):
    """Render details as a dataframe where each item field becomes a column.

    Args:
        items: List of item dictionaries
        title: Title for the details section
        name_key: Key for name in item dict
        status_key: Key for status in item dict
        link_keys: List of keys for link fields in item dict
        additional_columns: Dictionary mapping column names to item keys
    """
    if not items:
        st.info("No items found")
        return

    st.subheader(title)

    # Get all unique keys from all items
    all_keys = set()
    for item in items:
        all_keys.update(item.keys())

    # Sort keys to ensure consistent column order
    sorted_keys = sorted(all_keys)

    # Prepare data for dataframe
    data = []
    for item in items:
        row = {}
        for key in sorted_keys:
            value = item.get(key, "")
            row[key] = value
        data.append(row)

    # Create dataframe
    df = pd.DataFrame(data)

    # Configure column display
    column_config = {}

    # Determine which columns should be link columns
    link_columns = set(link_keys) if link_keys else set()

    for col_name in df.columns:
        if col_name in link_columns:
            # Use LinkColumn for link fields
            column_config[col_name] = st.column_config.LinkColumn(
                col_name, width="small"
            )

    # Display the dataframe
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config=column_config,
    )


def render_chart(
    chart_func,
    no_data_message="No data available yet. The chart will appear once data is collected.",
    message="rendering chart",
):
    """Render a chart with standardized error handling and fallback messages.

    Args:
        chart_func: Function that returns an Altair chart
        no_data_message: Message to show when no data is available
        message: Base message for exceptions
    """
    chart = chart_func()

    if chart is not None:
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info(no_data_message)
