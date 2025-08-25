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
import logging
from typing import Callable, List, Dict, Any


def render_panel_with_fragments(
    title: str,
    metrics_func: Callable = None,
    chart_func: Callable = None,
    details_func: Callable = None,
    error_message: str = "Error rendering panel",
    base_height: int = 800,
    max_height: int = 1200,
    item_count_estimator: Callable = None,
):
    """Render a panel with standardized structure and error handling.

    Args:
        title: Panel title
        metrics_func: Function to render metrics section
        chart_func: Function to render chart section
        details_func: Function to render details section
        error_message: Base error message for exceptions
        base_height: Base height for panels without details (default: 800)
        max_height: Maximum height for panels with details (default: 1200)
        item_count_estimator: Function that returns estimated number of items in details
    """
    logger = logging.getLogger(__name__)

    try:
        # Calculate dynamic height based on whether details are present
        if base_height is None:
            container_height = None
        else:
            if details_func:
                # Estimate number of items if estimator is provided
                item_count = 0
                if item_count_estimator:
                    try:
                        item_count = item_count_estimator()
                    except Exception:
                        # If estimator fails, use default
                        item_count = 0

                # Calculate height based on item count
                if item_count == 0:
                    # No items, use base height
                    container_height = base_height
                elif item_count <= 3:
                    # Few items, add moderate height
                    container_height = min(base_height + 150, max_height)
                elif item_count <= 8:
                    # Medium number of items, add more height
                    container_height = min(base_height + 300, max_height)
                else:
                    # Many items, use maximum height
                    container_height = max_height
            else:
                # For panels without details (like cost), use base height
                container_height = base_height

        with st.container(height=container_height, border=True):
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


def create_fragment_wrapper(func: Callable, update_interval: int = 5):
    """Create a fragment wrapper for a function with standardized update interval.

    Args:
        func: Function to wrap in fragment
        update_interval: Update interval in seconds

    Returns:
        Callable: Wrapped function with fragment decorator
    """
    from streamlit import fragment

    @fragment(run_every=update_interval)
    def wrapped_func():
        return func()

    return wrapped_func


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
