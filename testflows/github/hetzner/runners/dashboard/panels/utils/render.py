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
from typing import Callable, List, Dict, Any


def render_panel_with_fragments(
    title: str,
    metrics_func: Callable = None,
    chart_func: Callable = None,
    details_func: Callable = None,
    error_message: str = "Error rendering panel",
):
    """Render a panel with standardized structure and error handling.

    Args:
        title: Panel title
        metrics_func: Function to render metrics section
        chart_func: Function to render chart section
        details_func: Function to render details section
        error_message: Base error message for exceptions
    """
    logger = logging.getLogger(__name__)

    try:
        with st.container(border=True):
            st.header(title)

            # Render metrics if provided
            if metrics_func:
                metrics_func()

            # Render chart if provided
            if chart_func:
                chart_func()

            # Render details if provided
            if details_func:
                details_func()

    except Exception as e:
        logger.exception(f"{error_message}: {e}")
        st.error(f"{error_message}: {e}")


def render_metrics_columns(metrics_data: List[Dict[str, Any]]):
    """Render metrics in columns with standardized layout.

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
        else:
            # Use TextColumn for all other fields
            column_config[col_name] = st.column_config.TextColumn(
                col_name, width="medium"
            )

    # Display the dataframe
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config=column_config,
    )


def render_expandable_details(
    items: List[Dict[str, Any]],
    title_prefix: str = "Item",
    status_key: str = "status",
    name_key: str = "name",
    content_builder: Callable = None,
):
    """Render expandable details for a list of items.

    Args:
        items: List of item dictionaries
        title_prefix: Prefix for expander title
        status_key: Key for status in item dict
        name_key: Key for name in item dict
        content_builder: Function to build content for each item
    """
    if not items:
        st.info("No items found")
        return

    st.subheader("Details")

    for item in items:
        try:
            name = item.get(name_key, "Unknown")
            status = item.get(status_key, "unknown")

            # Create expander title
            expander_title = f"{title_prefix}: {name} ({status})"

            with st.expander(expander_title, expanded=False):
                if content_builder:
                    content_builder(item)
                else:
                    # Default content builder - just show all key-value pairs
                    content_lines = []
                    for key, value in item.items():
                        if key not in [name_key, status_key]:
                            content_lines.append(f"**{key.title()}:** {value}")

                    if content_lines:
                        st.markdown("  \n".join(content_lines))

        except Exception as e:
            logging.exception(f"Error processing item: {item}")
            continue


def render_with_error_handling(
    func: Callable,
    error_message: str = "Error occurred",
    fallback_message: str = None,
):
    """Render a function with standardized error handling.

    Args:
        func: Function to render
        error_message: Base error message
        fallback_message: Message to show on error (if None, shows error)
    """
    try:
        return func()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"{error_message}: {e}")

        if fallback_message:
            st.info(fallback_message)
        else:
            st.error(f"{error_message}: {e}")

        return None
