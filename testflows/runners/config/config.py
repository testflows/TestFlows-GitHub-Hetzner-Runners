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
from ..providers import hetzner, aws, azure, gcp, scaleway

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


class LocationError(Exception):
    pass


class ImageError(Exception):
    pass


class SetupScriptError(Exception):
    pass


class StartupScriptError(Exception):
    pass


class ServerTypeError(Exception):
    pass


class ConfigError(Exception):
    pass


path = args.path_type
count = args.count_type
image = args.image_type
location = args.location_type
server_type = args.server_type
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

    def get_enabled_providers(self) -> list[str]:
        """Get list of enabled (configured) providers."""
        enabled = []
        if hetzner.config.is_enabled(self.providers.hetzner):
            enabled.append("hetzner")
        if aws.config.is_enabled(self.providers.aws):
            enabled.append("aws")
        if azure.config.is_enabled(self.providers.azure):
            enabled.append("azure")
        if gcp.config.is_enabled(self.providers.gcp):
            enabled.append("gcp")
        if scaleway.config.is_enabled(self.providers.scaleway):
            enabled.append("scaleway")

        return enabled

    def get_provider_config(self, provider_name: str):
        """Get configuration for a specific provider."""
        provider_map = {
            "hetzner": self.providers.hetzner,
            "aws": self.providers.aws,
            "azure": self.providers.azure,
            "gcp": self.providers.gcp,
            "scaleway": self.providers.scaleway,
        }
        return provider_map.get(provider_name)

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
                "providers",  # Skip providers, handled separately
            ]:
                continue

            arg_value = getattr(args, attr)

            if arg_value is not None:
                setattr(self, attr, arg_value)

        # Update provider-specific settings
        self._update_provider_settings(args)

    def _update_provider_settings(self, args):
        """Update provider-specific settings from CLI arguments."""
        # Create provider instances if they don't exist but have CLI args
        if not self.providers.hetzner and hetzner.config.has_cli_args(args):
            self.providers.hetzner = hetzner_provider()
        if not self.providers.aws and aws.config.has_cli_args(args):
            self.providers.aws = aws_provider()
        if not self.providers.azure and azure.config.has_cli_args(args):
            self.providers.azure = azure_provider()
        if not self.providers.gcp and gcp.config.has_cli_args(args):
            self.providers.gcp = gcp_provider()
        if not self.providers.scaleway and scaleway.config.has_cli_args(args):
            self.providers.scaleway = scaleway_provider()

        # Update each provider using their config modules
        hetzner.config.update_from_args(self.providers.hetzner, args)
        aws.config.update_from_args(self.providers.aws, args)
        azure.config.update_from_args(self.providers.azure, args)
        gcp.config.update_from_args(self.providers.gcp, args)
        scaleway.config.update_from_args(self.providers.scaleway, args)

        # Update cloud deployment settings
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

    def _parse_provider_list(self, provider_args) -> list[str]:
        """Parse provider arguments supporting both multiple flags and comma-separated values."""
        if not provider_args:
            return []

        valid_providers = {"hetzner", "aws", "azure", "gcp", "scaleway"}
        parsed = []

        for arg in provider_args:
            # Split by comma and strip whitespace
            providers = [p.strip() for p in arg.split(",")]
            for provider in providers:
                if provider in valid_providers:
                    if provider not in parsed:  # Avoid duplicates
                        parsed.append(provider)
                else:
                    # Log warning or raise error for invalid provider
                    print(
                        f"Warning: Unknown provider '{provider}'. Valid providers: {', '.join(sorted(valid_providers))}"
                    )

        return parsed

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


def parse_config(filename: str):
    """Load and parse yaml configuration file into config object.

    Does not check if ssh_key, or additional_ssh_keys exist.
    Does not check server_type exists.
    Does not check image exists.
    Does not check location exists.
    Does not check server_type is available for the location.
    Does not check if image exists for the server_type.
    """
    with open(filename, "r") as f:
        doc = yaml.load(f, Loader=yaml.SafeLoader)

    if doc.get("config") is None:
        assert False, "config: entry is missing"

    doc = doc["config"]

    if doc.get("setup_script"):
        assert (
            False
        ), "config.setup_script is deprecated, use the new config.scripts option"

    if doc.get("startup_x64_script"):
        assert (
            False
        ), "config.startup_x64_script is deprecated, use the new config.scripts option"

    if doc.get("startup_arm64_script"):
        assert (
            False
        ), "config.startup_x64_script is deprecated, see the new config.scripts option"

    if doc.get("ssh_key") is not None:
        assert isinstance(doc["ssh_key"], str), "config.ssh_key: is not a string"
        doc["ssh_key"] = path(doc["ssh_key"], check_exists=False)

    if doc.get("additional_ssh_keys") is not None:
        assert isinstance(
            doc["additional_ssh_keys"], list
        ), "config.additional_ssh_keys: not a list"
        for i, key in enumerate(doc["additional_ssh_keys"]):
            assert isinstance(
                key, str
            ), f"config.additional_ssh_keys[{i}]: is not a string"

    if doc.get("with_label") is not None:
        assert isinstance(doc["with_label"], list), "config.with_label: is not a list"
        for i, label in enumerate(doc["with_label"]):
            assert isinstance(label, str), f"config.with_label[{i}]: is not a string"
        doc["with_label"] = [label.lower().strip() for label in doc["with_label"]]

    if doc.get("label_prefix") is not None:
        assert isinstance(
            doc["label_prefix"], str
        ), "config.label_prefix: is not a string"
        doc["label_prefix"] = doc["label_prefix"].lower().strip()

    if doc.get("meta_label") is not None:
        assert isinstance(
            doc["meta_label"], dict
        ), "config.meta_label is not a dictionary"
        for i, meta in enumerate(doc["meta_label"]):
            assert isinstance(
                meta, str
            ), f"config.meta_label.{meta}: name is not a string"
            assert isinstance(
                doc["meta_label"][meta], list
            ), f"config.meta_label.{meta}: is not a list"
            for j, v in enumerate(doc["meta_label"][meta]):
                assert isinstance(
                    v, str
                ), f"config.meta_label.{meta}[{j}]: is not a string"
            doc["meta_label"][meta] = set(doc["meta_label"][meta])

        doc["meta_label"] = {
            meta.lower().strip(): [
                label.lower().strip() for label in doc["meta_label"][meta]
            ]
            for meta in doc["meta_label"]
        }

    if doc.get("recycle") is not None:
        assert isinstance(doc["recycle"], bool), "config.recycle: is not a boolean"

    if doc.get("end_of_life") is not None:
        v = doc["end_of_life"]
        assert isinstance(v, int), "config.end_of_life: is not integer"
        assert v > 0 and v < 60, "config.end_of_life: is not > 0 and < 60"

    if doc.get("delete_random") is not None:
        assert isinstance(
            doc["delete_random"], bool
        ), "config.delete_random: is not a boolean"

    if doc.get("max_runners") is not None:
        v = doc["max_runners"]
        assert isinstance(v, int) and v > 0, "config.max_runners: is not an integer > 0"

    if doc.get("max_runners_for_label") is not None:
        assert isinstance(
            doc["max_runners_for_label"], list
        ), "config.max_runners_for_label: is not a list"
        for i, item in enumerate(doc["max_runners_for_label"]):
            assert isinstance(
                item, dict
            ), f"config.max_runners_for_label[{i}]: is not an object"
            assert (
                "labels" in item
            ), f"config.max_runners_for_label[{i}]: missing 'labels' field"
            assert (
                "max" in item
            ), f"config.max_runners_for_label[{i}]: missing 'max' field"
            assert isinstance(
                item["labels"], list
            ), f"config.max_runners_for_label[{i}].labels: is not a list"
            assert (
                isinstance(item["max"], int) and item["max"] > 0
            ), f"config.max_runners_for_label[{i}].max: is not an integer > 0"
            for j, label in enumerate(item["labels"]):
                assert isinstance(
                    label, str
                ), f"config.max_runners_for_label[{i}].labels[{j}]: is not a string"
                assert (
                    label.strip()
                ), f"config.max_runners_for_label[{i}].labels[{j}]: cannot be empty"
            # Convert to our internal format (set of labels, count)
            doc["max_runners_for_label"][i] = (
                set(label.strip().lower() for label in item["labels"]),
                item["max"],
            )

    if doc.get("max_runners_in_workflow_run") is not None:
        v = doc["max_runners_in_workflow_run"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.max_runners_in_workflow_run: is not an integer > 0"

    if doc.get("default_image") is not None:
        try:
            doc["default_image"] = image(doc["default_image"])
        except Exception as e:
            assert False, f"config.default_image: {e}"

    if doc.get("default_server_type") is not None:
        try:
            doc["default_server_type"] = server_type(doc["default_server_type"])
        except Exception as e:
            assert False, f"config.default_server_type: {e}"

    if doc.get("default_location") is not None:
        try:
            v = doc["default_location"]
            assert isinstance(v, str), "is not a string"
            doc["default_location"] = location(v)
        except Exception as e:
            assert False, f"config.default_location: {e}"

    if doc.get("default_volume_location") is not None:
        try:
            v = doc["default_volume_location"]
            assert isinstance(v, str), "is not a string"
            doc["default_volume_location"] = location(v)
        except Exception as e:
            assert False, f"config.default_volume_location: {e}"

    if doc.get("default_volume_size") is not None:
        v = doc["default_volume_size"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.default_volume_size: is not an integer > 0"

    if doc.get("workers") is not None:
        v = doc["workers"]
        assert isinstance(v, int) and v > 0, "config.workers: is not an integer > 0"

    if doc.get("scripts") is not None:
        try:
            doc["scripts"] = path(doc["scripts"])
        except Exception as e:
            assert False, f"config.scripts: {e}"

    if doc.get("max_powered_off_time") is not None:
        v = doc["max_powered_off_time"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.max_powered_off_time: is not an integer > 0"

    if doc.get("max_unused_runner_time") is not None:
        v = doc["max_unused_runner_time"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.max_unused_runner_time: is not an integer > 0"

    if doc.get("max_runner_registration_time") is not None:
        v = doc["max_runner_registration_time"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.max_runner_registration_time: is not an integer > 0"

    if doc.get("max_server_ready_time") is not None:
        v = doc["max_server_ready_time"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.max_server_ready_time: is not an integer > 0"

    if doc.get("scale_up_interval") is not None:
        v = doc["scale_up_interval"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.scale_up_interval: is not an integer > 0"

    if doc.get("scale_down_interval") is not None:
        v = doc["scale_down_interval"]
        assert (
            isinstance(v, int) and v > 0
        ), "config.scale_down_interval: is not an integer > 0"

    if doc.get("metrics_port") is not None:
        v = doc["metrics_port"]
        assert (
            isinstance(v, int) and v > 0 and v < 65536
        ), "config.metrics_port: is not an integer between 1 and 65535"

    if doc.get("metrics_host") is not None:
        v = doc["metrics_host"]
        assert isinstance(v, str), "config.metrics_host: is not a string"
        assert v.strip(), "config.metrics_host: cannot be empty"

    if doc.get("dashboard_port") is not None:
        v = doc["dashboard_port"]
        assert (
            isinstance(v, int) and v > 0 and v < 65536
        ), "config.dashboard_port: is not an integer between 1 and 65535"

    if doc.get("dashboard_host") is not None:
        v = doc["dashboard_host"]
        assert isinstance(v, str), "config.dashboard_host: is not a string"
        assert v.strip(), "config.dashboard_host: cannot be empty"

    if doc.get("debug") is not None:
        assert isinstance(doc["debug"], bool), "config.debug: not a boolean"

    if doc.get("logger_config") is not None:
        assert (
            doc["logger_config"].get("loggers") is not None
        ), "config.logger_config.loggers is not defined"
        assert (
            doc["logger_config"]["loggers"].get("testflows.runners") is not None
        ), 'config.logger_config.loggers."testflows.runners" is not defined'
        assert (
            doc["logger_config"]["loggers"]["testflows.runners"].get("handlers")
            is not None
        ), 'config.logger_config.loggers."testflows.runners".handlers is not defined'

        assert isinstance(
            doc["logger_config"]["loggers"]["testflows.runners"]["handlers"],
            list,
        ), 'config.logger_config.loggers."testflows.runners".handlers is not a list'
        assert (
            "stdout"
            in doc["logger_config"]["loggers"]["testflows.runners"]["handlers"]
        ), 'config.logger_config.loggers."testflows.runners".handlers missing stdout'

        assert (
            doc["logger_config"]["handlers"].get("rotating_logfile") is not None
        ), "config.logger_config.handlers.rotating_logfile is not defined"
        assert (
            doc["logger_config"]["handlers"]["rotating_logfile"].get("filename")
            is not None
        ), "config.logger_config.handlers.rotating_logfile.filename is not defined"

        try:
            logging.config.dictConfig(doc["logger_config"])
        except Exception as e:
            assert False, f"config.logger_config: {e}"

    if doc.get("logger_format") is not None:
        _logger_format_columns = {}
        assert isinstance(
            doc["logger_format"], dict
        ), f"config.logger_format is not a dictionary"

        assert (
            doc["logger_format"].get("delimiter") is not None
        ), "config.logger_format.delimiter is not defined"
        assert isinstance(
            doc["logger_format"]["delimiter"], str
        ), f"config.logger_format.delimiter is not a string"

        assert (
            doc["logger_format"].get("columns") is not None
        ), "config.logger_format.columns  is not defined"
        assert isinstance(
            doc["logger_format"]["columns"], list
        ), "config.logger_format.columns is not a list"

        for i, item in enumerate(doc["logger_format"]["columns"]):
            assert (
                item.get("column") is not None
            ), f"config.logger_format[{i}].column is not defined"
            assert isinstance(
                item["column"], str
            ), f"config.logger_format[{i}].column is not a string"
            assert (
                item.get("index") is not None
            ), f"config.logger_format[{i}].index is not defined"
            assert (
                isinstance(item["index"], int) and item["index"] >= 0
            ), f"config.logger_format[{i}].index: {item['index']} is not an integer >= 0"
            assert (
                item.get("width") is not None
            ), f"config.logger_format[{i}].width is not defined"
            assert (
                isinstance(item["width"], int) and item["width"] >= 0
            ), f"config.logger_format[{i}].width: {item['width']} is not an integer >= 0"
            _logger_format_columns[item["column"]] = (item["index"], item["width"])
        doc["logger_format"]["columns"] = _logger_format_columns

        assert (
            doc["logger_format"].get("default") is not None
        ), "config.logger_format.default is not defined"
        assert isinstance(
            doc["logger_format"]["default"], list
        ), "config.logger_format.default is not an array"

        for i, item in enumerate(doc["logger_format"]["default"]):
            assert (
                item.get("column") is not None
            ), f"config.logger_format.default[{i}].column is not defined"
            assert (
                item["column"] in doc["logger_format"]["columns"]
            ), f"config.logger_format.default[{i}].column is not valid"
            if item.get("width") is not None:
                assert (
                    isinstance(item["width"], int) and item["width"] > 0
                ), f"config.logger_format.default[{i}].width is not an integer > 0"

    if doc.get("cloud") is not None:
        if doc["cloud"].get("server_name") is not None:
            assert isinstance(
                doc["cloud"]["server_name"], str
            ), "config.cloud.server_name: is not a string"
        if doc["cloud"].get("deploy") is not None:
            if doc["cloud"]["deploy"].get("server_type") is not None:
                try:
                    doc["cloud"]["deploy"]["server_type"] = server_type(
                        doc["cloud"]["deploy"]["server_type"]
                    )
                except Exception as e:
                    assert False, f"config.cloud.deploy.server_type: {e}"
            if doc["cloud"]["deploy"].get("image") is not None:
                try:
                    doc["cloud"]["deploy"]["image"] = image(
                        doc["cloud"]["deploy"]["image"]
                    )
                except Exception as e:
                    assert False, f"config.cloud.deploy.image: {e}"
            if doc["cloud"]["deploy"].get("location") is not None:
                try:
                    doc["cloud"]["deploy"]["location"] = location(
                        doc["cloud"]["deploy"]["location"]
                    )
                except Exception as e:
                    assert False, f"config.cloud.deploy.location: {e}"
            if doc["cloud"]["deploy"].get("setup_script") is not None:
                try:
                    doc["cloud"]["deploy"]["setup_script"] = path(
                        doc["cloud"]["deploy"]["setup_script"]
                    )
                except Exception as e:
                    assert False, f"config.cloud.deploy.setup_script: {e}"

        if doc["cloud"].get("server_name"):
            doc["cloud"] = cloud(
                doc["cloud"]["server_name"],
                host=doc["cloud"].get("host"),
                deploy=deploy_(**doc["cloud"].get("deploy", {})),
            )
        else:
            doc["cloud"] = cloud(
                deploy=deploy_(**doc["cloud"].get("deploy", {})),
            )

    if doc.get("standby_runners"):
        assert isinstance(
            doc["standby_runners"], list
        ), "config.standby_runners: is not a list"

        for i, entry in enumerate(doc["standby_runners"]):
            assert isinstance(
                entry, dict
            ), f"config.standby_runners[{i}]: is not an dictionary"
            if entry.get("labels") is not None:
                assert isinstance(
                    entry["labels"], list
                ), f"config.standby_runners[{i}].labels: is not a list"
                for j, label in enumerate(entry["labels"]):
                    assert isinstance(
                        label, str
                    ), f"config.standby_runners[{i}].labels[{j}]: {label} is not a string"
                entry["labels"] = [label.lower().strip() for label in entry["labels"]]
            if entry.get("count") is not None:
                v = entry["count"]
                assert (
                    isinstance(v, int) and v > 0
                ), f"config.standby_runners[{i}].count: is not an integer > 0"
            if entry.get("replenish_immediately") is not None:
                assert isinstance(
                    entry["replenish_immediately"], bool
                ), f"config.standby_runners[{i}].replenish_immediately: is not a boolean"

        doc["standby_runners"] = [
            standby_runner(**entry) for entry in doc["standby_runners"]
        ]

    if doc.get("server_prices") is not None:
        assert False, "config.server_prices: should not be defined"

    if doc.get("config_file") is not None:
        assert False, "config.config_file: should not be defined"

    if doc.get("service_mode") is not None:
        assert False, "config.service_mode: should not be defined"

    if doc.get("embedded_mode") is not None:
        assert False, "config.embedded_mode: should not be defined"

    try:
        return Config(**doc)
    except Exception as e:
        assert False, f"config: {e}"


def check_setup_script(script: str):
    """Check if setup script is valid."""
    if not os.path.exists(script):
        raise SetupScriptError(f"invalid setup script path '{script}'")
    return script


def check_startup_script(script: str):
    """Check if startup script is valid."""
    if not os.path.exists(script):
        raise StartupScriptError(f"invalid startup script path '{script}'")
    return script
