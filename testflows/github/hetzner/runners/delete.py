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
from hcloud import Client
from hcloud.servers.client import BoundServer

from github import Github
from github.Repository import Repository
from github.SelfHostedActionsRunner import SelfHostedActionsRunner

from .scale_up import server_name_prefix
from .config import Config
from .actions import Action
from .request import request


def all(args, config: Config):
    """Delete all servers."""
    config.check("hetzner_token")

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action("Logging in to GitHub"):
        github = Github(login_or_token=config.github_token)

    with Action(f"Getting repository {config.github_repository}"):
        repo: Repository = github.get_repo(config.github_repository)

    with Action("Getting list of self-hosted runners"):
        runners: list[SelfHostedActionsRunner] = repo.get_self_hosted_runners()

    for runner in runners:
        with Action(f"Deleting runner {runner.name}") as action:
            _, resp = request(
                f"https://api.github.com/repos/{config.github_repository}/actions/runners/{runner.id}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {config.github_token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                method="DELETE",
                data={},
            )
            action.note(f"{resp.status}")

    with Action("Getting list of servers"):
        servers: list[BoundServer] = client.servers.get_all()
        servers = [
            server for server in servers if server.name.startswith(server_name_prefix)
        ]

    for server in servers:
        with Action(f"Deleting server {server.name}"):
            server.delete()
