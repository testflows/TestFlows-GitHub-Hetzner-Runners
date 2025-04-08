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

from ...config import Config
from ..colors import COLORS
from . import panel
from ... import __version__


def update_info_list(config: Config):
    """Create a list of information values."""

    info_items = []

    # Create values
    values = [
        panel.create_item_value("Version", __version__),
        panel.create_item_value(
            "GitHub Repository",
            config.github_repository,
            link={
                "text": "View on GitHub",
                "href": f"https://github.com/{config.github_repository}",
            },
        ),
        panel.create_item_value(
            "Required Labels (--with-label)", ", ".join(config.with_label)
        ),
        panel.create_item_value(
            "Label Prefix (--label-prefix)", config.label_prefix or "[no prefix]"
        ),
        panel.create_item_value(
            "Meta Labels (--meta-label)",
            (
                ", ".join(f"{k}: {', '.join(v)}" for k, v in config.meta_label.items())
                if config.meta_label
                else "[no meta labels]"
            ),
        ),
        panel.create_item_value("Max Runners (--max-runners)", config.max_runners),
        panel.create_item_value(
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
        panel.create_item_value(
            "Max Runners in Workflow Run (--max-runners-in-workflow-run)",
            config.max_runners_in_workflow_run or "[no limit]",
        ),
        panel.create_item_value(
            "Recycle Runners (--recycle)", "yes" if config.recycle else "no"
        ),
        panel.create_item_value("End of Life (--end-of-life)", config.end_of_life),
        panel.create_item_value(
            "Delete Random (--delete-random)", "yes" if config.delete_random else "no"
        ),
        panel.create_item_value(
            "Debug Mode (--debug)", "yes" if config.debug else "no"
        ),
        panel.create_item_value(
            "Service Mode (--service-mode)", "yes" if config.service_mode else "no"
        ),
        panel.create_item_value(
            "Embedded Mode (--embedded-mode)", "yes" if config.embedded_mode else "no"
        ),
        panel.create_item_value("Workers (--workers)", config.workers),
        panel.create_item_value("Scripts (--scripts)", config.scripts),
        panel.create_item_value(
            "Max Powered Off Time (seconds) (--max-powered-off-time)",
            config.max_powered_off_time,
        ),
        panel.create_item_value(
            "Max Unused Runner Time (seconds) (--max-unused-runner-time)",
            config.max_unused_runner_time,
        ),
        panel.create_item_value(
            "Max Runner Registration Time (seconds) (--max-runner-registration-time)",
            config.max_runner_registration_time,
        ),
        panel.create_item_value(
            "Max Server Ready Time (seconds) (--max-server-ready-time)",
            config.max_server_ready_time,
        ),
        panel.create_item_value(
            "Scale Up Interval (seconds) (--scale-up-interval)",
            config.scale_up_interval,
        ),
        panel.create_item_value(
            "Scale Down Interval (seconds) (--scale-down-interval)",
            config.scale_down_interval,
        ),
        panel.create_item_value(
            "Default Image (--default-image)",
            config.default_image.name if config.default_image else "[no default image]",
        ),
        panel.create_item_value(
            "Default Server Type (--default-server-type)",
            (
                config.default_server_type.name
                if config.default_server_type
                else "[no default server type]"
            ),
        ),
        panel.create_item_value(
            "Default Location (--default-location)",
            (
                config.default_location.name
                if config.default_location
                else "[no default location]"
            ),
        ),
        panel.create_item_value(
            "Config File (--config)", config.config_file or "[no config file]"
        ),
        panel.create_item_value("Metrics Port (--metrics-port)", config.metrics_port),
        panel.create_item_value("Metrics Host (--metrics-host)", config.metrics_host),
        panel.create_item_value(
            "Dashboard Port (--dashboard-port)", config.dashboard_port
        ),
        panel.create_item_value(
            "Dashboard Host (--dashboard-host)", config.dashboard_host
        ),
        panel.create_item_value(
            "SSH Key (--ssh-key)", config.ssh_key or "[no SSH key]"
        ),
        panel.create_item_value(
            "Additional SSH Keys",
            (
                ", ".join(config.additional_ssh_keys)
                if config.additional_ssh_keys
                else "[no additional SSH keys]"
            ),
        ),
    ]

    info_items.append(
        panel.create_list_item("system-information", COLORS["nav"], None, values)
    )

    return panel.create_list("system information", 1, info_items, "System Information")


def create_panel():
    """Create information panel."""
    return panel.create_panel("System Information", with_header=True, with_graph=False)
