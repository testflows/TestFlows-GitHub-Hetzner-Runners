import os
import re
import sys
import yaml
import base64
import hashlib
import logging
import logging.config
import dataclasses

from dataclasses import dataclass

from hcloud.images.domain import Image
from hcloud.server_types.domain import ServerType
from hcloud.locations.domain import Location
import testflows.runners.args as args

from ..actions import Action
from ..logger import default_format as logger_format
from ..ordered_set import OrderedSet as set
from .. import errors

current_dir = os.path.dirname(__file__)

# add support for parsing ${ENV_VAR} in config
env_pattern = re.compile(r".*?\${(.*?)}.*?")

default_user_config = os.path.expanduser("~/.tfs-runners/config.yaml")

# store all the environment variables used inside the config file
config_vars = {}


def env_constructor(loader, node):
    value = loader.construct_scalar(node)
    for group in env_pattern.findall(value):
        env_value = os.environ.get(group)
        if env_value is None:
            assert (
                False
            ), f"environment variable ${group} used in the config is not defined"
        value = value.replace(f"${{{group}}}", env_value)
        config_vars[group] = env_value
    return value


yaml.add_implicit_resolver("!path", env_pattern, None, yaml.SafeLoader)
yaml.add_constructor("!path", env_constructor, yaml.SafeLoader)


path = args.path_type
count = args.count_type
image = args.image_type
location = args.location_type
server_type = args.server_type
end_of_life = args.end_of_life_type
meta_label_type = args.meta_label_type


# Re-export error classes from errors module for backwards compatibility
ConfigError = errors.ConfigError
LocationError = errors.LocationError
ImageError = errors.ImageError
SetupScriptError = errors.SetupScriptError
StartupScriptError = errors.StartupScriptError
ServerTypeError = errors.ServerTypeError


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
    max_runners: int = None
    end_of_life: int = None
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
    subnets: list[str] = None
    key_name: str = None
    ssh_user: str = "ubuntu"
    max_runners: int = None
    end_of_life: int = None
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
class provider_list:
    """Multi-provider configuration."""

    hetzner: hetzner_provider = None
    aws: aws_provider = None


@dataclass
class deploy_:
    server_type: ServerType = server_type("cx23")
    image: Image = image("x86:system:ubuntu-22.04")
    location: Location = None
    setup_script: str = os.path.join(current_dir, "..", "scripts", "deploy", "setup.sh")


@dataclass
class cloud:
    provider: str = "hetzner"
    server_name: str = "tfs-runners-service"
    host: str = None
    deploy: deploy_ = dataclasses.field(default_factory=deploy_)


@dataclass
class Config:
    """Program configuration class."""

    github_token: str = os.getenv("GITHUB_TOKEN")
    github_repository: str = os.getenv("GITHUB_REPOSITORY")
    hetzner_token: str = os.getenv("HETZNER_TOKEN")

    # Multi-provider configuration
    providers: provider_list = dataclasses.field(default_factory=provider_list)

    # Provider-agnostic settings
    ssh_key: str = os.path.expanduser("~/.ssh/id_rsa.pub")
    additional_ssh_keys: list[str] = None
    with_label: list[str] = None
    label_prefix: str = ""
    meta_label: dict[str, set[str]] = None
    recycle: bool = True
    recycle_grace_period: int = 1200
    end_of_life: int = 50
    delete_random: bool = False
    max_runners: int = 10
    max_runners_for_label: list[tuple[set[str], int]] = None
    max_runners_in_workflow_run: int = None
    default_image: Image = image("x86:system:ubuntu-22.04")
    default_server_type: ServerType = server_type("cx23")
    default_location: Location = None
    default_volume_location: Location = location("nbg1")
    default_volume_size: int = 10
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
        # Normalise: if the flat hetzner_token field is unset but the new-style
        # providers.hetzner.token is set, promote it so that legacy code paths
        # (cloud.py, servers.py, volumes.py, etc.) that read config.hetzner_token
        # see the correct value without needing to be updated individually.
        if not self.hetzner_token and self.providers and self.providers.hetzner:
            if self.providers.hetzner.token:
                self.hetzner_token = self.providers.hetzner.token

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

    def update(self, args):
        """Update configuration file using command line arguments."""
        for attr in vars(self):
            if attr in [
                "config_file",
                "logger_config",
                "logger_format",
                "cloud",
                "standby_runners",
                "additional_ssh_keys",
                "server_prices",
                "providers",
            ]:
                continue

            arg_value = getattr(args, attr, None)

            if arg_value is not None:
                setattr(self, attr, arg_value)

        if getattr(args, "cloud_server_name", None) is not None:
            self.cloud.server_name = args.cloud_server_name

        if getattr(args, "cloud_host", None) is not None:
            self.cloud.host = args.cloud_host

        if getattr(args, "cloud_deploy_location", None) is not None:
            self.cloud.deploy.location = args.cloud_deploy_location

        if getattr(args, "cloud_deploy_server_type", None) is not None:
            self.cloud.deploy.server_type = args.cloud_deploy_server_type

        if getattr(args, "cloud_deploy_image", None) is not None:
            self.cloud.deploy.image = args.cloud_deploy_image

        if getattr(args, "cloud_deploy_setup_script", None) is not None:
            self.cloud.deploy.setup_script = args.cloud_deploy_setup_script

    def check(self, *parameters):
        """Check mandatory configuration parameters."""

        if not parameters:
            # Check GitHub credentials.
            for name in ("github_token", "github_repository"):
                if not getattr(self, name):
                    print(
                        f"argument error: --{name.lower().replace('_','-')} is not defined",
                        file=sys.stderr,
                    )
                    sys.exit(1)
            # Check that at least one provider is configured.
            has_hetzner = self.hetzner_token or (
                self.providers.hetzner is not None
                and bool(self.providers.hetzner.token)
            )
            has_aws = (
                self.providers.aws is not None
                and bool(self.providers.aws.access_key_id)
                and bool(self.providers.aws.secret_access_key)
            )
            if not (has_hetzner or has_aws):
                print(
                    "argument error: no cloud provider configured; "
                    "set --hetzner-token or add providers.hetzner.token / providers.aws credentials to config file",
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


def read(path: str):
    """Load raw configuration document."""
    with open(path, "r") as f:
        return yaml.load(f, Loader=yaml.SafeLoader)


def write(file, doc: dict):
    """Write raw configuration document to file."""
    yaml.dump(doc, file)


def check_scripts(scripts: str):
    """Check if scripts directory exists."""
    if not os.path.exists(scripts):
        raise errors.ScriptsError(f"invalid scripts directory '{scripts}'")
    return scripts


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
