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
from hcloud.ssh_keys.domain import SSHKey

import testflows.runners.args as args

from ..hclient import HClient as Client
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
class provider_list:
    """Multi-provider configuration."""

    hetzner: hetzner_provider = None
    aws: aws_provider = None
    azure: azure_provider = None
    gcp: gcp_provider = None
    scaleway: scaleway_provider = None


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
            has_provider = self.hetzner_token or (
                self.providers.hetzner is not None
                and bool(self.providers.hetzner.token)
            )
            if not has_provider:
                print(
                    "argument error: no cloud provider configured; "
                    "set --hetzner-token or add providers.hetzner.token to config file",
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


def check_ssh_key(client: Client, ssh_key: str, is_file=True):
    """Check that ssh key exists if not create it."""

    def fingerprint(ssh_key):
        """Calculate fingerprint of a public SSH key."""
        encoded_key = base64.b64decode(ssh_key.strip().split()[1].encode("utf-8"))
        md5_digest = hashlib.md5(encoded_key).hexdigest()

        return ":".join(a + b for a, b in zip(md5_digest[::2], md5_digest[1::2]))

    if is_file:
        with open(ssh_key, "r", encoding="utf-8") as ssh_key_file:
            public_key = ssh_key_file.read()
    else:
        public_key = ssh_key

    name = hashlib.md5(public_key.encode("utf-8")).hexdigest()
    ssh_key: SSHKey = SSHKey(
        name=name, public_key=public_key, fingerprint=fingerprint(public_key)
    )

    existing_ssh_key = client.ssh_keys.get_by_fingerprint(
        fingerprint=ssh_key.fingerprint
    )

    if not existing_ssh_key:
        with Action(
            f"Creating SSH key {ssh_key.name} with fingerprint {ssh_key.fingerprint}",
            stacklevel=3,
        ):
            ssh_key = client.ssh_keys.create(
                name=ssh_key.name, public_key=ssh_key.public_key
            )
    else:
        ssh_key = existing_ssh_key

    return ssh_key


def check_image(client: Client, image: Image):
    """Check if image exists.
    If image type is not 'system' then use image description to find it.
    """

    if image.type in ("system", "app"):
        _image = client.images.get_by_name_and_architecture(
            name=image.name, architecture=image.architecture
        )
        if not _image:
            raise errors.ImageError(
                f"image type:'{image.type}' name:'{image.name}' architecture:'{image.architecture}' not found"
            )
        return _image
    else:
        # backup or snapshot
        try:
            return [
                i
                for i in client.images.get_all(
                    type=image.type, architecture=image.architecture
                )
                if i.description == image.description
            ][0]
        except IndexError:
            raise errors.ImageError(
                f"image type:'{image.type}' name:'{image.description}' architecture:'{image.architecture}' not found"
            )


def check_location(client: Client, location: Location, required=False):
    """Check if location exists."""
    if location is None:
        if required:
            raise errors.LocationError(f"location is not defined")
        return None
    _location = client.locations.get_by_name(location.name)
    if not _location:
        raise errors.LocationError(f"location '{location.name}' not found")
    return _location


def check_server_type(client: Client, server_type: ServerType):
    """Check if server type exists."""
    _type: ServerType = client.server_types.get_by_name(server_type.name)
    if not _type:
        raise errors.ServerTypeError(f"server type '{server_type.name}' not found")
    return _type


def check_prices(client: Client):
    """Check server prices."""
    server_types: list[ServerType] = client.server_types.get_all()
    return {
        t.name.lower(): {
            price["location"]: float(price["price_hourly"]["gross"])
            for price in t.prices
        }
        for t in server_types
    }


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
