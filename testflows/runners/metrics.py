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
import psutil
from datetime import datetime

from github.WorkflowRun import WorkflowRun
from github.WorkflowJob import WorkflowJob
from prometheus_client import Counter, Gauge, Histogram, Info
from .constants import standby_server_name_prefix
from .server import get_runner_server_name


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

# Volume metrics
VOLUMES_TOTAL = Gauge(
    "github_hetzner_runners_volumes_total",
    "Total number of volumes",
    ["status"],  # status: available, creating, attached
)

VOLUMES_TOTAL_COUNT = Gauge(
    "github_hetzner_runners_volumes_total_count",
    "Total number of volumes across all statuses",
)

VOLUMES_CREATED_TOTAL = Counter(
    "github_hetzner_runners_volumes_created_total",
    "Total number of volumes created",
    ["volume_type", "location"],
)

VOLUMES_DELETED_TOTAL = Counter(
    "github_hetzner_runners_volumes_deleted_total",
    "Total number of volumes deleted",
    ["volume_type", "location"],
)

# Detailed volume metrics
VOLUME_INFO = Info(
    "github_hetzner_runners_volume",
    "Information about a volume",
    ["volume_id", "volume_name"],
)

VOLUME_LABELS = Gauge(
    "github_hetzner_runners_volume_labels",
    "Labels assigned to volumes",
    ["volume_id", "volume_name", "label"],
)

VOLUME_STATUS = Gauge(
    "github_hetzner_runners_volume_status",
    "Volume status (1 for active, 0 for inactive)",
    [
        "volume_id",
        "volume_name",
        "status",  # status: available, creating, attached
    ],
)

VOLUME_ATTACHMENT = Gauge(
    "github_hetzner_runners_volume_attachment",
    "Volume attachment status",
    [
        "volume_id",
        "volume_name",
        "attached",  # attached: true, false
    ],
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

ZOMBIE_SERVER_INFO = Gauge(
    "github_hetzner_runners_zombie_server",
    "Zombie server information including age in seconds",
    ["server_id", "server_name", "server_type", "location", "status", "created"],
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

UNUSED_RUNNER_INFO = Gauge(
    "github_hetzner_runners_unused_runner",
    "Unused runner information including age in seconds",
    [
        "runner_id",
        "runner_name",
        "server_id",
        "server_name",
        "server_type",
        "location",
        "status",
        "created",
    ],
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
        "server_location",
        "server_labels",
        "timestamp_iso",
        "error",
    ],
)

# Scale down failure metrics
SCALE_DOWN_FAILURES_LAST_HOUR = Gauge(
    "github_hetzner_runners_scale_down_failures_last_hour",
    "Total number of scale down failures in the last hour",
)

SCALE_DOWN_FAILURE_DETAILS_LAST_HOUR = Gauge(
    "github_hetzner_runners_scale_down_failure_last_hour",
    "Details about scale down failures in the last hour",
    [
        "error_type",
        "server_name",
        "server_type",
        "server_location",
        "server_labels",
        "timestamp_iso",
        "error",
    ],
)

# System health metrics
SYSTEM_CPU_PERCENT = Gauge(
    "github_hetzner_runners_system_cpu_percent",
    "System CPU utilization percentage",
)

SYSTEM_MEMORY_TOTAL = Gauge(
    "github_hetzner_runners_system_memory_total_bytes",
    "Total system memory in bytes",
)

SYSTEM_MEMORY_AVAILABLE = Gauge(
    "github_hetzner_runners_system_memory_available_bytes",
    "Available system memory in bytes",
)

SYSTEM_MEMORY_USED = Gauge(
    "github_hetzner_runners_system_memory_used_bytes",
    "Used system memory in bytes",
)

SYSTEM_MEMORY_PERCENT = Gauge(
    "github_hetzner_runners_system_memory_percent",
    "System memory utilization percentage",
)

SYSTEM_DISK_TOTAL = Gauge(
    "github_hetzner_runners_system_disk_total_bytes",
    "Total disk space in bytes",
    ["mountpoint"],
)

SYSTEM_DISK_USED = Gauge(
    "github_hetzner_runners_system_disk_used_bytes",
    "Used disk space in bytes",
    ["mountpoint"],
)

SYSTEM_DISK_FREE = Gauge(
    "github_hetzner_runners_system_disk_free_bytes",
    "Free disk space in bytes",
    ["mountpoint"],
)

SYSTEM_DISK_PERCENT = Gauge(
    "github_hetzner_runners_system_disk_percent",
    "Disk utilization percentage",
    ["mountpoint"],
)

PROCESS_CPU_PERCENT = Gauge(
    "github_hetzner_runners_process_cpu_percent",
    "Current process CPU utilization percentage",
)

PROCESS_MEMORY_RSS = Gauge(
    "github_hetzner_runners_process_memory_rss_bytes",
    "Current process RSS memory usage in bytes",
)

PROCESS_MEMORY_VMS = Gauge(
    "github_hetzner_runners_process_memory_vms_bytes",
    "Current process VMS memory usage in bytes",
)

PROCESS_MEMORY_PERCENT = Gauge(
    "github_hetzner_runners_process_memory_percent",
    "Current process memory utilization percentage",
)

PROCESS_NUM_THREADS = Gauge(
    "github_hetzner_runners_process_num_threads",
    "Number of threads used by current process",
)

PROCESS_NUM_FDS = Gauge(
    "github_hetzner_runners_process_num_fds",
    "Number of file descriptors used by current process",
)

SYSTEM_LOAD_AVERAGE_1M = Gauge(
    "github_hetzner_runners_system_load_average_1m",
    "System load average over 1 minute",
)

SYSTEM_LOAD_AVERAGE_5M = Gauge(
    "github_hetzner_runners_system_load_average_5m",
    "System load average over 5 minutes",
)

SYSTEM_LOAD_AVERAGE_15M = Gauge(
    "github_hetzner_runners_system_load_average_15m",
    "System load average over 15 minutes",
)

SYSTEM_NUM_CPUS = Gauge(
    "github_hetzner_runners_system_num_cpus",
    "Number of CPU cores",
)

SYSTEM_BOOT_TIME = Gauge(
    "github_hetzner_runners_system_boot_time",
    "System boot time as Unix timestamp",
)

# Simple root disk metric (no labels)
SYSTEM_ROOT_DISK_PERCENT = Gauge(
    "github_hetzner_runners_system_root_disk_percent",
    "Root filesystem disk usage percentage",
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

    total_servers = 0

    # Track counts by status
    status_counts = {}

    # Define all possible statuses
    all_statuses = ["running", "off", "initializing", "ready", "busy"]

    for server in servers:
        # Count servers by status
        status = normalize_status(server, "server_status")
        status_counts[status] = status_counts.get(status, 0) + 1
        total_servers += 1

        # Calculate costs once
        total_cost = None
        server_ipv4_cost = None
        server_ipv6_cost = None

        if server_prices:
            try:
                server_type = server.server_type.name
                location = server.server_location.name
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
                "id": str(server.server.id),
                "name": server.name,
                "type": nested_getattr(server, "server_type", "name"),
                "location": nested_getattr(server, "server_location", "name"),
                "image": nested_getattr(server, "server", "image", "name"),
                "architecture": nested_getattr(
                    server, "server", "image", "architecture"
                ),
                "status": status,
                "runner_status": normalize_status(server),
                "ipv4": nested_getattr(server, "server", "public_net", "ipv4", "ip"),
                "ipv6": nested_getattr(server, "server", "public_net", "ipv6", "ip"),
                "created": (
                    nested_getattr(server, "server", "created").strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if nested_getattr(server, "server", "created")
                    else ""
                ),
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
        except AttributeError:
            # Skip label and status tracking if required attributes are missing
            pass

    # Set total counts
    SERVERS_TOTAL_COUNT.set(total_servers)

    # Set counts for all possible statuses, defaulting to 0 if not present
    for status in all_statuses:
        SERVERS_TOTAL.labels(status=status).set(status_counts.get(status, 0))


def update_volumes(volumes, price=0.044):
    """Update all volume-related metrics.

    Args:
        volumes: List of volumes to track metrics for
        price: Price per GB per month in EUR (default: 0.044)
    """
    # Clear all existing volume metrics
    VOLUME_INFO._metrics.clear()
    VOLUME_LABELS._metrics.clear()
    VOLUME_STATUS._metrics.clear()
    VOLUME_ATTACHMENT._metrics.clear()

    total_volumes = 0

    # Track counts by status
    status_counts = {}

    # Define all possible statuses
    all_statuses = ["available", "creating", "attached"]

    for volume in volumes:
        # Count volumes by status
        # Determine status based on volume state and attachment
        if hasattr(volume, "server") and volume.server is not None:
            status = "attached"
        else:
            status = getattr(volume, "status", "unknown")

        status_counts[status] = status_counts.get(status, 0) + 1
        total_volumes += 1

        try:
            # Calculate volume cost
            volume_size_gb = getattr(volume, "size", 0)
            # Convert monthly price to hourly (price per GB per month / hours per month)
            cost_hourly = (
                (price * volume_size_gb) / (24 * 30) if volume_size_gb > 0 else 0.0
            )

            # Track detailed volume information
            volume_info = {
                "name": volume.name,
                "size": str(volume.size),
                "location": (
                    getattr(volume.location, "name", "unknown")
                    if hasattr(volume, "location") and volume.location
                    else "unknown"
                ),
                "status": status,  # Use the status we determined above
                "format": getattr(volume, "format", "unknown"),
                "created": (
                    volume.created.strftime("%Y-%m-%d %H:%M:%S")
                    if hasattr(volume, "created") and volume.created
                    else ""
                ),
                "cost_hourly": str(cost_hourly) if cost_hourly > 0 else None,
                "cost_currency": "EUR",
            }

            # Calculate total cost based on volume lifetime
            try:
                created = getattr(volume, "created", None)
                if created and cost_hourly > 0:
                    lifetime_seconds = time.time() - created.timestamp()
                    lifetime_hours = max(
                        1.0, lifetime_seconds / 3600.0
                    )  # minimum 1 hour billing
                    total_cost_so_far = cost_hourly * lifetime_hours
                    volume_info["cost_total"] = f"{total_cost_so_far:.3f}"
            except (AttributeError, TypeError):
                pass

            # Server information removed from volume metrics

            VOLUME_INFO.labels(volume_id=str(volume.id), volume_name=volume.name).info(
                volume_info
            )

            # Track volume labels
            if hasattr(volume, "labels"):
                for label_name, label_value in volume.labels.items():
                    VOLUME_LABELS.labels(
                        volume_id=str(volume.id),
                        volume_name=volume.name,
                        label=f"{label_name}:{label_value}".lower(),
                    ).set(1)

            # Track volume status
            VOLUME_STATUS.labels(
                volume_id=str(volume.id),
                volume_name=volume.name,
                status=status,
            ).set(1)

            # Track volume attachment
            is_attached = hasattr(volume, "server") and volume.server is not None

            VOLUME_ATTACHMENT.labels(
                volume_id=str(volume.id),
                volume_name=volume.name,
                attached=str(is_attached).lower(),
            ).set(1)

        except AttributeError:
            # Skip volume metrics if volume.id or volume.name is missing
            pass

    # Set total counts
    VOLUMES_TOTAL_COUNT.set(total_volumes)

    # Set counts for all possible statuses, defaulting to 0 if not present
    for status in all_statuses:
        VOLUMES_TOTAL.labels(status=status).set(status_counts.get(status, 0))


def update_runners(
    runners,
    github_repository,
):
    """Update all runner-related metrics."""
    # Clear all existing runner metrics
    RUNNER_INFO._metrics.clear()
    RUNNER_LABELS._metrics.clear()
    RUNNER_STATUS._metrics.clear()

    total_runners = 0
    busy_runners = 0

    # Track counts by status
    status_counts = {}

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
        except AttributeError:
            # Skip runner metrics if runner.id or runner.name is missing
            pass

    # Set total counts
    RUNNERS_TOTAL_COUNT.set(total_runners)
    RUNNERS_BUSY.set(busy_runners)

    # Set counts by status
    for status in ["online", "offline"]:
        RUNNERS_TOTAL.labels(status=status).set(status_counts.get(status, 0))


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
    error_type, server_name, server_type, server_location, error_details, cache=[]
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
                "server_location": server_location,
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
                server_location=error["server_location"] or "",
                timestamp_iso=timestamp_iso,
                server_labels=str(error["error_details"]["labels"]),
                error=str(error["error_details"]["error"]),
            ).set(1)


def record_scale_down_failure(
    error_type, server_name, server_type, server_location, error_details, cache=[]
):
    """Record a scale down failure or success.

    Args:
        error_type: Type of the error or "success" for successful scale down
        server_name: Name of the server
        server_type: Type of the server
        server_location: Location of the server
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
                "server_location": server_location,
                "error_details": error_details,
            }
        )

    # Clean up timestamps older than 1 hour
    while cache and cache[0]["timestamp"] < current_time - 3600:  # 1 hour in seconds
        cache.pop(0)

    SCALE_DOWN_FAILURES_LAST_HOUR.set(len(cache))

    # Clear all existing failure details metrics
    SCALE_DOWN_FAILURE_DETAILS_LAST_HOUR._metrics.clear()

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
            SCALE_DOWN_FAILURE_DETAILS_LAST_HOUR.labels(
                error_type=error["error_type"],
                server_name=error["server_name"],
                server_type=error["server_type"],
                server_location=error["server_location"] or "",
                timestamp_iso=timestamp_iso,
                server_labels=str(error["error_details"]["labels"]),
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


def update_zombie_servers(zombie_servers_dict):
    """Update zombie server metrics.

    Args:
        zombie_servers_dict: Dictionary of zombie servers with server objects
    """
    # Clear existing zombie server metrics
    ZOMBIE_SERVERS_TOTAL._metrics.clear()
    ZOMBIE_SERVER_INFO._metrics.clear()

    total_zombie_servers = 0
    zombie_counts = {}
    current_time = time.time()

    for server_name, zombie_server in zombie_servers_dict.items():
        server = zombie_server.server
        server_type = server.server_type.name
        location = server.datacenter.location.name
        key = (server_type, location)

        # Count by type and location
        zombie_counts[key] = zombie_counts.get(key, 0) + 1
        total_zombie_servers += 1

        # Track zombie server age
        zombie_age = current_time - zombie_server.time
        ZOMBIE_SERVER_INFO.labels(
            server_id=str(server.id),
            server_name=server.name,
            server_type=server_type,
            location=location,
            status=server.status,
            created=server.created.isoformat() if server.created else "",
        ).set(zombie_age)

    # Set total count
    ZOMBIE_SERVERS_TOTAL_COUNT.set(total_zombie_servers)

    # Set counts by type and location
    for (server_type, location), count in zombie_counts.items():
        ZOMBIE_SERVERS_TOTAL.labels(server_type=server_type, location=location).set(
            count
        )


def update_unused_runners(unused_runners_dict):
    """Update unused runner metrics.

    Args:
        unused_runners_dict: Dictionary of unused runners with runner objects
    """
    # Clear existing unused runner metrics
    UNUSED_RUNNERS_TOTAL._metrics.clear()
    UNUSED_RUNNER_INFO._metrics.clear()
    UNUSED_RUNNERS_TOTAL_COUNT.set(0)

    total_unused_runners = 0
    unused_counts = {}
    current_time = time.time()

    for runner_name, unused_runner in unused_runners_dict.items():
        runner = unused_runner.runner

        # Try to get server type and location from runner name
        # This assumes runner names follow the pattern: server_name-runner_id
        server_name = get_runner_server_name(runner_name)
        server_type = "unknown"
        location = "unknown"

        # Extract server type and location from server name if possible
        # This is a simplified approach - in practice, you might need to look up the actual server
        if server_name and "-" in server_name:
            parts = server_name.split("-")
            if len(parts) >= 3:
                # Assuming format: prefix-type-location-...
                server_type = parts[1] if len(parts) > 1 else "unknown"
                location = parts[2] if len(parts) > 2 else "unknown"

        key = (server_type, location)

        # Count by type and location
        unused_counts[key] = unused_counts.get(key, 0) + 1
        total_unused_runners += 1

        # Track unused runner age
        unused_age = current_time - unused_runner.time
        # Extract server name from runner name (this is the actual server name)
        server_name = get_runner_server_name(runner_name)
        # For now we don't have direct server object access, but server_name is correct
        server_id = "unknown"
        status = "unknown"
        created = ""

        UNUSED_RUNNER_INFO.labels(
            runner_id=str(runner.id),
            runner_name=runner.name,
            server_id=server_id,
            server_name=server_name or "unknown",
            server_type=server_type,
            location=location,
            status=status,
            created=created,
        ).set(unused_age)

    # Set total count
    UNUSED_RUNNERS_TOTAL_COUNT.set(total_unused_runners)

    # Set counts by type and location
    for (server_type, location), count in unused_counts.items():
        UNUSED_RUNNERS_TOTAL.labels(server_type=server_type, location=location).set(
            count
        )


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


def update_system_health():
    """Update system health metrics.

    This function collects various system health metrics including:
    - CPU utilization (system and process)
    - Memory usage (system and process)
    - Disk usage
    - Process statistics (threads, file descriptors)
    - System load averages
    - System information (CPU count, boot time)
    """
    try:
        # Get current process
        current_process = psutil.Process()

        # System CPU metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        SYSTEM_CPU_PERCENT.set(cpu_percent)

        # System memory metrics
        memory = psutil.virtual_memory()
        SYSTEM_MEMORY_TOTAL.set(memory.total)
        SYSTEM_MEMORY_AVAILABLE.set(memory.available)
        SYSTEM_MEMORY_USED.set(memory.used)
        SYSTEM_MEMORY_PERCENT.set(memory.percent)

        # System disk metrics
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                mountpoint = partition.mountpoint

                SYSTEM_DISK_TOTAL.labels(mountpoint=mountpoint).set(usage.total)
                SYSTEM_DISK_USED.labels(mountpoint=mountpoint).set(usage.used)
                SYSTEM_DISK_FREE.labels(mountpoint=mountpoint).set(usage.free)
                SYSTEM_DISK_PERCENT.labels(mountpoint=mountpoint).set(usage.percent)

                # Set simple root disk metric for root filesystem
                if mountpoint == "/":
                    SYSTEM_ROOT_DISK_PERCENT.set(usage.percent)
            except (PermissionError, FileNotFoundError):
                # Skip partitions that can't be accessed
                continue

        # Process CPU metrics
        try:
            process_cpu_percent = current_process.cpu_percent()
            PROCESS_CPU_PERCENT.set(process_cpu_percent)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        # Process memory metrics
        try:
            process_memory = current_process.memory_info()
            PROCESS_MEMORY_RSS.set(process_memory.rss)
            PROCESS_MEMORY_VMS.set(process_memory.vms)

            # Calculate process memory percentage
            process_memory_percent = current_process.memory_percent()
            PROCESS_MEMORY_PERCENT.set(process_memory_percent)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        # Process thread and file descriptor metrics
        try:
            PROCESS_NUM_THREADS.set(current_process.num_threads())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        try:
            # Get number of file descriptors (Unix only)
            if hasattr(current_process, "num_fds"):
                PROCESS_NUM_FDS.set(current_process.num_fds())
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            pass

        # System load averages
        try:
            load_avg = psutil.getloadavg()
            SYSTEM_LOAD_AVERAGE_1M.set(load_avg[0])
            SYSTEM_LOAD_AVERAGE_5M.set(load_avg[1])
            SYSTEM_LOAD_AVERAGE_15M.set(load_avg[2])
        except (OSError, AttributeError):
            # Load average not available on all systems
            pass

        # System information
        SYSTEM_NUM_CPUS.set(psutil.cpu_count())
        SYSTEM_BOOT_TIME.set(psutil.boot_time())

    except Exception as e:
        logging.exception(f"Error updating system health metrics: {e}")
