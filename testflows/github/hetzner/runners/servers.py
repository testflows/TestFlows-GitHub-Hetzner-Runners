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

from github import Github
from github.Repository import Repository
from github.SelfHostedActionsRunner import SelfHostedActionsRunner

from hcloud.servers.client import BoundServer
from hcloud.servers.domain import Server

from .actions import Action
from .config import Config
from .server import ssh_command
from .scale_up import server_name_prefix, runner_name_prefix
from .hclient import HClient as Client
from .request import request
from .constants import github_runner_label

status_icon = {
    Server.STATUS_INIT: "⏳",
    Server.STATUS_DELETING: "🗑️",
    Server.STATUS_MIGRATING: "📦",
    Server.STATUS_OFF: "🔴",
    Server.STATUS_REBUILDING: "🛠️",
    Server.STATUS_RUNNING: "🟢",
    Server.STATUS_STARTING: "🚀",
    Server.STATUS_STOPPING: "🛑",
    Server.STATUS_UNKNOWN: "❓",
}


def list(args, config: Config):
    """List all current runner servers."""
    config.check("hetzner_token")

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action("Getting a list of servers"):
        servers = client.servers.get_all(label_selector=f"{github_runner_label}=active")

    if not servers:
        print("No servers found", file=sys.stdout)
        return

    list_servers = []

    if args.list_name:
        list_servers += [
            s for s in servers if any([s.name.startswith(n) for n in args.list_name])
        ]

    if args.list_server_name:
        list_servers += [s for s in servers if s.name in args.list_server_name]

    if args.list_id:
        list_servers += [s for s in servers if s.id in args.list_id]

    if not args.list_name and not args.list_server_name and not args.list_id:
        # list all servers by default
        args.list_all = True

    if args.list_all:
        list_servers = servers[:]

    if not list_servers:
        print("No servers selected", file=sys.stderr)
        return

    print(
        "  ",
        f"{'status':10}",
        "name,",
        "id,",
        "type,",
        "location,",
        "image",
        file=sys.stdout,
    )

    for server in list_servers:
        icon = status_icon.get(server.status, "❓")
        print(
            icon,
            f"{server.status:10}",
            server.name,
            server.id,
            server.server_type.name,
            server.datacenter.location.name,
            server.image.name,
            file=sys.stdout,
        )


def delete(args, config: Config):
    """Delete runners and servers."""
    config.check("hetzner_token")

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action("Logging in to GitHub"):
        github = Github(login_or_token=config.github_token)

    with Action(f"Getting repository {config.github_repository}"):
        repo: Repository = github.get_repo(config.github_repository)

    with Action("Getting list of self-hosted runners"):
        runners: list[SelfHostedActionsRunner] = repo.get_self_hosted_runners()
        runners = [
            runner for runner in runners if runner.name.startswith(runner_name_prefix)
        ]

    with Action("Getting list of servers"):
        servers: list[BoundServer] = client.servers.get_all(
            label_selector=f"{github_runner_label}=active"
        )

    if not runners and not servers:
        print("No servers found", file=sys.stdout)
        return

    delete_runners = []
    delete_servers = []

    if args.delete_name:
        delete_runners += [
            r for r in runners if any([r.name.startswith(n) for n in args.delete_name])
        ]
        delete_servers += [
            s for s in servers if any([s.name.startswith(n) for n in args.delete_name])
        ]

    if args.delete_server_name:
        delete_servers_by_name = [
            s for s in servers if s.name in args.delete_server_name
        ]
        delete_runners += [
            r for r in runners if r.name in [s.name for s in delete_servers_by_name]
        ]
        delete_servers += delete_servers_by_name

    if args.delete_id:
        # we can only delete servers by id
        delete_servers_by_id = [s for s in servers if s.id in args.delete_id]
        delete_runners += [
            r for r in runners if r.name in [s.name for s in delete_servers_by_id]
        ]
        delete_servers += delete_servers_by_id

    if args.delete_all:
        delete_servers = servers[:]
        delete_runners = runners[:]

    if not delete_runners and not delete_servers:
        print("No servers selected", file=sys.stderr)
        return

    for runner in delete_runners:
        with Action(f"🗑️  Deleting runner {runner.name}") as action:
            _, resp = request(
                f"https://api.github.com/repos/{config.github_repository}/actions/runners/{runner.id}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {config.github_token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                method="DELETE",
                data={},
            )
            action.note(f"   {resp.status}")

    for server in delete_servers:
        with Action(
            f"🗑️  Deleting server {server.name} with id {server.id} in {server.datacenter.location.name}"
        ):
            server.delete()


def ssh_client(args, config: Config, server_name: str = None):
    """Open ssh client to the server."""
    config.check("hetzner_token")

    if server_name is None:
        server_name = args.name

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action(f"Getting server {server_name}"):
        server: BoundServer = client.servers.get_by_name(server_name)

        if server is None:
            raise ValueError(f"server not found")

        if server.status != server.STATUS_RUNNING:
            raise ValueError(f"server status is {server.status}")

    with Action("Opening SSH client"):
        os.system(ssh_command(server=server))


def ssh_client_command(args, config: Config, server_name: str = None):
    """Return ssh command to connect server."""
    config.check("hetzner_token")

    if server_name is None:
        server_name = args.name

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action(f"Getting server {server_name}"):
        server: BoundServer = client.servers.get_by_name(server_name)

        if server is None:
            raise ValueError(f"server not found")

    print(ssh_command(server=server), file=sys.stdout)
