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
import sys
import math
import types
import github

from .actions import Action
from .config import Config
from .config import check_prices
from .scale_up import get_runner_server_type_and_location
from .streamingyaml import StreamingYAMLWriter

from datetime import timedelta
from hcloud import Client
from github import Github
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun
from github.WorkflowJob import WorkflowJob


class Output:
    """Output to multiple streams."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, message):
        for stream in self.streams:
            stream.write(message)

    def flush(self):
        for stream in self.streams:
            stream.flush()


def duration_str(duration: timedelta):
    """Convert timedelta duration to string 'hh:mm:ss'."""

    if duration is None:
        return None

    s = duration.total_seconds()
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))


def get_workflow_job(self, id_or_name) -> WorkflowJob:
    """
    Repository get_workflow_job method.

    :calls: `GET /repos/{owner}/{repo}/actions/jobs/{job_id}
    :param id: int or string

    :rtype: :class:`github.WorkflowJob.WorkflowJob`
    """
    assert isinstance(id_or_name, int) or isinstance(id_or_name, str), id_or_name
    headers, data = self._requester.requestJsonAndCheck(
        "GET", f"{self.url}/actions/jobs/{id_or_name}"
    )
    return WorkflowJob(self._requester, headers, data, completed=True)


def attempt_jobs(self, attempt_number):
    """
    WorkflowRun attempt_jobs method.

    :calls "`GET /repos/{owner}/{repo}/actions/runs/{run_id}/attempts/{attempt_number}/jobs`_
    :param attempt_number: int
    :rtype: :class:`github.PaginatedList.PaginatedList` of :class:`github.WorkflowJob.WorkflowJob`
    """

    url_parameters = dict()

    return github.PaginatedList.PaginatedList(
        github.WorkflowJob.WorkflowJob,
        self._requester,
        f"{self.url}/attempts/{attempt_number}/jobs",
        url_parameters,
        list_item="jobs",
    )


def extend_repository(repo: Repository):
    """Extend repository object."""

    repo.get_workflow_job = types.MethodType(get_workflow_job, repo)
    return repo


def extend_workflow_run(run: WorkflowRun):
    """Extend workflow run object."""

    run.attempt_jobs = types.MethodType(attempt_jobs, run)
    return run


def get_server_price(
    server_prices: dict[str, dict[str, float]],
    server_type: str,
    server_location: str,
    ipv4_price: float,
    ipv6_price: float,
) -> float:
    """Get server price."""
    price = None
    if ipv4_price is None:
        ipv4_price
    try:
        price = server_prices[server_type][server_location] + ipv4_price + ipv6_price
    except KeyError:
        pass
    return price


def get_runner_server_price_per_second(
    server_prices: dict[str, dict[str, float]],
    runner_name: str,
    ipv4_price: float,
    ipv6_price: float,
) -> float:
    """Get runner server price per second."""

    price_per_second = None

    server_type, server_location = get_runner_server_type_and_location(runner_name)
    server_price_per_hour = get_server_price(
        server_prices, server_type, server_location, ipv4_price, ipv6_price
    )

    if server_price_per_hour is not None:
        price_per_second = server_price_per_hour / 3600

    return price_per_second, server_type, server_location


def login_and_get_prices(
    args, config: Config
) -> tuple[Repository, dict[str, dict[str, float]]]:
    """Login and get prices."""

    config.check("github_token")
    config.check("github_repository")
    config.check("hetzner_token")

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action("Logging in to GitHub"):
        github = Github(login_or_token=config.github_token, per_page=100)

    with Action(f"Getting repository {config.github_repository}"):
        repo: Repository = github.get_repo(config.github_repository)

    with Action("Getting current server prices"):
        server_prices = check_prices(client)

    return (repo, server_prices)


def get_estimate_for_jobs(
    writer: StreamingYAMLWriter,
    jobs: list[WorkflowJob],
    server_prices: dict[str, dict[str, float]],
    ipv4_price: float,
    ipv6_price: float,
):
    """Collect estimate for the given jobs."""

    servers = {}
    best_estimate, worst_estimate = None, None
    total_duration, unknown_duration = None, None
    unknown_jobs = 0

    for i, job in enumerate(jobs, 1):
        duration = None

        if job.completed_at and job.started_at:
            duration = job.completed_at - job.started_at

        runner_name = job.raw_data["runner_name"]

        job_entry = {
            "name": job.name,
            "id": job.id,
            "status": job.status,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "duration": duration_str(duration),
            "url": job.url,
            "run_id": job.run_id,
            "run_url": job.run_url,
            "runner_id": job.raw_data["runner_id"],
            "runner_name": runner_name,
            "runner_group_id": job.raw_data["runner_group_id"],
            "runner_group_name": job.raw_data["runner_group_name"],
            "workflow_name": job.raw_data["workflow_name"],
        }

        price, server_type, server_location = get_runner_server_price_per_second(
            server_prices, runner_name, ipv4_price, ipv6_price
        )

        job_entry["estimate"] = {
            "servers": [
                {
                    "type": server_type,
                    "location": server_location,
                    "price": (price * 3600) if price is not None else price,
                    "duration": None,
                    "worst": None,
                    "best": None,
                }
            ],
            "worst": None,
            "best": None,
        }

        if not (server_type, server_location) in servers:
            servers[(server_type, server_location)] = {
                "price": job_entry["estimate"]["servers"][0]["price"],
                "duration": None,
                "worst": None,
                "best": None,
            }

        server = servers[(server_type, server_location)]

        if duration is not None:
            if unknown_duration is None:
                unknown_duration = timedelta()
            if total_duration is None:
                total_duration = timedelta()

            server["duration"] = (
                server["duration"] if server["duration"] is not None else timedelta()
            ) + duration

            job_entry["estimate"]["servers"][0]["duration"] = duration_str(
                server["duration"]
            )

        if price is not None and duration is not None:
            job_best_estimate = duration.total_seconds() * price
            job_worst_estimate = (
                math.ceil(duration.total_seconds() / 3600) * 3600 * price
            )
            # update total
            best_estimate = (
                best_estimate if best_estimate is not None else 0
            ) + job_best_estimate
            worst_estimate = (
                worst_estimate if worst_estimate is not None else 0
            ) + job_worst_estimate

            job_entry["estimate"]["servers"][0]["worst"] = job_worst_estimate
            job_entry["estimate"]["servers"][0]["best"] = job_best_estimate

            # estimates for the server are the same as the whole job
            # as only 1 server is used per job
            job_entry["estimate"]["worst"] = job_worst_estimate
            job_entry["estimate"]["best"] = job_best_estimate

            # update server["worst"] and server["best"] total estimates
            server["best"] = (
                server["best"] if server["best"] is not None else 0
            ) + job_best_estimate
            server["worst"] = (
                server["worst"] if server["worst"] is not None else 0
            ) + job_worst_estimate

        else:
            unknown_jobs += 1
            if duration is not None:
                unknown_duration += duration

        if duration is not None:
            total_duration += duration

        writer.add_list_element(value=job_entry)

    return (
        i,
        total_duration,
        unknown_jobs,
        unknown_duration,
        servers,
        worst_estimate,
        best_estimate,
    )


def workflow_run(
    args,
    config: Config,
    repo: Repository = None,
    workflow_run: WorkflowRun = None,
    server_prices=None,
    writer=None,
):
    """Estimate cost for a given workflow run."""
    run_attempt = None

    if writer is None:
        streams = Output(*([sys.stdout] + ([args.output] if args.output else [])))
        writer = StreamingYAMLWriter(stream=streams, indent=0)

    if workflow_run is None:
        run_id = args.id
        repo, server_prices = login_and_get_prices(args, config)
        run_attempt = args.run_attempt

    else:
        run_id = workflow_run.id

    with Action(f"Getting jobs for the workflow run id {run_id}") as action:
        if workflow_run is None:
            workflow_run: WorkflowRun = repo.get_workflow_run(run_id)
            workflow_run = extend_workflow_run(workflow_run)

        workflow_entry = {"name": workflow_run.name, "id": workflow_run.id}

        if run_attempt is None:
            workflow_entry["attempt"] = workflow_run.run_attempt
            jobs = workflow_run.jobs()
        else:
            workflow_entry["attempt"] = run_attempt
            jobs = workflow_run.attempt_jobs(run_attempt)

        _, list_value_writer = writer.add_list_element(workflow_entry)
        jobs_writer = list_value_writer.add_key("jobs")

        (
            count,
            total_duration,
            unknown_jobs,
            unknown_duration,
            servers,
            worst_estimate,
            best_estimate,
        ) = get_estimate_for_jobs(
            jobs_writer, jobs, server_prices, args.ipv4_price, args.ipv6_price
        )

        workflow_totals = {}

        workflow_totals["total"] = {
            "jobs": count,
            "duration": duration_str(total_duration),
        }
        workflow_totals["known"] = {
            "jobs": count - unknown_jobs,
            "duration": duration_str(
                (total_duration - unknown_duration)
                if total_duration is not None
                else None
            ),
        }
        workflow_totals["unknown"] = {
            "jobs": unknown_jobs,
            "duration": duration_str(unknown_duration),
        }
        workflow_totals["estimate"] = {
            "servers": [],
            "worst": worst_estimate,
            "best": best_estimate,
        }

        for server_type, server_location in servers:
            server = servers[(server_type, server_location)]
            workflow_totals["estimate"]["servers"].append(
                {
                    "type": server_type,
                    "location": server_location,
                    "price": server["price"],
                    "duration": duration_str(server["duration"]),
                    "worst": server["worst"],
                    "best": server["best"],
                }
            )

        list_value_writer.add_value(workflow_totals)


def workflow_runs(args, config: Config):
    """Estimate cost for different workflow runs."""
    repo, server_prices = login_and_get_prices(args, config)

    runs_args = {}
    if args.runs_actor:
        runs_args["actor"] = args.runs_actor
    if args.runs_branch:
        runs_args["branch"] = args.runs_branch
    if args.runs_event:
        runs_args["event"] = args.runs_event
    if args.runs_status:
        runs_args["status"] = args.runs_status
    if args.runs_exclude_pull_requests:
        runs_args["exclude_pull_requests"] = True
    if args.runs_head_sha:
        runs_args["head_sha"] = args.runs_head_sha

    streams = Output(*([sys.stdout] + ([args.output] if args.output else [])))

    with Action(f"Getting workflow runs") as action:
        for run in repo.get_workflow_runs(**runs_args):
            run = extend_workflow_run(run)
            writer = StreamingYAMLWriter(stream=streams, indent=0)
            workflow_run(
                args=args,
                config=config,
                repo=repo,
                workflow_run=run,
                server_prices=server_prices,
                writer=writer,
            )
            try:
                input("✋ Press any key to continue (Ctrl-D to abort)...")
            except EOFError:
                print("")
                break


def workflow_job(args, config: Config):
    """Estimate cost for a specific workflow job."""

    repo, server_prices = login_and_get_prices(args, config)
    repo = extend_repository(repo)
    streams = Output(*([sys.stdout] + ([args.output] if args.output else [])))
    writer = StreamingYAMLWriter(stream=streams, indent=0)

    with Action(f"Getting workflow job id {args.id}") as action:
        workflow_job = repo.get_workflow_job(args.id)

        get_estimate_for_jobs(
            writer, [workflow_job], server_prices, args.ipv4_price, args.ipv6_price
        )
