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
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import threading
import sys
import os
from typing import Optional
import logging
import asyncio
import weakref
from tornado import web

# Add the project root to sys.path
project_root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now try absolute imports
import testflows.github.hetzner.runners.dashboard2.bootstrap as bootstrap
import testflows.github.hetzner.runners.dashboard2.metrics as metrics
from testflows.github.hetzner.runners.dashboard2.colors import (
    COLORS,
    STATE_COLORS,
    STREAMLIT_COLORS,
)
from testflows.github.hetzner.runners import __version__


def configure_page():
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title="GitHub Hetzner Runners Dashboard",
        page_icon="🚀",
        layout="wide",
    )

    # Hide only essential Streamlit UI elements (minimal CSS)
    st.markdown(
        """
    <style>
    .stAppDeployButton {
        visibility: hidden;
    }
    .footer-center {
        text-align: center;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def render_header():
    """Render the header section with logo, title, and update interval selector."""
    # Logo using st.image for compatibility
    st.image(
        "https://raw.githubusercontent.com/testflows/TestFlows-ArtWork/refs/heads/master/images/logo.png",
        width=80,
    )

    # Header section
    col1, col2 = st.columns([3, 1], gap="medium")

    with col1:
        st.title("GitHub Hetzner Runners Dashboard")

    with col2:
        st.caption("update interval:")
        st.selectbox(
            "Update Interval",
            options=[5, 10, 30, 60, 300],
            format_func=lambda x: f"{x} seconds" if x < 60 else f"{x//60} minutes",
            index=0,
            key="update_interval",
            label_visibility="collapsed",
        )

    st.divider()


def render_metrics_gauges():
    """Render the metrics gauges section."""
    logger = logging.getLogger(__name__)

    try:
        # Get metrics data
        heartbeat_status, _ = metrics.get_heartbeat_status()
        cost_summary = metrics.get_cost_summary()
        servers_summary = metrics.get_servers_summary()
        runners_summary = metrics.get_runners_summary()
        jobs_summary = metrics.get_jobs_summary()
        errors_summary = metrics.get_errors_summary()

    except Exception as e:
        logger.exception(f"Error fetching metrics: {e}")
        print(f"❌ Error fetching metrics: {e}")
        st.error(f"Error fetching metrics: {e}")
        return

    # Gauges in columns
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7, gap="medium")

    with col1:
        st.caption("Heartbeat")
        # Use st.text instead of st.markdown for heartbeat
        if heartbeat_status:
            st.metric(label="Heartbeat", value="🟢", label_visibility="collapsed")
        else:
            st.metric(label="Heartbeat", value="🔴", label_visibility="collapsed")

    with col2:
        st.caption("Cost (€/h)")
        st.metric(
            label="Cost (€/h)",
            value=f"{cost_summary['hourly']:.3f}",
            label_visibility="collapsed",
        )

    with col3:
        st.caption("Servers")
        st.metric(
            label="Servers",
            value=servers_summary["total"],
            label_visibility="collapsed",
        )

    with col4:
        st.caption("Runners")
        st.metric(
            label="Runners",
            value=runners_summary["total"],
            label_visibility="collapsed",
        )

    with col5:
        st.caption("Queued Jobs")
        st.metric(
            label="Queued Jobs",
            value=jobs_summary["queued"],
            label_visibility="collapsed",
        )

    with col6:
        st.caption("Running Jobs")
        st.metric(
            label="Running Jobs",
            value=jobs_summary["running"],
            label_visibility="collapsed",
        )

    with col7:
        st.caption("Scale Up Errors")
        st.metric(
            label="Scale Up Errors",
            value=errors_summary["last_hour"],
            label_visibility="collapsed",
        )

    st.divider()


def auto_refresh():
    """Handle automatic refresh of the dashboard based on selected interval."""
    # Get the selected update interval (in seconds)
    update_interval = st.session_state.get("update_interval", 5)

    # Simple auto-refresh: sleep and rerun
    time.sleep(update_interval)
    st.rerun()


def render_footer():
    """Render the footer section with copyright and version information."""
    with st.container():
        st.caption(f"© 2023-{datetime.now().year} Katteli Inc. All rights reserved.")
        st.caption(f"TestFlows GitHub Hetzner Runners v{__version__}")


def main():
    """Main dashboard function."""
    # Set up logging for debug messages
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("🚀 Streamlit Dashboard Main Function Called")

    try:
        configure_page()
        render_header()
        render_metrics_gauges()
        render_footer()
        auto_refresh()

        logger.info("✅ Dashboard rendered successfully")

    except Exception as e:
        logger.exception(f"❌ Error in dashboard main: {e}")
        st.error(f"Dashboard Error: {e}")
        raise


def start_http_server(
    port: int = 8501, host: str = "0.0.0.0", config=None
) -> threading.Thread:
    """Start the Streamlit dashboard HTTP server in a daemon thread.

    This function follows the same signature as the original Dash dashboard
    to maintain compatibility with the main application.

    Args:
        port: The port to listen on, default: 8501
        host: The host to bind to, default: '0.0.0.0'
        config: Configuration object (not used in Streamlit but kept for compatibility)

    Returns:
        threading.Thread: The thread running the dashboard server
    """
    # Store config for potential future use
    global dashboard_config
    dashboard_config = config

    # Container to store the server instance
    server_container = {"server": None}

    def run_streamlit_in_thread():
        """Run Streamlit using bootstrap.py in the current thread."""
        logger = logging.getLogger(__name__)
        # Get the absolute path to the dashboard script
        script_path = os.path.abspath(__file__)
        try:
            # Configure Streamlit server options
            flag_options = {
                "server_port": port,
                "server_address": host,
                "server_headless": True,
                "browser_gatherUsageStats": False,
                "logger_level": "info",
            }

            # Load configuration options
            bootstrap.load_config_options(flag_options)

            # Get weak reference to current thread for cleanup
            current_thread = threading.current_thread()
            thread_ref = weakref.ref(current_thread)

            # Run the server using bootstrap - this will handle cleanup automatically
            server = bootstrap.run_in_thread(
                main_script_path=script_path,
                is_hello=False,
                args=[],
                flag_options=flag_options,
                thread_ref=thread_ref,
            )

            # Store server reference for potential external access
            server_container["server"] = server

        except Exception as e:
            logger.exception(f"Error starting Streamlit dashboard: {e}")

    # Start Streamlit in a daemon thread
    thread = threading.Thread(target=run_streamlit_in_thread, daemon=True)

    # Store server container reference on thread for external access
    thread.server_container = server_container

    thread.start()

    return thread


# Global variable to store config
dashboard_config = None


if __name__ == "__main__":
    main()
