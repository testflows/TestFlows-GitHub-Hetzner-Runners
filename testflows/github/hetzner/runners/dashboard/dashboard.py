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
import weakref
import logging
import threading
import importlib
import functools
from types import SimpleNamespace

import streamlit as st


# Add the project root to sys.path
project_root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now try absolute imports
import testflows.github.hetzner.runners.dashboard.bootstrap as bootstrap
import testflows.github.hetzner.runners.dashboard.panels.update_interval as update_interval
import testflows.github.hetzner.runners.dashboard.renderers as renderers
import testflows.github.hetzner.runners.dashboard.metrics.tracker as tracker


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
    div.stButton > button {
        padding: 5px;
        border: none;
        border-bottom: 2px solid lightblue;
        border-radius: 0;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def reload_panels(reload: bool = False):
    """Dynamically reload all panel modules and return them as a namespace."""
    panels = SimpleNamespace()

    # Define panel names and load them
    panel_names = [
        "header",
        "footer",
        "gauges",
        "info",
        "cost",
        "servers",
        "volumes",
        "jobs",
        "runners",
        "standby",
        "scale_up_errors",
        "scale_down_errors",
        "system_health",
        "log",
    ]

    for name in panel_names:
        module_name = f"testflows.github.hetzner.runners.dashboard.panels.{name}"

        # Reload if already loaded, otherwise import
        if module_name in sys.modules:
            if reload:
                importlib.reload(sys.modules[module_name])
            setattr(panels, name, sys.modules[module_name])
        else:
            setattr(panels, name, importlib.import_module(module_name))

    return panels


def main():
    """Main dashboard function."""
    logger = logging.getLogger(__name__)

    logger.info("🚀 Streamlit Dashboard Main Function Called")

    server = sys.argv[1]
    config = sys.argv[2]

    @st.cache_resource
    def configure_download_handlers():
        """Configure download handlers for the server."""
        server.add_download_handler(
            endpoint="log",
            file=config.logger_config["handlers"]["rotating_logfile"]["filename"],
        )
        server.add_download_handler(endpoint="config", file=config.config_file)

    try:
        # Configure download handlers
        configure_download_handlers()

        # Reload panels and get them
        panels = reload_panels()

        # Tick tracker to ensure all metrics are updated
        tracker.tick()

        @st.fragment(run_every=update_interval.update_interval)
        def render_page():
            configure_page()

            # Always visible panels (outside tabs)
            panels.header.render()
            panels.gauges.render()

            # Build tabs for panels that should be in tabs
            tabbed_panels = {
                "Cost": panels.cost.render,
                "Servers": panels.servers.render,
                "Volumes": panels.volumes.render,
                "Jobs": panels.jobs.render,
                "Runners": panels.runners.render,
                "Standby": functools.partial(panels.standby.render, config),
                "Scale-up Errors": panels.scale_up_errors.render,
                "Scale-down Errors": panels.scale_down_errors.render,
                "Configuration": functools.partial(panels.info.render, config),
                "System Health": panels.system_health.render,
                "Log": functools.partial(panels.log.render, config),
            }

            # Render tabs with smart fragment-based navigation
            renderers.render_smart_tabs(tabbed_panels)

            # Footer panel at the bottom
            panels.footer.render()

        render_page()

        logger.info("✅ Dashboard rendered successfully")

    except Exception as e:
        logger.exception(f"❌ Error in dashboard main: {e}")
        st.error(f"Dashboard Error: {e}")
        raise


def save_config(config=None):
    if config is None:
        config = st.session_state["config"]

    st.session_state["config"] = config

    return config


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
                "server_enableWebsocketCompression": True,
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
                args=[config],
                flag_options=flag_options,
                thread_ref=thread_ref,
            )

        except Exception as e:
            logger.exception(f"Error starting Streamlit dashboard: {e}")

    # Start Streamlit in a daemon thread
    thread = threading.Thread(target=run_streamlit_in_thread, daemon=True)

    # Start metric tracking
    tracker.start_tracking()

    # Start server thread
    thread.start()

    return thread


if __name__ == "__main__":
    main()
