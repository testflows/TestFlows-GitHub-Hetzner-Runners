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
import logging
import threading

from .actions import Action
from .scripts import Scripts
from .request import request
from .args import image_type, check_image

from .server import wait_ssh, ssh, wait_ready

from hcloud import Client, APIException
from hcloud.ssh_keys.domain import SSHKey
from hcloud.server_types.domain import ServerType
from hcloud.locations.domain import Location
from hcloud.servers.client import BoundServer
from hcloud.images.domain import Image

from github.Repository import Repository
from github.WorkflowJob import WorkflowJob

from concurrent.futures import ThreadPoolExecutor, Future

server_name_prefix = "github-runner-"
runner_name_prefix = server_name_prefix


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


def create_server(
    setup_worker_pool: ThreadPoolExecutor,
    client: Client,
    job: WorkflowJob,
    name: str,
    server_type: ServerType,
    server_location: Location,
    server_image: Image,
    setup_script: str,
    startup_script: str,
    github_token: str,
    github_repository: str,
    ssh_key: SSHKey,
    timeout=60,
):
    """Create specified number of server instances."""

    with Action("Create server"):
        response = client.servers.create(
            name=name,
            server_type=server_type,
            location=server_location,
            image=server_image,
            ssh_keys=[ssh_key],
        )
        server: BoundServer = response.server

    with Action(f"Waiting for server {server.name} to be ready") as action:
        wait_ready(server=server, timeout=timeout, action=action)

    setup_worker_pool.submit(
        server_setup,
        server=response.server,
        setup_script=setup_script,
        startup_script=startup_script,
        github_token=github_token,
        github_repository=github_repository,
        runner_labels=",".join(job.raw_data["labels"]),
        timeout=timeout,
    )


def get_server_type(job: WorkflowJob, default: ServerType, label_prefix="type-"):
    """Get server type for the specified job."""
    server_type = None

    if server_type is None:
        for label in job.raw_data["labels"]:
            if label.startswith(label_prefix):
                server_type_name = label.split(label_prefix, 1)[-1].lower()
                server_type = ServerType(name=server_type_name)

    if server_type is None:
        server_type = default

    return server_type


def get_server_location(job: WorkflowJob, default: Location = None, label_prefix="in-"):
    """Get preferred server location for the specified job.

    By default, location is set to `None` to avoid server type mismatching
    the location as some server types are not available at some locations.
    """
    server_location: Location = None

    if server_location is None:
        for label in job.raw_data["labels"]:
            if label.startswith(label_prefix):
                server_location_name = label.split(label_prefix, 1)[-1].lower()
                server_location = Location(name=server_location_name)

    if server_location is None and default:
        server_location = default

    return server_location


def get_server_image(
    client: Client, job: WorkflowJob, default: Image, label_prefix="image-"
):
    """Get preferred server image for the specified job."""
    server_image: Image = None

    if server_image is None:
        for label in job.raw_data["labels"]:
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


def scale_up(
    terminate: threading.Event,
    repo: Repository,
    client: Client,
    scripts: Scripts,
    worker_pool: ThreadPoolExecutor,
    github_token: str,
    github_repository: str,
    ssh_key: SSHKey,
    default_type: ServerType,
    default_location: Location,
    default_image: Image,
    interval: int,
    max_servers: int,
    max_server_ready_time: int,
):
    """Scale up service."""

    with ThreadPoolExecutor(
        max_workers=worker_pool._max_workers, thread_name_prefix=f"setup-worker"
    ) as setup_worker_pool:

        while True:
            if terminate.is_set():
                with Action("Terminating scale up service"):
                    break

            with Action("Getting workflow runs", level=logging.DEBUG):
                workflow_runs = repo.get_workflow_runs(branch="main", status="queued")

            futures: list[Future] = []

            with Action("Looking for jobs", level=logging.DEBUG) as action:
                for run in workflow_runs:
                    for job in run.jobs():
                        with Action("Getting list of servers", level=logging.DEBUG):
                            servers: list[BoundServer] = client.servers.get_all()
                            servers = [
                                server
                                for server in servers
                                if server.name.startswith(server_name_prefix)
                            ]

                        server_name = f"{server_name_prefix}{job.run_id}-{job.id}"

                        if job.status != "completed":
                            if server_name in [server.name for server in servers]:
                                with Action(
                                    f"Server already exists for {job.status} {job}",
                                    level=logging.DEBUG,
                                ):
                                    continue

                            with Action(
                                f"Found job for which server was not created {job}"
                            ):
                                server_type = get_server_type(
                                    job=job, default=default_type
                                )
                                server_location = get_server_location(
                                    job=job, default=default_location
                                )
                                server_image = get_server_image(
                                    client=client, job=job, default=default_image
                                )
                                startup_script = get_startup_script(
                                    server_type=server_type, scripts=scripts
                                )

                                if max_servers is not None:
                                    if len(servers) >= max_servers:
                                        with Action(
                                            f"Maximum number of servers {max_servers} has been reached"
                                        ):
                                            break

                                futures.append(
                                    worker_pool.submit(
                                        create_server,
                                        setup_worker_pool=setup_worker_pool,
                                        client=client,
                                        job=job,
                                        name=server_name,
                                        server_type=server_type,
                                        server_location=server_location,
                                        server_image=server_image,
                                        setup_script=scripts.setup,
                                        startup_script=startup_script,
                                        github_token=github_token,
                                        github_repository=github_repository,
                                        ssh_key=ssh_key,
                                        timeout=max_server_ready_time,
                                    )
                                )
                    else:
                        continue
                    break

            for future in futures:
                with Action("Waiting to finish creating servers", ignore_fail=True):
                    future.result()

            with Action(
                f"Sleeping until next interval {interval}s", level=logging.DEBUG
            ):
                time.sleep(interval)
