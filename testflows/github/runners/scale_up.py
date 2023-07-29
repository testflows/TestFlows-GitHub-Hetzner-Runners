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
import uuid
import logging
import threading

from dataclasses import dataclass

from .actions import Action
from .scripts import Scripts
from .request import request
from .args import image_type
from .logger import logger
from .config import check_image
from .config import standby_runner as StandbyRunner

from .server import wait_ssh, ssh, wait_ready

from hcloud import Client
from hcloud.ssh_keys.domain import SSHKey
from hcloud.server_types.domain import ServerType
from hcloud.locations.domain import Location
from hcloud.servers.client import BoundServer
from hcloud.servers.domain import Server
from hcloud.images.domain import Image
from hcloud.helpers.labels import LabelValidator

from github.Repository import Repository
from github.WorkflowJob import WorkflowJob
from github.WorkflowRun import WorkflowRun
from github.SelfHostedActionsRunner import SelfHostedActionsRunner

from concurrent.futures import ThreadPoolExecutor, Future

server_name_prefix = "github-runner-"
runner_name_prefix = server_name_prefix
standby_server_name_prefix = f"{server_name_prefix}standby-"
standby_runner_name_prefix = standby_server_name_prefix


@dataclass
class RunnerServer:
    name: str
    labels: set[str]
    server_status: str = Server.STATUS_STARTING
    status: str = "initializing"  # busy, ready


def server_setup(
    server: BoundServer,
    setup_script: str,
    startup_script: str,
    github_token: str,
    github_repository: str,
    runner_labels: str,
    timeout: float = 60,
):
    """Setup new server instance."""
    with Action("Wait for SSH connection to be ready"):
        wait_ssh(server=server, timeout=timeout)

    with Action("Getting registration token for the runner"):
        content, resp = request(
            f"https://api.github.com/repos/{github_repository}/actions/runners/registration-token",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {github_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            data={},
            format="json",
        )
        GITHUB_RUNNER_TOKEN = content["token"]

    with Action("Getting current directory"):
        current_dir = os.path.dirname(__file__)

    with Action("Executing setup.sh script"):
        ssh(server, f"bash -s  < {setup_script}")

    with Action("Executing startup.sh script"):
        ssh(
            server,
            f"'sudo -u ubuntu "
            f"GITHUB_REPOSITORY=\"{os.getenv('GITHUB_REPOSITORY')}\" "
            f'GITHUB_RUNNER_TOKEN="{GITHUB_RUNNER_TOKEN}" '
            f"GITHUB_RUNNER_GROUP=Default "
            f'GITHUB_RUNNER_LABELS="{runner_labels}" '
            f"bash -s' < {startup_script}",
        )


def get_server_type(labels: set[str], default: ServerType, label_prefix="type-"):
    """Get server type for the specified job."""
    server_type = None

    if server_type is None:
        for label in labels:
            if label.startswith(label_prefix):
                server_type_name = label.split(label_prefix, 1)[-1].lower()
                server_type = ServerType(name=server_type_name)

    if server_type is None:
        server_type = default

    return server_type


def get_server_location(labels: set[str], default: Location = None, label_prefix="in-"):
    """Get preferred server location for the specified job.

    By default, location is set to `None` to avoid server type mismatching
    the location as some server types are not available at some locations.
    """
    server_location: Location = None

    if server_location is None:
        for label in labels:
            if label.startswith(label_prefix):
                server_location_name = label.split(label_prefix, 1)[-1].lower()
                server_location = Location(name=server_location_name)

    if server_location is None and default:
        server_location = default

    return server_location


def get_server_image(
    client: Client, labels: set[str], default: Image, label_prefix="image-"
):
    """Get preferred server image for the specified job."""
    server_image: Image = None

    if server_image is None:
        for label in labels:
            if label.startswith(label_prefix):
                server_image = check_image(
                    client,
                    image_type(label.split(label_prefix, 1)[-1].lower(), separator="-"),
                )

    if server_image is None:
        server_image = default

    return server_image


def get_startup_script(server_type: ServerType, scripts: Scripts):
    """Get startup script based on the requested server type.
    ARM64 servers type names start with "CA" prefix.

    For example, CAX11, CAX21, CAX31, and CAX41
    """
    if server_type.name.lower().startswith("ca"):
        return scripts.startup_arm64

    return scripts.startup_x64


def create_server(
    setup_worker_pool: ThreadPoolExecutor,
    client: Client,
    labels: set[str],
    name: str,
    default_server_type: ServerType,
    default_location: Location,
    default_image: Image,
    scripts: Scripts,
    github_token: str,
    github_repository: str,
    ssh_key: SSHKey,
    timeout=60,
):
    """Create specified number of server instances."""

    server_type = get_server_type(labels=labels, default=default_server_type)
    server_location = get_server_location(labels=labels, default=default_location)
    server_image = get_server_image(client=client, labels=labels, default=default_image)
    startup_script = get_startup_script(server_type=server_type, scripts=scripts)

    server_labels = {
        f"github-runner-label-{i}": value for i, value in enumerate(labels)
    }

    with Action("Validating server labels"):
        valid, error_msg = LabelValidator.validate_verbose(labels=server_labels)
        if not valid:
            raise ValueError(f"invalid server labels {server_labels}: {error_msg}")

    with Action(f"Creating server {name} with labels {labels}"):
        response = client.servers.create(
            name=name,
            server_type=server_type,
            location=server_location,
            image=server_image,
            ssh_keys=[ssh_key],
            labels=server_labels,
        )
        server: BoundServer = response.server

    with Action(f"Waiting for server {server.name} to be ready") as action:
        wait_ready(server=server, timeout=timeout, action=action)

    setup_worker_pool.submit(
        server_setup,
        server=response.server,
        setup_script=scripts.setup,
        startup_script=startup_script,
        github_token=github_token,
        github_repository=github_repository,
        runner_labels=",".join(labels),
        timeout=timeout,
    )


def count_available(servers: list[RunnerServer], labels: set[str]):
    """Return number of available servers that match
    that match labels (subset).
    """
    count = 0

    for runner_server in servers:
        if runner_server.server_status == Server.STATUS_OFF:
            continue
        if labels.issubset(runner_server.labels):
            if runner_server.status in ("initializing", "ready"):
                count += 1

    return count


def count_present(servers: list[RunnerServer], labels: set[str]):
    """Return number of present servers that match
    that match labels (subset).
    """
    count = 0

    for runner_server in servers:
        if runner_server.server_status == Server.STATUS_OFF:
            continue
        if labels.issubset(runner_server.labels):
            count += 1

    return count


def scale_up(
    terminate: threading.Event,
    repo: Repository,
    client: Client,
    scripts: Scripts,
    worker_pool: ThreadPoolExecutor,
    github_token: str,
    github_repository: str,
    ssh_key: SSHKey,
    default_server_type: ServerType,
    default_location: Location,
    default_image: Image,
    interval: int,
    max_servers: int,
    max_server_ready_time: int,
    debug: bool = False,
    standby_runners: list[StandbyRunner] = None,
):
    """Scale up service."""

    def create_runner_server(
        name: str,
        labels: set[str],
        setup_worker_pool: ThreadPoolExecutor,
        futures: list[Future],
        servers: list[RunnerServer],
    ):
        """Create new server that would provide a runner with given labels."""
        if max_servers is not None:
            if len(servers) >= max_servers:
                with Action(
                    f"Maximum number of servers {max_servers} has been reached"
                ):
                    raise StopIteration("maximum number of servers reached")

        future = worker_pool.submit(
            create_server,
            setup_worker_pool=setup_worker_pool,
            client=client,
            labels=labels,
            name=name,
            default_server_type=default_server_type,
            default_location=default_location,
            default_image=default_image,
            scripts=scripts,
            github_token=github_token,
            github_repository=github_repository,
            ssh_key=ssh_key,
            timeout=max_server_ready_time,
        )
        future.server_name = name

        futures.append(future)
        servers.append(RunnerServer(name=name, labels=labels))

    with ThreadPoolExecutor(
        max_workers=worker_pool._max_workers, thread_name_prefix=f"setup-worker"
    ) as setup_worker_pool:

        while True:
            if terminate.is_set():
                with Action("Terminating scale up service"):
                    break

            try:
                with Action("Getting workflow runs", level=logging.DEBUG):
                    workflow_runs = repo.get_workflow_runs(status="queued")

                futures: list[Future] = []

                with Action("Getting list of servers", level=logging.DEBUG):
                    servers = [
                        RunnerServer(
                            name=server.name,
                            server_status=server.status,
                            labels=set(
                                [
                                    value
                                    for name, value in server.labels.items()
                                    if name.startswith("github-runner-label")
                                ]
                            ),
                        )
                        for server in client.servers.get_all()
                        if server.name.startswith(server_name_prefix)
                    ]

                with Action("Getting list of self-hosted runners", level=logging.DEBUG):
                    runners: list[SelfHostedActionsRunner] = [
                        runner
                        for runner in repo.get_self_hosted_runners()
                        if runner.name.startswith(runner_name_prefix)
                    ]

                with Action("Setting status of servers based on the runner status"):
                    for runner in runners:
                        for server in servers:
                            if server.name == runner.name:
                                if runner.status == "online":
                                    server.status = "busy" if runner.busy else "ready"

                with Action("Looking for queued jobs", level=logging.DEBUG):
                    try:
                        for run in workflow_runs:
                            for job in run.jobs():
                                labels = set(job.raw_data["labels"])

                                server_name = f"{server_name_prefix}{job.id}"

                                if job.status != "completed":
                                    if server_name in [
                                        server.name for server in servers
                                    ]:
                                        with Action(
                                            f"Server already exists for {job.status} {job}",
                                            level=logging.DEBUG,
                                        ):
                                            continue

                                    if job.status == "in_progress":
                                        # check we job is running on a standby runner
                                        if job.raw_data["runner_name"].startswith(
                                            standby_runner_name_prefix
                                        ):
                                            continue

                                        with Action(
                                            f"Finding labels for the job from which {job} stole the runner"
                                        ):
                                            labels = set(
                                                [
                                                    label["name"]
                                                    for label in repo.get_self_hosted_runner(
                                                        job.raw_data["runner_id"]
                                                    ).labels()
                                                ]
                                            )

                                    with Action(f"Creating new server for {job}"):
                                        create_runner_server(
                                            name=server_name,
                                            labels=labels,
                                            setup_worker_pool=setup_worker_pool,
                                            futures=futures,
                                            servers=servers,
                                        )
                    except StopIteration:
                        pass

                with Action("Checking standby runner pool"):
                    for standby_runner in standby_runners:
                        labels = set(standby_runner.labels)
                        replenish_immediately = standby_runner.replenish_immediately
                        if replenish_immediately:
                            available = count_available(servers=servers, labels=labels)
                        else:
                            available = count_present(server=servers, labels=labels)

                        if available < standby_runner.count:
                            for _ in range(standby_runner.count - available):
                                try:
                                    with Action(
                                        f"Replenishing{' immediately' if replenish_immediately else ''} standby server with {labels}"
                                    ):
                                        create_runner_server(
                                            name=f"{standby_server_name_prefix}{str(uuid.uuid1()).replace('-','')}",
                                            labels=labels,
                                            setup_worker_pool=setup_worker_pool,
                                            futures=futures,
                                            servers=servers,
                                        )
                                except StopIteration:
                                    break

                for future in futures:
                    with Action(
                        f"Waiting to finish creating server {future.server_name}",
                        ignore_fail=True,
                    ):
                        future.result()

            except Exception as exc:
                msg = f"❗ Error: {type(exc).__name__} {exc}"
                if debug:
                    logger.exception(f"{msg}\n{exc}")
                else:
                    logger.error(msg)

            with Action(
                f"Sleeping until next interval {interval}s", level=logging.DEBUG
            ):
                time.sleep(interval)
