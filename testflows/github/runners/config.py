import os
import sys

from dataclasses import dataclass

from hcloud import Client
from hcloud.images.domain import Image

import testflows.github.runners.args as args


class ImageNotFoundError(Exception):
    pass


path = args.path_type
count = args.count_type
image = args.image_type
location = args.location_type
server_type = args.server_type


@dataclass
class standby_runner:
    labels: list[str]
    count: count = 1
    replenish_immediately: bool = True


@dataclass
class deploy:
    server_type: server_type = "cpx11"
    image: image = image("system:ubuntu-22.04")
    location: location = None
    setup_script: path = None


@dataclass
class cloud:
    server_name: str = "github-runners"
    deploy: deploy = deploy()


@dataclass
class Config:
    """Program configuration class."""

    github_token: str = os.getenv("GITHUB_TOKEN")
    github_repository: str = os.getenv("GITHUB_REPOSITORY")
    hetzner_token: str = os.getenv("HETZNER_TOKEN")
    ssh_key: str = os.path.expanduser("~/.ssh/id_rsa.pub")
    max_runners: count = 10
    default_image: image = image("system:ubuntu-22.04")
    default_server_type: server_type = server_type("cx11")
    default_location: location = None
    workers: count = 10
    setup_script: path = None
    startup_x64_script: path = None
    startup_arm64_script: path = None
    max_powered_off_time: count = 60
    max_unused_runner_time: count = 120
    max_runner_registration_time: count = 120
    max_server_ready_time: count = 120
    scale_up_interval: count = 15
    scale_down_interval: count = 15
    debug: bool = False
    # special
    logger_config: dict = None
    cloud: cloud = cloud()
    standby_runners: list[standby_runner] = None
    config_file: path = None

    def __post_init__(self):
        if self.standby_runners is None:
            self.standby_runners = []

    def update(self, args):
        """Update configuration file using command line arguments."""
        for attr in vars(self):
            if attr in ["config_file", "logger_config", "cloud", "standby_runners"]:
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


def check_image(client: Client, image: Image):
    """Check if image exists.
    If image type is not 'system' then use image description to find it.
    """

    if image.type in ("system", "app"):
        return client.images.get_by_name(image.name)
    else:
        # backup or snapshot
        try:
            return [
                i
                for i in client.images.get_all(type=image.type)
                if i.description == image.description
            ][0]
        except IndexError:
            raise ImageNotFoundError(f"{image.type}:{image.description} not found")
