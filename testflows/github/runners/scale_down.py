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
import logging
import threading

from dataclasses import dataclass

from .actions import Action
from .scale_up import runner_server_prefix

from github.Repository import Repository
from github.SelfHostedActionsRunner import SelfHostedActionsRunner

from hcloud import Client
from hcloud.servers.client import BoundServer


@dataclass
class PoweredOffServer:
    """Powered off server."""

    time: float
    server: BoundServer
    observed_interval: float


@dataclass
class ZombieServer:
    """Zombie server."""

    time: float
    server: BoundServer
    observed_interval: float


@dataclass
class IdleRunner:
    """Idle self-hosted runner."""

    time: float
    runner: SelfHostedActionsRunner
    observed_interval: float


def scale_down(
    terminate: threading.Event,
    repo: Repository,
    client: Client,
    max_powered_off_time: int,
    max_idle_runner_time: int,
    max_runner_registration_time: int,
    interval: int,
):
    """Scale down service by deleting any powered off server,
    any server that has stale idle runner, or any server that failed to register its
    runner (zombie server).
    """
    powered_off_servers: dict[str, PoweredOffServer] = {}
    idle_runners: dict[str, IdleRunner] = {}
    zombie_servers: dict[str, ZombieServer] = {}

    while True:
        current_interval = time.time()

        if terminate.is_set():
            with Action("Terminating scale down service"):
                break

        with Action("Getting list of servers", level=logging.DEBUG):
            servers: list[BoundServer] = client.servers.get_all()
            servers = [
                server
                for server in servers
                if server.name.startswith(runner_server_prefix)
            ]

        with Action("Getting list of self-hosted runners", level=logging.DEBUG):
            runners: list[SelfHostedActionsRunner] = repo.get_self_hosted_runners()

        with Action("Looking for powered off or zombie servers", level=logging.DEBUG):
            for server in servers:
                if server.status == server.STATUS_OFF:
                    if server.name not in powered_off_servers:
                        with Action(f"Found new powered off server {server.name}"):
                            powered_off_servers[server.name] = PoweredOffServer(
                                time=time.time(),
                                server=server,
                                observed_interval=current_interval,
                            )
                    powered_off_servers[server.name].server = server
                    powered_off_servers[
                        server.name
                    ].observed_interval = current_interval

                elif server.status == server.STATUS_RUNNING:
                    if server.name not in [runner.name for runner in runners]:
                        if server.name not in zombie_servers:
                            with Action(
                                f"Found new potential zombie server {server.name}"
                            ):
                                zombie_servers[server.name] = ZombieServer(
                                    time=time.time(),
                                    server=server,
                                    observed_interval=current_interval,
                                )
                        zombie_servers[server.name].server = server
                        zombie_servers[server.name].observed_interval = current_interval

                    else:
                        zombie_servers.pop(server.name, None)

        with Action("Looking for idle runners", level=logging.DEBUG):
            for runner in runners:
                if runner.status == "online" and not runner.busy:
                    if runner.name not in idle_runners:
                        with Action(f"Found new idle runner {runner.name}"):
                            idle_runners[runner.name] = IdleRunner(
                                time=time.time(),
                                runner=runner,
                                observed_interval=current_interval,
                            )
                    idle_runners[runner.name].runner = runner
                    idle_runners[runner.name].observed_interval = current_interval

        with Action(
            "Checking which powered off servers need to be deleted", level=logging.DEBUG
        ):
            for server_name in list(powered_off_servers.keys()):
                powered_off_server = powered_off_servers[server_name]

                if powered_off_server.observed_interval != current_interval:
                    with Action(f"Forgetting about powered off server {server.name}"):
                        powered_off_servers.pop(server_name)

                else:
                    if time.time() - powered_off_server.time > max_powered_off_time:
                        with Action(
                            f"Deleting powered off server {server_name}",
                            ignore_fail=True,
                        ) as action:
                            powered_off_server.server.delete()
                            powered_off_servers.pop(server_name)

        with Action(
            "Checking which zombie servers need to be deleted", level=logging.DEBUG
        ):
            for server_name in list(zombie_servers.keys()):
                zombie_server = zombie_servers[server_name]

                if zombie_server.observed_interval != current_interval:
                    with Action(f"Forgetting about zombie server {server.name}"):
                        zombie_servers.pop(server_name)

                else:
                    if time.time() - zombie_server.time > max_runner_registration_time:
                        with Action(
                            f"Deleting zombie server {server_name}",
                            ignore_fail=True,
                        ) as action:
                            zombie_server.server.delete()
                            zombie_servers.pop(server_name)

        with Action(
            "Checking which idle runners need to be removed and their servers deleted",
            level=logging.DEBUG,
        ):

            for idle_runner_name in list(idle_runners.keys()):
                idle_runner = idle_runners[idle_runner_name]

                if idle_runner.observed_interval != current_interval:
                    with Action(f"Forgetting about idle runner {idle_runner_name}"):
                        idle_runners.pop(idle_runner_name)

                else:
                    if time.time() - idle_runner.time > max_idle_runner_time:
                        runner_server = None

                        with Action(
                            f"Try to find server for the runner {idle_runner_name}",
                            ignore_fail=True,
                        ):
                            runner_server = client.servers.get_by_name(idle_runner_name)

                        if runner_server is not None:
                            with Action(
                                f"Deleting idle runner server {runner_server.name}",
                                ignore_fail=True,
                            ):
                                runner_server.delete()
                                runner_server = None

                        if runner_server is None:
                            with Action(
                                f"Removing self-hosted runner {idle_runner_name}",
                                ignore_fail=True,
                            ):
                                repo.remove_self_hosted_runner(idle_runner.runner)

        with Action(f"Sleeping until next interval {interval}s", level=logging.DEBUG):
            time.sleep(interval)
