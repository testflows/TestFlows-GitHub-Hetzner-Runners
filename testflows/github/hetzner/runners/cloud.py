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
import tempfile

from hcloud import Client
from hcloud.ssh_keys.domain import SSHKey
from hcloud.servers.client import BoundServer

from .actions import Action
from .config import (
    Config,
    check_image,
    check_location,
    check_server_type,
    check_ssh_key,
    write as write_config,
    read as read_config,
)
from . import __version__

from .server import wait_ready, wait_ssh, ssh, scp, ip_address, ssh_command
from .servers import ssh_client as server_ssh_client
from .servers import ssh_client_command as server_ssh_client_command
from .service import command_options

current_dir = os.path.dirname(__file__)
deploy_scripts_folder = "/home/ubuntu/.github-hetzner-runners/scripts/"
deploy_configs_folder = "/home/ubuntu/.github-hetzner-runners/"


def deploy(args, config: Config, redeploy=False):
    """Deploy or redeploy github-hetzner-runners as a service to a
    new Hetzner server instance."""
    config.check()
    version = args.version or __version__
    server_name = config.cloud.server_name
    ssh_keys: list[SSHKey] = []

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action(f"Checking if SSH key exists"):
        ssh_keys.append(check_ssh_key(client, config.ssh_key))

        if config.additional_ssh_keys:
            for key in config.additional_ssh_keys:
                ssh_keys.append(check_ssh_key(client, key, is_file=False))

    if redeploy:
        with Action(f"Getting server {server_name}"):
            server: BoundServer = client.servers.get_by_name(server_name)
            if not server:
                raise ValueError(f"server {server_name} not found")

        uninstall(args=args, config=config, server=server)

        with Action("Cleaning copied scripts"):
            ssh(server, f"rm -rf {deploy_scripts_folder}*", stacklevel=4)

        with Action("Cleaning copied configs"):
            ssh(server, f"rm -rf {deploy_configs_folder}*.yaml", stacklevel=4)

    else:
        deploy_setup_script = config.cloud.deploy.setup_script or os.path.join(
            current_dir, "scripts", "deploy", "setup.sh"
        )

        if args.force:
            with Action(
                f"Checking if server {server_name} already exists", ignore_fail=True
            ):
                server: BoundServer = client.servers.get_by_name(server_name)
                if server is not None:
                    with Action(f"Deleting server {server_name}"):
                        server.delete()

        with Action("Checking if default image exists"):
            config.default_image = check_image(
                client=client, image=config.default_image
            )

        with Action("Checking if default location exists"):
            config.default_location = check_location(client, config.default_location)

        with Action("Checking if default server type exists"):
            config.default_server_type = check_server_type(
                client, config.default_server_type
            )

        with Action("Checking if cloud service server type exists"):
            config.cloud.deploy.server_type = check_server_type(
                client=client, server_type=config.cloud.deploy.server_type
            )

        with Action("Checking if cloud service server image exists"):
            config.cloud.deploy.image = check_image(
                client=client, image=config.cloud.deploy.image
            )

        with Action("Checking if cloud service server location exists"):
            config.cloud.deploy.location = check_location(
                client=client, location=config.cloud.deploy.location
            )

        with Action(f"Creating new server"):
            response = client.servers.create(
                name=server_name,
                server_type=config.cloud.deploy.server_type,
                image=config.cloud.deploy.image,
                location=config.cloud.deploy.location,
                ssh_keys=ssh_keys,
            )
            server: BoundServer = response.server

        with Action(f"Waiting for server to be ready") as action:
            wait_ready(
                server=server, timeout=config.max_server_ready_time, action=action
            )

        with Action("Wait for SSH connection to be ready"):
            wait_ssh(server=server, timeout=config.max_server_ready_time)

        with Action("Executing setup.sh script"):
            ssh(server, f"bash -s  < {deploy_setup_script}", stacklevel=4)

    with Action(f"Installing github-hetzner-runners {version}"):
        command = (
            f"'sudo -u ubuntu pip3 install testflows.github.hetzner.runners=={version}'"
        )

        if version.strip().lower() == "latest":
            command = f"'sudo -u ubuntu pip3 install testflows.github.hetzner.runners'"
            if redeploy:
                command.replace("pip3 install", "pip3 install --upgrade")

        ssh(server, command, stacklevel=4)

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
        ssh(server, f"chown -R ubuntu:ubuntu {deploy_scripts_folder}", stacklevel=4)

    with Action(
        f"Copying config file{(' ' + config.config_file) if config.config_file else ''}"
    ):
        with tempfile.NamedTemporaryFile("w") as file:
            with Action(
                f"{'Modifying' if config.config_file else 'Creating'} "
                "config file and adding this SSH key to the SSH keys list"
            ):
                raw_config = {"config": {}}
                if config.config_file:
                    raw_config = read_config(config.config_file)
                additional_ssh_keys = raw_config["config"].get(
                    "additional_ssh_keys", []
                )
                additional_ssh_keys.append(ssh_keys[0].public_key)
                raw_config["config"]["additional_ssh_keys"] = list(
                    set(additional_ssh_keys)
                )
                write_config(file, raw_config)
                file.flush()
            scp(
                source=file.name,
                destination=f"root@{ip}:{deploy_configs_folder}config.yaml",
            )
            config.config_file = os.path.join(
                deploy_configs_folder,
                "config.yaml",
            )

    with Action("Fixing ownership of any copied configs"):
        ssh(server, f"chown -R ubuntu:ubuntu {deploy_configs_folder}", stacklevel=4)

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
            if not server:
                raise ValueError(f"server {server_name} not found")

    with Action("Installing service"):
        command = f"\"su - ubuntu -c '"
        command += "github-hetzner-runners"
        command += command_options(
            config,
            github_token=config.github_token,
            github_repository=config.github_repository,
            hetzner_token=config.hetzner_token,
        )
        command += " service install -f'\""

        ssh(server, command)


def upgrade(args, config: Config):
    """Upgrade github-hetzner-runners application on a cloud instance."""
    config.check("hetzner_token")
    server_name = config.cloud.server_name
    upgrade_version = args.upgrade_version

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action(f"Getting server {server_name}"):
        server: BoundServer = client.servers.get_by_name(server_name)
        if not server:
            raise ValueError(f"server {server_name} not found")

    stop(args, config=config, server=server)

    if upgrade_version:
        with Action(f"Upgrading github-hetzner-runners to version {upgrade_version}"):
            ssh(
                server,
                f"'sudo -u ubuntu pip3 install testflows.github.hetzner.runners=={upgrade_version}'",
                stacklevel=4,
            )
    else:
        with Action(f"Upgrading github-hetzner-runners the latest version"):
            ssh(
                server,
                f"'sudo -u ubuntu pip3 install --upgrade testflows.github.hetzner.runners'",
                stacklevel=4,
            )

    start(args, config=config, server=server)


def uninstall(args, config: Config, server: BoundServer = None):
    """Uninstall github-hetzner-runners service from a cloud instance."""
    if server is None:
        config.check("hetzner_token")
        server_name = config.cloud.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=config.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server: BoundServer = client.servers.get_by_name(server_name)
            if not server:
                raise ValueError(f"server {server_name} not found")

    with Action("Uninstalling service"):
        command = f"\"su - ubuntu -c 'github-hetzner-runners service uninstall'\""
        ssh(server, command, stacklevel=4)


def delete(args, config: Config):
    """Delete github-hetzner-runners service running
    on Hetzner server instance by stopping the service
    and deleting the server."""
    config.check("hetzner_token")
    server_name = config.cloud.server_name

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action(f"Getting server {server_name}"):
        server: BoundServer = client.servers.get_by_name(server_name)
        if not server:
            raise ValueError(f"server {server_name} not found")

    with Action("Uninstalling service", ignore_fail=True):
        command = f"\"su - ubuntu -c 'github-hetzner-runners service uninstall'\""
        ssh(server, command, stacklevel=4)

    with Action(f"Deleting server {server_name}"):
        server.delete()


def log(args, config: Config, server: BoundServer = None):
    """Get cloud server service log."""
    if server is None:
        config.check("hetzner_token")
        server_name = config.cloud.server_name

        client = Client(token=config.hetzner_token)
        server: BoundServer = client.servers.get_by_name(server_name)

        if not server:
            raise ValueError(f"server {server_name} not found")

    command = (
        f"\"su - ubuntu -c 'github-hetzner-runners service log"
        + (" -f" if args.follow else "")
        + (f" -c {args.columns.value}" if args.columns else "")
        + (f" -n {args.lines}" if args.lines else "")
        + (" --raw" if args.raw else "")
        + "'\""
    )
    ssh(server, command, use_logger=False, stacklevel=4)


def delete_log(args, config: Config, server: BoundServer = None):
    """Delete cloud server service log."""
    if server is None:
        config.check("hetzner_token")
        server_name = config.cloud.server_name

        client = Client(token=config.hetzner_token)
        server: BoundServer = client.servers.get_by_name(server_name)

        if not server:
            raise ValueError(f"server {server_name} not found")

    command = f"\"su - ubuntu -c 'github-hetzner-runners service log delete'\""
    ssh(server, command, use_logger=False, stacklevel=4)


def status(args, config: Config, server: BoundServer = None):
    """Get cloud server service status."""
    if server is None:
        config.check("hetzner_token")
        server_name = config.cloud.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=config.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server = client.servers.get_by_name(server_name)
            if not server:
                raise ValueError(f"server {server_name} not found")

    with Action("Getting status"):
        command = f"\"su - ubuntu -c 'github-hetzner-runners service status'\""
        ssh(server, command, stacklevel=4)


def start(args, config: Config, server: BoundServer = None):
    """Start cloud server service."""
    if server is None:
        config.check("hetzner_token")
        server_name = config.cloud.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=config.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server = client.servers.get_by_name(server_name)
            if not server:
                raise ValueError(f"server {server_name} not found")

    with Action("Starting service"):
        command = f"\"su - ubuntu -c 'github-hetzner-runners service start'\""
        ssh(server, command, stacklevel=4)


def stop(args, config: Config, server: BoundServer = None):
    """Stop cloud server service."""
    if server is None:
        config.check("hetzner_token")
        server_name = config.cloud.server_name

        with Action("Logging in to Hetzner Cloud"):
            client = Client(token=config.hetzner_token)

        with Action(f"Getting server {server_name}"):
            server = client.servers.get_by_name(server_name)
            if not server:
                raise ValueError(f"server {server_name} not found")

    with Action("Stopping service"):
        command = f"\"su - ubuntu -c 'github-hetzner-runners service stop'\""
        ssh(server, command, stacklevel=4)


def ssh_client(args, config: Config):
    """Open ssh client to github-hetzner-runners service running
    on Hetzner server instance.
    """
    config.check("hetzner_token")
    server_name = config.cloud.server_name

    server_ssh_client(args=args, config=config, server_name=server_name)


def ssh_client_command(args, config: Config):
    """Return ssh command to connect to github-hetzner-runners service running
    on Hetzner server instance.
    """
    config.check("hetzner_token")
    server_name = config.cloud.server_name

    server_ssh_client_command(args=args, config=config, server_name=server_name)
