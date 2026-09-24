import os
import re
import yaml

from argparse import ArgumentTypeError

from .. import errors
from ..providers.hetzner import config as hetzner_config
from ..providers.aws import config as aws_config
from ..providers.scaleway import config as scaleway_config

# Validators re-exported from the argtypes leaf under their historical names
# (config.parse still does `from .config import path`).
from ..argtypes import (
    path_type as path,
    count_type as count,
    image_type as image,
    location_type as location,
    server_type,
    end_of_life_type as end_of_life,
    meta_label_type,
)

# Schema dataclasses re-exported from the config_schema leaf for backward
# compat. Providers import them from config_schema directly (never this module)
# to avoid the config <-> providers import cycle.
from ..config_schema import (
    standby_runner,
    provider_defaults,
    hetzner_provider,
    aws_provider,
    scaleway_provider,
    dedicated_static_ssh,
    dedicated_static_group,
    dedicated_static_provider,
    provider_list,
    deploy_,
    cloud,
    Config,
)

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


# Re-export error classes from errors module for backwards compatibility
ConfigError = errors.ConfigError
LocationError = errors.LocationError
ImageError = errors.ImageError
SetupScriptError = errors.SetupScriptError
RecycleScriptError = errors.RecycleScriptError
StartupScriptError = errors.StartupScriptError
ServerTypeError = errors.ServerTypeError


# Top-level Config fields that have a matching CLI flag. apply_args copies a
# provided (non-None) arg onto each of these. It is an allow-list on purpose:
# a newly added Config field is not overridable until it is listed here, which
# fails safe. A forgotten entry merely drops a CLI override; a deny-list would
# instead let a forgotten entry clobber structural config. Nested/structural
# fields (providers, cloud, standby_runners, ...) are applied through their own
# seams below, not here.
_CLI_OVERRIDABLE_FIELDS = (
    "github_token",
    "github_repository",
    "ssh_key",
    "with_label",
    "label_prefix",
    "meta_label",
    "recycle",
    "recycle_grace_period",
    "end_of_life",
    "delete_random",
    "max_runners",
    "max_runners_for_label",
    "max_runners_in_workflow_run",
    "workers",
    "scripts",
    "max_powered_off_time",
    "max_unused_runner_time",
    "max_runner_registration_time",
    "max_server_ready_time",
    "scale_up_interval",
    "scale_down_interval",
    "metrics_port",
    "metrics_host",
    "dashboard_port",
    "dashboard_host",
    "debug",
    "service_mode",
    "embedded_mode",
    "enabled_providers",
)


def coerce_deploy_field(cloud_provider: str, field: str, value):
    """Coerce one ``cloud.deploy.*`` value for *cloud_provider*.

    Hetzner deploy specs are hcloud-typed (``Location``/``ServerType``/``Image``);
    every other provider keeps its native string, validated later at deploy time
    by that provider's own ``get_image``/``get_server_type``/``get_location``.
    Shared by the CLI path (``apply_args``) and the config-file path
    (``parse.py``), so a Hetzner deploy target is validated the same way
    regardless of where the value came from. Raises a plain ``ValueError``
    naming only the bad value, not the surface it arrived through — each
    caller adds its own context (a CLI option name, or a config path).
    """
    if value is None or cloud_provider != "hetzner":
        return value
    factory = {"server_type": server_type, "image": image, "location": location}[
        field
    ]
    try:
        return factory(value)
    except Exception as e:
        raise ValueError(str(e)) from e


# Option name for each cloud.deploy field, used only by the CLI path below to
# name the flag in its ArgumentTypeError.
_DEPLOY_FIELD_OPTIONS = {
    "server_type": "-t/--type",
    "image": "-i/--image",
    "location": "-l/--location",
}


def apply_args(config, args):
    """Apply command-line argument overrides onto a Config."""
    for attr in _CLI_OVERRIDABLE_FIELDS:
        arg_value = getattr(args, attr, None)
        if arg_value is not None:
            setattr(config, attr, arg_value)

    # Provider configuration is nested and intentionally skipped above.
    # Apply Hetzner-specific CLI overrides through its provider update hook.
    if config.providers.hetzner is not None:
        hetzner_config.update_from_args(config.providers.hetzner, args)
    elif getattr(args, "hetzner_token", None):
        config.providers.hetzner = hetzner_provider()
        hetzner_config.update_from_args(config.providers.hetzner, args)

    # Apply AWS CLI overrides. Create from flags only with both keys.
    if config.providers.aws is not None:
        aws_config.update_from_args(config.providers.aws, args)
    elif getattr(args, "aws_access_key_id", None) and getattr(
        args, "aws_secret_access_key", None
    ):
        config.providers.aws = aws_provider()
        aws_config.update_from_args(config.providers.aws, args)

    # Apply Scaleway CLI overrides. Create from flags only with all three credentials.
    if config.providers.scaleway is not None:
        scaleway_config.update_from_args(config.providers.scaleway, args)
    elif (
        getattr(args, "scaleway_access_key", None)
        and getattr(args, "scaleway_secret_key", None)
        and getattr(args, "scaleway_project_id", None)
    ):
        config.providers.scaleway = scaleway_provider()
        scaleway_config.update_from_args(config.providers.scaleway, args)

    if getattr(args, "cloud_server_name", None) is not None:
        config.cloud.server_name = args.cloud_server_name

    if getattr(args, "cloud_host", None) is not None:
        config.cloud.host = args.cloud_host

    if getattr(args, "cloud_user", None) is not None:
        config.cloud.ssh_user = args.cloud_user

    # -l/-t/-i are validated for whichever provider will actually deploy to,
    # not always Hetzner. A bad value is a bad CLI option, so it is reported
    # as one: ArgumentTypeError naming the flag, not coerce_deploy_field's
    # bare ValueError (parse.py's config-file path uses that one as-is, since
    # there it's a bad YAML value rather than a bad flag).
    for dest, field in (
        ("cloud_deploy_location", "location"),
        ("cloud_deploy_server_type", "server_type"),
        ("cloud_deploy_image", "image"),
    ):
        raw_value = getattr(args, dest, None)
        if raw_value is not None:
            try:
                setattr(
                    config.cloud.deploy,
                    field,
                    coerce_deploy_field(config.cloud.provider, field, raw_value),
                )
            except ValueError as e:
                option = _DEPLOY_FIELD_OPTIONS[field]
                raise ArgumentTypeError(
                    f"invalid value for {option} ({raw_value!r}): {e}"
                ) from e

    if getattr(args, "cloud_deploy_setup_script", None) is not None:
        config.cloud.deploy.setup_script = args.cloud_deploy_setup_script


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


def check_recycle_script(script: str):
    """Check if recycle script is valid."""
    if not os.path.exists(script):
        raise errors.RecycleScriptError(f"invalid recycle script path '{script}'")
    return script
