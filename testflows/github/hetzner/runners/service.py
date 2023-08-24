# Copyright 2023 Katteli Inc.
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
import json
import textwrap

NAME = "github-hetzner-runners"
SERVICE = f"/etc/systemd/system/{NAME}.service"

from .actions import Action
from .logger import decode_message


def command_options(
    config,
    github_token="$GITHUB_TOKEN",
    github_repository="$GITHUB_REPOSITORY",
    hetzner_token="$HETZNER_TOKEN",
):
    """Build service install command options not including:

    --github-token
    --github-repository
    --hetzner-token
    --ssh-key
    """
    command = ""
    command += f" --github-token {github_token}"
    command += f" --github-repository {github_repository}"
    command += f" --hetzner-token {hetzner_token}"
    command += f" --config {config.config_file}" if config.config_file else ""
    command += f" --recycle " + "on" if config.recycle else "off"
    command += f" --end-of-life {config.end_of_life}" if config.end_of_life else ""
    command += f" --with-label {config.with_label}" if config.with_label else ""
    command += f" --workers {config.workers}"
    command += f" --default-type {config.default_server_type.name}"
    command += (
        f" --default-location {config.default_location.name}"
        if config.default_location
        else ""
    )
    command += f" --default-image {config.default_image.architecture}:{config.default_image.type}:{config.default_image.name or config.default_image.description}"
    command += f" --max-runners {config.max_runners}" if config.max_runners else ""
    command += (
        f" --max-runners-in-workflow-run {config.max_runners_in_workflow_run}"
        if config.max_runners_in_workflow_run
        else ""
    )
    command += f" --setup-script {config.setup_script}" if config.setup_script else ""
    command += (
        f" --startup-x64-script {config.startup_x64_script}"
        if config.startup_x64_script
        else ""
    )
    command += (
        f" --startup-arm64-script {config.startup_arm64_script}"
        if config.startup_arm64_script
        else ""
    )
    command += (
        f" --max-powered-off-time {config.max_powered_off_time}"
        f" --max-unused-runner-time {config.max_unused_runner_time}"
        f" --max-runner-registration-time {config.max_runner_registration_time}"
        f" --max-server-ready-time {config.max_server_ready_time}"
        f" --scale-up-interval {config.scale_up_interval}"
        f" --scale-down-interval {config.scale_down_interval}"
    )
    command += f" --debug" if config.debug else ""

    return command


def install(args, config):
    """Install service."""
    config.check()
    force = args.force
    current_dir = os.path.dirname(__file__)

    with Action("Checking if service is already installed"):
        if os.path.exists(SERVICE):
            if not force:
                raise ValueError("service has already been installed")
            with Action("Stopping service"):
                os.system(f"sudo service {NAME} stop")

    with Action(f"Deleting old rotating log files"):
        os.system(
            f"rm -rf {config.logger_config['handlers']['rotating_service_logfile']['filename']}*"
        )

    with Action(f"Installing {SERVICE}"):
        binary = os.path.join(
            current_dir, "bin", "github-hetzner-runners --service-mode"
        )
        contents = (
            "[Unit]\n"
            "Description=Autoscaling GitHub Actions Runners\n"
            "After=multi-user.target\n"
            "[Service]\n"
            f"User={os.getuid()}\n"
            f"Group={os.getgid()}\n"
            "Type=simple\n"
            "Restart=always\n"
            "KillSignal=SIGINT\n"
            "TimeoutStopSec=90\n"
            f"Environment=GITHUB_TOKEN={config.github_token}\n"
            f"Environment=GITHUB_REPOSITORY={config.github_repository}\n"
            f"Environment=HETZNER_TOKEN={config.hetzner_token}\n"
            f"ExecStart={binary}"
        )
        contents += f" --ssh-key {config.ssh_key}"
        contents += command_options(config)
        contents += "\n" "[Install]\n" "WantedBy=multi-user.target\n"

        os.system(f"sudo bash -c \"cat > {SERVICE}\" <<'EOF'\n{contents}\nEOF")
        os.system(f"sudo chmod 700 {SERVICE}")

    with Action("Reloading systemd"):
        os.system("sudo systemctl daemon-reload")

    with Action("Enabling service"):
        os.system(f"sudo systemctl enable {NAME}.service")

    with Action("Starting service"):
        os.system(f"sudo service {NAME} start")


def uninstall(args, config=None):
    """Uninstall service."""
    with Action("Stopping service"):
        os.system(f"sudo service {NAME} stop")

    with Action("Disabling service"):
        os.system(f"sudo systemctl disable {NAME}.service")

    with Action(f"Removing {SERVICE}"):
        os.system(f"sudo rm -f {SERVICE}")

    with Action("Reloading systemd"):
        os.system("sudo systemctl daemon-reload")


def log(args, config=None):
    """Get service log."""
    logger_columns = config.logger_format["columns"]
    format = ""
    if not args.raw:
        format = f" | github-hetzner-runners --embedded-mode"
        if config.debug:
            format += " --debug"
        if config.config_file:
            format += f" -c {config.config_file}"
        format += " service log"
        if args.columns:
            format += f" --columns"
            columns = []
            for c in args.columns:
                assert (
                    c["column"] in logger_columns
                ), f"column {c['column']} is not valid"
                columns.append(
                    f"{c['column']}" + (f":{c['width']}" if c.get("width") else "")
                )
            format += f" {','.join(columns)}"
        format += " format -"

    rotating_service_logfile = config.logger_config["handlers"][
        "rotating_service_logfile"
    ]["filename"]

    if args.follow:
        lines = "10" if not args.lines else args.lines
        os.system(
            f'bash -c "tail -n {lines} -f {rotating_service_logfile} | tee{format}"'
        )
    else:
        lines = "+0" if not args.lines else args.lines
        os.system(
            f'bash -c "ls -tr {rotating_service_logfile}* | xargs tail -n {lines}{format}"'
        )


def delete_log(args, config=None):
    """Delete log."""
    with Action(f"Deleting log files"):
        os.system(
            f"rm -rf {config.logger_config['handlers']['rotating_service_logfile']['filename']}*"
        )


def format_log(args, config=None):
    """Format raw log."""
    columns = config.logger_format["columns"]
    delimiter = config.logger_format["delimiter"]
    default = args.columns or config.logger_format["default"]

    class Wrapper(textwrap.TextWrapper):
        """Custom wrapper that preserves new lines."""

        def wrap(self, text):
            split_text = text.split("\n")
            lines = [
                line
                for para in split_text
                for line in textwrap.TextWrapper.wrap(self, para)
            ]
            return lines

    for c in default:
        assert c["column"] in columns, f"{c['column']} is not valid"

    # name, index, width
    selected = [
        (
            c["column"],
            columns[c["column"]][0],
            (columns[c["column"]][1] if c.get("width") is None else c.get("width")),
        )
        for c in default
    ]

    while True:
        line = args.input.readline()
        if not line:
            break

        columns = line.split(delimiter, len(columns) - 1)
        for i, c in enumerate(columns):
            columns[i] = decode_message(c)

        wrapped = [
            (width, Wrapper(width).wrap(columns[index])) for _, index, width in selected
        ]
        max_lines = max(len(lines) for width, lines in wrapped)
        for m in range(max_lines):
            for width, c in wrapped:
                v = ""
                if m < len(c):
                    v = c[m]
                sys.stdout.write(f"{v:<{width}} ")
            sys.stdout.write("\n")
        sys.stdout.flush()


def start(args, config=None):
    """Start service."""
    with Action(f"Starting service {NAME}"):
        os.system(f"sudo service {NAME} start")


def stop(args, config=None):
    """Stop service."""
    with Action(f"Stopping service {NAME}"):
        os.system(f"sudo service {NAME} stop")


def status(args, config=None):
    """Get service status."""
    with Action(f"Getting service {NAME} status"):
        os.system(f"sudo service {NAME} status")
