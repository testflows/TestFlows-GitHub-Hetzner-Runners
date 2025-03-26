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
import queue
import logging
import threading

from dataclasses import dataclass

from .actions import Action
from .request import request
from .args import image_type
from .logger import logger
from . import metrics
from .config import Config, check_image, check_startup_script, check_setup_script
from .config import standby_runner as StandbyRunner
from .hclient import HClient as Client
from .utils import get_runner_server_type_and_location
from .constants import (
    server_name_prefix,
    runner_name_prefix,
    standby_server_name_prefix,
    standby_runner_name_prefix,
    recycle_server_name_prefix,
    server_ssh_key_label,
)

from .server import wait_ssh, ssh

from hcloud import APIException
from hcloud.ssh_keys.domain import SSHKey
from hcloud.server_types.domain import ServerType
from hcloud.locations.domain import Location
from hcloud.servers.client import BoundServer
from hcloud.servers.domain import Server, ServerCreatePublicNetwork
from hcloud.images.domain import Image
from hcloud.helpers.labels import LabelValidator

from github import Github
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun
from github.SelfHostedActionsRunner import SelfHostedActionsRunner

from concurrent.futures import ThreadPoolExecutor, Future


@dataclass
class ScaleUpFailureMessage:
    """Scale up server failure."""

    time: float
    labels: set[str]
    server_name: str
    exception: Exception


class MaxNumberOfServersReached(Exception):
    """Exception to indicate that scale up service
    reached maximum number of servers."""

    pass


class CanceledServerCreation(Exception):
    """Exception to indicate that server creation was canceled."""

    pass


@dataclass
class RunnerServer:
    name: str
    labels: set[str]
    server_type: ServerType
    server_location: Location
    server_status: str = Server.STATUS_STARTING
    status: str = "initializing"  # busy, ready
    server: BoundServer = None


def uid():
    """Return unique id - just a timestamp."""
    return str(time.time()).replace(".", "")


def get_runner_server_name(runner_name: str) -> str:
    """Determine runner's server name."""
    return "-".join(runner_name.split("-")[:5])


def get_runner_server_type_and_location(runner_name: str):
    """Determine runner's server type, and location."""
    server_type, server_location = None, None

    if runner_name and runner_name.startswith(runner_name_prefix):
        if len(runner_name.split("-")) == 7:
            server_type, server_location = runner_name.split("-")[5:]

    return server_type, server_location


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
    with Action("Wait for SSH connection to be ready", server_name=server.name):
        wait_ssh(server=server, timeout=timeout)

    with Action("Getting registration token for the runner", server_name=server.name):
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

    with Action("Executing setup.sh script", server_name=server.name):
        ssh(server, f"bash -s  < {setup_script}", stacklevel=5)

    with Action("Executing startup.sh script", server_name=server.name):
        ssh(
            server,
            f"'sudo -u ubuntu "
            f'GITHUB_REPOSITORY="{github_repository}" '
            f'GITHUB_RUNNER_TOKEN="{GITHUB_RUNNER_TOKEN}" '
            f"GITHUB_RUNNER_GROUP=Default "
            f'GITHUB_RUNNER_LABELS="{runner_labels}" '
            f'SERVER_ID="{server.id}" '
            f'SERVER_TYPE_NAME="{server.server_type.name}" '
            f'SERVER_LOCATION_NAME="{server.datacenter.location.name}" '
            f"bash -s' < {startup_script}",
            stacklevel=5,
        )


def get_server_types(labels: set[str], default: ServerType, label_prefix: str = ""):
    """Get server types for the specified job."""
    server_types: list[ServerType] = []

    if label_prefix and not label_prefix.endswith("-"):
        label_prefix += "-"
    label_prefix += "type-"
    label_prefix = label_prefix.lower()

    for label in labels:
        label = label.lower()
        if label.startswith(label_prefix):
            server_type_name = label.split(label_prefix, 1)[-1].lower()
            server_type = ServerType(name=server_type_name)
            server_types.append(server_type)

    if not server_types:
        server_types = [default]

    return server_types


def get_server_locations(
    labels: set[str], default: Location = None, label_prefix: str = ""
):
    """Get preferred server locations for the specified job.

    By default, location is set to `None` to avoid server type mismatching
    the location as some server types are not available at some locations.
    """
    server_locations: list[Location] = []

    if label_prefix and not label_prefix.endswith("-"):
        label_prefix += "-"
    label_prefix += "in-"
    label_prefix = label_prefix.lower()

    for label in labels:
        label = label.lower()
        if label.startswith(label_prefix):
            server_location_name = label.split(label_prefix, 1)[-1].lower()
            server_location = Location(name=server_location_name)
            server_locations.append(server_location)

    if not server_locations:
        server_locations = [default]

    return server_locations


def get_server_image(
    client: Client, labels: set[str], default: Image, label_prefix: str = ""
):
    """Get preferred server image for the specified job."""
    server_image: Image = None

    if label_prefix and not label_prefix.endswith("-"):
        label_prefix += "-"
    label_prefix += "image-"
    label_prefix = label_prefix.lower()

    for label in labels:
        label = label.lower()
        if label.startswith(label_prefix):
            server_image = check_image(
                client,
                image_type(label.split(label_prefix, 1)[-1].lower(), separator="-"),
            )

    if server_image is None:
        server_image = default

    return server_image


def get_server_arch(server_type: ServerType):
    """Get server architecture base on the requested server type.
    ARM64 servers type names start with "CA" prefix.

    For example, CAX11, CAX21, CAX31, and CAX41
    """
    if server_type.name.lower().startswith("ca"):
        return "arm64"
    return "x64"


def get_setup_script(
    scripts: str, labels: set[str], default: str = "setup.sh", label_prefix: str = ""
):
    """Get setup script."""
    script = None

    if label_prefix and not label_prefix.endswith("-"):
        label_prefix += "-"
    label_prefix += "setup-"
    label_prefix = label_prefix.lower()

    for label in labels:
        label = label.lower()
        if label.startswith(label_prefix):
            script = label.split(label_prefix, 1)[-1] + ".sh"

    if script is None:
        script = default

    script = check_setup_script(os.path.join(scripts, script))

    return script


def get_startup_script(
    scripts: str,
    server_type: ServerType,
    labels: set[str],
    default: str = "startup-{arch}.sh",
    label_prefix: str = "",
):
    """Get startup script based on the requested server type.
    ARM64 servers type names start with "CA" prefix.

    For example, CAX11, CAX21, CAX31, and CAX41
    """
    script = None
    default = default.format(arch=get_server_arch(server_type))

    if label_prefix and not label_prefix.endswith("-"):
        label_prefix += "-"
    label_prefix += "startup-"
    label_prefix = label_prefix.lower()

    for label in labels:
        label = label.lower()
        if label.startswith(label_prefix):
            script = label.split(label_prefix, 1)[-1] + ".sh"

    if script is None:
        script = default

    script = check_startup_script(os.path.join(scripts, script))

    return script


def get_server_net_config(labels: set[str], label_prefix: str = ""):
    """Get server network configuration."""

    if label_prefix and not label_prefix.endswith("-"):
        label_prefix += "-"
    label_prefix += "net-"
    label_prefix = label_prefix.lower()

    enable_ipv4 = False
    enable_ipv6 = False

    for label in labels:
        label = label.lower()
        if label.startswith(label_prefix):
            ip_version = label.split(label_prefix, 1)[-1].lower()
            if ip_version == "ipv4":
                enable_ipv4 = True
            elif ip_version == "ipv6":
                enable_ipv6 = True

    if not enable_ipv4 and not enable_ipv6:
        enable_ipv4 = enable_ipv6 = True

    server_net_config = ServerCreatePublicNetwork(
        enable_ipv4=enable_ipv4, enable_ipv6=enable_ipv6
    )

    return server_net_config


def expand_meta_label(
    meta_label: dict[str, set[str]], labels: set[str], label_prefix: str = ""
):
    """Expand any meta labels."""
    expanded_labels = []
    label_prefix = label_prefix.lower()

    for label in labels:
        label = label.lower()
        expanded_labels.append(label)
        if label.startswith(label_prefix):
            raw_label = label.split(label_prefix, 1)[-1] if label_prefix else label
            if raw_label in meta_label:
                expanded_labels += list(meta_label[label])

    return set(expanded_labels)


def raise_exception(exc):
    """Task to raise an exception using the worker pool."""
    raise exc


def get_job_labels(job):
    """Get job labels."""
    return set([label.lower() for label in job.raw_data["labels"]])


def job_matches_labels(job_labels, with_label):
    """Check if job matches with_label criteria."""
    if with_label is None:
        return True

    for label in with_label:
        if not label.lower() in job_labels:
            return (False, label)

    return True


def filtered_run_jobs(workflow_runs: list[WorkflowRun], with_label: list[str]):
    """Filter jobs to select only queued or in progress and match with_label criteria."""
    run_jobs = []
    for run in workflow_runs:
        for job in run.jobs():
            if job.status == "completed":
                continue
            if not (job.status == "in_progress" or job.status == "queued"):
                continue
            labels = get_job_labels(job)
            if job_matches_labels(labels, with_label) is True:
                run_jobs.append((run, job))
    return run_jobs


def create_server(
    hetzner_token: str,
    setup_worker_pool: ThreadPoolExecutor,
    labels: set[str],
    name: str,
    server_type: ServerType,
    server_location: Location,
    server_image: Image,
    server_net_config: ServerCreatePublicNetwork,
    startup_script: str,
    setup_script: str,
    github_token: str,
    github_repository: str,
    ssh_keys: list[SSHKey],
    timeout: float = 60,
    canceled: threading.Event = None,
    semaphore: threading.Semaphore = None,
    active_attempt: list[int] = None,
    attempt: int = 0,
):
    """Create specified number of server instances."""
    start_time = time.time()

    while True:
        if canceled is not None and canceled.is_set():
            with Action(
                f"Server creation for {name} of {server_type} in {server_location} canceled",
                level=logging.DEBUG,
                stacklevel=3,
                server_name=name,
            ):
                raise CanceledServerCreation("Server creation canceled")

        if semaphore is None or semaphore.acquire(timeout=1.0):
            try:
                if active_attempt is not None:
                    # only proceed if this is our turn
                    if active_attempt[0] != attempt:
                        continue
                    # increment the attempt number so that if we fail
                    # another attempt can proceed next time
                    active_attempt[0] += 1

                client = Client(token=hetzner_token)
                server_labels = {
                    f"github-hetzner-runner-label-{i}": value
                    for i, value in enumerate(labels)
                }
                server_labels[server_ssh_key_label] = ssh_keys[0].name

                with Action(f"Validating server {name} labels", server_name=name):
                    valid, error_msg = LabelValidator.validate_verbose(
                        labels=server_labels
                    )
                    if not valid:
                        raise ValueError(
                            f"invalid server labels {server_labels}: {error_msg}"
                        )

                with Action(
                    f"Creating server {name} with labels {labels}", server_name=name
                ):
                    response = client.servers.create(
                        name=name,
                        server_type=server_type,
                        location=server_location,
                        image=server_image,
                        ssh_keys=ssh_keys,
                        labels=server_labels,
                        public_net=server_net_config,
                    )
                    server: BoundServer = response.server

                    metrics.record_server_creation(
                        server_type=server_type.name,
                        location=server_location.name if server_location else None,
                        creation_time=time.time() - start_time,
                    )

                with Action(
                    f"Successfully created server {name} of {server_type} in {server_location}, canceling other attempts",
                    level=logging.DEBUG,
                    stacklevel=3,
                    server_name=name,
                ):
                    canceled.set()
                # break out of the loop
                break

            finally:
                if semaphore is not None:
                    semaphore.release()

    setup_worker_pool.submit(
        server_setup,
        server=response.server,
        setup_script=setup_script,
        startup_script=startup_script,
        github_token=github_token,
        github_repository=github_repository,
        runner_labels=",".join(labels),
        timeout=timeout,
    )


def recycle_server(
    server_name: str,
    hetzner_token: str,
    setup_worker_pool: ThreadPoolExecutor,
    labels: set[str],
    name: str,
    server_image: Image,
    startup_script: str,
    setup_script: str,
    github_token: str,
    github_repository: str,
    ssh_key: SSHKey,
    timeout=60,
):
    """Create specified number of server instances."""
    client = Client(token=hetzner_token, poll_interval=1)

    server_labels = {
        f"github-hetzner-runner-label-{i}": value for i, value in enumerate(labels)
    }
    server_labels[server_ssh_key_label] = ssh_key.name

    with Action(f"Validating server {name} labels", server_name=name):
        valid, error_msg = LabelValidator.validate_verbose(labels=server_labels)
        if not valid:
            raise ValueError(f"invalid server labels {server_labels}: {error_msg}")

    with Action(f"Get recyclable server {server_name}", server_name=name):
        server: BoundServer = client.servers.get_by_name(name=server_name)

    with Action(f"Recycling server {server_name} to make {name}", server_name=name):
        server = server.update(name=name, labels=server_labels)

    with Action(f"Rebuilding recycled server {server.name} image", server_name=name):
        server.rebuild(image=server_image).action.wait_until_finished(
            max_retries=timeout
        )

    setup_worker_pool.submit(
        server_setup,
        server=server,
        setup_script=setup_script,
        startup_script=startup_script,
        github_token=github_token,
        github_repository=github_repository,
        runner_labels=",".join(labels),
        timeout=timeout,
    )


def count_available_runners(runners: list[SelfHostedActionsRunner], labels: set[str]):
    """Return number of available runners that match labels (subset)."""
    count = 0

    for runner in runners:
        if runner.status == "online":
            runner_labels = set([label["name"].lower() for label in runner.labels()])
            if labels.issubset(runner_labels):
                if not runner.busy:
                    count += 1

    return count


def count_available(servers: list[RunnerServer], labels: set[str]):
    """Return number of available servers that match labels (subset)."""
    count = 0

    for runner_server in servers:
        if runner_server.server_status == Server.STATUS_OFF:
            continue
        if labels.issubset(runner_server.labels):
            if runner_server.status in ("initializing", "ready"):
                count += 1

    return count


def count_present(servers: list[RunnerServer], labels: set[str]):
    """Return number of present servers that match labels (subset)."""
    count = 0

    for runner_server in servers:
        if runner_server.server_status == Server.STATUS_OFF:
            continue
        if labels.issubset(runner_server.labels):
            count += 1

    return count


def max_servers_in_workflow_run_reached(
    run_id,
    servers: list[BoundServer],
    max_servers_in_workflow_run: int,
    server_name: str = None,
):
    """Return True if maximum number of servers in workflow run has been reached."""
    with Action(
        f"Check maximum number of servers used in workflow run {run_id}",
        level=logging.DEBUG,
        stacklevel=3,
        run_id=run_id,
        server_name=server_name,
    ):
        run_server_name_prefix = f"{server_name_prefix}{run_id}"
        servers_in_run = [
            server
            for server in servers
            if server.name.startswith(run_server_name_prefix)
        ]
        if len(servers_in_run) >= max_servers_in_workflow_run:
            with Action(
                f"Maximum number of servers {max_servers_in_workflow_run} for {run_id} has been reached",
                stacklevel=3,
                run_id=run_id,
                server_name=server_name,
            ):
                return True
    return False


def recyclable_server_match(
    server: RunnerServer,
    server_type: ServerType,
    server_location: Location,
    server_net_config: ServerCreatePublicNetwork,
    ssh_key: SSHKey,
):
    """Check if a recyclable server matches for the specified
    server type, location, and ssh key."""
    if server.server_type.name != server_type.name:
        return False

    if server_location and server.server_location.name != server_location.name:
        return False

    if server_net_config.enable_ipv4 and server.server.public_net.ipv4 is None:
        return False

    if not server_net_config.enable_ipv4 and server.server.public_net.ipv4 is not None:
        return False

    if server_net_config.enable_ipv6 and server.server.public_net.ipv6 is None:
        return False

    if not server_net_config.enable_ipv6 and server.server.public_net.ipv6 is not None:
        return False

    return ssh_key.name == server.server.labels.get(server_ssh_key_label)


def scale_up(
    terminate: threading.Event,
    mailbox: queue.Queue,
    worker_pool: ThreadPoolExecutor,
    ssh_keys: list[SSHKey],
    config: Config,
):
    """Scale up service."""
    github_token: str = config.github_token
    github_repository: str = config.github_repository
    hetzner_token: str = config.hetzner_token
    default_server_type: ServerType = config.default_server_type
    default_location: Location = config.default_location
    default_image: Image = config.default_image
    interval_period: int = config.scale_up_interval
    max_servers: int = config.max_runners
    max_servers_in_workflow_run: int = config.max_runners_in_workflow_run
    max_server_ready_time: int = config.max_server_ready_time
    debug: bool = config.debug
    standby_runners: list[StandbyRunner] = config.standby_runners
    recycle: bool = config.recycle
    with_label: list[str] = config.with_label
    label_prefix: str = config.label_prefix
    meta_label: dict[str, set[str]] = config.meta_label
    scripts: str = config.scripts
    server_prices: dict[str, dict[str, float]] = config.server_prices
    interval: int = -1

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=hetzner_token)

    def create_runner_server(
        name: str,
        labels: set[str],
        setup_worker_pool: ThreadPoolExecutor,
        futures: list[Future],
        servers: list[RunnerServer],
    ):
        """Create new server that would provide a runner with given labels."""
        recyclable_servers: list[BoundServer] = []

        # signal to stop creating a new server
        create_server_canceled = threading.Event()
        # semaphore to limit the number of concurrent server creations to 1
        create_server_semaphore = threading.Semaphore(1)
        # active_attempt
        create_server_active_attempt = [0]
        # attempt number
        create_server_attempt = -1

        labels = expand_meta_label(meta_label=meta_label, labels=labels)

        server_types = get_server_types(
            labels=labels, default=default_server_type, label_prefix=label_prefix
        )
        server_locations = get_server_locations(
            labels=labels, default=default_location, label_prefix=label_prefix
        )
        server_image = get_server_image(
            client=client,
            labels=labels,
            default=default_image,
            label_prefix=label_prefix,
        )
        setup_script = get_setup_script(
            scripts=scripts,
            labels=labels,
            label_prefix=label_prefix,
        )
        server_net_config = get_server_net_config(
            labels=labels, label_prefix=label_prefix
        )

        if recycle:
            for server_type in server_types:
                for server_location in server_locations:
                    startup_script = get_startup_script(
                        scripts=scripts,
                        server_type=server_type,
                        labels=labels,
                        label_prefix=label_prefix,
                    )

                    with Action(
                        f"Trying to create recycled server {name} of {server_type} in {server_location}",
                        stacklevel=3,
                        level=logging.DEBUG,
                        server_name=name,
                    ):
                        pass

                    for server in servers:
                        if server.name.startswith(recycle_server_name_prefix):
                            recyclable_servers.append(server)

                            with Action(
                                f"Checking if we can recycle {server.name}",
                                stacklevel=3,
                                level=logging.DEBUG,
                                server_name=name,
                            ):
                                pass

                            if recyclable_server_match(
                                server=server,
                                server_type=server_type,
                                server_location=server_location,
                                server_net_config=server_net_config,
                                ssh_key=ssh_keys[0],
                            ):
                                future = worker_pool.submit(
                                    recycle_server,
                                    server_name=server.name,
                                    hetzner_token=hetzner_token,
                                    setup_worker_pool=setup_worker_pool,
                                    labels=labels,
                                    name=name,
                                    server_image=server_image,
                                    startup_script=startup_script,
                                    setup_script=setup_script,
                                    github_token=github_token,
                                    github_repository=github_repository,
                                    ssh_key=ssh_keys[0],
                                    timeout=max_server_ready_time,
                                )
                                future.server_name = name
                                future.server_type = server_type
                                future.server_location = server_location
                                future.server_labels = labels
                                futures.append(future)
                                servers.pop(servers.index(server))
                                return
                            else:
                                with Action(
                                    f"Recyclable server {server.name} did not match {name}",
                                    stacklevel=3,
                                    level=logging.DEBUG,
                                    server_name=name,
                                ):
                                    pass

        for server_type in server_types:
            for server_location in server_locations:
                # pre-increment the attempt number that starts from 0
                create_server_attempt += 1

                startup_script = get_startup_script(
                    scripts=scripts,
                    server_type=server_type,
                    labels=labels,
                    label_prefix=label_prefix,
                )

                with Action(
                    f"Trying to create new server {name} of {server_type} in {server_location}",
                    stacklevel=3,
                    level=logging.DEBUG,
                    server_name=name,
                ):
                    pass

                if max_servers is not None:
                    if len(servers) >= max_servers:
                        with Action(
                            f"Maximum number of servers {max_servers} has been reached",
                            stacklevel=3,
                            server_name=name,
                        ):
                            future = worker_pool.submit(
                                raise_exception,
                                exc=MaxNumberOfServersReached(
                                    f"maximum number of servers reached {len(servers)}/{max_servers}"
                                ),
                            )
                            future.server_name = name
                            future.server_type = server_type
                            future.server_location = server_location
                            future.server_labels = labels
                            futures.append(future)
                            raise StopIteration("maximum number of servers reached")

                future = worker_pool.submit(
                    create_server,
                    hetzner_token=hetzner_token,
                    setup_worker_pool=setup_worker_pool,
                    labels=labels,
                    name=name,
                    server_type=server_type,
                    server_location=server_location,
                    server_image=server_image,
                    server_net_config=server_net_config,
                    setup_script=setup_script,
                    startup_script=startup_script,
                    github_token=github_token,
                    github_repository=github_repository,
                    ssh_keys=ssh_keys,
                    timeout=max_server_ready_time,
                    canceled=create_server_canceled,
                    semaphore=create_server_semaphore,
                    active_attempt=create_server_active_attempt,
                    attempt=create_server_attempt,
                )
                future.server_name = name
                future.server_type = server_type
                future.server_location = server_location
                future.server_labels = labels
                futures.append(future)

    with Action("Logging in to GitHub"):
        github = Github(login_or_token=github_token, per_page=100)

    with Action(f"Getting repository {github_repository}"):
        repo: Repository = github.get_repo(github_repository)

    with ThreadPoolExecutor(
        max_workers=worker_pool._max_workers, thread_name_prefix=f"setup-worker"
    ) as setup_worker_pool:
        while True:
            interval += 1
            if terminate.is_set():
                with Action("Terminating scale up service", interval=interval):
                    break

            with Action(
                "Scale up cycle",
                level=logging.DEBUG,
                ignore_fail=True,
                interval=interval,
            ) as scale_up_cycle:
                # Update service heartbeat
                metrics.update_heartbeat()

                futures: list[Future] = []
                workflow_runs = []
                servers = []
                runners = []

                with Action(
                    "Getting workflow runs", level=logging.DEBUG, interval=interval
                ):
                    queued_runs = list(repo.get_workflow_runs(status="queued"))
                    in_progress_runs = list(
                        repo.get_workflow_runs(status="in_progress")
                    )
                    # Update job metrics using only queued or in progress runs that match with_label criteria
                    metrics.update_jobs(
                        filtered_run_jobs(queued_runs + in_progress_runs, with_label)
                    )
                    # For job processing, we'll use only queued runs
                    workflow_runs = queued_runs

                with Action(
                    "Getting list of servers", level=logging.DEBUG, interval=interval
                ):
                    servers = [
                        RunnerServer(
                            name=server.name,
                            server_status=server.status,
                            labels=set(
                                [
                                    value.lower()
                                    for name, value in server.labels.items()
                                    if name.startswith("github-hetzner-runner-label")
                                ]
                            ),
                            server_type=server.server_type,
                            server_location=server.datacenter.location,
                            server=server,
                        )
                        for server in client.servers.get_all()
                        if server.name.startswith(server_name_prefix)
                    ]

                with Action(
                    "Getting list of self-hosted runners",
                    level=logging.DEBUG,
                    interval=interval,
                ):
                    runners: list[SelfHostedActionsRunner] = [
                        runner
                        for runner in repo.get_self_hosted_runners()
                        if runner.name.startswith(runner_name_prefix)
                    ]

                with Action(
                    "Setting status of servers based on the runner status",
                    level=logging.DEBUG,
                    interval=interval,
                ):
                    for runner in runners:
                        for server in servers:
                            if runner.name.startswith(server.name):
                                if runner.status == "online":
                                    server.status = "busy" if runner.busy else "ready"

                # Update all metrics
                metrics.update_servers(servers, server_prices)
                metrics.update_runners(
                    runners,
                    github_repository,
                    max_server_ready_time,
                    get_runner_server_type_and_location_fn=get_runner_server_type_and_location,
                )
                metrics.update_pools(
                    servers,
                    standby_runners,
                    count_available_fn=count_available,
                )

                with Action(
                    "Looking for queued jobs",
                    level=logging.DEBUG,
                    interval=interval,
                ):
                    try:
                        for run in workflow_runs:
                            with Action(
                                f"Checking jobs for workflow run {run}",
                                level=logging.DEBUG,
                                run_id=run.id,
                                interval=interval,
                            ):
                                pass
                            if max_servers_in_workflow_run is not None:
                                if max_servers_in_workflow_run_reached(
                                    run_id=run.id,
                                    servers=servers,
                                    max_servers_in_workflow_run=max_servers_in_workflow_run,
                                ):
                                    continue

                            for job in run.jobs():
                                if terminate.is_set():
                                    raise StopIteration("terminating")

                                with Action(
                                    f"Checking job {job} {job.status}",
                                    level=logging.DEBUG,
                                    run_id=run.id,
                                    job_id=job.id,
                                    interval=interval,
                                ):
                                    pass

                                labels = get_job_labels(job)
                                server_name = (
                                    f"{server_name_prefix}{job.run_id}-{job.id}"
                                )

                                if job.status != "completed":
                                    if server_name in [
                                        server.name for server in servers
                                    ]:
                                        with Action(
                                            f"Server already exists for {job.status} {job}",
                                            level=logging.DEBUG,
                                            server_name=server_name,
                                            interval=interval,
                                        ):
                                            continue

                                    if job.status == "in_progress":
                                        # skip jobs that were assigned to some other runners
                                        if not job.raw_data["runner_name"].startswith(
                                            runner_name_prefix
                                        ):
                                            continue

                                        # check if the job is running on a standby runner
                                        if job.raw_data["runner_name"].startswith(
                                            standby_runner_name_prefix
                                        ):
                                            continue

                                        with Action(
                                            f"Finding labels for the job from which {job} stole the runner",
                                            server_name=server_name,
                                            interval=interval,
                                        ):
                                            labels = set(
                                                [
                                                    label["name"].lower()
                                                    for label in repo.get_self_hosted_runner(
                                                        job.raw_data["runner_id"]
                                                    ).labels()
                                                ]
                                            )

                                    if max_servers_in_workflow_run is not None:
                                        if max_servers_in_workflow_run_reached(
                                            run_id=run.id,
                                            servers=servers,
                                            max_servers_in_workflow_run=max_servers_in_workflow_run,
                                            server_name=server_name,
                                        ):
                                            break

                                    result = job_matches_labels(labels, with_label)
                                    if result is not True:
                                        _, missing_label = result
                                        with Action(
                                            f"Skipping {job} with {labels} as it is missing label '{missing_label}'",
                                            server_name=server_name,
                                            interval=interval,
                                        ):
                                            continue

                                    with Action(
                                        f"Checking available runners for {job}"
                                    ):
                                        available = count_available_runners(
                                            runners=runners, labels=labels
                                        )
                                        if available > 0:
                                            with Action(
                                                f"Found at least one potentially available runner for {job}"
                                            ):
                                                continue

                                    with Action(
                                        f"Creating new server for {job}",
                                        server_name=server_name,
                                        interval=interval,
                                    ):
                                        create_runner_server(
                                            name=server_name,
                                            labels=labels,
                                            setup_worker_pool=setup_worker_pool,
                                            futures=futures,
                                            servers=servers,
                                        )
                    except StopIteration:
                        pass

                if standby_runners:
                    with Action("Checking standby runner pool", interval=interval):
                        for standby_runner in standby_runners:
                            labels = set(standby_runner.labels)
                            replenish_immediately = standby_runner.replenish_immediately
                            if replenish_immediately:
                                available = count_available(
                                    servers=servers, labels=labels
                                )
                            else:
                                available = count_present(
                                    servers=servers, labels=labels
                                )

                            if available < standby_runner.count:
                                for _ in range(standby_runner.count - available):
                                    if terminate.is_set():
                                        break
                                    try:
                                        with Action(
                                            f"Replenishing{' immediately' if replenish_immediately else ''} standby server with {labels}",
                                            interval=interval,
                                        ):
                                            create_runner_server(
                                                name=f"{standby_server_name_prefix}{uid()}",
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
                        server_name=future.server_name,
                        interval=interval,
                    ):
                        try:
                            future.result()
                            servers.append(
                                RunnerServer(
                                    name=future.server_name,
                                    server_type=future.server_type,
                                    server_location=future.server_location,
                                    labels=future.server_labels,
                                )
                            )

                        except CanceledServerCreation:
                            pass

                        except Exception as exc:
                            try:
                                send_failure = False

                                error_type = "error"
                                error_details = {
                                    "error": str(exc),
                                    "server_type": future.server_type.name,
                                    "location": (
                                        future.server_location.name
                                        if future.server_location
                                        else ""
                                    ),
                                    "labels": ",".join(future.server_labels),
                                    "timestamp": time.time(),
                                }

                                if isinstance(exc, MaxNumberOfServersReached):
                                    send_failure = True
                                    error_type = "max_servers_reached"

                                if isinstance(exc, APIException):
                                    error_type = "api_exception"
                                    if exc.code == "resource_limit_exceeded":
                                        send_failure = True
                                        error_type = "resource_limit_exceeded"

                                metrics.record_scale_up_failure(
                                    error_type=error_type,
                                    server_name=future.server_name,
                                    server_type=future.server_type.name,
                                    location=(
                                        future.server_location.name
                                        if future.server_location
                                        else ""
                                    ),
                                    error_details=error_details,
                                )

                                if send_failure:
                                    with Action(
                                        f"Adding scale up failure {exc} message to mailbox for {future.server_name}",
                                        server_name=future.server_name,
                                        interval=interval,
                                    ):
                                        mailbox.put(
                                            ScaleUpFailureMessage(
                                                time=time.time(),
                                                labels=future.server_labels,
                                                server_name=future.server_name,
                                                exception=exc,
                                            )
                                        )
                            finally:
                                raise

            if scale_up_cycle.exc_value is None:
                with Action(
                    "Recording successful scale up cycle",
                    ignore_fail=True,
                    level=logging.DEBUG,
                ):
                    metrics.record_scale_up_failure(
                        error_type="success",
                        server_name=None,
                        server_type=None,
                        location=None,
                        error_details=None,
                    )

            with Action(
                f"Sleeping until next interval {interval_period}s",
                level=logging.DEBUG,
                interval=interval,
            ):
                time.sleep(interval_period)
