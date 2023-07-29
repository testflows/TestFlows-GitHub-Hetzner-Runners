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
import hashlib

from hcloud import Client
from hcloud.ssh_keys.domain import SSHKey
from hcloud.servers.client import BoundServer

from .actions import Action
from .config import Config, check_image
from . import __version__

from .server import wait_ready, wait_ssh, ssh, scp, ip_address, ssh_command
from .service import command_options

current_dir = os.path.dirname(__file__)
deploy_scripts_folder = "/home/ubuntu/.github-runners/scripts/"
deploy_configs_folder = "/home/ubuntu/.github-runners/configs/"


def deploy(args, config: Config, redeploy=False):
    """Deploy or redeploy github-runners as a service to a
    new Hetzner server instance."""
    config.check()
    version = args.version or __version__
    server_name = config.cloud.server_name

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    if redeploy:
        with Action(f"Getting server {server_name}"):
            server: BoundServer = client.servers.get_by_name(server_name)

        uninstall(args=args, config=config, server=server)

        with Action("Cleaning copied scripts"):
            ssh(server, f"rm -rf {deploy_scripts_folder}*")

        with Action("Cleaning copied configs"):
            ssh(server, f"rm -rf {deploy_configs_folder}*")

    else:
        deploy_setup_script = config.cloud.deploy.setup_script or os.path.join(
            current_dir, "scripts", "deploy", "setup.sh"
        )

        if args.force:
            with Action(
                f"Checking if server {server_name} already exists", ignore_fail=True
            ):
                server: BoundServer = client.servers.get_by_name(server_name)
                with Action(f"Deleting server {server_name}"):
                    server.delete()

        with Action("Checking if default image exists"):
            config.default_image = check_image(
                client=client, image=config.default_image
            )

        with Action("Checking if server image exists"):
            config.cloud.deploy.image = check_image(
                client=client, image=config.cloud.deploy.image
            )

        with Action(f"Checking if SSH key exists"):
            with open(config.ssh_key, "r", encoding="utf-8") as ssh_key_file:
                public_key = ssh_key_file.read()
            key_name = hashlib.md5(public_key.encode("utf-8")).hexdigest()
            ssh_key = SSHKey(name=key_name, public_key=public_key)

            if not client.ssh_keys.get_by_name(name=ssh_key.name):
                with Action(f"Creating SSH key {ssh_key.name}"):
                    client.ssh_keys.create(
                        name=ssh_key.name, public_key=ssh_key.public_key
                    )

        with Action(f"Creating new server"):
            response = client.servers.create(
                name=server_name,
                server_type=config.cloud.deploy.server_type,
                image=config.cloud.deploy.image,
                location=config.cloud.deploy.location,
                ssh_keys=[ssh_key],
            )
            server: BoundServer = response.server

        with Action(f"Waiting for server to be ready") as action:
            wait_ready(
                server=server, timeout=config.max_server_ready_time, action=action
            )

        with Action("Wait for SSH connection to be ready"):
            wait_ssh(server=server, timeout=config.max_server_ready_time)

        with Action("Executing setup.sh script"):
            ssh(
                server,
                f"bash -s  < {deploy_setup_script}",
            )

    with Action(f"Installing github-runners {version}"):
        command = f"'sudo -u ubuntu pip3 install testflows.github.runners=={version}'"

        if version.strip().lower() == "latest":
            command = f"'sudo -u ubuntu pip3 install testflows.github.runners'"
            if redeploy:
                command.replace("pip3 install", "pip3 install --upgrade")

        ssh(server, command)

    with Action("Copying any custom scripts"):
        ip = ip_address(server)

        if config.setup_script:
            with Action(f"Copying custom setup script {config.setup_script}"):
                scp(
                    source=config.setup_script,
                    destination=f"root@{ip}:{deploy_scripts_folder}.",
                )
                config.setup_script = os.path.join(
                    deploy_scripts_folder,
                    os.path.basename(config.setup_script),
                )

        if config.startup_x64_script:
            with Action(
                f"Copying custom startup x64 script {config.startup_x64_script}"
            ):
                scp(
                    source=config.startup_x64_script,
                    destination=f"root@{ip}:{deploy_scripts_folder}.",
                )
                config.startup_x64_script = os.path.join(
                    deploy_scripts_folder,
                    os.path.basename(config.startup_x64_script),
                )

        if config.startup_arm64_script:
            with Action(
                f"Copying custom startup ARM64 script {config.startup_arm64_script}"
            ):
                scp(
                    source=config.startup_arm64_script,
                    destination=f"root@{ip}:{deploy_scripts_folder}.",
                )
                config.startup_arm64_script = os.path.join(
                    deploy_scripts_folder,
                    os.path.basename(config.startup_arm64_script),
                )

    with Action("Fixing ownership of any copied scripts"):
        ssh(server, f"chown -R ubuntu:ubuntu {deploy_scripts_folder}")

    if config.config_file:
        with Action(f"Copying config file {config.config_file}"):
            scp(
                source=config.config_file,
                destination=f"root@{ip}:{deploy_configs_folder}.",
            )
            config.config_file = os.path.join(
                deploy_configs_folder,
                os.path.basename(config.config_file),
            )

    with Action("Fixing ownership of any copied configs"):
        ssh(server, f"chown -R ubuntu:ubuntu {deploy_configs_folder}")

    install(args, config=config, server=server)


def redeploy(args, config: Config):
    """Redeploy service on a existing cloud instance."""
    deploy(args=args, config=config, redeploy=True)


def install(args, config: Config, server: BoundServer = None):
    """Install service on a cloud instance."""
    if server is None:
        config.check()
        server_name = config.cloud.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=config.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server: BoundServer = client.servers.get_by_name(server_name)

    with Action("Installing service"):
        command = f"\"su - ubuntu -c '"
        command += f"GITHUB_TOKEN={config.github_token} "
        command += f"GITHUB_REPOSITORY={config.github_repository} "
        command += f"HETZNER_TOKEN={config.hetzner_token} "

        command += "github-runners"
        command += command_options(config)
        command += " service install -f'\""

        ssh(server, command)


def upgrade(args, config: Config):
    """Upgrade github-runners application on a cloud instance."""
    config.check("hetzner_token")
    server_name = config.cloud.server_name
    upgrade_version = args.upgrade_version

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action(f"Getting server {server_name}"):
        server: BoundServer = client.servers.get_by_name(server_name)

    stop(args, config=config, server=server)

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

    start(args, config=config, server=server)


def uninstall(args, config: Config, server: BoundServer = None):
    """Uninstall github-runners service from a cloud instance."""
    if server is None:
        config.check("hetzner_token")
        server_name = config.cloud.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=config.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server: BoundServer = client.servers.get_by_name(server_name)

    with Action("Uninstalling service"):
        command = f"\"su - ubuntu -c 'github-runners service uninstall'\""
        ssh(server, command)


def delete(args, config: Config):
    """Delete github-runners service running
    on Hetzner server instance by stopping the service
    and deleting the server."""
    config.check("hetzner_token")
    server_name = config.cloud.server_name

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action(f"Getting server {server_name}"):
        server: BoundServer = client.servers.get_by_name(server_name)

    with Action("Uninstalling service"):
        command = f"\"su - ubuntu -c 'github-runners service uninstall'\""
        ssh(server, command)

    with Action(f"Deleting server {server_name}"):
        server.delete()


def logs(args, config: Config, server: BoundServer = None):
    """Get cloud server service logs."""
    if server is None:
        config.check("hetzner_token")
        server_name = config.cloud.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=config.hetzner_token)

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


def status(args, config: Config, server: BoundServer = None):
    """Get cloud server service status."""
    if server is None:
        config.check("hetzner_token")
        server_name = config.cloud.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=config.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server = client.servers.get_by_name(server_name)

    with Action("Getting status"):
        command = f"\"su - ubuntu -c 'github-runners service status'\""
        ssh(server, command)


def start(args, config: Config, server: BoundServer = None):
    """Start cloud server service."""
    if server is None:
        config.check("hetzner_token")
        server_name = config.cloud.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=config.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server = client.servers.get_by_name(server_name)

    with Action("Starting service"):
        command = f"\"su - ubuntu -c 'github-runners service start'\""
        ssh(server, command)


def stop(args, config: Config, server: BoundServer = None):
    """Stop cloud server service."""
    if server is None:
        config.check("hetzner_token")
        server_name = config.cloud.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=config.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server = client.servers.get_by_name(server_name)

    with Action("Stopping service"):
        command = f"\"su - ubuntu -c 'github-runners service stop'\""
        ssh(server, command)


def ssh_client(args, config: Config):
    """Open ssh client to github-runners service running
    on Hetzner server instance.
    """
    config.check("hetzner_token")
    server_name = config.cloud.server_name

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action(f"Getting server {server_name}"):
        server: BoundServer = client.servers.get_by_name(server_name)

    with Action("Opening SSH client"):
        os.system(ssh_command(server=server))


def ssh_client_command(args, config: Config):
    """Return ssh command to connect to github-runners service running
    on Hetzner server instance.
    """
    config.check("hetzner_token")
    server_name = config.cloud.server_name

    client = Client(token=config.hetzner_token)
    server: BoundServer = client.servers.get_by_name(server_name)
    print(ssh_command(server=server), file=sys.stdout)
