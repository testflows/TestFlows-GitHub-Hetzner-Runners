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
import math
import time
import copy
import queue
import random
import logging
import threading

from dataclasses import dataclass

from .actions import Action
from . import metrics
from .constants import (
    server_name_prefix,
    runner_name_prefix,
    standby_runner_name_prefix,
    recycle_server_name_prefix,
    server_ssh_key_label,
)
from .scale_up import (
    uid,
    StandbyRunner,
    ScaleUpFailureMessage,
    get_runner_server_name,
)
from .logger import logger
from .server import age
from .config import Config
from .hclient import HClient as Client

from github import Github
from github.Repository import Repository
from github.SelfHostedActionsRunner import SelfHostedActionsRunner

from hcloud.servers.client import BoundServer
from hcloud.ssh_keys.domain import SSHKey


@dataclass
class ScaleUpFailure:
    """Scale up server failure."""

    time: float
    labels: set[str]
    server_name: str
    exception: Exception
    count: int
    observed_interval: float


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
class UnusedRunner:
    """Unused self-hosted runner."""

    time: float
    runner: SelfHostedActionsRunner
    observed_interval: float


def delete_recyclable_server(
    server_name,
    recyclable_servers: list[BoundServer],
    server_prices: dict[str, dict[str, float]],
    stack_level=2,
):
    """Deleting recycle server either randomly or the cheapest if server prices are available.

    :param server_name: name of the server that we are trying to create
    :param recyclable_servers: list of recyclable servers
    :param server_prices: dictionary of server prices
    """
    if not recyclable_servers:
        return

    picking = "randomly picked"
    if server_prices is None:
        random.shuffle(recyclable_servers)
    else:
        picking = "the cheapest"

        def sorting_key(server):
            server_type_name = server.server_type.name
            server_location_name = server.datacenter.location.name
            server_age = age(server) if server else 0
            try:
                return (60 - server_age.minutes) - server_prices[server_type_name][
                    server_location_name
                ] / 60
            except KeyError:
                with Action(
                    f"price for {server_type_name} at {server_location_name} is missing",
                    level=logging.ERROR,
                    stacklevel=stack_level + 1,
                    server_name=server_name,
                ):
                    return math.inf

        recyclable_servers.sort(key=sorting_key, reverse=True)

    recyclable_server = recyclable_servers.pop()

    with Action(
        f"Deleting {picking} recyclable server {recyclable_server.name} with type "
        f"{recyclable_server.server_type.name}",
        stacklevel=stack_level,
        ignore_fail=True,
        server_name=server_name,
    ):
        recyclable_server.delete()

    return recyclable_server.name


def recycle_server(reason: str, server: BoundServer, ssh_key: SSHKey, end_of_life: int):
    """Recycle server."""
    days, hours, minutes, _ = age(server=server)

    if not server_ssh_key_label in server.labels:
        with Action(
            f"Try deleting {reason} server {server.name} "
            f"used {days}d{hours}h{minutes}m "
            "as it has no SSH key label",
            stacklevel=3,
            ignore_fail=True,
            server_name=server.name,
        ):
            try:
                server.delete()
            finally:
                return

    if server.labels[server_ssh_key_label] != ssh_key.name:
        with Action(
            f"Try deleting {reason} server {server.name} "
            f"used {days}d{hours}h{minutes}m "
            "as it has a different SSH key",
            stacklevel=3,
            ignore_fail=True,
            server_name=server.name,
        ):
            try:
                server.delete()
            finally:
                return

    if minutes >= end_of_life:
        with Action(
            f"Try deleting {reason} server {server.name} "
            f"used {days}d{hours}h{minutes}m "
            "as it is end of life",
            stacklevel=3,
            ignore_fail=True,
            server_name=server.name,
        ):
            try:
                server.delete()
            finally:
                return

    if not server.name.startswith(recycle_server_name_prefix):
        with Action(
            f"Marking {reason} server {server.name} "
            f"used {days}d{hours}h{minutes}m "
            f"for recycling with {60 - minutes}m of life",
            stacklevel=3,
            ignore_fail=True,
            server_name=server.name,
        ):
            server.power_off()
            server.update(name=f"{recycle_server_name_prefix}{uid()}")


def scale_down(
    terminate: threading.Event, mailbox: queue.Queue, ssh_key: SSHKey, config: Config
):
    """Scale down service by deleting any powered off server,
    any server that has unused runner, or any server that failed to register its
    runner (zombie server).
    """
    debug: bool = config.debug
    standby_runners: list[StandbyRunner] = config.standby_runners
    interval_period: int = config.scale_down_interval
    scaleup_interval_period: int = config.scale_up_interval
    hetzner_token: str = config.hetzner_token
    github_token: str = config.github_token
    github_repository: str = config.github_repository
    recycle: bool = config.recycle
    end_of_life: int = config.end_of_life
    max_powered_off_time: int = config.max_powered_off_time
    max_unused_runner_time: int = config.max_unused_runner_time
    max_runner_registration_time: int = config.max_runner_registration_time
    server_prices: dict[str, dict[str, float]] = config.server_prices
    powered_off_servers: dict[str, PoweredOffServer] = {}
    unused_runners: dict[str, UnusedRunner] = {}
    zombie_servers: dict[str, ZombieServer] = {}
    scaleup_failures: dict[str, ScaleUpFailure] = {}
    interval: int = -1

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=hetzner_token)

    with Action("Logging in to GitHub"):
        github = Github(login_or_token=github_token, per_page=100)

    with Action(f"Getting repository {github_repository}"):
        repo: Repository = github.get_repo(github_repository)

    while True:
        interval += 1
        current_interval = time.time()
        recyclable_servers: dict[str, BoundServer] = {}

        if terminate.is_set():
            with Action("Terminating scale down service", interval=interval):
                break

        with Action(
            "Scale down cycle", level=logging.DEBUG, ignore_fail=True, interval=interval
        ):

            with Action(
                "Getting list of servers", level=logging.DEBUG, interval=interval
            ):
                servers: list[BoundServer] = client.servers.get_all()
                servers = [
                    server
                    for server in servers
                    if server.name.startswith(server_name_prefix)
                ]

            with Action(
                "Getting runner labels for each server",
                level=logging.DEBUG,
                interval=interval,
            ):
                servers_labels = {}
                for server in servers:
                    servers_labels[server.name] = set(
                        [
                            value.lower()
                            for name, value in server.labels.items()
                            if name.startswith("github-hetzner-runner-label")
                        ]
                    )

            with Action(
                "Getting list of self-hosted runners",
                level=logging.DEBUG,
                interval=interval,
            ):
                runners: list[SelfHostedActionsRunner] = repo.get_self_hosted_runners()

            if recycle:
                with Action(
                    "Looking for recyclable servers",
                    level=logging.DEBUG,
                    interval=interval,
                ):
                    for server in servers:
                        if server.status == server.STATUS_OFF:
                            if server.name.startswith(recycle_server_name_prefix):
                                if server.name not in recyclable_servers:
                                    recyclable_servers[server.name] = server

            with Action(
                "Looking for powered off or zombie servers",
                level=logging.DEBUG,
                interval=interval,
            ):
                for server in servers:
                    if server.status == server.STATUS_OFF:
                        if not server.name.startswith(recycle_server_name_prefix):
                            if server.name not in powered_off_servers:
                                with Action(
                                    f"Found new powered off server {server.name}",
                                    server_name=server.name,
                                    interval=interval,
                                ):
                                    powered_off_servers[server.name] = PoweredOffServer(
                                        time=current_interval,
                                        server=server,
                                        observed_interval=current_interval,
                                    )
                            powered_off_servers[server.name].server = server
                            powered_off_servers[server.name].observed_interval = (
                                current_interval
                            )

                    elif server.status == server.STATUS_RUNNING:
                        if not any(
                            [
                                runner.name
                                for runner in runners
                                if runner.name.startswith(server.name)
                            ]
                        ):
                            if server.name not in zombie_servers:
                                with Action(
                                    f"Found new potential zombie server {server.name}",
                                    server_name=server.name,
                                    interval=interval,
                                ):
                                    zombie_servers[server.name] = ZombieServer(
                                        time=current_interval,
                                        server=server,
                                        observed_interval=current_interval,
                                    )
                            zombie_servers[server.name].server = server
                            zombie_servers[server.name].observed_interval = (
                                current_interval
                            )

                        else:
                            zombie_servers.pop(server.name, None)

            with Action(
                "Looking for unused runners", level=logging.DEBUG, interval=interval
            ):
                _standby_runners = copy.deepcopy(standby_runners)
                for runner in runners:
                    if (runner.status == "online" and not runner.busy) or (
                        runner.status == "offline"
                    ):
                        if runner.name.startswith(runner_name_prefix):
                            # skip any specified standby runners
                            if runner.name.startswith(standby_runner_name_prefix):
                                found = False
                                for standby_runner in _standby_runners:
                                    if set(standby_runner.labels).issubset(
                                        set(
                                            [
                                                label["name"].lower()
                                                for label in runner.labels()
                                            ]
                                        )
                                    ):
                                        standby_runner.count -= 1
                                        # check if we have too many
                                        if standby_runner.count > -1:
                                            found = True
                                        break
                                if found:
                                    continue
                            if runner.name not in unused_runners:
                                with Action(
                                    f"Found new unused runner {runner.name}",
                                    server_name=get_runner_server_name(runner.name),
                                    interval=interval,
                                ):
                                    unused_runners[runner.name] = UnusedRunner(
                                        time=current_interval,
                                        runner=runner,
                                        observed_interval=current_interval,
                                    )
                            unused_runners[runner.name].runner = runner
                            unused_runners[runner.name].observed_interval = (
                                current_interval
                            )

            with Action(
                "Checking for scale up failures", level=logging.DEBUG, interval=interval
            ):
                while not mailbox.empty():
                    try:
                        scaleup_failure: ScaleUpFailureMessage = mailbox.get(
                            block=False
                        )

                        if scaleup_failure.server_name not in scaleup_failures:
                            with Action(
                                f"Found new scale up failure for {scaleup_failure.server_name}",
                                server_name=scaleup_failure.server_name,
                                interval=interval,
                            ):
                                scaleup_failures[scaleup_failure.server_name] = (
                                    ScaleUpFailure(
                                        time=scaleup_failure.time,
                                        labels=scaleup_failure.labels,
                                        server_name=scaleup_failure.server_name,
                                        exception=scaleup_failure.exception,
                                        count=1,
                                        observed_interval=current_interval,
                                    )
                                )
                        else:
                            scaleup_failures[scaleup_failure.server_name].exception = (
                                scaleup_failure.exception
                            )
                            scaleup_failures[scaleup_failure.server_name].count += 1
                            scaleup_failures[
                                scaleup_failure.server_name
                            ].observed_interval = current_interval

                    except queue.Empty:
                        continue

            with Action(
                "Checking which powered off servers need to be deleted",
                level=logging.DEBUG,
                interval=interval,
            ):
                for server_name in list(powered_off_servers.keys()):
                    powered_off_server = powered_off_servers[server_name]

                    if powered_off_server.observed_interval != current_interval:
                        with Action(
                            f"Forgetting about powered off server {server.name}",
                            server_name=server_name,
                            interval=interval,
                        ):
                            powered_off_servers.pop(server_name)

                    else:
                        if (
                            current_interval - powered_off_server.time
                            > max_powered_off_time
                        ):
                            if recycle:
                                recycle_server(
                                    reason="powered off",
                                    server=powered_off_server.server,
                                    ssh_key=ssh_key,
                                    end_of_life=end_of_life,
                                )
                            else:
                                with Action(
                                    f"Deleting powered off server {server_name}",
                                    ignore_fail=True,
                                    server_name=server_name,
                                    interval=interval,
                                ) as action:
                                    metrics.record_server_deletion(
                                        server_type=powered_off_server.server.server_type.name,
                                        location=powered_off_server.server.datacenter.location.name,
                                        reason="powered_off",
                                    )
                                    powered_off_server.server.delete()
                            powered_off_servers.pop(server_name)

            with Action(
                "Checking which zombie servers need to be deleted",
                level=logging.DEBUG,
                interval=interval,
            ):
                for server_name in list(zombie_servers.keys()):
                    zombie_server = zombie_servers[server_name]

                    if zombie_server.observed_interval != current_interval:
                        with Action(
                            f"Forgetting about zombie server {server_name}",
                            server_name=server_name,
                            interval=interval,
                        ):
                            zombie_servers.pop(server_name)

                    else:
                        if (
                            current_interval - zombie_server.time
                            > max_runner_registration_time
                        ):
                            if recycle:
                                recycle_server(
                                    reason="zombie",
                                    server=zombie_server.server,
                                    ssh_key=ssh_key,
                                    end_of_life=end_of_life,
                                )
                            else:
                                with Action(
                                    f"Deleting zombie server {server_name}",
                                    ignore_fail=True,
                                    server_name=server_name,
                                    interval=interval,
                                ) as action:
                                    metrics.record_server_deletion(
                                        server_type=zombie_server.server.server_type.name,
                                        location=zombie_server.server.datacenter.location.name,
                                        reason="zombie",
                                    )
                                    zombie_server.server.delete()
                            zombie_servers.pop(server_name)

            with Action(
                "Checking which unused runners need to be removed",
                level=logging.DEBUG,
                interval=interval,
            ):
                for runner_name in list(unused_runners.keys()):
                    unused_runner = unused_runners[runner_name]

                    if unused_runner.observed_interval != current_interval:
                        with Action(
                            f"Forgetting about unused runner {runner_name}",
                            server_name=get_runner_server_name(runner_name),
                            interval=interval,
                        ):
                            unused_runners.pop(runner_name)

                    else:
                        if (
                            current_interval - unused_runner.time
                            > max_unused_runner_time
                        ):
                            runner_server = None

                            with Action(
                                f"Try to find server for the runner {runner_name}",
                                ignore_fail=True,
                                server_name=get_runner_server_name(runner_name),
                                interval=interval,
                            ):
                                runner_server = client.servers.get_by_name(
                                    get_runner_server_name(runner_name)
                                )

                            if runner_server is not None:
                                if recycle:
                                    recycle_server(
                                        reason="unused runner",
                                        server=runner_server,
                                        ssh_key=ssh_key,
                                        end_of_life=end_of_life,
                                    )
                                else:
                                    with Action(
                                        f"Deleting unused runner server {runner_server.name}",
                                        ignore_fail=True,
                                        server_name=runner_server.name,
                                        interval=interval,
                                    ):
                                        metrics.record_server_deletion(
                                            server_type=runner_server.server_type.name,
                                            location=runner_server.datacenter.location.name,
                                            reason="unused",
                                        )
                                        runner_server.delete()
                                runner_server = None

                            if runner_server is None:
                                with Action(
                                    f"Removing self-hosted runner {runner_name}",
                                    ignore_fail=True,
                                    server_name=get_runner_server_name(runner_name),
                                    interval=interval,
                                ):
                                    repo.remove_self_hosted_runner(unused_runner.runner)
                                    unused_runners.pop(runner_name)

            with Action(
                "Checking which recyclable servers need to be deleted",
                level=logging.DEBUG,
                interval=interval,
            ):
                for server_name in list(recyclable_servers.keys()):
                    if terminate.is_set():
                        break
                    recyclable_server = recyclable_servers[server_name]
                    recycle_server(
                        reason="unused recyclable",
                        server=recyclable_server,
                        ssh_key=ssh_key,
                        end_of_life=end_of_life,
                    )
                    recyclable_servers.pop(server_name)

            with Action(
                "Checking which recyclable servers need to be deleted to try to resolve scale up failures",
                level=logging.DEBUG,
                interval=interval,
            ):
                process_failures = []

                for server_name in list(scaleup_failures.keys()):
                    scaleup_failure: ScaleUpFailure = scaleup_failures[server_name]

                    if terminate.is_set():
                        break

                    forget_reason = ""
                    forget_failure = False
                    for labels in servers_labels.values():
                        if scaleup_failure.labels.issubset(labels):
                            forget_reason = " at least one server could match labels"
                            forget_failure = True

                    if scaleup_failure.count < 2 and (
                        current_interval - scaleup_failure.time
                        > 2 * scaleup_interval_period
                    ):
                        forget_reason = " sporadic fail"
                        forget_failure = True

                    if not recyclable_servers:
                        forget_reason = " no recyclable servers to delete"
                        forget_failure = True

                    if forget_failure:
                        with Action(
                            f"Forgetting about scale up failure for {server_name}{forget_reason}",
                            server_name=server_name,
                            interval=interval,
                        ):
                            scaleup_failures.pop(server_name)
                    else:
                        process_failures.append(scaleup_failure)

                if recyclable_servers:
                    for scaleup_failure in process_failures:
                        if scaleup_failure.count > 2 and (
                            current_interval - scaleup_failure.time
                            > 2 * scaleup_interval_period
                        ):
                            with Action(
                                f"Picking recyclable server to be deleted to resolve scale up failure for {scaleup_failure.server_name}",
                                server_name=scaleup_failure.server_name,
                                interval=interval,
                            ):
                                deleted_recyclable_server_name = (
                                    delete_recyclable_server(
                                        recyclable_servers=list(
                                            recyclable_servers.values()
                                        ),
                                        server_prices=server_prices,
                                        stack_level=3,
                                        server_name=server_name,
                                    )
                                )
                                if deleted_recyclable_server_name is not None:
                                    recyclable_servers.pop(
                                        deleted_recyclable_server_name
                                    )
                                    scaleup_failures.pop(scaleup_failure.server_name)

        with Action(
            f"Sleeping until next interval {interval_period}s",
            level=logging.DEBUG,
            interval=interval,
        ):
            time.sleep(interval_period)
