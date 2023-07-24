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
from .shell import shell
from .scripts import Scripts
from .request import request

from hcloud import Client
from hcloud.ssh_keys.domain import SSHKey
from hcloud.server_types.domain import ServerType
from hcloud.servers.client import BoundServer
from hcloud.images.domain import Image

from github.Repository import Repository
from github.WorkflowJob import WorkflowJob

from concurrent.futures import ThreadPoolExecutor, Future


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

    ip = server.public_net.primary_ipv4.ip
    ssh = f'ssh -q -o "StrictHostKeyChecking no" root@{ip}'

    with Action("SSH to server"):
        attempt = -1
        start_time = time.time()

        while True:
            attempt += 1

            with Action(
                f"Trying to connect to {server.name}@{ip}...{attempt}", ignore_fail=True
            ):
                returncode = shell(f"{ssh} hostname")
                if returncode == 0:
                    break

            if time.time() - start_time >= timeout:
                shell(f"{ssh} hostname")
            else:
                time.sleep(5)

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

    with Action("Get current directory"):
        current_dir = os.path.dirname(__file__)

    with Action("Executing setup.sh script"):
        shell(f"{ssh} bash -s  < {setup_script}")

    with Action("Executing startup.sh script"):
        shell(
            f"{ssh} 'sudo -u runner "
            f"GITHUB_REPOSITORY=\"{os.getenv('GITHUB_REPOSITORY')}\" "
            f'GITHUB_RUNNER_TOKEN="{GITHUB_RUNNER_TOKEN}" '
            f"GITHUB_RUNNER_GROUP=Default "
            f'GITHUB_RUNNER_LABELS="{runner_labels}" '
            f"bash -s' < {startup_script}"
        )


def create_server(
    client: Client,
    job: WorkflowJob,
    name: str,
    server_type: ServerType,
    setup_script: str,
    startup_script: str,
    github_token: str,
    github_repository: str,
    ssh_key: SSHKey,
    image: Image,
    count=1,
    timeout=60,
):
    """Create specified number of server instances."""

    with Action("Create server"):
        response = client.servers.create(
            name=name,
            server_type=server_type,
            image=image,
            ssh_keys=[ssh_key],
        )
        server: BoundServer = response.server

    with Action(f"Waiting for server {server.name}") as action:
        start_time = time.time()

        while True:
            status = server.status
            action.note(f"{server.name} {status}")
            if status == server.STATUS_RUNNING:
                break
            if time.time() - start_time >= timeout:
                raise TimeoutError("waiting for server to start running")
            time.sleep(1)
            server.reload()

    server_setup(
        server=response.server,
        setup_script=setup_script,
        startup_script=startup_script,
        github_token=github_token,
        github_repository=github_repository,
        runner_labels=",".join(job.raw_data["labels"]),
    )


def get_server_type(job: WorkflowJob, default="cx11", label_prefix="server-"):
    """Get server type for the specified job."""
    server_type = None
    server_type_name = default

    if server_type is None:
        for label in job.raw_data["labels"]:
            if label.startswith(label_prefix):
                server_type_name = label.split(label_prefix, 1)[-1].lower()
                server_type = ServerType(name=server_type_name)

    if server_type is None:
        server_type = ServerType(name=server_type_name)

    return server_type


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
    image: Image,
    interval: int,
    max_servers: int,
):
    """Scale up service."""
    while True:
        if terminate.is_set():
            with Action("Terminating scale up service"):
                break

        with Action("Getting list of servers", level=logging.DEBUG):
            servers: list[BoundServer] = client.servers.get_all()

        with Action("Getting workflow runs", level=logging.DEBUG):
            workflow_runs = repo.get_workflow_runs(branch="main", status="queued")

        futures: list[Future] = []

        with Action("Looking for queued jobs", level=logging.DEBUG) as action:
            for run in workflow_runs:
                for job in run.jobs():
                    if job.status == "queued":
                        with Action(f"Found queued job {job}"):
                            server_name = f"gh-actions-runner-{job.run_id}"
                            server_type = get_server_type(job=job)
                            startup_script = get_startup_script(
                                server_type=server_type, scripts=scripts
                            )

                            if max_servers is not None:
                                with Action(
                                    f"Checking if maximum number of servers has been reached",
                                    level=logging.DEBUG,
                                ):
                                    if len(servers) >= max_servers:
                                        with Action(
                                            f"Maximum number of servers {max_servers} has been reached"
                                        ):
                                            continue

                            with Action(
                                f"Checking if server already exists for {job}",
                                level=logging.DEBUG,
                            ) as action:
                                if server_name in [server.name for server in servers]:
                                    with Action(f"Server already exists for {job}"):
                                        continue

                            futures.append(
                                worker_pool.submit(
                                    create_server,
                                    client=client,
                                    job=job,
                                    name=server_name,
                                    server_type=server_type,
                                    setup_script=scripts.setup,
                                    startup_script=startup_script,
                                    github_token=github_token,
                                    github_repository=github_repository,
                                    ssh_key=ssh_key,
                                    image=image,
                                )
                            )

        for future in futures:
            with Action("Waiting to finish creating server", ignore_fail=True):
                future.result()

        with Action(f"Sleeping until next interval {interval}s", level=logging.DEBUG):
            time.sleep(interval)
