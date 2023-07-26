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
from .args import check, check_image
from . import __version__

from .server import wait_ready, wait_ssh, ssh, scp, ip_address
from .service import command_options

current_dir = os.path.dirname(__file__)


def deploy(args):
    """Deploy github-runners as a service to a
    new Hetzner server instance."""
    check(args)

    server_name = args.server_name
    deploy_setup_script = args.deploy_setup_script or os.path.join(
        current_dir, "scripts", "deploy", "setup.sh"
    )

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=args.hetzner_token)

    if args.force:
        with Action(
            f"Checking if server {server_name} already exists", ignore_fail=True
        ):
            server: BoundServer = client.servers.get_by_name(server_name)
            with Action(f"Deleting server {server_name}"):
                server.delete()

    with Action("Checking if default image exists"):
        args.default_image = check_image(client=client, image=args.default_image)

    with Action("Checking if server image exists"):
        args.image = check_image(client=client, image=args.image)

    with Action(f"Checking if SSH key exists"):
        with open(args.ssh_key, "r", encoding="utf-8") as ssh_key_file:
            public_key = ssh_key_file.read()
        key_name = hashlib.md5(public_key.encode("utf-8")).hexdigest()
        ssh_key = SSHKey(name=key_name, public_key=public_key)

        if not client.ssh_keys.get_by_name(name=ssh_key.name):
            with Action(f"Creating SSH key {ssh_key.name}"):
                client.ssh_keys.create(name=ssh_key.name, public_key=ssh_key.public_key)

    with Action(f"Creating new server"):
        response = client.servers.create(
            name=server_name,
            server_type=args.type,
            image=args.image,
            location=args.location,
            ssh_keys=[ssh_key],
        )
        server: BoundServer = response.server

    with Action(f"Waiting for server to be ready") as action:
        wait_ready(server=server, timeout=args.max_server_ready_time, action=action)

    with Action("Wait for SSH connection to be ready"):
        wait_ssh(server=server, timeout=args.max_server_ready_time)

    with Action("Executing setup.sh script"):
        ssh(
            server,
            f"bash -s  < {deploy_setup_script}",
        )

    with Action("Installing github-runners"):
        ssh(
            server,
            f"'sudo -u ubuntu pip3 install testflows.github.runners=={__version__}'",
        )

    with Action("Copying any custom scripts"):
        ip = ip_address(server)
        for script in [
            args.setup_script,
            args.startup_x64_script,
            args.startup_arm64_script,
        ]:
            if script:
                with Action(f"Copying custom script {script}"):
                    scp(
                        source=script, destination=f"ubuntu@{ip}:/home/ubuntu/scripts/."
                    )

    install(args, server=server)


def install(args, server: BoundServer = None):
    """Install service on a cloud instance."""
    if server is None:
        check(args)

        server_name = args.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=args.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server: BoundServer = client.servers.get_by_name(server_name)

    with Action("Installing service"):
        command = f"\"su - ubuntu -c '"
        command += f"GITHUB_TOKEN={args.github_token} "
        command += f"GITHUB_REPOSITORY={args.github_repository} "
        command += f"HETZNER_TOKEN={args.hetzner_token} "

        command += "github-runners"
        command += command_options(args)
        command += " service install -f'\""

        ssh(server, command)


def upgrade(args):
    """Upgrade github-runners application on a cloud instance."""
    server_name = args.server_name
    upgrade_version = args.upgrade_version

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=args.hetzner_token)

    with Action(f"Getting server {server_name}"):
        server: BoundServer = client.servers.get_by_name(server_name)

    stop(args, server=server)

    if upgrade_version:
        with Action(f"Upgrading github-runners to version {upgrade_version}"):
            ssh(
                server,
                f"'sudo -u ubuntu pip3 install testflows.github.runners=={upgrade_version}'",
            )
    else:
        with Action(f"Upgrading github-runners the latest version"):
            ssh(
                server,
                f"'sudo -u ubuntu pip3 install --upgrade testflows.github.runners'",
            )

    start(args, server=server)


def uninstall(args):
    """Uninstall github-runners service from a cloud instance."""
    server_name = args.server_name

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=args.hetzner_token)

    with Action(f"Getting server {server_name}"):
        server: BoundServer = client.servers.get_by_name(server_name)

    with Action("Uninstalling service"):
        command = f"\"su - ubuntu -c 'github-runners service uninstall'\""
        ssh(server, command)


def delete(args):
    """Delete github-runners service running
    on Hetzner server instance by stopping the service
    and deleting the server."""
    server_name = args.server_name

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=args.hetzner_token)

    with Action(f"Getting server {server_name}"):
        server: BoundServer = client.servers.get_by_name(server_name)

    with Action("Uninstalling service"):
        command = f"\"su - ubuntu -c 'github-runners service uninstall'\""
        ssh(server, command)

    with Action(f"Deleting server {server_name}"):
        server.delete()


def logs(args, server: BoundServer = None):
    """Get cloud server service logs."""
    if server is None:
        server_name = args.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=args.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server: BoundServer = client.servers.get_by_name(server_name)

    if server is None:
        raise ValueError("server not found")

    command = (
        f"\"su - ubuntu -c 'github-runners service logs"
        + (" -f" if args.follow else "")
        + "'\""
    )
    ssh(server, command, use_logger=False)


def status(args, server: BoundServer = None):
    """Get cloud server service status."""
    if server is None:
        server_name = args.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=args.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server = client.servers.get_by_name(server_name)

    with Action("Getting status"):
        command = f"\"su - ubuntu -c 'github-runners service status'\""
        ssh(server, command)


def start(args, server: BoundServer = None):
    """Start cloud server service."""
    if server is None:
        server_name = args.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=args.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server = client.servers.get_by_name(server_name)

    with Action("Starting service"):
        command = f"\"su - ubuntu -c 'github-runners service start'\""
        ssh(server, command)


def stop(args, server: BoundServer = None):
    """Stop cloud server service."""
    if server is None:
        server_name = args.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=args.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server = client.servers.get_by_name(server_name)

    with Action("Stopping service"):
        command = f"\"su - ubuntu -c 'github-runners service stop'\""
        ssh(server, command)
