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
import hashlib

from hcloud import Client
from hcloud.ssh_keys.domain import SSHKey
from hcloud.server_types.domain import ServerType
from hcloud.servers.client import BoundServer
from hcloud.images.domain import Image
from hcloud.locations.domain import Location

from .actions import Action
from .args import check
from . import __version__

from .server import wait_ready, wait_ssh, ssh

current_dir = os.path.dirname(__file__)


def deploy(args, timeout=60):
    """Deploy github-runners as a service to a
    new Hetzner server instance."""
    check(args)

    server_name = args.server_name

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=args.hetzner_token)

    if args.force:
        with Action(
            f"Checking if server {server_name} already exists", ignore_fail=True
        ):
            server: BoundServer = client.servers.get_by_name(server_name)
            with Action(f"Deleting server {server_name}"):
                server.delete()

    with Action(f"Checking if SSH key exists"):
        public_key = args.ssh_key.read()
        key_name = hashlib.md5(public_key.encode("utf-8")).hexdigest()
        ssh_key = SSHKey(name=key_name, public_key=public_key)

        if not client.ssh_keys.get_by_name(name=ssh_key.name):
            with Action(f"Creating SSH key {ssh_key.name}"):
                client.ssh_keys.create(name=ssh_key.name, public_key=ssh_key.public_key)

    with Action(f"Creating new server"):
        response = client.servers.create(
            name=server_name,
            server_type=ServerType(name=args.type),
            image=Image(name=args.image),
            location=Location(name=args.location),
            ssh_keys=[ssh_key],
        )
        server: BoundServer = response.server

    with Action(f"Waiting for server to be ready") as action:
        wait_ready(server=server, timeout=timeout, action=action)

    with Action("Wait for SSH connection to be ready"):
        wait_ssh(server=server, timeout=timeout)

    with Action("Executing setup.sh script"):
        ssh(
            server,
            f"bash -s  < {os.path.join(current_dir, 'scripts', 'deploy', 'setup.sh')}",
        )

    with Action("Installing github-runners"):
        ssh(
            server,
            f"'sudo -u runner pip3 install testflows.github.runners=={__version__}'",
        )

    install(args, server=server)


def install(args, server: BoundServer = None):
    """Install service on a cloud instance."""
    if server is None:
        check(args)

        server_name = args.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=args.hetzner_token)

        with Action(f"Checking if server {server_name} already exists"):
            server: BoundServer = client.servers.get_by_name(server_name)

    with Action("Installing service"):
        command = f"\"su - runner -c '"
        command += f"GITHUB_TOKEN={args.github_token} "
        command += f"GITHUB_REPOSITORY={args.github_repository} "
        command += f"HETZNER_TOKEN={args.hetzner_token} "

        command += "github-runners"
        command += f" --workers {args.workers}"
        command += f" --hetzner-image {args.hetzner_image}"
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
        command += " service install -f'\""

        ssh(server, command)


def upgrade(args):
    """Upgrade github-runners application on a cloud instance."""
    server_name = args.server_name
    upgrade_version = args.upgrade_version

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=args.hetzner_token)

    with Action(f"Checking if server {server_name} already exists"):
        server: BoundServer = client.servers.get_by_name(server_name)

    stop(args, server=server)

    if upgrade_version:
        with Action(f"Upgrading github-runners to version {upgrade_version}"):
            ssh(
                server,
                f"'sudo -u runner pip3 install testflows.github.runners=={upgrade_version}'",
            )
    else:
        with Action(f"Upgrading github-runners the latest version"):
            ssh(
                server,
                f"'sudo -u runner pip3 install --upgrade testflows.github.runners'",
            )

    start(args, server=server)


def uninstall(args):
    """Uninstall github-runners service from a cloud instance."""
    server_name = args.server_name

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=args.hetzner_token)

    with Action(f"Checking if server {server_name} already exists"):
        server: BoundServer = client.servers.get_by_name(server_name)

    with Action("Uninstalling service"):
        command = f"\"su - runner -c 'github-runners service uninstall'\""
        ssh(server, command)


def delete(args):
    """Delete github-runners service running
    on Hetzner server instance by stopping the service
    and deleting the server."""
    server_name = args.server_name

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=args.hetzner_token)

    with Action(f"Checking if server {server_name} already exists"):
        server: BoundServer = client.servers.get_by_name(server_name)

    with Action("Uninstalling service"):
        command = f"\"su - runner -c 'github-runners service uninstall'\""
        ssh(server, command)

    with Action(f"Deleting server {server_name}"):
        server.delete()


def logs(args, server: BoundServer = None):
    """Get cloud server service logs."""
    if server is None:
        server_name = args.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=args.hetzner_token)

        with Action(f"Checking if server {server_name} already exists"):
            server = client.servers.get_by_name(server_name)

    with Action("Getting logs"):
        command = (
            f"\"su - runner -c 'github-runners service logs"
            + (" -f" if args.follow else "")
            + "'\""
        )
        ssh(server, command)


def status(args, server: BoundServer = None):
    """Get cloud server service status."""
    if server is None:
        server_name = args.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=args.hetzner_token)

        with Action(f"Checking if server {server_name} already exists"):
            server = client.servers.get_by_name(server_name)

    with Action("Getting status"):
        command = f"\"su - runner -c 'github-runners service status'\""
        ssh(server, command)


def start(args, server: BoundServer = None):
    """Start cloud server service."""
    if server is None:
        server_name = args.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=args.hetzner_token)

        with Action(f"Checking if server {server_name} already exists"):
            server = client.servers.get_by_name(server_name)

    with Action("Starting service"):
        command = f"\"su - runner -c 'github-runners service start'\""
        ssh(server, command)


def stop(args, server: BoundServer = None):
    """Stop cloud server service."""
    if server is None:
        server_name = args.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=args.hetzner_token)

        with Action(f"Checking if server {server_name} already exists"):
            server = client.servers.get_by_name(server_name)

    with Action("Stopping service"):
        command = f"\"su - runner -c 'github-runners service stop'\""
        ssh(server, command)