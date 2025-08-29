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
from ..colors import COLORS
from ... import __version__


def create_item_value(label, value, value_color=None, link=None):
    """Create a labeled value with optional link.

    This function mimics the original dashboard panel's create_item_value function
    but returns a dictionary that can be used by Streamlit components.

    Args:
        label (str): Label text
        value (str): Value text
        value_color (str, optional): Color for the value text (not used in Streamlit version)
        link (dict, optional): Link configuration with 'text' and 'href' keys

    Returns:
        dict: Dictionary containing label, value, and link information
    """
    return {"label": label, "value": value, "link": link}


def create_list_item(name, color, header, values):
    """Create a list item with its name, header and values.

    This function mimics the original dashboard panel's create_list_item function
    but returns a dictionary that can be used by Streamlit components.

    Args:
        name (str): Name/identifier of the item
        color (str): Color (not used in Streamlit version)
        header: Header content (not used in this context)
        values (list): List of value dictionaries

    Returns:
        dict: Dictionary containing the list item information
    """
    return {"name": name, "values": values}


def create_list(name, count, items, title):
    """Create a list of items with their descriptions.

    This function mimics the original dashboard panel's create_list function
    but returns a dictionary that can be used by Streamlit components.

    Args:
        name (str): Name of the list
        count (int): Number of items
        items (list): List of items to display
        title (str): Title for the list

    Returns:
        dict: Dictionary containing the list information
    """
    return {"name": name, "count": count, "items": items, "title": title}


def create_panel(title, with_header=True, with_graph=False):
    """Create information panel.

    This function maintains API compatibility with the original dashboard.

    Args:
        title (str): Panel title
        with_header (bool): Whether to include header
        with_graph (bool): Whether to include graph (not used in info panel)

    Returns:
        dict: Panel configuration dictionary
    """
    return {"title": title, "with_header": with_header, "with_graph": with_graph}


def update_info_list(config: Config):
    """Create a list of information values.

    This function replicates the exact structure and content from the original
    dashboard/panels/info.py file.

    Args:
        config (Config): Configuration object

    Returns:
        dict: Information list structure
    """
    info_items = []

    # Create values - exact copy from original
    values = [
        create_item_value("Version", __version__),
        create_item_value(
            "GitHub Repository",
            config.github_repository,
            link={
                "text": "View on GitHub",
                "href": f"https://github.com/{config.github_repository}",
            },
        ),
        create_item_value(
            "Required Labels (--with-label)", ", ".join(config.with_label)
        ),
        create_item_value(
            "Label Prefix (--label-prefix)", config.label_prefix or "[no prefix]"
        ),
        create_item_value(
            "Meta Labels (--meta-label)",
            (
                ", ".join(f"{k}: {', '.join(v)}" for k, v in config.meta_label.items())
                if config.meta_label
                else "[no meta labels]"
            ),
        ),
        create_item_value("Max Runners (--max-runners)", config.max_runners),
        create_item_value(
            "Max Runners for Label (--max-runners-for-label)",
            (
                ", ".join(
                    f"{', '.join(sorted(labels))}:{max_count}"
                    for labels, max_count in config.max_runners_for_label
                )
                if config.max_runners_for_label
                else "[no label limits]"
            ),
        ),
        create_item_value(
            "Max Runners in Workflow Run (--max-runners-in-workflow-run)",
            config.max_runners_in_workflow_run or "[no limit]",
        ),
        create_item_value(
            "Recycle Runners (--recycle)", "yes" if config.recycle else "no"
        ),
        create_item_value("End of Life (--end-of-life)", config.end_of_life),
        create_item_value(
            "Delete Random (--delete-random)", "yes" if config.delete_random else "no"
        ),
        create_item_value("Debug Mode (--debug)", "yes" if config.debug else "no"),
        create_item_value(
            "Service Mode (--service-mode)", "yes" if config.service_mode else "no"
        ),
        create_item_value(
            "Embedded Mode (--embedded-mode)", "yes" if config.embedded_mode else "no"
        ),
        create_item_value("Workers (--workers)", config.workers),
        create_item_value("Scripts (--scripts)", config.scripts),
        create_item_value(
            "Max Powered Off Time (seconds) (--max-powered-off-time)",
            config.max_powered_off_time,
        ),
        create_item_value(
            "Max Unused Runner Time (seconds) (--max-unused-runner-time)",
            config.max_unused_runner_time,
        ),
        create_item_value(
            "Max Runner Registration Time (seconds) (--max-runner-registration-time)",
            config.max_runner_registration_time,
        ),
        create_item_value(
            "Max Server Ready Time (seconds) (--max-server-ready-time)",
            config.max_server_ready_time,
        ),
        create_item_value(
            "Scale Up Interval (seconds) (--scale-up-interval)",
            config.scale_up_interval,
        ),
        create_item_value(
            "Scale Down Interval (seconds) (--scale-down-interval)",
            config.scale_down_interval,
        ),
        create_item_value(
            "Default Image (--default-image)",
            config.default_image.name if config.default_image else "[no default image]",
        ),
        create_item_value(
            "Default Server Type (--default-server-type)",
            (
                config.default_server_type.name
                if config.default_server_type
                else "[no default server type]"
            ),
        ),
        create_item_value(
            "Default Location (--default-location)",
            (
                config.default_location.name
                if config.default_location
                else "[no default location]"
            ),
        ),
        create_item_value(
            "Config File (--config)", config.config_file or "[no config file]"
        ),
        create_item_value("Metrics Port (--metrics-port)", config.metrics_port),
        create_item_value("Metrics Host (--metrics-host)", config.metrics_host),
        create_item_value("Dashboard Port (--dashboard-port)", config.dashboard_port),
        create_item_value("Dashboard Host (--dashboard-host)", config.dashboard_host),
        create_item_value("SSH Key (--ssh-key)", config.ssh_key or "[no SSH key]"),
        create_item_value(
            "Additional SSH Keys",
            (
                ", ".join(config.additional_ssh_keys)
                if config.additional_ssh_keys
                else "[no additional SSH keys]"
            ),
        ),
    ]

    info_items.append(
        create_list_item("system-information", COLORS["nav"], None, values)
    )

    return create_list("system information", 1, info_items, "System Information")


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
            with open(config.config_file, "r") as f:
                config_content = f.read()

            st.download_button(
                label="📄 Download Config",
                data=config_content,
                file_name=os.path.basename(config.config_file),
                mime="text/yaml",
                use_container_width=False,
                help="Download config file",
                key="download_config_btn",
            )
        else:
            # Show a disabled button when no config file is available
            st.button(
                "📄 No Config",
                disabled=True,
                help="No config file was specified",
                key="download_config_disabled_btn",
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
    st.header("System Information")

    if config is None:
        st.warning("Configuration not available")
        return

    # Add download config button
    create_download_config_button(config)

    # Get the structured information list (same as original dashboard)
    info_data = update_info_list(config)

    # Extract values from the structured data
    if info_data and info_data["items"]:
        values = info_data["items"][0]["values"]

        # Create a scrollable container with max height (like original dashboard)
        with st.container(border=False):
            # Convert configuration items to separate label and value lists
            labels = []
            values_list = []
            links_list = []
            for item in values:
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
    else:
        st.warning("No configuration information available")
