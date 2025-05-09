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

from hcloud.servers.client import BoundServer
from hcloud.servers.domain import Server

from .actions import Action
from .config import Config
from .server import ssh_command
from .scale_up import server_name_prefix
from .hclient import HClient as Client

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
        servers = client.servers.get_all()
        if not servers:
            print("No servers found", file=sys.stdout)
            return

        print("  ", f"{'status':10}", "name", file=sys.stdout)

        for server in servers:
            if not server.name.startswith("github-hetzner-runner"):
                continue
            icon = status_icon.get(server.status, "❓")
            print(icon, f"{server.status:10}", server.name, file=sys.stdout)


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
