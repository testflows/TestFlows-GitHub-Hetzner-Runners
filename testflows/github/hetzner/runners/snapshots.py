#!/usr/bin/env python3
# Copyright 2024 Katteli Inc.
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
from hcloud import Client
from hcloud.servers.client import BoundServer

from .actions import Action
from .config import Config, check_ssh_key, check_setup_script
from .server import wait_ready, wait_ssh, ssh


def create(args, config: Config, timeout=60):
    """Create custom snapshot image."""

    snapshot_name = args.create_snapshots_name

    config.check("hetzner_token")
    check_setup_script(args.create_snapshots_setup_script)

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action("Check SSH key"):
        ssh_keys = [check_ssh_key(client, config.ssh_key)]

    with Action(f"Creating server {args.create_snapshots_server_name}"):
        response = client.servers.create(
            name=args.create_snapshots_server_name,
            server_type=args.create_snapshots_server_type,
            image=args.create_snapshots_server_image,
            ssh_keys=ssh_keys,
        )
        server: BoundServer = response.server

    try:
        with Action(f"Waiting for server {server.name} to be ready"):
            wait_ready(server=server, timeout=timeout)

        with Action("Wait for SSH connection to be ready"):
            wait_ssh(server=server, timeout=timeout)

        with Action("Executing setup script"):
            ssh(server, f"bash -s  < {args.create_snapshots_setup_script}")

        with Action("Power off the server"):
            server.shutdown().wait_until_finished()

        with Action(f"Generate snapshot {snapshot_name}"):
            server.create_image(description=snapshot_name)

    finally:
        with Action(f"Remove {server.name} server instance"):
            server.delete()
