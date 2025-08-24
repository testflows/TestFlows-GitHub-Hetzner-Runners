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
import os
import sys
import time
import weakref
import logging
import threading

import streamlit as st


# Add the project root to sys.path
project_root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now try absolute imports
import testflows.github.hetzner.runners.dashboard2 as dashboard
import testflows.github.hetzner.runners.dashboard2.panels.header as header
import testflows.github.hetzner.runners.dashboard2.panels.footer as footer
import testflows.github.hetzner.runners.dashboard2.panels.gauges as gauges
import testflows.github.hetzner.runners.dashboard2.bootstrap as bootstrap


def configure_page():
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title="GitHub Hetzner Runners Dashboard",
        page_icon=None,
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


def auto_refresh():
    """Handle automatic refresh of the dashboard based on selected interval."""
    # Get the selected update interval (in seconds)
    update_interval = st.session_state.get("update_interval", 5)

    # Simple auto-refresh: sleep and rerun
    time.sleep(update_interval)
    st.rerun()


def main():
    """Main dashboard function."""
    # Set up logging for debug messages
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("🚀 Streamlit Dashboard Main Function Called")

    try:
        configure_page()
        header.render()
        gauges.render()
        footer.render()
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
