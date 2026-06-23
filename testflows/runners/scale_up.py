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

from .logger import logger
from . import metrics
from .config import (
    Config,
    check_recycle_script,
    check_startup_script,
    check_setup_script,
)
from .config import standby_runner as StandbyRunner
from .utils import get_runner_server_type
from .cloud_provider import CloudProvider, ProviderServer, ProviderServerType
from .errors import ServerTypeError, ImageSpecFormatError, LocationError
from .constants import (
    server_name_prefix,
    runner_name_prefix,
    standby_server_name_prefix,
    standby_runner_name_prefix,
    recycle_server_name_prefix,
    server_ssh_key_label,
    github_runner_label,
    recycle_timestamp_label,
)

from .server import wait_ssh, ssh, get_runner_server_name
from .ordered_set import OrderedSet as set

from hcloud import APIException
from hcloud.ssh_keys.domain import SSHKey
from hcloud.server_types.domain import ServerType
from hcloud.locations.domain import Location
from hcloud.servers.client import BoundServer, BoundVolume
from hcloud.servers.domain import Server, ServerCreatePublicNetwork


from github import Auth, Github
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun
from github.SelfHostedActionsRunner import SelfHostedActionsRunner
from github.GithubException import GithubException

from requests.exceptions import RetryError as RequestsRetryError

from concurrent.futures import ThreadPoolExecutor, Future

# Lock to access the volumes list
volumes_lock = threading.Lock()


@dataclass
class ScaleUpFailureMessage:
    """Scale up server failure."""

    time: float
    labels: list[str]
    server_name: str
    exception: Exception


class MaxNumberOfServersReached(Exception):
    """Exception to indicate that scale up service
    reached maximum number of servers."""

    pass


class MaxNumberOfServersForLabelReached(Exception):
    """Exception to indicate that server can't be created
    because label-specific limit has been reached."""

    pass


class CanceledServerCreation(Exception):
    """Exception to indicate that server creation was canceled."""

    pass


@dataclass
class Volume:
    """Volume configuration."""

    name: str
    size: int  # size in GB


@dataclass
class RunnerServer:
    name: str
    labels: set[str]
    server_type: str
    server_location: str
    server_volumes: list[Volume] = None
    server_status: str = CloudProvider.STATUS_STARTING
    runner_status: str = "initializing"  # busy, ready
    server: ProviderServer = None
    provider_name: str = None

    def __post_init__(self):
        if self.server_volumes is None:
            self.server_volumes = []


def uid():
    """Return unique id - just a timestamp with fixed width up to microseconds."""
    return f"{time.time():.6f}".replace(".", "")


def get_volume_name(name: str):
    """Get volume name. Format: <name>-<architecture>-<os_flavor>-<os_version>-<uid>."""
    return name.split("-", 1)[0]


def get_runner_server_type(runner_name: str) -> str | None:
    """Return the server type embedded in a runner name, or None."""
    if runner_name and runner_name.startswith(runner_name_prefix):
        parts = runner_name.split("-", 4)
        if len(parts) == 5:
            return parts[4]
    return None


def server_setup(
    server: ProviderServer,
    setup_script: str,
    startup_script: str,
    github_token: str,
    github_repository: str,
    runner_labels: str,
    timeout: float = 60,
):
    """Setup new server instance."""
    cache_volume_name = "cache"

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

    with Action("Resizing and mounting volumes", server_name=server.name):
        if server.volumes:
            ssh(
                server,
                "'sudo echo \"name,id,size,mount,device,used,free,usage\" > /etc/hetzner-volumes'",
                stacklevel=5,
            )

        cache_volume_found = False

        for volume in sorted(server.volumes, key=lambda v: v.name):
            volume_name = get_volume_name(volume.name)
            ssh(
                server,
                (
                    f"'sudo mkdir -p /mnt/{volume_name} "
                    f"&& sudo umount {volume.device_path} 2>/dev/null || true"
                    f"&& sudo e2fsck -f -y {volume.device_path} || true "
                    f"&& sudo e2fsck -f -y {volume.device_path} "
                    f"&& sudo resize2fs {volume.device_path} "
                    f"&& sudo mount -o discard,defaults {volume.device_path} /mnt/{volume_name} "
                    f'&& sudo echo "{volume.name},{volume.id},{volume.size}GB,/mnt/{volume_name},{volume.device_path},$(df -h /mnt/{volume_name} | awk "NR==2 {{print \\$3\\",\\"\\$4\\",\\"\\$5}}")" >> /etc/hetzner-volumes\''
                ),
                stacklevel=5,
            )

            if not cache_volume_found and volume_name.startswith("cache"):
                cache_volume_name = volume_name
                cache_volume_found = True
                with Action(
                    "Mounting apt-archives and apt-lists cache", server_name=server.name
                ):
                    ssh(
                        server,
                        (
                            f"'sudo mkdir -p /mnt/{volume_name}/apt-archives /mnt/{volume_name}/apt-lists /var/cache/apt/archives /var/lib/apt/lists "
                            f"&& sudo mount --bind /mnt/{volume_name}/apt-archives /var/cache/apt/archives "
                            f"&& sudo mount --bind /mnt/{volume_name}/apt-lists /var/lib/apt/lists'"
                        ),
                        stacklevel=5,
                    )

                with Action(
                    "Check apt-lists validity and clear if invalid",
                    server_name=server.name,
                ):
                    ssh(
                        server,
                        (
                            "'if ! sudo apt-get update -qq; then "
                            'echo "APT update failed, clearing lists and retrying..."; '
                            "sudo rm -rf /var/lib/apt/lists/* && "
                            "sudo mkdir -p /var/lib/apt/lists && "
                            "sudo apt-get update; "
                            "fi'"
                        ),
                        stacklevel=5,
                    )

    # When the SSH user is not root (e.g. 'ubuntu' on AWS), setup.sh and other
    # privileged operations must be prefixed with 'sudo'.
    sudo = "sudo " if server.ssh_user != "root" else ""

    with Action(f"Executing {os.path.basename(setup_script)} script", server_name=server.name):
        ssh(
            server,
            f'{sudo}env CACHE_DIR="/mnt/{cache_volume_name}" bash -s  < {setup_script}',
            stacklevel=5,
        )

    with Action("Updating volumes permissions", server_name=server.name):
        for volume in server.volumes:
            volume_name = get_volume_name(volume.name)
            ssh(
                server,
                (f"'sudo chown ubuntu:ubuntu /mnt/{volume_name}'"),
                stacklevel=5,
            )

    with Action(f"Executing {os.path.basename(startup_script)} script", server_name=server.name):
        # When the SSH user is not root, drop 'sudo -u ubuntu' — we are already
        # the target user. When root (Hetzner), keep the original 'sudo -u ubuntu'.
        if server.ssh_user == "root":
            run_as = "sudo -u ubuntu "
        else:
            run_as = ""
        ssh(
            server,
            f"'{run_as}"
            f'CACHE_DIR="/mnt/{cache_volume_name}" '
            f'GITHUB_REPOSITORY="{github_repository}" '
            f'GITHUB_RUNNER_TOKEN="{GITHUB_RUNNER_TOKEN}" '
            f"GITHUB_RUNNER_GROUP=Default "
            f'GITHUB_RUNNER_LABELS="{runner_labels}" '
            f'GITHUB_RUNNER_NAME="{server.name}" '
            f'SERVER_NAME="{server.name}" '
            f'SERVER_ID="{server.id}" '
            f'SERVER_TYPE_NAME="{server.server_type}" '
            f'SERVER_LOCATION_NAME="{server.location}" '
            f"bash -s' < {startup_script}",
            stacklevel=5,
        )


def get_server_types(labels: list[str], default, label_prefix: str = "") -> list[str]:
    """Get server type names for the specified job.

    Returns plain type name strings so that each provider can interpret them
    via its own ``get_server_type`` method.
    """
    server_types: list[str] = []

    if label_prefix and not label_prefix.endswith("-"):
        label_prefix += "-"
    label_prefix += "type-"
    label_prefix = label_prefix.lower()

    for label in labels:
        label = label.lower()
        if label.startswith(label_prefix):
            server_type_name = label.split(label_prefix, 1)[-1].lower()
            if "-" in server_type_name:
                # skip composite label
                continue
            server_types.append(server_type_name)

    if not server_types:
        # default may be a plain string or a validated provider type object
        # (e.g. a hcloud ServerType stored back into config during startup).
        server_types = [default.name if hasattr(default, "name") else default]

    return server_types


def get_server_locations(
    labels: list[str], default: str | None = None, label_prefix: str = ""
) -> list[str | None]:
    """Get preferred server location names for the specified job.

    Returns plain location name strings so that each provider can interpret
    them via its own ``get_location`` method (e.g. Hetzner DC name ``nbg1``,
    AWS AZ ``us-east-1a``).

    By default, location is set to ``None`` to avoid server type mismatching
    the location as some server types are not available at some locations.
    """
    server_locations: list[str | None] = []

    if label_prefix and not label_prefix.endswith("-"):
        label_prefix += "-"
    label_prefix += "in-"
    label_prefix = label_prefix.lower()

    for label in labels:
        label = label.lower()
        if label.startswith(label_prefix):
            server_location_name = label.split(label_prefix, 1)[-1].lower()
            server_locations.append(server_location_name)

    if not server_locations:
        server_locations = [default]

    return server_locations


def get_server_image(
    provider: CloudProvider, labels: list[str], default, label_prefix: str = ""
):
    """Get preferred server image for the specified job."""
    server_image = None

    if label_prefix and not label_prefix.endswith("-"):
        label_prefix += "-"
    label_prefix += "image-"
    label_prefix = label_prefix.lower()

    for label in labels:
        label = label.lower()
        if label.startswith(label_prefix):
            try:
                server_image = provider.get_image(label.split(label_prefix, 1)[-1].lower())
            except ImageSpecFormatError:
                pass  # spec not in this provider's format; try next label

    if server_image is None:
        server_image = default

    return server_image


def parse_volume_size(size_str: str, default: int):
    """Convert size string to GB integer.

    Args:
        size_str: Size string (e.g. "20", "20GB")
        default: Default size in GB if parsing fails

    Returns:
        int: Size in GB
    """
    size = default
    size_str = size_str.lower()

    try:
        if size_str.endswith("gb"):
            size = int(size_str[:-2])  # assume GB by default
        else:
            size = int(size_str)
    except ValueError:
        pass

    return abs(size)


def get_server_volumes(labels: list[str], default: int = 10, label_prefix: str = ""):
    """Get volumes for the specified job.

    Args:
        labels: Set of job labels
        default: Default volume size in GB if not specified in label
        label_prefix: Optional prefix for volume labels

    Returns:
        list[Volume]: List of volumes with their names and sizes

    Example labels:
        volume-my_volume
        volume-my_volume-20
        volume-my_volume-20GB
    """
    volumes: dict[str, Volume] = {}

    if label_prefix and not label_prefix.endswith("-"):
        label_prefix += "-"
    label_prefix += "volume-"
    label_prefix = label_prefix.lower()

    for label in labels:
        label = label.lower()
        if label.startswith(label_prefix):
            # Extract volume name and optional size
            name, *size_parts = label.split(label_prefix, 1)[-1].split("-", 2)
            size = parse_volume_size(size_parts[0] if size_parts else "", default)
            volumes[name] = Volume(name=name, size=size)

    return list(volumes.values())


def get_setup_script(
    scripts: str, labels: list[str], default: str = "setup.sh", label_prefix: str = ""
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


def get_recycle_script(
    scripts: str, labels: list[str], default: str = "recycle.sh", label_prefix: str = ""
):
    """Get recycle script.

    Required when recycle_without_rebuild is enabled. Both label overrides
    (recycle-<name>) and the default recycle.sh must point to an existing script.
    """
    script = None

    if label_prefix and not label_prefix.endswith("-"):
        label_prefix += "-"
    label_prefix += "recycle-"
    label_prefix = label_prefix.lower()

    for label in labels:
        label = label.lower()
        if label.startswith(label_prefix):
            script = label.split(label_prefix, 1)[-1] + ".sh"

    if script is None:
        script = default

    return check_recycle_script(os.path.join(scripts, script))


def get_startup_script(
    scripts: str,
    provider: CloudProvider,
    server_type: ProviderServerType,
    labels: list[str],
    default: str = "startup-{arch}.sh",
    label_prefix: str = "",
):
    """Get startup script for the requested server type.

    The provider determines the CPU architecture so each implementation can
    apply its own type-name convention (Hetzner: ``cax`` prefix; AWS: ``t4g``
    prefix; etc.).
    """
    script = None
    default = default.format(arch=provider.get_server_arch(server_type))

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


def get_server_net_config(labels: list[str], label_prefix: str = ""):
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
    meta_label: dict[str, set[str]], labels: list[str], label_prefix: str = ""
):
    """Expand any meta labels."""
    expanded_labels = []
    label_prefix = label_prefix.lower()
    composite_labels = ["type-", "in-"]

    if label_prefix and not label_prefix.endswith("-"):
        label_prefix += "-"

    for label in labels:
        label = label.lower()
        expanded_labels.append(label)
        if label.startswith(label_prefix):
            raw_label = label.split(label_prefix, 1)[-1] if label_prefix else label
            if label in meta_label:
                expanded_labels += list(meta_label[label])
            for composite_label in composite_labels:
                if raw_label.startswith(composite_label):
                    composite_values = (
                        raw_label.split(composite_label, 1)[-1].lower().split("-")
                    )
                    for composite_value in composite_values:
                        expanded_labels.append(
                            f"{label_prefix}{composite_label}{composite_value}"
                        )

    return list(dict.fromkeys(expanded_labels))


def _loc_name(location) -> str | None:
    """Return the name string for a location regardless of whether it is a
    provider Location object (with a .name attribute) or already a plain string."""
    if location is None:
        return None
    return location.name if hasattr(location, "name") else str(location)


def _expand_locations(
    locations: list[str | None], provider: CloudProvider
) -> list[str | None]:
    """Expand each location in *locations* through the provider's
    ``expand_location_label`` and return a flat list.

    ``None`` entries (meaning "use provider default") are preserved as-is.
    """
    result = []
    for loc in locations:
        if loc is None:
            result.append(None)
        else:
            result.extend(provider.expand_location_label(loc))
    return result


def _resolve_provider(
    type_name: str, providers: list
) -> tuple[CloudProvider, ProviderServerType]:
    """Return (provider, ProviderServerType) for the first provider that supports the type.

    Tries each provider in order. Raises ServerTypeError if none recognises the type.
    """
    for p in providers:
        try:
            return p, p.get_server_type(type_name)
        except ServerTypeError:
            continue
    raise ServerTypeError(f"no configured provider supports server type '{type_name}'")


def raise_exception(exc):
    """Task to raise an exception using the worker pool."""
    raise exc


def get_job_labels(job):
    """Get job labels."""
    return list(dict.fromkeys(label.lower() for label in job.raw_data["labels"]))


def job_matches_labels(job_labels, with_label):
    """Check if job matches with_label criteria."""
    if with_label is None:
        return True

    for label in with_label:
        if not label.lower() in job_labels:
            return (False, label)

    return True


def filtered_run_jobs(
    workflow_runs: list[WorkflowRun], with_label: list[str], action: Action
):
    """Filter jobs to select only queued or in progress and match with_label criteria."""
    run_jobs = []
    for run in workflow_runs:
        try:
            jobs = list(run.jobs())
        except (GithubException, RequestsRetryError) as exc:
            # Log and skip API calls that fail (e.g., GitHub 502, timeout, retry errors)
            action.note(
                f"WARNING:Skipping workflow run {run.id}, failed to fetch jobs: {exc}"
            )
            continue

        for job in jobs:
            if job.status == "completed":
                continue
            if not (job.status == "in_progress" or job.status == "queued"):
                continue
            labels = get_job_labels(job)
            if job_matches_labels(labels, with_label) is True:
                run_jobs.append((run, job))
    return run_jobs


def filtered_servers(servers: list[RunnerServer], with_label: list[str]):
    """Filter servers to select only servers that match with_label criteria."""
    filtered_servers = []
    for server in servers:
        labels = server.labels
        if job_matches_labels(labels, with_label) is True:
            filtered_servers.append(server)
    return filtered_servers


def check_max_servers_for_label_reached(
    max_servers_for_label, job_labels, servers, futures=None
):
    """Check if we've reached any label-specific limits for the given job labels.

    Args:
        max_servers_for_label: List of tuples containing (label_set, max_count)
        job_labels: The labels of the job (already lowercase from get_job_labels)
        servers: List of existing servers (labels are already lowercase in RunnerServer objects)
        futures: List of futures for servers being created (optional)

    Returns:
        tuple: (bool, tuple) - (False if limit reached, (label_set, count, max_count) if limit reached)
    """
    if not max_servers_for_label:
        return False, None  # No label-specific limits configured

    # Check each configured label set
    for label_set, max_count in max_servers_for_label:
        # Check if job has all labels in this set
        if label_set.issubset(job_labels):
            # Count servers with these labels (including those being created)
            count = get_server_count_with_labels(servers, label_set, futures)

            # If we've reached the limit, don't scale up
            if count >= max_count:
                return True, (label_set, count, max_count)

    return False, None  # No limits reached


def get_server_bound_volumes(
    action: Action,
    provider: CloudProvider,
    server_image,
    server_location: Location,
    server_volumes: list[Volume],
    volumes: list[BoundVolume],
):
    """Get a list of bound volumes to be attached to the server."""
    server_bound_volumes: list[BoundVolume] = []

    for server_volume in server_volumes:
        found_existing_volume = False

        for volume in volumes:
            if volume.server is not None:
                # already attached to a server
                continue
            if volume.status != volume.STATUS_AVAILABLE:
                # volume is not available
                continue
            if server_location.name != volume.location.name:
                # volume is not in the same location
                continue
            if get_volume_name(volume.name) != server_volume.name:
                # volume name does not match
                continue
            if server_image.architecture != volume.labels.get(
                "github-hetzner-runner-arch"
            ):
                # volume architecture does not match
                continue
            if server_image.os_flavor != volume.labels.get("github-hetzner-runner-os"):
                # volume os flavor does not match
                continue
            if server_image.os_version != volume.labels.get(
                "github-hetzner-runner-os-version"
            ):
                # volume os version does not match
                continue
            # resize volume to the requested size if needed
            if volume.size < server_volume.size:
                action.note(
                    f"Resizing volume {volume.name} in {volume.location.name} from {volume.size}GB to {server_volume.size}GB"
                )
                volume.resize(server_volume.size).wait_until_finished()
                volume.size = server_volume.size

            action.note(
                f"Adding existing volume {volume.name} in {volume.location.name} that matches {server_volume.name}"
            )
            server_bound_volumes.append(volume)
            found_existing_volume = True
            break

        if found_existing_volume:
            continue

        action.note(
            f"Creating new volume {server_volume.name} in {server_location.name} with size {server_volume.size}GB"
        )

        new_pv = provider.create_volume(
            name=f"{server_volume.name}-{server_image.architecture}-{server_image.os_flavor}-{server_image.os_version}-{uid()}",
            size=server_volume.size,
            location=server_location,
            labels=provider.build_volume_labels(
                server_image.architecture,
                server_image.os_flavor,
                server_image.os_version,
            ),
            format="ext4",
            automount=False,
        )
        new_volume = new_pv._native

        assert (
            new_pv.status == "available"
        ), f"Newly created volume {new_volume.name} in {new_pv.location} is not available ({new_pv.status})"

        volumes.append(new_volume)

        action.note(
            f"Adding newly created volume {new_volume.name} in {new_pv.location} that matches {server_volume.name}"
        )
        server_bound_volumes.append(new_volume)

    return server_bound_volumes


def create_server(
    provider: CloudProvider,
    setup_worker_pool: ThreadPoolExecutor,
    labels: list[str],
    name: str,
    server_type: ProviderServerType,
    server_location,
    server_volumes: list[Volume],
    server_image,
    server_net_config,
    startup_script: str,
    setup_script: str,
    github_token: str,
    github_repository: str,
    ssh_keys: list,
    volumes: list,
    timeout: float = 60,
    canceled: threading.Event = None,
    semaphore: threading.Semaphore = None,
    active_attempt: list[int] = None,
    attempt: int = 0,
):
    """Create specified number of server instances."""
    start_time = time.time()

    while True:
        if semaphore is None or semaphore.acquire(timeout=1.0):
            try:
                if canceled is not None and canceled.is_set():
                    with Action(
                        f"Server creation for {name} with labels {labels} of {server_type} in {_loc_name(server_location) or 'None'} canceled",
                        level=logging.DEBUG,
                        stacklevel=3,
                        server_name=name,
                    ):
                        raise CanceledServerCreation("Server creation canceled")

                if active_attempt is not None:
                    # only proceed if this is our turn
                    if active_attempt[0] != attempt:
                        continue
                    # increment the attempt number so that if we fail
                    # another attempt can proceed next time
                    active_attempt[0] += 1

                server_labels = provider.build_server_labels(
                    labels, ssh_keys[0].name if ssh_keys else None
                )

                with Action(
                    f"Validating server {name} labels {labels} of {server_type} in {_loc_name(server_location) or 'None'}",
                    level=logging.DEBUG,
                    stacklevel=3,
                    server_name=name,
                ):
                    valid, error_msg = provider.validate_labels(server_labels)
                    if not valid:
                        raise ValueError(
                            f"invalid server labels {server_labels}: {error_msg}"
                        )

                with volumes_lock:
                    server_bound_volumes: list[BoundVolume] = []
                    try:
                        if server_volumes:
                            with Action(
                                f"Preparing volumes for server {name} with labels {labels} of {server_type} in {_loc_name(server_location) or 'None'}",
                                level=logging.DEBUG,
                                stacklevel=3,
                                server_name=name,
                            ) as action:
                                server_bound_volumes = get_server_bound_volumes(
                                    action,
                                    provider,
                                    server_image,
                                    server_location,
                                    server_volumes,
                                    volumes,
                                )

                        with Action(
                            f"Creating server {name} with labels {labels} of {server_type} in {_loc_name(server_location) or 'None'}",
                            stacklevel=3,
                            server_name=name,
                        ):
                            provider_server = provider.create_server(
                                name=name,
                                server_type=server_type,
                                location=server_location,
                                volumes=server_bound_volumes,
                                automount=False,
                                image=server_image,
                                ssh_keys=ssh_keys,
                                labels=server_labels,
                                public_net=server_net_config,
                            )

                    except Exception as e:
                        for volume in server_bound_volumes:
                            # mark server bound volume as not attached to any server
                            volume.server = None
                        raise

                metrics.record_server_creation(
                    server_type=server_type.name,
                    location=_loc_name(server_location),
                    creation_time=time.time() - start_time,
                )

                with Action(
                    f"Successfully created server {name} with labels {labels} of {server_type} in {_loc_name(server_location) or 'None'}, canceling other attempts",
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
        server=provider_server,
        setup_script=setup_script,
        startup_script=startup_script,
        github_token=github_token,
        github_repository=github_repository,
        runner_labels=",".join(labels),
        timeout=timeout,
    )


def recycle_server(
    server_name: str,
    server_volumes: list[Volume],
    provider: CloudProvider,
    setup_worker_pool: ThreadPoolExecutor,
    labels: list[str],
    name: str,
    server_image,
    startup_script: str,
    setup_script: str,
    github_token: str,
    github_repository: str,
    ssh_key: SSHKey,
    timeout=60,
    without_rebuild: bool = False,
    recycle_script: str = None,
):
    """Repurpose a recycled server as an active runner.

    When recycling a server, we merge existing labels with the new runner labels
    to preserve any critical labels. The recycle timestamp label is removed since
    the server is now active again.

    If without_rebuild is True, the server image is not rebuilt. Instead the server
    is powered on and recycle_script is run in place of setup_script before startup.
    """
    with Action(f"Get recyclable server {server_name}", server_name=name):
        provider_server = provider.get_server(name=server_name)

    # Start with existing labels and merge in the new runner labels.
    # This preserves any labels that aren't explicitly being replaced.
    merged_labels = dict(provider_server.labels)
    runner_labels = provider.build_server_labels(
        labels, ssh_key.name if ssh_key is not None else None
    )
    merged_labels.update(runner_labels)

    # Remove recycle timestamp label since server is now active.
    merged_labels.pop(recycle_timestamp_label, None)

    with Action(f"Validating server {name} labels", server_name=name):
        valid, error_msg = provider.validate_labels(merged_labels)
        if not valid:
            raise ValueError(f"invalid server labels {merged_labels}: {error_msg}")

    with Action(f"Recycling server {server_name} to make {name}", server_name=name):
        provider.update_server(provider_server, name=name, labels=merged_labels)

    if without_rebuild:
        with Action(
            f"Powering on recycled server {provider_server.name} without rebuild",
            server_name=name,
        ):
            provider.power_on_server(provider_server, timeout=timeout)
        setup_script = recycle_script
    else:
        with Action(
            f"Rebuilding recycled server {provider_server.name} image", server_name=name
        ):
            provider.rebuild_server(provider_server, server_image)

    setup_worker_pool.submit(
        server_setup,
        server=provider_server,
        setup_script=setup_script,
        startup_script=startup_script,
        github_token=github_token,
        github_repository=github_repository,
        runner_labels=",".join(labels),
        timeout=timeout,
    )


def count_available_runners(runners: list[SelfHostedActionsRunner], labels: list[str]):
    """Return number of available runners that match labels (subset)."""
    count = 0
    label_set = set(labels)

    for runner in runners:
        if runner.status == "online":
            runner_labels = set([label["name"].lower() for label in runner.labels])
            if label_set.issubset(runner_labels):
                if not runner.busy:
                    count += 1

    return count


def count_available(servers: list[RunnerServer], labels: list[str]):
    """Return number of available servers that match labels (subset)."""
    count = 0
    label_set = set(labels)

    for runner_server in servers:
        if runner_server.server_status == CloudProvider.STATUS_OFF:
            continue
        if label_set.issubset(runner_server.labels):
            if runner_server.runner_status in ("initializing", "ready"):
                count += 1

    return count


def count_present(servers: list[RunnerServer], labels: list[str]):
    """Return number of present servers that match labels (subset)."""
    count = 0
    label_set = set(labels)

    for runner_server in servers:
        if runner_server.server_status == CloudProvider.STATUS_OFF:
            continue
        if label_set.issubset(runner_server.labels):
            count += 1

    return count


def max_servers_in_workflow_run_reached(
    run_id,
    servers: list[BoundServer],
    max_servers_in_workflow_run: int,
    server_name: str = None,
    futures: list[Future] = None,
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

        # Count servers being created for this workflow run
        if futures:
            servers_in_run_count = len(servers_in_run) + sum(
                1
                for future in futures
                if hasattr(future, "server_name")
                and future.server_name.startswith(run_server_name_prefix)
            )
        else:
            servers_in_run_count = len(servers_in_run)

        if servers_in_run_count >= max_servers_in_workflow_run:
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
    server_type: str,
    server_location: str | None,
    server_volumes: list[Volume],
    server_net_config: ServerCreatePublicNetwork,
    ssh_key: SSHKey,
):
    """Check if a recyclable server matches for the specified
    server type, location, and ssh key."""
    if server.server_type != server_type:
        return False

    if server_location and server.server_location != server_location:
        return False

    native = server.server._native

    if server_net_config.enable_ipv4 and native.public_net.ipv4 is None:
        return False

    if not server_net_config.enable_ipv4 and native.public_net.ipv4 is not None:
        return False

    if server_net_config.enable_ipv6 and native.public_net.ipv6 is None:
        return False

    if not server_net_config.enable_ipv6 and native.public_net.ipv6 is not None:
        return False

    if set([v.name for v in server_volumes]) != set(
        [v.name for v in server.server_volumes]
    ):
        return False

    if ssh_key is None:
        return False
    return ssh_key.name == native.labels.get(server_ssh_key_label)


def set_future_attributes(
    future, name, server_type, server_location, server_volumes, labels,
    provider_name=None, counts_toward_capacity=True,
):
    """Set common attributes on a future object.

    Args:
        future: The future object to set attributes on
        name: The server name
        server_type: The server type
        server_location: The server location
        labels: The server labels
        provider_name: Name of the provider that will create this server.
        counts_toward_capacity: False for synthetic raise_exception futures
            that represent a rejected attempt rather than a real server.
    """
    future.server_name = name
    future.server_type = server_type
    future.server_location = server_location
    future.server_volumes = server_volumes
    future.server_labels = labels
    future.provider_name = provider_name
    future.counts_toward_capacity = counts_toward_capacity


def get_total_server_count(servers, futures=None):
    """Get the total count of servers including those being created.

    Args:
        servers: List of existing servers
        futures: List of futures for servers being created (optional)

    Returns:
        int: Total count of servers
    """
    count = len(servers)
    if futures:
        count += sum(
            1 for f in futures
            if getattr(f, "counts_toward_capacity", True)
        )
    return count


def get_provider_server_count(servers, futures, provider_name: str) -> int:
    """Count servers and pending futures belonging to a specific provider."""
    count = sum(1 for s in servers if s.provider_name == provider_name)
    if futures:
        count += sum(
            1 for f in futures
            if getattr(f, "provider_name", None) == provider_name
            and getattr(f, "counts_toward_capacity", True)
        )
    return count


def get_server_count_with_labels(servers, label_set, futures=None):
    """Get the count of servers with specific labels, including those being created.

    Args:
        servers: List of existing servers
        label_set: Set of labels to check for
        futures: List of futures for servers being created (optional)

    Returns:
        int: Count of servers with the specified labels
    """
    count = sum(1 for server in servers if label_set.issubset(server.labels))

    if futures:
        count += sum(
            1
            for future in futures
            if hasattr(future, "server_labels")
            and label_set.issubset(future.server_labels)
        )

    return count


def scale_up(
    terminate: threading.Event,
    mailbox: queue.Queue,
    worker_pool: ThreadPoolExecutor,
    ssh_keys: dict[str, list],
    config: Config,
    providers: list[CloudProvider] = None,
):
    """Scale up service."""
    github_token: str = config.github_token
    github_repository: str = config.github_repository
    default_server_type: ServerType = config.default_server_type
    default_volume_size: int = config.default_volume_size
    default_volume_location: str | None = (
        config.default_volume_location.name if config.default_volume_location else None
    )
    default_location: str | None = (
        config.default_location.name if config.default_location else None
    )
    default_image = config.default_image
    interval_period: int = config.scale_up_interval
    max_servers: int = config.max_runners
    max_servers_for_label: list[tuple[set[str], int]] = config.max_runners_for_label
    max_servers_in_workflow_run: int = config.max_runners_in_workflow_run
    max_server_ready_time: int = config.max_server_ready_time
    debug: bool = config.debug
    standby_runners: list[StandbyRunner] = config.standby_runners
    recycle: bool = config.recycle
    recycle_without_rebuild: bool = config.recycle_without_rebuild
    with_label: list[str] = config.with_label
    label_prefix: str = config.label_prefix
    meta_label: dict[str, set[str]] = config.meta_label
    scripts: str = config.scripts
    if not hasattr(config, "server_prices") or config.server_prices is None:
        config.server_prices = {}
    interval: int = -1

    if providers is None:
        from .providers.hetzner.provider import HetznerCloudProvider
        providers = [HetznerCloudProvider(token=config.hetzner_token)]

    def create_runner_server(
        name: str,
        labels: list[str],
        setup_worker_pool: ThreadPoolExecutor,
        futures: list[Future],
        servers: list[RunnerServer],
        volumes: list[BoundVolume],
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
        server_volumes = get_server_volumes(
            labels=labels, default=default_volume_size, label_prefix=label_prefix
        )
        if server_volumes:
            if server_locations == [None]:
                server_locations = [
                    default_volume_location,
                ]
        setup_script = get_setup_script(
            scripts=scripts,
            labels=labels,
            label_prefix=label_prefix,
        )
        server_net_config = get_server_net_config(
            labels=labels, label_prefix=label_prefix
        )

        # Resolve provider and validate type for each requested server type.
        # get_server_image is called per type since image specs are provider-specific.
        resolved = []
        for type_name in server_types:
            try:
                rp, vt = _resolve_provider(type_name, providers)
            except ServerTypeError:
                continue
            provider_default_image = (
                rp.default_image if rp.default_image is not None else default_image
            )
            resolved.append(
                (
                    type_name,
                    rp,
                    vt,
                    get_server_image(
                        provider=rp,
                        labels=labels,
                        default=provider_default_image,
                        label_prefix=label_prefix,
                    ),
                )
            )

        if recycle:
            for type_name, resolved_provider, validated_type, server_image in resolved:
                if not resolved_provider.supports_recycling:
                    continue
                provider_ssh_keys = ssh_keys.get(resolved_provider.name, [])
                for loc_name in _expand_locations(server_locations, resolved_provider):
                    effective_loc = loc_name if loc_name is not None else resolved_provider.default_location
                    server_location = resolved_provider.get_location(effective_loc)
                    startup_script = get_startup_script(
                        scripts=scripts,
                        provider=resolved_provider,
                        server_type=validated_type,
                        labels=labels,
                        label_prefix=label_prefix,
                    )

                    with Action(
                        f"Trying to create recycled server {name} of {type_name} in {loc_name or 'None'} with volumes {server_volumes}",
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
                                server_type=type_name,
                                server_location=(
                                    _loc_name(server_location)
                                ),
                                server_volumes=server_volumes,
                                server_net_config=server_net_config,
                                ssh_key=provider_ssh_keys[0] if provider_ssh_keys else None,
                            ):
                                recycle_script = get_recycle_script(
                                    scripts=scripts,
                                    labels=labels,
                                    label_prefix=label_prefix,
                                ) if recycle_without_rebuild else None
                                future = worker_pool.submit(
                                    recycle_server,
                                    server_name=server.name,
                                    server_volumes=server.server_volumes,
                                    provider=resolved_provider,
                                    setup_worker_pool=setup_worker_pool,
                                    labels=labels,
                                    name=name,
                                    server_image=server_image,
                                    startup_script=startup_script,
                                    setup_script=setup_script,
                                    github_token=github_token,
                                    github_repository=github_repository,
                                    ssh_key=provider_ssh_keys[0] if provider_ssh_keys else None,
                                    timeout=max_server_ready_time,
                                    without_rebuild=recycle_without_rebuild,
                                    recycle_script=recycle_script,
                                )
                                set_future_attributes(
                                    future,
                                    name,
                                    validated_type,
                                    server_location,
                                    server_volumes,
                                    labels,
                                    provider_name=resolved_provider.name,
                                )
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

        for type_name, resolved_provider, validated_type, server_image in resolved:
            if server_volumes and not resolved_provider.supports_volumes:
                with Action(
                    f"Skipping provider {resolved_provider.name} for {name}: job requires volumes but provider does not support them",
                    stacklevel=3,
                    level=logging.DEBUG,
                    server_name=name,
                ):
                    pass
                continue
            provider_ssh_keys = ssh_keys.get(resolved_provider.name, [])
            for loc_name in _expand_locations(server_locations, resolved_provider):
                effective_loc = loc_name if loc_name is not None else resolved_provider.default_location
                try:
                    server_location = resolved_provider.get_location(effective_loc)
                except LocationError:
                    with Action(
                        f"Skipping location {effective_loc!r} for provider {resolved_provider.name}: location not recognised",
                        stacklevel=3,
                        level=logging.DEBUG,
                        server_name=name,
                    ):
                        pass
                    continue
                # pre-increment the attempt number that starts from 0
                create_server_attempt += 1

                startup_script = get_startup_script(
                    scripts=scripts,
                    provider=resolved_provider,
                    server_type=validated_type,
                    labels=labels,
                    label_prefix=label_prefix,
                )

                with Action(
                    f"Trying to create new server {name} of {type_name} in {loc_name or 'None'} with volumes {server_volumes}",
                    stacklevel=3,
                    level=logging.DEBUG,
                    server_name=name,
                ):
                    pass

                # Global cap — skipped for this provider if it has its own cap,
                # since the per-provider check below is the authoritative limit.
                # Servers from providers that have their own cap are excluded from
                # the global count so they don't crowd out uncapped providers.
                if max_servers is not None and resolved_provider.max_runners is None:
                    _capped = {p.name for p in providers if p.max_runners is not None}
                    _gs = [s for s in servers if getattr(s, "provider_name", None) not in _capped]
                    _gf = [f for f in (futures or []) if getattr(f, "provider_name", None) not in _capped]
                    total_servers_count = get_total_server_count(_gs, _gf)
                    if total_servers_count >= max_servers:
                        with Action(
                            f"Maximum number of servers {max_servers} has been reached",
                            stacklevel=3,
                            server_name=name,
                        ):
                            future = worker_pool.submit(
                                raise_exception,
                                exc=MaxNumberOfServersReached(
                                    f"maximum number of servers reached {total_servers_count}/{max_servers}"
                                ),
                            )
                            set_future_attributes(
                                future,
                                name,
                                validated_type,
                                server_location,
                                server_volumes,
                                labels,
                                provider_name=resolved_provider.name,
                                counts_toward_capacity=False,
                            )
                            futures.append(future)
                            raise StopIteration("maximum number of servers reached")

                # Check per-provider runner cap
                provider_max = resolved_provider.max_runners
                if provider_max is not None:
                    provider_count = get_provider_server_count(
                        servers, futures, resolved_provider.name
                    )
                    if provider_count >= provider_max:
                        with Action(
                            f"Maximum number of servers {provider_max} for provider {resolved_provider.name} has been reached",
                            stacklevel=3,
                            server_name=name,
                        ):
                            future = worker_pool.submit(
                                raise_exception,
                                exc=MaxNumberOfServersReached(
                                    f"maximum number of servers for provider {resolved_provider.name} reached {provider_count}/{provider_max}"
                                ),
                            )
                            set_future_attributes(
                                future,
                                name,
                                validated_type,
                                server_location,
                                server_volumes,
                                labels,
                                provider_name=resolved_provider.name,
                                counts_toward_capacity=False,
                            )
                            futures.append(future)
                            continue

                # Check label-specific limits
                if max_servers_for_label:
                    limit_reached, limit_info = check_max_servers_for_label_reached(
                        max_servers_for_label, labels, servers, futures
                    )
                    if limit_reached:
                        label_set, count, max_count = limit_info
                        with Action(
                            f"Maximum number of servers {max_count} for labels {label_set} reached",
                            stacklevel=3,
                            server_name=name,
                        ):
                            future = worker_pool.submit(
                                raise_exception,
                                exc=MaxNumberOfServersForLabelReached(
                                    f"Maximum number of servers for labels {label_set} reached {count}/{max_count}"
                                ),
                            )
                            set_future_attributes(
                                future,
                                name,
                                validated_type,
                                server_location,
                                server_volumes,
                                labels,
                                provider_name=resolved_provider.name,
                                counts_toward_capacity=False,
                            )
                            futures.append(future)
                            return

                future = worker_pool.submit(
                    create_server,
                    provider=resolved_provider,
                    setup_worker_pool=setup_worker_pool,
                    labels=labels,
                    name=name,
                    server_type=validated_type,
                    server_location=server_location,
                    server_volumes=server_volumes,
                    server_image=server_image,
                    server_net_config=server_net_config,
                    setup_script=setup_script,
                    startup_script=startup_script,
                    github_token=github_token,
                    github_repository=github_repository,
                    ssh_keys=provider_ssh_keys,
                    volumes=volumes,
                    timeout=max_server_ready_time,
                    canceled=create_server_canceled,
                    semaphore=create_server_semaphore,
                    active_attempt=create_server_active_attempt,
                    attempt=create_server_attempt,
                )
                set_future_attributes(
                    future, name, validated_type, server_location, server_volumes, labels,
                    provider_name=resolved_provider.name,
                )
                futures.append(future)

    with Action("Logging in to GitHub"):
        github = Github(auth=Auth.Token(github_token), per_page=100)

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
                runs_jobs = []
                servers = []
                runners = []

                with Action(
                    "Getting workflow runs", level=logging.DEBUG, interval=interval
                ) as action:
                    queued_runs = list(repo.get_workflow_runs(status="queued"))
                    in_progress_runs = list(
                        repo.get_workflow_runs(status="in_progress")
                    )
                    # Update job metrics using only queued or in progress runs that match with_label criteria
                    runs_jobs = filtered_run_jobs(
                        queued_runs + in_progress_runs, with_label, action=action
                    )
                    metrics.update_jobs(runs_jobs)
                    # For job processing, we'll use both queued and in_progress runs
                    # to ensure stolen runner detection works for all cases
                    workflow_runs = queued_runs + in_progress_runs

                with Action(
                    "Getting list of servers", level=logging.DEBUG, interval=interval
                ):
                    servers = filtered_servers(
                        [
                            RunnerServer(
                                name=ps.name,
                                server_status=ps.status,
                                labels=p.get_runner_labels(ps),
                                server_type=ps.server_type,
                                server_location=ps.location,
                                server_volumes=[
                                    Volume(
                                        name=get_volume_name(v.name),
                                        size=v.size,
                                    )
                                    for v in ps.volumes
                                ],
                                server=ps,
                                provider_name=p.name,
                            )
                            for p in providers
                            for ps in p.list_runner_servers()
                        ],
                        with_label,
                    )

                with Action(
                    "Getting list of available volumes",
                    level=logging.DEBUG,
                    interval=interval,
                ):
                    # Fan out across all providers; skip those that don't support volumes.
                    all_volumes = []
                    for _p in providers:
                        try:
                            all_volumes.extend(
                                _p.list_volumes(
                                    label_selector="github-hetzner-runner-volume=active"
                                )
                            )
                        except NotImplementedError:
                            pass
                    # Filter to only available volumes for server attachment logic.
                    # Pass native objects so get_server_bound_volumes can resize/attach.
                    volumes = [
                        v._native for v in all_volumes if v.status == "available"
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
                    filtered_runners = []
                    for runner in runners:
                        for server in servers:
                            if runner.name.startswith(server.name):
                                if runner.status == "online":
                                    server.runner_status = "busy" if runner.busy else "ready"
                                filtered_runners.append(runner)
                    runners = filtered_runners

                # Lazily fetch prices for any provider that is missing them
                for _p in providers:
                    if _p.name not in config.server_prices:
                        try:
                            _prices = _p.get_prices()
                            if _prices:
                                config.server_prices[_p.name] = {
                                    "prices": _prices,
                                    "currency": _p.currency,
                                }
                        except Exception as _e:
                            logging.debug(f"Could not fetch prices for {_p.name}: {_e}")

                # Update all metrics
                metrics.update_servers(servers, config.server_prices)
                metrics.update_runners(
                    runners,
                    github_repository,
                )
                metrics.update_pools(
                    servers,
                    standby_runners,
                    count_available_fn=count_available,
                )
                metrics.update_volumes(all_volumes)
                metrics.update_system_health()

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
                                    futures=futures,
                                ):
                                    continue

                            for job_run, job in runs_jobs:
                                if job_run.id != run.id:
                                    continue
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
                                _expanded = expand_meta_label(
                                    meta_label=meta_label, labels=labels
                                )
                                _type_names = get_server_types(
                                    _expanded, default_server_type, label_prefix
                                )
                                _primary_type = (
                                    _type_names[0] if _type_names else "unknown"
                                )
                                server_name = f"{server_name_prefix}{job.run_id}-{job.id}-{_primary_type}"

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
                                        # skip jobs running on external runners (not managed by this service)
                                        if not job.raw_data["runner_name"].startswith(
                                            runner_name_prefix
                                        ):
                                            continue

                                        # check if the job is running on a standby runner
                                        if job.raw_data["runner_name"].startswith(
                                            standby_runner_name_prefix
                                        ):
                                            continue

                                        # If the runner's own server is gone this is a
                                        # race condition (runner finished, scale_down
                                        # cleaned it up, GitHub API still shows in_progress)
                                        # or an end-of-life termination — not a theft.
                                        # Only proceed if the runner's server still exists.
                                        _runner_server_names = {s.name for s in servers}
                                        if job.raw_data["runner_name"] not in _runner_server_names:
                                            continue

                                        # Only replenish if standbys are configured.
                                        if not standby_runners:
                                            continue

                                        with Action(
                                            f"Finding labels for the job from which {job} stole the runner",
                                            server_name=server_name,
                                            interval=interval,
                                        ):
                                            labels = list(
                                                dict.fromkeys(
                                                    label["name"].lower()
                                                    for label in repo.get_self_hosted_runner(
                                                        job.raw_data["runner_id"]
                                                    ).labels
                                                )
                                            )

                                    if max_servers_in_workflow_run is not None:
                                        if max_servers_in_workflow_run_reached(
                                            run_id=run.id,
                                            servers=servers,
                                            max_servers_in_workflow_run=max_servers_in_workflow_run,
                                            server_name=server_name,
                                            futures=futures,
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
                                                f"Found at least one potentially available runner for {job}",
                                                server_name=server_name,
                                                interval=interval,
                                            ):
                                                continue
                                    try:
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
                                                volumes=volumes,
                                            )
                                    except StopIteration:
                                        raise
                                    except Exception:
                                        pass
                    except StopIteration:
                        pass
                    except Exception:
                        pass

                if standby_runners:
                    try:
                        with Action("Checking standby runner pool", interval=interval):
                            for standby_runner in standby_runners:
                                labels = list(
                                    dict.fromkeys(
                                        standby_runner.labels + (with_label or [])
                                    )
                                )
                                replenish_immediately = (
                                    standby_runner.replenish_immediately
                                )
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
                                                    volumes=volumes,
                                                )
                                        except StopIteration:
                                            raise
                                        except Exception:
                                            break
                    except StopIteration:
                        pass
                    except Exception:
                        pass

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
                                    server_type=getattr(future.server_type, "name", None) or str(future.server_type or ""),
                                    server_location=getattr(future.server_location, "name", None) or str(future.server_location or ""),
                                    server_volumes=future.server_volumes,
                                    server_status=future.server_volumes,
                                    labels=set(future.server_labels),
                                    provider_name=getattr(future, "provider_name", None),
                                )
                            )

                        except CanceledServerCreation:
                            pass

                        except Exception as exc:
                            send_failure = False

                            error_type = "error"
                            error_details = {
                                "error": str(exc),
                                "server_type": future.server_type.name,
                                "location": (
                                    _loc_name(future.server_location) or ""
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
                                server_location=(
                                    _loc_name(future.server_location) or ""
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
                                # Don't re-raise expected fallback errors — let
                                # the loop continue so later futures for the same
                                # server (e.g. a different provider) can succeed
                                # and be added to servers.
                            else:
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
                        server_location=None,
                        error_details=None,
                    )

            with Action(
                f"Sleeping until next interval {interval_period}s",
                level=logging.DEBUG,
                interval=interval,
            ):
                time.sleep(interval_period)
