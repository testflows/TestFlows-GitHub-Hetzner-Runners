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
import time

from hcloud import Client
from hcloud.ssh_keys.domain import SSHKey
from hcloud.server_types.domain import ServerType
from hcloud.servers.client import BoundServer
from hcloud.images.domain import Image

from .actions import Action
from .shell import shell
from .args import check
from . import __version__

current_dir = os.path.dirname(__file__)


def deploy(args, timeout=60):
    """Deploy github-runners as a service to a
    new Hetzner server instance."""
    check(args)

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=args.hetzner_token)

    with Action(f"Creating new server"):
        response = client.servers.create(
            name="github-runners",
            server_type=ServerType("cx11"),
            image=Image(args.hetzner_image),
            ssh_keys=[SSHKey(name=args.hetzner_ssh_key)],
        )
        server: BoundServer = response.server

    with Action(f"Waiting for server {server.name}") as action:
        start_time = time.time()

        while True:
            status = server.status
            action.note(f"{server.name} {status}")
            if status == server.STATUS_RUNNING:
                break
            if time.time() - start_time >= timeout:
                raise TimeoutError("waiting for server to start running")
            time.sleep(1)
            server.reload()

    ip = server.public_net.primary_ipv4.ip
    ssh = f'ssh -q -o "StrictHostKeyChecking no" root@{ip}'

    with Action("SSH to server"):
        attempt = -1
        start_time = time.time()

        while True:
            attempt += 1

            with Action(
                f"Trying to connect to {server.name}@{ip}...{attempt}", ignore_fail=True
            ):
                returncode = shell(f"{ssh} hostname")
                if returncode == 0:
                    break

            if time.time() - start_time >= timeout:
                shell(f"{ssh} hostname")
            else:
                time.sleep(5)

    with Action("Executing setup.sh script"):
        shell(
            f"{ssh} bash -s  < {os.path.join(current_dir, 'scripts', 'deploy', 'setup.sh')}"
        )

    with Action("Installing github-runners"):
        shell(f"{ssh} 'sudo -u runner pip3 install testflows.github.runners'")

    with Action("Installing service"):
        command = f"{ssh} 'sudo -u runner "

        command += f"GITHUB_TOKEN={args.github_token} "
        command += f"GITHUB_REPOSITORY={args.github_repository} "
        command += f"HETZNER_TOKEN={args.hetzner_token} "
        command += f"HETZNER_SSH_KEY={args.hetzner_ssh_key} "
        command += f"HETZNER_IMAGE={args.hetzner_image} "

        command += "github-runners"

        command += f" --workers {args.workers}"

        command += f" --max-runners {args.max_runners}" if args.max_runners else ""
        command += (
            f" --logger-config {args.logger_config}" if args.logger_config else ""
        )
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
            f" --scale-up-interval {args.scale_up_interval}"
            f" --scale-down-interval {args.scale_down_interval}"
        )
        command += f" --debug" if args.debug else ""
        command += " service install'"

        shell(command)
