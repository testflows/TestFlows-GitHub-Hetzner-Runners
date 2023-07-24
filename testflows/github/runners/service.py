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

NAME = "github-runners"
SERVICE = f"/etc/systemd/system/{NAME}.service"
SERVICE_BIN = "/usr/local/bin/github-runners"

from .actions import Action
from .args import check


def install(args):
    """Install service."""
    check(args)

    force = args.force

    current_dir = os.path.dirname(__file__)

    with Action("Checking if service is already installed"):
        if os.path.exists(SERVICE):
            if not force:
                raise ValueError("service has already been installed")

    with Action(f"Installing {SERVICE_BIN}") as action:
        binary = os.path.join(current_dir, "bin", "github-runners")
        action.note(f"{binary}")

        with open(SERVICE_BIN, "w") as file:
            with open(binary, "r") as content:
                file.write(content.read())

        os.chmod(SERVICE_BIN, 0o755)

    with Action(f"Installing {SERVICE}"):
        with open(SERVICE, "w") as file:
            contents = (
                "[Unit]\n"
                "Description=Autoscaling GitHub Actions Runners\n"
                "After=multi-user.target\n"
                "[Service]\n"
                "Type=simple\n"
                "Restart=always\n"
                f"Environment=GITHUB_TOKEN={args.github_token}\n"
                f"Environment=GITHUB_REPOSITORY={args.github_repository}\n"
                f"Environment=HETZNER_TOKEN={args.hetzner_token}\n"
                f"Environment=HETZNER_SSH_KEY={args.hetzner_ssh_key}\n"
                f"Environment=HETZNER_IMAGE={args.hetzner_image}\n"
                f"ExecStart={SERVICE_BIN}"
                f" --workers {args.workers}"
            )
            contents += f" --max-runners {args.max_runners}" if args.max_runners else ""
            contents += (
                f" --logger-config {args.logger_config}" if args.logger_config else ""
            )
            contents += (
                f" --setup-script {args.setup_script}" if args.setup_script else ""
            )
            contents += (
                f" --startup-x64-script {args.startup_x64_script}"
                if args.startup_x64_script
                else ""
            )
            contents += (
                f" --startup-arm64-script {args.startup_arm64_script}"
                if args.startup_arm64_script
                else ""
            )
            contents += (
                f" --max-powered-off-time {args.max_powered_off_time}"
                f" --max-idle-runner-time {args.max_idle_runner_time}"
                f" --max-runner-registration-time {args.max_runner_registration_time}"
                f" --scale-up-interval {args.scale_up_interval}"
                f" --scale-down-interval {args.scale_down_interval}"
            )
            contents += f" --debug" if args.debug else ""
            contents += "\n" "[Install]\n" "WantedBy=multi-user.target\n"
            file.write(contents)
        os.chmod(SERVICE, 0o700)

    with Action("Reloading systemd"):
        os.system("systemctl daemon-reload")

    with Action("Enabling service"):
        os.system(f"systemctl enable {NAME}.service")

    with Action("Starting service"):
        os.system(f"service {NAME} start")


def uninstall(args):
    """Uninstall service."""
    force = args.force

    with Action("Stopping service"):
        os.system(f"service {NAME} stop")

    with Action("Disabling service"):
        os.system(f"systemctl disable {NAME}.service")

    with Action(f"Removing {SERVICE}"):
        try:
            os.remove(SERVICE)
        except FileNotFoundError:
            pass

    with Action("Reloading systemd"):
        os.system("systemctl daemon-reload")


def logs(args):
    """Get service logs"""
    os.system(f"journalctl -u {NAME}.service -f")


def start(args):
    """Start service."""
    os.system(f"service {NAME} start")


def stop(args):
    """Stop service."""
    os.system(f"service {NAME} stop")


def status(args):
    """Get service status."""
    os.system(f"service {NAME} status")
