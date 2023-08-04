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
import time

from datetime import datetime, timezone
from collections import namedtuple

from hcloud.servers.client import BoundServer

from .actions import Action
from .shell import shell

ServerAge = namedtuple("ServerAge", "days hours minutes seconds")


def age(server: BoundServer):
    """Return server's age."""
    now = datetime.now(timezone.utc)
    used = now - server.created
    days = used.days
    hours, remainder = divmod(used.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return ServerAge(days=days, hours=hours, minutes=minutes, seconds=seconds)


def ip_address(server: BoundServer):
    """Return IPv4 address of the server."""
    return server.public_net.primary_ipv4.ip


def wait_ssh(server: BoundServer, timeout: float):
    """Wait until SSH connection is ready."""
    ip = ip_address(server=server)

    attempt = -1
    start_time = time.time()

    while True:
        attempt += 1
        with Action(
            f"Trying to connect to {server.name}@{ip}...{attempt}",
            ignore_fail=True,
            stacklevel=3,
            server_name=server.name,
        ):
            returncode = ssh(server, "hostname", check=False, stacklevel=4)
            if returncode == 0:
                break
        if time.time() - start_time >= timeout:
            ssh(server, "hostname")
        else:
            time.sleep(5)


def ssh_command(server: BoundServer):
    """Return ssh command."""
    ip = ip_address(server=server)
    return f'ssh -q -o "StrictHostKeyChecking no" root@{ip}'


def ssh(server: BoundServer, cmd: str, *args, stacklevel=3, **kwargs):
    """Execute command over SSH."""
    return shell(
        f"{ssh_command(server=server)} {cmd}",
        *args,
        **kwargs,
        server_name=server.name,
        stacklevel=stacklevel,
    )


def scp(source: str, destination: str, *args, **kwargs):
    """Execute copy over SSH."""
    scp_command = f'scp -q -o "StrictHostKeyChecking no" {source} {destination}'
    return shell(f"{scp_command}", *args, **kwargs)


def wait_ready(server: BoundServer, timeout: float, action: Action = None):
    """Wait for server to be ready."""
    start_time = time.time()

    while True:
        status = server.status
        if action:
            action.note(f"{server.name} {status}", stacklevel=4)
        if status == server.STATUS_RUNNING:
            break
        if time.time() - start_time >= timeout:
            raise TimeoutError("waiting for server to start running")
        time.sleep(1)
        server.reload()
