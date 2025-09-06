import os
import re
import sys
import yaml
import logging
import logging.config
import dataclasses

from dataclasses import dataclass

import testflows.runners.args as args

from ..logger import default_format as logger_format
from .. import errors

current_dir = os.path.dirname(__file__)

# add support for parsing ${ENV_VAR} in config
env_pattern = re.compile(r".*?\${(.*?)}.*?")

default_user_config = os.path.expanduser("~/.tfs-runners/config.yaml")


def env_constructor(loader, node):
    value = loader.construct_scalar(node)
    for group in env_pattern.findall(value):
        env_value = os.environ.get(group)
        if env_value is None:
            assert (
                False
            ), f"environment variable ${group} used in the config is not defined"
        value = value.replace(f"${{{group}}}", env_value)
    return value


yaml.add_implicit_resolver("!path", env_pattern, None, yaml.SafeLoader)
yaml.add_constructor("!path", env_constructor, yaml.SafeLoader)


path = args.path_type
count = args.count_type
end_of_life = args.end_of_life_type
meta_label_type = args.meta_label_type


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
    volume_size: int = 20
    volume_location: str = None
    volume_type: str = None  # Optional, provider-specific


@dataclass
class hetzner_provider:
    """Hetzner Cloud provider configuration."""

    token: str = None
    defaults: provider_defaults = dataclasses.field(
        default_factory=lambda: provider_defaults(
            image="x86:system:ubuntu-22.04",
            server_type="cx31",
            location="nbg1",
            volume_size=20,
            volume_location="nbg1",
        )
    )


@dataclass
class aws_provider:
    """AWS provider configuration."""

    access_key_id: str = None
    secret_access_key: str = None
    security_group: str = None
    subnet: str = None
    key_name: str = None
    defaults: provider_defaults = dataclasses.field(
        default_factory=lambda: provider_defaults(
            image="resolve:ssm:/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp3/ami-id",
            server_type="t3.medium",
            location="us-east-1a",
            volume_size=20,
            volume_location="us-east-1a",
            volume_type="gp3",
        )
    )


@dataclass
class azure_provider:
    """Azure provider configuration."""

    subscription_id: str = None
    tenant_id: str = None
    client_id: str = None
    client_secret: str = None
    resource_group: str = None
    defaults: provider_defaults = dataclasses.field(
        default_factory=lambda: provider_defaults(
            image="Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest",
            server_type="Standard_B2s",
            location="East US",
            volume_size=20,
            volume_location="East US",
            volume_type="Premium_LRS",
        )
    )


@dataclass
class gcp_provider:
    """GCP provider configuration."""

    project_id: str = None
    service_account_key: str = None
    network: str = "default"
    subnetwork: str = "default"
    defaults: provider_defaults = dataclasses.field(
        default_factory=lambda: provider_defaults(
            image="projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts",
            server_type="e2-medium",
            location="us-central1-a",
            volume_size=20,
            volume_location="us-central1-a",
            volume_type="pd-ssd",
        )
    )


@dataclass
class scaleway_provider:
    """Scaleway provider configuration."""

    access_key: str = None
    secret_key: str = None
    organization_id: str = None
    defaults: provider_defaults = dataclasses.field(
        default_factory=lambda: provider_defaults(
            image="ubuntu_jammy",
            server_type="DEV1-M",
            location="par1",
            volume_size=20,
            volume_location="par1",
            volume_type="b_ssd",
        )
    )


@dataclass
class providers:
    """Multi-provider configuration."""

    hetzner: hetzner_provider = None
    aws: aws_provider = None
    azure: azure_provider = None
    gcp: gcp_provider = None
    scaleway: scaleway_provider = None


@dataclass
class deploy_:
    server_type: str = "cpx21"
    image: str = "x86:system:ubuntu-22.04"
    location: str = None  # Optional location for service deployment
    setup_script: str = os.path.join(current_dir, "..", "scripts", "deploy", "setup.sh")


@dataclass
class cloud:
    provider: str = "hetzner"
    server_name: str = "tfs-runners-service"
    host: str = None  # Optional direct host/IP for SSH connection (bypasses API lookup)
    deploy: deploy_ = dataclasses.field(default_factory=deploy_)


@dataclass
class Config:
    """Program configuration class."""

    github_token: str = os.getenv("GITHUB_TOKEN")
    github_repository: str = os.getenv("GITHUB_REPOSITORY")

    # Multi-provider configuration
    providers: providers = dataclasses.field(default_factory=providers)

    # Provider-agnostic settings
    ssh_key: str = os.path.expanduser("~/.ssh/id_rsa.pub")
    additional_ssh_keys: list[str] = None
    with_label: list[str] = None
    label_prefix: str = ""
    meta_label: dict[str, set[str]] = None
    recycle: bool = True
    end_of_life: int = 50
    delete_random: bool = False
    max_runners: int = 10
    max_runners_for_label: list[tuple[set[str], int]] = None
    max_runners_in_workflow_run: int = None
    workers: int = 10
    scripts: str = os.path.join(current_dir, "..", "scripts")
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

    def check(self, *parameters):
        """Check mandatory configuration parameters."""

        if not parameters:
            parameters = ["github_token", "github_repository"]

        for name in parameters:
            value = getattr(self, name)
            if value:
                continue
            print(
                f"argument error: --{name.lower().replace('_','-')} is not defined",
                file=sys.stderr,
            )
            sys.exit(1)


def read(path: str):
    """Load raw configuration document."""
    with open(path, "r") as f:
        return yaml.load(f, Loader=yaml.SafeLoader)


def write(file, doc: dict):
    """Write raw configuration document to file."""
    yaml.dump(doc, file)


def check_setup_script(script: str):
    """Check if setup script is valid."""
    if not os.path.exists(script):
        raise errors.SetupScriptError(f"invalid setup script path '{script}'")
    return script


def check_startup_script(script: str):
    """Check if startup script is valid."""
    if not os.path.exists(script):
        raise errors.StartupScriptError(f"invalid startup script path '{script}'")
    return script
