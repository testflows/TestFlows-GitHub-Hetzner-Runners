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
import streamlit as st
import pandas as pd

from ...config import Config
from .. import renderers
from ... import __version__


def get_config_data(config: Config):
    """Get configuration data as a simple list of dictionaries.

    Args:
        config (Config): Configuration object

    Returns:
        list: List of configuration items with label, value, and optional link
    """
    return [
        {"label": "Version", "value": __version__, "link": None},
        {
            "label": "GitHub Repository",
            "value": config.github_repository,
            "link": {
                "text": "View on GitHub",
                "href": f"https://github.com/{config.github_repository}",
            },
        },
        {
            "label": "Required Labels (--with-label)",
            "value": ", ".join(config.with_label),
            "link": None,
        },
        {
            "label": "Label Prefix (--label-prefix)",
            "value": config.label_prefix or "",
            "link": None,
        },
        {
            "label": "Meta Labels (--meta-label)",
            "value": (
                ", ".join(f"{k}: {', '.join(v)}" for k, v in config.meta_label.items())
                if config.meta_label
                else ""
            ),
            "link": None,
        },
        {
            "label": "Max Runners (--max-runners)",
            "value": config.max_runners,
            "link": None,
        },
        {
            "label": "Max Runners for Label (--max-runners-for-label)",
            "value": (
                ", ".join(
                    f"{', '.join(sorted(labels))}:{max_count}"
                    for labels, max_count in config.max_runners_for_label
                )
                if config.max_runners_for_label
                else ""
            ),
            "link": None,
        },
        {
            "label": "Max Runners in Workflow Run (--max-runners-in-workflow-run)",
            "value": config.max_runners_in_workflow_run or "",
            "link": None,
        },
        {
            "label": "Recycle Runners (--recycle)",
            "value": "yes" if config.recycle else "no",
            "link": None,
        },
        {
            "label": "End of Life (--end-of-life)",
            "value": config.end_of_life,
            "link": None,
        },
        {
            "label": "Delete Random (--delete-random)",
            "value": "yes" if config.delete_random else "no",
            "link": None,
        },
        {
            "label": "Debug Mode (--debug)",
            "value": "yes" if config.debug else "no",
            "link": None,
        },
        {
            "label": "Service Mode (--service-mode)",
            "value": "yes" if config.service_mode else "no",
            "link": None,
        },
        {
            "label": "Embedded Mode (--embedded-mode)",
            "value": "yes" if config.embedded_mode else "no",
            "link": None,
        },
        {"label": "Workers (--workers)", "value": config.workers, "link": None},
        {"label": "Scripts (--scripts)", "value": config.scripts, "link": None},
        {
            "label": "Max Powered Off Time (seconds) (--max-powered-off-time)",
            "value": config.max_powered_off_time,
            "link": None,
        },
        {
            "label": "Max Unused Runner Time (seconds) (--max-unused-runner-time)",
            "value": config.max_unused_runner_time,
            "link": None,
        },
        {
            "label": "Max Runner Registration Time (seconds) (--max-runner-registration-time)",
            "value": config.max_runner_registration_time,
            "link": None,
        },
        {
            "label": "Max Server Ready Time (seconds) (--max-server-ready-time)",
            "value": config.max_server_ready_time,
            "link": None,
        },
        {
            "label": "Scale Up Interval (seconds) (--scale-up-interval)",
            "value": config.scale_up_interval,
            "link": None,
        },
        {
            "label": "Scale Down Interval (seconds) (--scale-down-interval)",
            "value": config.scale_down_interval,
            "link": None,
        },
        {
            "label": "Config File (--config)",
            "value": config.config_file or "",
            "link": None,
        },
        {
            "label": "Metrics Port (--metrics-port)",
            "value": config.metrics_port,
            "link": None,
        },
        {
            "label": "Metrics Host (--metrics-host)",
            "value": config.metrics_host,
            "link": None,
        },
        {
            "label": "Dashboard Port (--dashboard-port)",
            "value": config.dashboard_port,
            "link": None,
        },
        {
            "label": "Dashboard Host (--dashboard-host)",
            "value": config.dashboard_host,
            "link": None,
        },
        {
            "label": "SSH Key (--ssh-key)",
            "value": config.ssh_key or "",
            "link": None,
        },
        {
            "label": "Additional SSH Keys",
            "value": (
                ", ".join(config.additional_ssh_keys)
                if config.additional_ssh_keys
                else ""
            ),
            "link": None,
        },
    ]


def render_config_item(label: str, value, link: dict = None):
    """Render a single configuration item with label and value.

    Args:
        label: The configuration label
        value: The configuration value
        link: Optional dictionary with 'text' and 'href' keys for adding a link

    Returns:
        tuple: (label, formatted_value, link_href) tuple for the configuration item
    """
    if link:
        formatted_value = f"{value} ({link['text']})"
        link_href = link["href"]
    else:
        formatted_value = str(value)
        link_href = ""

    return label, formatted_value, link_href


def create_download_config_button(config: Config):
    """Create download button for config file.

    Args:
        config: Configuration object containing config file path
    """
    try:
        if config.config_file and os.path.exists(config.config_file):
            st.link_button(
                "📥 Config",
                help="Download config file",
                url="/download/config",
                type="secondary",
            )
        else:
            # Show a disabled button when no config file is available
            st.button(
                "📄 No Config",
                disabled=True,
                help="No config file was specified",
                key="download_config_disabled_btn",
                type="secondary",
            )

    except Exception as e:
        st.error(f"Error creating download config button: {str(e)}")


def render(config: Config):
    """Render the system information panel with configuration details.

    This function displays the information in a Streamlit-compatible format
    while maintaining the same structure and content as the original dashboard.

    Args:
        config: Configuration object containing system settings
    """
    with renderers.errors("rendering configuration panel"):
        with st.container(border=True):
            st.header("Configuration")

            if config is None:
                st.warning("Configuration not available")
                return

            # Add download config button
            create_download_config_button(config)

            # Get configuration data directly
            config_data = get_config_data(config)

            # Create a scrollable container with max height (like original dashboard)
            with st.container(border=False):
                # Convert configuration items to separate label and value lists
                labels = []
                values_list = []
                links_list = []
                for item in config_data:
                    label, formatted_value, link_href = render_config_item(
                        item["label"], item["value"], item.get("link")
                    )
                    labels.append(label)
                    values_list.append(formatted_value)
                    links_list.append(link_href)

                # Create a dataframe with three columns
                df = pd.DataFrame(
                    {"Name": labels, "Value": values_list, "Link": links_list}
                )

                # Display the dataframe with column headers, maintaining original order
                st.dataframe(
                    df,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Name": st.column_config.TextColumn("Name", width="medium"),
                        "Value": st.column_config.TextColumn("Value", width="large"),
                        "Link": st.column_config.LinkColumn("Link", width="small"),
                    },
                )
