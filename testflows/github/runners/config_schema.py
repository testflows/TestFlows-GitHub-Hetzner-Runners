# Copyright 2023-2025 Katteli Inc.
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
"""Config schema dataclasses.

Layer-1 leaf: imports only stdlib, hcloud domain types, the vendored
ordered_set, the logger default, and the pure argtypes validators. It must NOT
import the ``config`` package, ``args``, or ``providers`` — that keeps providers
free to import their config dataclasses from here without a cycle.
"""
import os
import sys
import dataclasses
from dataclasses import dataclass

from hcloud.images.domain import Image
from hcloud.server_types.domain import ServerType
from hcloud.locations.domain import Location

from .logger import default_format as logger_format
from .ordered_set import OrderedSet as set
from .argtypes import image_type as image, server_type

current_dir = os.path.dirname(__file__)


@dataclass
class standby_runner:
    labels: list[str]
    count: int = 1
    replenish_immediately: bool = True


@dataclass
class provider_defaults:
    """Generic provider defaults structure."""

    image: str = None
    server_type: str = None
    location: str = None
    # Root/boot disk of the runner server (AWS EBS, Scaleway SBS boot); the
    # default for the disk- label. Not the caching volume.
    disk_size: int = None
    disk_type: str = None  # root disk type, e.g. AWS EBS "gp3"
    # Caching volume attached via the volume- label (Hetzner only).
    volume_size: int = None
    volume_location: str = None


@dataclass
class hetzner_provider:
    """Hetzner Cloud provider configuration."""

    token: str = None
    max_runners: int = None
    end_of_life: int = None
    recycle: bool = None
    recycle_grace_period: int = None
    recycle_with_rebuild: bool = False
    defaults: provider_defaults = dataclasses.field(
        default_factory=lambda: provider_defaults(
            image="x86:system:ubuntu-22.04",
            server_type="cx23",
            location=None,
            volume_size=10,
            volume_location="nbg1",
        )
    )


@dataclass
class aws_provider:
    """AWS provider configuration."""

    access_key_id: str = None
    secret_access_key: str = None
    security_group: str = None
    subnets: list[str] = None
    key_name: str = None
    ssh_user: str = "ubuntu"
    max_runners: int = None
    end_of_life: int = None
    recycle: bool = None
    recycle_grace_period: int = None
    defaults: provider_defaults = dataclasses.field(
        default_factory=lambda: provider_defaults(
            image="ubuntu-22.04",
            server_type="t3.medium",
            location="us-east-1a",
            disk_size=20,
            disk_type="gp3",
        )
    )


@dataclass
class scaleway_provider:
    """Scaleway provider configuration.

    Instance types are configured in the canonical dot-form (e.g. ``dev1.s``),
    not Scaleway's native dash-form (``DEV1-S``), because the runner label
    grammar reserves ``-`` as a separator.
    """

    access_key: str = None
    secret_key: str = None
    project_id: str = None
    organization_id: str = None
    ssh_user: str = "root"
    max_runners: int = None
    end_of_life: int = None
    recycle: bool = None
    recycle_grace_period: int = None
    defaults: provider_defaults = dataclasses.field(
        default_factory=lambda: provider_defaults(
            image="ubuntu_jammy",
            server_type="dev1.m",
            location="fr-par-1",
            disk_size=20,
        )
    )


@dataclass
class dedicated_static_ssh:
    user: str = "root"
    port: int = 22
    key: str = None


@dataclass
class dedicated_static_group:
    labels: list[str]
    hosts: list[str]
    ssh: dedicated_static_ssh = None


@dataclass
class dedicated_static_provider:
    """Static dedicated-host provider configuration."""

    ssh_defaults: dedicated_static_ssh = dataclasses.field(
        default_factory=dedicated_static_ssh
    )
    claim_ttl_minutes: int = 360
    groups: dict[str, dedicated_static_group] = dataclasses.field(default_factory=dict)


@dataclass
class provider_list:
    """Multi-provider configuration."""

    # Field order is the provider precedence used when a job carries no type/
    # location label: the first *configured* provider seeds the default server
    # type/location/volume. Scaleway is ahead of AWS deliberately.
    hetzner: hetzner_provider = None
    scaleway: scaleway_provider = None
    aws: aws_provider = None
    dedicated_static: dedicated_static_provider = None


@dataclass
class deploy_:
    server_type: ServerType = server_type("cx23")
    image: Image = image("x86:system:ubuntu-22.04")
    location: Location = None
    setup_script: str = os.path.join(current_dir, "scripts", "deploy", "setup.sh")


@dataclass
class cloud:
    provider: str = "hetzner"
    server_name: str = "tfs-github-runners-service"
    host: str = None
    # SSH login user for a --host direct connection. None lets ssh resolve it
    # (e.g. from ~/.ssh/config for a host alias) and falls back to the
    # configured provider's ssh_user when a provider is configured.
    ssh_user: str = None
    deploy: deploy_ = dataclasses.field(default_factory=deploy_)


@dataclass
class Config:
    """Program configuration class."""

    github_token: str = os.getenv("GITHUB_TOKEN")
    github_repository: str = os.getenv("GITHUB_REPOSITORY")

    # Multi-provider configuration
    providers: provider_list = dataclasses.field(default_factory=provider_list)

    # CLI-only: restricts provider_factory to this subset of configured
    # providers (--provider). None means "everything configured" — unchanged
    # behavior. Not settable from the config file; see parse.py.
    enabled_providers: list[str] = None

    # Provider-agnostic settings
    ssh_key: str = os.path.expanduser("~/.ssh/id_rsa.pub")
    additional_ssh_keys: list[str] = None
    with_label: list[str] = None
    label_prefix: str = ""
    meta_label: dict[str, list[str]] = None
    recycle: bool = True
    recycle_grace_period: int = 1200
    end_of_life: int = 50
    delete_random: bool = False
    max_runners: int = 10
    max_runners_for_label: list[tuple[set[str], int]] = None
    max_runners_in_workflow_run: int = None
    workers: int = 10
    scripts: str = os.path.join(current_dir, "scripts")
    max_powered_off_time: int = 60
    max_unused_runner_time: int = 180
    max_runner_registration_time: int = 180
    max_server_ready_time: int = 180
    scale_up_interval: int = 60
    scale_down_interval: int = 60
    metrics_port: int = 9090
    metrics_host: str = "127.0.0.1"
    dashboard_port: int = 8090
    dashboard_host: str = "127.0.0.1"
    debug: bool = False

    # Service deployment configuration
    cloud: cloud = dataclasses.field(default_factory=cloud)
    standby_runners: list[standby_runner] = None

    # Internal/special
    service_mode: bool = False
    embedded_mode: bool = False
    logger_config: dict = None
    logger_format: dict = None
    server_prices: dict[str, dict[str, float]] = None
    config_file: str = None

    @property
    def hetzner_token(self):
        """Hetzner API token, derived from providers.hetzner.token.

        Read-only accessor for Hetzner-specific internal readers (images.py,
        volumes.py, servers.py, the systemd HETZNER_TOKEN env, ...). The token's
        sole source of truth is providers.hetzner.token; there is no top-level
        token field and it is never read from the environment.
        """
        if self.providers is not None and self.providers.hetzner is not None:
            return self.providers.hetzner.token
        return None

    def __post_init__(self):
        if self.with_label is None:
            self.with_label = ["self-hosted"]

        if self.standby_runners is None:
            self.standby_runners = []

        if self.additional_ssh_keys is None:
            self.additional_ssh_keys = []

        if self.meta_label is None:
            self.meta_label = {}

        if self.max_runners_for_label is None:
            self.max_runners_for_label = []

        if self.logger_format is None:
            self.logger_format = logger_format

        if self.providers is None:
            self.providers = provider_list()


    def check(self, *parameters):
        """Check mandatory configuration parameters."""

        if not parameters:
            for name in ("github_token", "github_repository"):
                if not getattr(self, name):
                    print(
                        f"argument error: --{name.lower().replace('_','-')} is not defined",
                        file=sys.stderr,
                    )
                    sys.exit(1)
            has_hetzner = self.providers.hetzner is not None and bool(
                self.providers.hetzner.token
            )
            has_aws = (
                self.providers.aws is not None
                and bool(self.providers.aws.access_key_id)
                and bool(self.providers.aws.secret_access_key)
            )
            has_scaleway = (
                self.providers.scaleway is not None
                and bool(self.providers.scaleway.access_key)
                and bool(self.providers.scaleway.secret_key)
                and bool(self.providers.scaleway.project_id)
            )
            has_dedicated_static = (
                self.providers.dedicated_static is not None
                and bool(self.providers.dedicated_static.groups)
            )
            completeness = {
                "hetzner": has_hetzner,
                "aws": has_aws,
                "scaleway": has_scaleway,
                "dedicated_static": has_dedicated_static,
            }
            if self.enabled_providers is not None:
                incomplete = [
                    name for name in self.enabled_providers if not completeness.get(name)
                ]
                if incomplete:
                    print(
                        "argument error: --provider requested "
                        f"{', '.join(incomplete)}, but "
                        f"{'each is' if len(incomplete) > 1 else 'it is'} "
                        "missing required credentials; add or complete "
                        + ", ".join(f"providers.{name}" for name in incomplete)
                        + " in the config file, or drop "
                        + ("them" if len(incomplete) > 1 else "it")
                        + " from --provider",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                return
            if not (
                has_hetzner or has_aws or has_scaleway or has_dedicated_static
            ):
                print(
                    "argument error: no cloud provider configured; "
                    "set --hetzner-token or add providers.hetzner.token / "
                    "providers.aws / providers.scaleway credentials / "
                    "providers.dedicated_static.groups to config file",
                    file=sys.stderr,
                )
                sys.exit(1)
            return

        for name in parameters:
            value = getattr(self, name)
            if value:
                continue
            print(
                f"argument error: --{name.lower().replace('_','-')} is not defined",
                file=sys.stderr,
            )
            sys.exit(1)
