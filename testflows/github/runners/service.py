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

from .actions import Action
from .args import check


def command_options(args):
    """Build service install command options not including:

    --github-token
    --github-repository
    --hetzner-token
    --ssh-key
    """
    command = ""
    command += f" --workers {args.workers}"
    command += f" --default-type {args.default_type.name}"
    command += (
        f" --default-location {args.default_location.name}"
        if args.default_location
        else ""
    )
    command += f" --default-image {args.default_image.type}:{args.default_image.name or args.default_image.description}"
    command += f" --max-runners {args.max_runners}" if args.max_runners else ""
    command += f" --logger-config {args.logger_config}" if args.logger_config else ""
    command += f" --setup-script {args.setup_script}" if args.setup_script else ""
    command += (
        f" --startup-x64-script {args.startup_x64_script}"
        if args.startup_x64_script
        else ""
    )
    command += (
        f" --startup-arm64-script {args.startup_arm64_script}"
        if args.startup_arm64_script
        else ""
    )
    command += (
        f" --max-powered-off-time {args.max_powered_off_time}"
        f" --max-idle-runner-time {args.max_idle_runner_time}"
        f" --max-runner-registration-time {args.max_runner_registration_time}"
        f" --max-server-ready-time {args.max_server_ready_time}"
        f" --scale-up-interval {args.scale_up_interval}"
        f" --scale-down-interval {args.scale_down_interval}"
    )
    command += f" --debug" if args.debug else ""

    return command


def install(args):
    """Install service."""
    check(args)

    force = args.force

    current_dir = os.path.dirname(__file__)

    with Action("Checking if service is already installed"):
        if os.path.exists(SERVICE):
            if not force:
                raise ValueError("service has already been installed")
            with Action("Stopping service"):
                os.system(f"sudo service {NAME} stop")

    with Action(f"Installing {SERVICE}"):
        binary = os.path.join(current_dir, "bin", "github-runners")
        contents = (
            "[Unit]\n"
            "Description=Autoscaling GitHub Actions Runners\n"
            "After=multi-user.target\n"
            "[Service]\n"
            f"User={os.getuid()}\n"
            f"Group={os.getgid()}\n"
            "Type=simple\n"
            "Restart=always\n"
            f"Environment=GITHUB_TOKEN={args.github_token}\n"
            f"Environment=GITHUB_REPOSITORY={args.github_repository}\n"
            f"Environment=HETZNER_TOKEN={args.hetzner_token}\n"
            f"ExecStart={binary}"
            f" --workers {args.workers}"
        )
        contents += f" --ssh-key {args.ssh_key}"
        contents += command_options(args)
        contents += "\n" "[Install]\n" "WantedBy=multi-user.target\n"

        os.system(f"sudo bash -c \"cat > {SERVICE}\" <<'EOF'\n{contents}\nEOF")
        os.system(f"sudo chmod 700 {SERVICE}")

    with Action("Reloading systemd"):
        os.system("sudo systemctl daemon-reload")

    with Action("Enabling service"):
        os.system(f"sudo systemctl enable {NAME}.service")

    with Action("Starting service"):
        os.system(f"sudo service {NAME} start")


def uninstall(args):
    """Uninstall service."""
    force = args.force

    with Action("Stopping service"):
        os.system(f"sudo service {NAME} stop")

    with Action("Disabling service"):
        os.system(f"sudo systemctl disable {NAME}.service")

    with Action(f"Removing {SERVICE}"):
        os.system(f"sudo rm -f {SERVICE}")

    with Action("Reloading systemd"):
        os.system("sudo systemctl daemon-reload")


def logs(args):
    """Get service logs."""
    os.system(
        f'sudo bash -c "journalctl -u {NAME}.service'
        + (" -f" if args.follow else "")
        + ' | tee"'
    )


def start(args):
    """Start service."""
    os.system(f"sudo service {NAME} start")


def stop(args):
    """Stop service."""
    os.system(f"sudo service {NAME} stop")


def status(args):
    """Get service status."""
    os.system(f"sudo service {NAME} status")
