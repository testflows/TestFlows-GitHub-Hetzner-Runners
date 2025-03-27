# Copyright 2025 Katteli Inc.
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
import dateutil.parser
import logging
from datetime import datetime

from github.WorkflowRun import WorkflowRun
from github.WorkflowJob import WorkflowJob
from prometheus_client import Counter, Gauge, Histogram, Info
from .estimate import get_server_price
from .constants import standby_server_name_prefix, recycle_server_name_prefix

# Server metrics
SERVERS_TOTAL = Gauge(
    "github_hetzner_runners_servers_total",
    "Total number of servers",
    ["status"],  # status: running, off, initializing, ready, busy
)

SERVERS_TOTAL_COUNT = Gauge(
    "github_hetzner_runners_servers_total_count",
    "Total number of servers across all statuses",
)

SERVERS_CREATED_TOTAL = Counter(
    "github_hetzner_runners_servers_created_total",
    "Total number of servers created",
    ["server_type", "location"],
)

SERVERS_DELETED_TOTAL = Counter(
    "github_hetzner_runners_servers_deleted_total",
    "Total number of servers deleted",
    ["server_type", "location"],
)

SERVER_CREATION_TIME = Histogram(
    "github_hetzner_runners_server_creation_seconds",
    "Time taken to create a server",
    ["server_type", "location"],
    # 10s, 30s, 1m, 2m, 5m, 10m, 20m, 30m
    buckets=[10, 30, 60, 120, 300, 600, 1200, 1800],
)

# Detailed server metrics
SERVER_INFO = Info(
    "github_hetzner_runners_server",
    "Information about a server",
    ["server_id", "server_name"],
)

SERVER_LABELS = Gauge(
    "github_hetzner_runners_server_labels",
    "Labels assigned to servers",
    ["server_id", "server_name", "label"],
)

SERVER_STATUS = Gauge(
    "github_hetzner_runners_server_status",
    "Server status (1 for active, 0 for inactive)",
    [
        "server_id",
        "server_name",
        "status",  # status: running, off, initializing, ready, busy
    ],
)

# Standby server metrics
STANDBY_SERVERS_TOTAL = Gauge(
    "github_hetzner_runners_standby_servers_total",
    "Total number of standby servers",
    [
        "status",
        "server_type",
        "location",
    ],  # status: running, off, initializing, ready, busy
)

STANDBY_SERVERS_LABELS = Gauge(
    "github_hetzner_runners_standby_servers_labels",
    "Labels assigned to standby servers",
    ["server_type", "location", "label"],
)

# Recycled server metrics
RECYCLED_SERVERS_TOTAL = Gauge(
    "github_hetzner_runners_recycled_servers_total",
    "Total number of recycled servers available",
    [
        "status",
        "server_type",
        "location",
    ],  # status: running, off, initializing, ready, busy
)

RECYCLED_SERVERS_LABELS = Gauge(
    "github_hetzner_runners_recycled_servers_labels",
    "Labels assigned to recycled servers",
    ["server_type", "location", "label"],
)

# Runner metrics
RUNNERS_TOTAL = Gauge(
    "github_hetzner_runners_runners_total",
    "Total number of runners",
    ["status"],  # status: online, offline
)

RUNNERS_TOTAL_COUNT = Gauge(
    "github_hetzner_runners_runners_total_count",
    "Total number of runners across all statuses",
)

RUNNERS_BUSY = Gauge("github_hetzner_runners_runners_busy", "Number of busy runners")

# Detailed runner metrics
RUNNER_INFO = Info(
    "github_hetzner_runners_runner",
    "Information about a runner",
    ["runner_id", "runner_name"],
)

RUNNER_LABELS = Gauge(
    "github_hetzner_runners_runner_labels",
    "Labels assigned to runners",
    ["runner_id", "runner_name", "label"],
)

RUNNER_STATUS = Gauge(
    "github_hetzner_runners_runner_status",
    "Runner status tracking both online/offline state and busy/ready state",
    ["runner_id", "runner_name", "status", "busy"],
)

# Job metrics
QUEUED_JOBS = Gauge("github_hetzner_runners_queued_jobs", "Number of queued jobs")
RUNNING_JOBS = Gauge("github_hetzner_runners_running_jobs", "Number of running jobs")

# Detailed job metrics
QUEUED_JOB_INFO = Info(
    "github_hetzner_runners_queued_job",
    "Information about a queued job",
    ["job_id", "run_id"],  # job_id and run_id as labels to uniquely identify jobs
)

RUNNING_JOB_INFO = Info(
    "github_hetzner_runners_running_job",
    "Information about a running job",
    ["job_id", "run_id"],  # job_id and run_id as labels to uniquely identify jobs
)

QUEUED_JOB_LABELS = Gauge(
    "github_hetzner_runners_queued_job_labels",
    "Labels requested by queued jobs",
    ["job_id", "run_id", "label"],  # track each label separately
)

RUNNING_JOB_LABELS = Gauge(
    "github_hetzner_runners_running_job_labels",
    "Labels assigned to running jobs",
    ["job_id", "run_id", "label"],  # track each label separately
)

QUEUED_JOB_WAIT_TIME = Gauge(
    "github_hetzner_runners_queued_job_wait_time_seconds",
    "Time job has been waiting in queue",
    ["job_id", "run_id"],
)

RUNNING_JOB_TIME = Gauge(
    "github_hetzner_runners_running_job_time_seconds",
    "Time job has been running",
    ["job_id", "run_id"],
)

# Server health metrics
ZOMBIE_SERVERS_TOTAL = Gauge(
    "github_hetzner_runners_zombie_servers_total",
    "Total number of zombie servers (servers without registered runners)",
    ["server_type", "location"],
)

ZOMBIE_SERVERS_TOTAL_COUNT = Gauge(
    "github_hetzner_runners_zombie_servers_total_count",
    "Total number of zombie servers across all types and locations",
)

ZOMBIE_SERVER_AGE = Gauge(
    "github_hetzner_runners_zombie_server_age_seconds",
    "Time since server became a zombie",
    ["server_id", "server_name"],
)

UNUSED_RUNNERS_TOTAL = Gauge(
    "github_hetzner_runners_unused_runners_total",
    "Total number of unused runners",
    ["server_type", "location"],
)

UNUSED_RUNNERS_TOTAL_COUNT = Gauge(
    "github_hetzner_runners_unused_runners_total_count",
    "Total number of unused runners across all types and locations",
)

UNUSED_RUNNER_AGE = Gauge(
    "github_hetzner_runners_unused_runner_age_seconds",
    "Time since runner was last used",
    ["runner_id", "runner_name"],
)

# Runner pool metrics
RUNNER_POOL_STATUS = Gauge(
    "github_hetzner_runners_pool_status",
    "Runner pool status (1 for active)",
    ["pool_type", "server_type", "location"],  # pool_type: standby, regular
)

RUNNER_POOL_CAPACITY = Gauge(
    "github_hetzner_runners_pool_capacity",
    "Runner pool target capacity",
    ["pool_type", "server_type", "location"],  # pool_type: standby, regular
)

RUNNER_POOL_AVAILABLE = Gauge(
    "github_hetzner_runners_pool_available",
    "Number of available runners in pool",
    ["pool_type", "server_type", "location"],  # pool_type: standby, regular
)

# Scale down metrics
SCALE_DOWN_OPERATIONS = Counter(
    "github_hetzner_runners_scale_down_operations_total",
    "Total number of scale down operations",
    ["reason", "server_type", "location"],  # reason: powered_off, unused, zombie
)

SCALE_DOWN_OPERATIONS_TOTAL = Counter(
    "github_hetzner_runners_scale_down_operations_total_count",
    "Total number of scale down operations across all reasons",
)

# API metrics
GITHUB_API_REMAINING = Gauge(
    "github_hetzner_runners_github_api_remaining",
    "Number of GitHub API calls remaining",
)

GITHUB_API_LIMIT = Gauge(
    "github_hetzner_runners_github_api_limit", "Total GitHub API rate limit"
)

GITHUB_API_RESET_TIME = Gauge(
    "github_hetzner_runners_github_api_reset_time",
    "Time until GitHub API rate limit resets in seconds",
)

# Cost metrics
COST_ESTIMATE = Gauge(
    "github_hetzner_runners_cost_estimate",
    "Estimated cost in EUR",
    ["server_type", "location"],
)

# Service health metrics
HEARTBEAT = Gauge(
    "github_hetzner_runners_heartbeat_timestamp",
    "Unix timestamp of the last service heartbeat",
)

# Scale up failure metrics
SCALE_UP_FAILURES_LAST_HOUR = Gauge(
    "github_hetzner_runners_scale_up_failures_last_hour",
    "Total number of scale up failures in the last hour",
)

SCALE_UP_FAILURE_DETAILS_LAST_HOUR = Gauge(
    "github_hetzner_runners_scale_up_failure_last_hour",
    "Details about scale up failures in the last hour",
    [
        "error_type",
        "server_name",
        "server_type",
        "location",
        "labels",
        "timestamp_iso",
        "error",
    ],
)


def update_heartbeat():
    """Update service heartbeat timestamp."""
    HEARTBEAT.set(time.time())


def normalize_status(obj, attr_name="status"):
    """Helper function to normalize status values with consistent error handling.

    Args:
        obj: Object containing the status attribute
        attr_name: Name of the status attribute to access

    Returns:
        Normalized status string, always lowercase, defaults to "unknown"
    """
    try:
        value = getattr(obj, attr_name)
        return value.lower() if value else "unknown"
    except AttributeError:
        return "unknown"


def nested_getattr(obj, *attrs, default=""):
    """Helper function to safely get nested attributes.
    Example: nested_getattr(server, "server", "public_net", "ipv4", "ip", default="")
    is equivalent to getattr(getattr(getattr(getattr(server, "server"), "public_net"), "ipv4"), "ip", default)
    but handles AttributeError at any level of nesting.
    """
    try:
        value = obj
        for attr in attrs[:-1]:
            value = getattr(value, attr)
        return getattr(value, attrs[-1], default)
    except AttributeError:
        return default


def format_server_lifetime(created_dt):
    """Format server lifetime into a human readable string.

    Args:
        created_dt: datetime object of server creation time

    Returns:
        Tuple of (formatted creation time, lifetime string)
    """
    # Convert to UTC if not already
    if created_dt.tzinfo is None:
        created_dt = created_dt.replace(tzinfo=dateutil.tz.UTC)

    lifetime_seconds = time.time() - created_dt.timestamp()
    days = int(lifetime_seconds // (24 * 3600))
    hours = int((lifetime_seconds % (24 * 3600)) // 3600)
    minutes = int((lifetime_seconds % 3600) // 60)
    lifetime_str = f"{days}d {hours}h {minutes}m"
    created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    return created_str, lifetime_str


def normalize_server_creation_time(server):
    """Helper function to normalize server creation time with consistent error handling.

    Args:
        server: Server object containing the creation timestamp

    Returns:
        Normalized creation time string with lifetime, defaults to empty string
    """
    created = nested_getattr(server, "server", "created")
    if not created:
        return ""

    try:
        created_str, lifetime_str = format_server_lifetime(created)
        return f"{created_str} ({lifetime_str})"
    except (ValueError, TypeError) as e:
        logging.debug(f"Failed to handle created timestamp {created}: {e}")
        return str(created)  # Fallback to string representation


def update_servers(servers, server_prices=None, ipv4_price=0.0008, ipv6_price=0.0000):
    """Update all server-related metrics.

    Args:
        servers: List of servers to track metrics for
        server_prices: Dictionary of server prices by type and location
        ipv4_price: Price per hour for IPv4 address (default: 0.0008 EUR)
        ipv6_price: Price per hour for IPv6 address (default: 0.0000 EUR)
    """
    # Clear all existing server metrics
    SERVER_INFO._metrics.clear()
    SERVER_LABELS._metrics.clear()
    SERVER_STATUS._metrics.clear()
    STANDBY_SERVERS_LABELS._metrics.clear()
    RECYCLED_SERVERS_LABELS._metrics.clear()

    total_servers = 0

    # Track counts by status
    status_counts = {}
    standby_counts = {}
    recycled_counts = {}

    # Define all possible statuses
    all_statuses = ["running", "off", "initializing", "ready", "busy"]

    for server in servers:
        # Count servers by status
        status = normalize_status(server, "server_status")
        status_counts[status] = status_counts.get(status, 0) + 1
        total_servers += 1

        # Calculate costs once
        total_cost = None
        base_cost = None
        server_ipv4_cost = None
        server_ipv6_cost = None

        if server_prices:
            try:
                server_type = server.server_type.name
                location = server.server_location.name
                base_cost = server_prices[server_type.lower()][location]
                server_ipv4_cost = (
                    ipv4_price
                    if nested_getattr(server, "server", "public_net", "ipv4", "ip")
                    else 0
                )
                server_ipv6_cost = (
                    ipv6_price
                    if nested_getattr(server, "server", "public_net", "ipv6", "ip")
                    else 0
                )

                total_cost = get_server_price(
                    server_prices,
                    server_type,
                    location,
                    ipv4_price=server_ipv4_cost,
                    ipv6_price=server_ipv6_cost,
                )

                # Set cost estimate metric
                if total_cost is not None:
                    COST_ESTIMATE.labels(
                        server_type=server_type,
                        location=location,
                    ).set(total_cost)
            except (KeyError, AttributeError):
                pass

        # Track detailed server information
        try:
            server_info = {
                "name": server.name,
                "type": nested_getattr(server, "server_type", "name"),
                "location": nested_getattr(server, "server_location", "name"),
                "status": status,
                "runner_status": normalize_status(server),
                "ipv4": nested_getattr(server, "server", "public_net", "ipv4", "ip"),
                "ipv6": nested_getattr(server, "server", "public_net", "ipv6", "ip"),
                "created": normalize_server_creation_time(server),
                "cost_hourly": str(total_cost) if total_cost is not None else None,
                "cost_currency": "EUR",
            }

            # Calculate total cost based on server lifetime
            try:
                created = nested_getattr(server, "server", "created")
                if created and total_cost is not None:
                    lifetime_seconds = time.time() - created.timestamp()
                    lifetime_hours = max(
                        1.0, lifetime_seconds / 3600.0
                    )  # minimum 1 hour billing
                    total_cost_so_far = total_cost * lifetime_hours
                    server_info["cost_total"] = f"{total_cost_so_far:.3f}"
            except (AttributeError, TypeError):
                pass

            SERVER_INFO.labels(
                server_id=str(server.server.id), server_name=server.name
            ).info(server_info)
        except AttributeError:
            # Skip server info if server.server.id or server.name is missing
            pass

        try:
            # Track server labels
            for label in server.labels:
                SERVER_LABELS.labels(
                    server_id=str(server.server.id),
                    server_name=server.name,
                    label=label.lower(),
                ).set(1)

            # Track server status
            SERVER_STATUS.labels(
                server_id=str(server.server.id),
                server_name=server.name,
                status=status,
            ).set(1)

            # Track standby servers
            if server.name.startswith(standby_server_name_prefix):
                key = (status, server.server_type.name, server.server_location.name)
                standby_counts[key] = standby_counts.get(key, 0) + 1

                for label in server.labels:
                    STANDBY_SERVERS_LABELS.labels(
                        server_type=server.server_type.name,
                        location=server.server_location.name,
                        label=label.lower(),
                    ).set(1)

            # Track recycled servers
            if server.name.startswith(recycle_server_name_prefix):
                key = (status, server.server_type.name, server.server_location.name)
                recycled_counts[key] = recycled_counts.get(key, 0) + 1

                for label in server.labels:
                    RECYCLED_SERVERS_LABELS.labels(
                        server_type=server.server_type.name,
                        location=server.server_location.name,
                        label=label.lower(),
                    ).set(1)
        except AttributeError:
            # Skip label and status tracking if required attributes are missing
            pass

    # Set total counts
    SERVERS_TOTAL_COUNT.set(total_servers)

    # Set counts for all possible statuses, defaulting to 0 if not present
    for status in all_statuses:
        SERVERS_TOTAL.labels(status=status).set(status_counts.get(status, 0))

    # Set standby server counts
    for (status, server_type, location), count in standby_counts.items():
        STANDBY_SERVERS_TOTAL.labels(
            status=status,
            server_type=server_type,
            location=location,
        ).set(count)

    # Set recycled server counts
    for (status, server_type, location), count in recycled_counts.items():
        RECYCLED_SERVERS_TOTAL.labels(
            status=status,
            server_type=server_type,
            location=location,
        ).set(count)


def update_runners(
    runners,
    github_repository,
    max_server_ready_time=None,
    get_runner_server_type_and_location_fn=None,
):
    """Update all runner-related metrics."""
    # Clear all existing runner metrics
    RUNNER_INFO._metrics.clear()
    RUNNER_LABELS._metrics.clear()
    RUNNER_STATUS._metrics.clear()

    total_runners = 0
    total_unused_runners = 0
    busy_runners = 0
    current_time = time.time()

    # Track counts by status
    status_counts = {}
    unused_counts = {}

    for runner in runners:
        # Count runners by status
        status = normalize_status(runner)
        status_counts[status] = status_counts.get(status, 0) + 1
        total_runners += 1

        try:
            # Track detailed runner information
            runner_info = {
                "name": runner.name,
                "os": getattr(runner, "os", "unknown"),
                "status": status,
                "busy": str(getattr(runner, "busy", False)).lower(),
                "repository": github_repository,
            }
            RUNNER_INFO.labels(runner_id=str(runner.id), runner_name=runner.name).info(
                runner_info
            )

            # Track runner labels
            if hasattr(runner, "raw_data") and "labels" in runner.raw_data:
                for label in runner.raw_data["labels"]:
                    RUNNER_LABELS.labels(
                        runner_id=str(runner.id),
                        runner_name=runner.name,
                        label=label["name"].lower(),
                    ).set(1)

            # Track runner status
            is_busy = getattr(runner, "busy", False)
            RUNNER_STATUS.labels(
                runner_id=str(runner.id),
                runner_name=runner.name,
                status=status,
                busy=str(is_busy).lower(),
            ).set(1)

            if status == "online" and is_busy:
                busy_runners += 1

            # Track unused runners
            if max_server_ready_time and status == "online" and not is_busy:
                last_job_time = getattr(runner, "last_job_time")
                if last_job_time:
                    unused_age = current_time - last_job_time
                    if unused_age > max_server_ready_time:
                        # Get server type and location from runner name
                        if get_runner_server_type_and_location_fn:
                            try:
                                server_type, location = (
                                    get_runner_server_type_and_location_fn(runner.name)
                                )
                                if server_type and location:
                                    key = (server_type, location)
                                    unused_counts[key] = unused_counts.get(key, 0) + 1
                                    total_unused_runners += 1
                                    UNUSED_RUNNER_AGE.labels(
                                        runner_id=str(runner.id),
                                        runner_name=runner.name,
                                    ).set(unused_age)
                            except (ValueError, AttributeError):
                                pass
        except AttributeError:
            # Skip runner metrics if runner.id or runner.name is missing
            pass

    # Set total counts
    RUNNERS_TOTAL_COUNT.set(total_runners)
    RUNNERS_BUSY.set(busy_runners)
    UNUSED_RUNNERS_TOTAL_COUNT.set(total_unused_runners)

    # Set counts by status
    for status in ["online", "offline"]:
        RUNNERS_TOTAL.labels(status=status).set(status_counts.get(status, 0))

    # Set unused runner counts
    for (server_type, location), count in unused_counts.items():
        UNUSED_RUNNERS_TOTAL.labels(
            server_type=server_type,
            location=location,
        ).set(count)


def update_jobs(run_jobs: list[(WorkflowRun, WorkflowJob)]):
    """Update all job-related metrics."""
    queued_count = 0
    running_count = 0
    current_time = time.time()

    # Clear all existing job metrics
    QUEUED_JOB_INFO._metrics.clear()
    QUEUED_JOB_LABELS._metrics.clear()
    QUEUED_JOB_WAIT_TIME._metrics.clear()
    RUNNING_JOB_INFO._metrics.clear()
    RUNNING_JOB_LABELS._metrics.clear()
    RUNNING_JOB_TIME._metrics.clear()

    for run, job in run_jobs:

        # Normalize job status
        status = normalize_status(job)

        job_info = {
            "name": job.name,
            "workflow_name": run.name,
            "repository": run.repository.full_name,
            "status": status,
            "queued_at": job.raw_data.get("started_at", ""),
            "run_attempt": str(run.run_attempt),
            "run_number": str(run.run_number),
            "head_branch": run.head_branch or "",
            "head_sha": run.head_sha or "",
        }

        if status == "queued":
            queued_count += 1
            # Track detailed job info
            QUEUED_JOB_INFO.labels(job_id=str(job.id), run_id=str(run.id)).info(
                job_info
            )

            # Track job labels
            for label in job.raw_data.get("labels", []):
                QUEUED_JOB_LABELS.labels(
                    job_id=str(job.id), run_id=str(run.id), label=label.lower()
                ).set(1)

            # Track job wait time
            started_at = job.raw_data.get("started_at")
            if started_at:
                started_at = dateutil.parser.parse(started_at)
                wait_time = current_time - started_at.timestamp()
                QUEUED_JOB_WAIT_TIME.labels(job_id=str(job.id), run_id=str(run.id)).set(
                    wait_time
                )

        elif status == "in_progress":
            running_count += 1
            # Track detailed job info
            RUNNING_JOB_INFO.labels(job_id=str(job.id), run_id=str(run.id)).info(
                job_info
            )

            # Track job labels
            for label in job.raw_data.get("labels", []):
                RUNNING_JOB_LABELS.labels(
                    job_id=str(job.id), run_id=str(run.id), label=label.lower()
                ).set(1)

            # Track job run time
            started_at = job.raw_data.get("started_at")
            if started_at:
                started_at = dateutil.parser.parse(started_at)
                run_time = current_time - started_at.timestamp()
                RUNNING_JOB_TIME.labels(job_id=str(job.id), run_id=str(run.id)).set(
                    run_time
                )

    # Set total counts
    QUEUED_JOBS.set(queued_count)
    RUNNING_JOBS.set(running_count)


def update_pools(servers, standby_runners, count_available_fn=None):
    """Update all pool-related metrics."""
    for server in servers:
        try:
            pool_type = (
                "standby"
                if server.name.startswith(standby_server_name_prefix)
                else "regular"
            )
            RUNNER_POOL_STATUS.labels(
                pool_type=pool_type,
                server_type=server.server_type.name,
                location=server.server_location.name,
            ).set(1)
        except AttributeError:
            # Skip server if required attributes are missing
            pass

    if standby_runners:
        for standby_runner in standby_runners:
            try:
                RUNNER_POOL_CAPACITY.labels(
                    pool_type="standby",
                    server_type=standby_runner.server_type.name,
                    location=standby_runner.location.name,
                ).set(standby_runner.count)

                if count_available_fn:
                    available = count_available_fn(
                        servers=servers, labels=set(standby_runner.labels)
                    )
                    RUNNER_POOL_AVAILABLE.labels(
                        pool_type="standby",
                        server_type=standby_runner.server_type.name,
                        location=standby_runner.location.name,
                    ).set(available)
            except AttributeError:
                # Skip standby runner if required attributes are missing
                pass


def record_scale_up_failure(
    error_type, server_name, server_type, location, error_details, cache=[]
):
    """Record a scale up failure or success.

    Args:
        error_type: Type of the error or "success" for successful scale up
        server_name: Name of the server
        server_type: Type of the server
        location: Location of the server
        error_details: Details about the error or success details
        cache: List to store error messages (optional)
    """
    current_time = time.time()

    # Only track failures in the cache
    if error_type != "success":
        # Add new error to cache with timestamp
        cache.append(
            {
                "timestamp": current_time,
                "error_type": error_type,
                "server_name": server_name,
                "server_type": server_type,
                "location": location,
                "error_details": error_details,
            }
        )

    # Clean up timestamps older than 1 hour
    while cache and cache[0]["timestamp"] < current_time - 3600:  # 1 hour in seconds
        cache.pop(0)

    SCALE_UP_FAILURES_LAST_HOUR.set(len(cache))

    # Clear all existing failure details metrics
    SCALE_UP_FAILURE_DETAILS_LAST_HOUR._metrics.clear()

    # Only create new metrics if there are failures
    if cache:
        # Update metrics from cache
        for error in cache:
            # Convert timestamps
            timestamp_iso = (
                datetime.fromtimestamp(error["timestamp"])
                .replace(tzinfo=dateutil.tz.UTC)
                .isoformat()
            )

            # Set gauge to 1 for each error
            SCALE_UP_FAILURE_DETAILS_LAST_HOUR.labels(
                error_type=error["error_type"],
                server_name=error["server_name"],
                server_type=error["server_type"],
                location=error["location"] or "",
                timestamp_iso=timestamp_iso,
                labels=str(error["error_details"]["labels"]),
                error=str(error["error_details"]["error"]),
            ).set(1)


def update_github_api(current_calls: int, total_calls: int, reset_time: float):
    """Update GitHub API metrics.

    Args:
        current_calls: Number of API calls remaining
        total_calls: Total API call limit
        reset_time: Unix timestamp when the rate limit will reset
    """
    GITHUB_API_REMAINING.set(current_calls)
    GITHUB_API_LIMIT.set(total_calls)
    GITHUB_API_RESET_TIME.set(reset_time - time.time())


def record_server_creation(server_type: str, location: str, creation_time: float):
    """Record metrics for a server creation.

    Args:
        server_type: The type of server created
        location: The location where server was created, or None
        creation_time: Time taken to create the server in seconds
    """
    location = location if location is not None else "unknown"
    SERVERS_CREATED_TOTAL.labels(server_type=server_type, location=location).inc()
    SERVER_CREATION_TIME.labels(server_type=server_type, location=location).observe(
        creation_time
    )


def record_server_deletion(server_type: str, location: str, reason: str):
    """Record metrics for a server deletion.

    Args:
        server_type: The type of server deleted
        location: The location where server was deleted, or None
        reason: The reason for deletion (powered_off, zombie, unused)
    """
    location = location if location is not None else "unknown"
    SERVERS_DELETED_TOTAL.labels(server_type=server_type, location=location).inc()
    SCALE_DOWN_OPERATIONS.labels(
        reason=reason, server_type=server_type, location=location
    ).inc()
    SCALE_DOWN_OPERATIONS_TOTAL.inc()
