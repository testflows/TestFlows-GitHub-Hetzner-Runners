import os
import re
import sys
import yaml
import base64
import hashlib
import logging
import logging.config

from dataclasses import dataclass

from hcloud import Client
from hcloud.images.domain import Image
from hcloud.server_types.domain import ServerType
from hcloud.locations.domain import Location
from hcloud.ssh_keys.domain import SSHKey

import testflows.github.hetzner.runners.args as args

from ..actions import Action
from ..logger import default_format as logger_format

current_dir = os.path.dirname(__file__)

# add support for parsing ${ENV_VAR} in config
env_pattern = re.compile(r".*?\${(.*?)}.*?")

default_user_config = os.path.expanduser("~/.github-hetzner-runners/config.yaml")


def env_constructor(loader, node):
    value = loader.construct_scalar(node)
    for group in env_pattern.findall(value):
        value = value.replace(f"${{{group}}}", os.environ.get(group))
    return value


yaml.add_implicit_resolver("!path", env_pattern, None, yaml.SafeLoader)
yaml.add_constructor("!path", env_constructor, yaml.SafeLoader)


class LocationError(Exception):
    pass


class ImageError(Exception):
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


@dataclass
class standby_runner:
    labels: list[str]
    count: int = 1
    replenish_immediately: bool = True


@dataclass
class deploy:
    server_type: ServerType = server_type("cpx11")
    image: Image = image("x86:system:ubuntu-22.04")
    location: Location = None
    setup_script: str = os.path.join(current_dir, "..", "scripts", "deploy", "setup.sh")


@dataclass
class cloud:
    server_name: str = "github-hetzner-runners"
    deploy: deploy = deploy()


@dataclass
class Config:
    """Program configuration class."""

    github_token: str = os.getenv("GITHUB_TOKEN")
    github_repository: str = os.getenv("GITHUB_REPOSITORY")
    hetzner_token: str = os.getenv("HETZNER_TOKEN")
    ssh_key: str = os.path.expanduser("~/.ssh/id_rsa.pub")
    additional_ssh_keys: list[str] = None
    with_label: str = None
    label_prefix: str = ""
    recycle: bool = True
    end_of_life: int = 50
    delete_random: bool = False
    max_runners: int = 10
    max_runners_in_workflow_run: int = None
    default_image: Image = image("x86:system:ubuntu-22.04")
    default_server_type: ServerType = server_type("cx11")
    default_location: Location = None
    workers: int = 10
    setup_script: str = os.path.join(current_dir, "..", "scripts", "setup.sh")
    startup_x64_script: str = os.path.join(
        current_dir, "..", "scripts", "startup_x64.sh"
    )
    startup_arm64_script: str = os.path.join(
        current_dir, "..", "scripts", "startup_arm64.sh"
    )
    max_powered_off_time: int = 60
    max_unused_runner_time: int = 180
    max_runner_registration_time: int = 180
    max_server_ready_time: int = 180
    scale_up_interval: int = 15
    scale_down_interval: int = 15
    debug: bool = False
    # special
    service_mode: bool = False
    embedded_mode: bool = False
    logger_config: dict = None
    logger_format: dict = None
    cloud: cloud = cloud()
    standby_runners: list[standby_runner] = None
    server_prices: dict[str, float] = None
    config_file: str = None

    def __post_init__(self):
        if self.standby_runners is None:
            self.standby_runners = []

        if self.additional_ssh_keys is None:
            self.additional_ssh_keys = []

        if self.logger_format is None:
            self.logger_format = logger_format

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
            ]:
                continue

            arg_value = getattr(args, attr)

            if arg_value is not None:
                setattr(self, attr, arg_value)

        if getattr(args, "cloud_server_name", None) is not None:
            self.cloud.server_name = args.cloud_server_name

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
            parameters = ["github_token", "github_repository", "hetzner_token"]

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
        assert isinstance(doc["with_label"], str), "config.with_label: is not a string"

    if doc.get("label_prefix") is not None:
        assert isinstance(
            doc["label_prefix"], str
        ), "config.label_prefix: is not a string"

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

    if doc.get("workers") is not None:
        v = doc["workers"]
        assert isinstance(v, int) and v > 0, "config.workers: is not an integer > 0"

    if doc.get("setup_script") is not None:
        try:
            doc["setup_script"] = path(doc["setup_script"])
        except Exception as e:
            assert False, f"config.setup_script: {e}"

    if doc.get("startup_x64_script") is not None:
        try:
            doc["startup_x64_script"] = path(doc["startup_x64_script"])
        except Exception as e:
            assert False, f"config.startup_x64_script: {e}"

    if doc.get("startup_arm64_script") is not None:
        try:
            doc["startup_arm64_script"] = path(doc["startup_arm64_script"])
        except Exception as e:
            assert False, f"config.startup_arm64_script: {e}"

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

    if doc.get("debug") is not None:
        assert isinstance(doc["debug"], bool), "config.debug: not a boolean"

    if doc.get("logger_config") is not None:
        assert (
            doc["logger_config"].get("loggers") is not None
        ), "config.logger_config.loggers is not defined"
        assert (
            doc["logger_config"]["loggers"].get("testflows.github.hetzner.runners")
            is not None
        ), 'config.logger_config.loggers."tesflows.github.hetzner.runners" is not defined'
        assert (
            doc["logger_config"]["loggers"]["testflows.github.hetzner.runners"].get(
                "handlers"
            )
            is not None
        ), 'config.logger_config.loggers."testflows.github.hetzner.runners".handlers is not defined'

        assert isinstance(
            doc["logger_config"]["loggers"]["testflows.github.hetzner.runners"][
                "handlers"
            ],
            list,
        ), 'config.logger_config.loggers."testflows.github.hetzner.runners".handlers is not a list'
        assert (
            "stdout"
            in doc["logger_config"]["loggers"]["testflows.github.hetzner.runners"][
                "handlers"
            ]
        ), 'config.logger_config.loggers."testflows.github.hetzner.runners".handlers missing stdout'

        assert (
            doc["logger_config"]["handlers"].get("rotating_service_logfile") is not None
        ), "config.logger_config.handlers.rotating_service_logfile is not defined"
        assert (
            doc["logger_config"]["handlers"]["rotating_service_logfile"].get("filename")
            is not None
        ), "config.logger_config.handlers.rotating_service_logfile.filename is not defined"

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
                deploy=deploy(**doc["cloud"].get("deploy", {})),
            )
        else:
            doc["cloud"] = cloud(
                deploy=deploy(**doc["cloud"].get("deploy", {})),
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

    if not client.ssh_keys.get_by_fingerprint(fingerprint=ssh_key.fingerprint):
        with Action(
            f"Creating SSH key {ssh_key.name} with fingerprint {ssh_key.fingerprint}",
            stacklevel=3,
        ):
            client.ssh_keys.create(name=ssh_key.name, public_key=ssh_key.public_key)

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
            raise ImageError(
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
            raise ImageError(
                f"image type:'{image.type}' name:'{image.description}' architecture:'{image.architecture}' not found"
            )


def check_location(client: Client, location: Location):
    """Check if location exists."""
    if location is None:
        return None
    _location = client.locations.get_by_name(location.name)
    if not _location:
        raise LocationError(f"location '{location.name}' not found")
    return _location


def check_server_type(client: Client, server_type: ServerType):
    """Check if server type exists."""
    _type: ServerType = client.server_types.get_by_name(server_type.name)
    if not _type:
        raise ServerTypeError(f"server type '{server_type.name}' not found")
    return _type


def check_prices(client: Client):
    server_types: list[ServerType] = client.server_types.get_all()
    return {
        t.name.lower(): {
            price["location"]: float(price["price_hourly"]["gross"])
            for price in t.prices
        }
        for t in server_types
    }
