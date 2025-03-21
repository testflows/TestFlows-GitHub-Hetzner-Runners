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
import socket
import ipaddress
import subprocess
import signal

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
    """Return IPv4 (default) or IPv6 address of the server."""
    if server.public_net.primary_ipv4 is not None:
        return server.public_net.primary_ipv4.ip
    return (
        ipaddress.IPv6Network(
            server.public_net.primary_ipv6.ip, strict=False
        ).network_address
        + 1
    )


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


def ssh_command(server: BoundServer, options: str = ""):
    """Return ssh command."""
    ip = ip_address(server=server)
    return f'ssh -q -o "StrictHostKeyChecking no" {options}{" " if options else ""}root@{ip}'


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


class ssh_tunnel:
    """Context manager for establishing SSH tunnels."""

    def __init__(
        self,
        server: BoundServer,
        local_port: int,
        remote_port: int,
        action: Action = None,
    ):
        """Initialize SSH tunnel.

        Args:
            server: Hetzner server to connect to
            local_port: Local port to bind the tunnel to
            remote_port: Remote port to forward to
            action: Optional Action context for logging
        """
        self.server = server
        self.local_port = local_port
        self.remote_port = remote_port
        self.process = None
        self.action = action

    def __enter__(self):
        # SSH tunnel options:
        # -N: don't execute remote command
        # -L: local port forwarding
        # -q: quiet mode
        # -o StrictHostKeyChecking=no: don't check host key
        options = f"-N -L {self.local_port}:localhost:{self.remote_port}"
        full_cmd = f"{ssh_command(server=self.server, options=options)}"

        if self.action:
            self.action.note(
                f"Establishing SSH tunnel from remote port {self.remote_port} to local port {self.local_port}",
                stacklevel=4,
            )

        self.process = subprocess.Popen(
            full_cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp,  # Create new process group
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass

    def wait_ready(self, timeout: float = 10.0, check_interval: float = 1):
        """Wait for the SSH tunnel to be ready by attempting to connect to the local port.

        Args:
            timeout: Maximum time to wait in seconds
            check_interval: Time between connection attempts in seconds

        Returns:
            True if tunnel is ready, False if timeout occurred
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.25)  # Short timeout for connection attempt
                result = sock.connect_ex(("127.0.0.1", self.local_port))
                sock.close()
                if result == 0:
                    return True
            except Exception:
                pass
            time.sleep(check_interval)

        return False
