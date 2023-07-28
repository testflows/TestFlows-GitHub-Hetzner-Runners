from dataclasses import dataclass

import testflows.github.runners.args as args


class path:
    def __init__(self, path):
        self.value = args.path_type(path)


class count:
    def __init__(self, count):
        self.value = args.count_type(count)


class image:
    """:param image: type:name_or_description, example: system:ubuntu-22.04"""

    def __init__(self, image: str):
        self.value = args.image_type(image)


class location:
    """:param location: ash, nbg1, etc."""

    def __init__(self, location: str):
        self.value = args.location_type(location)


class server_type:
    """:param type: either cx11, cpx11, ... etc."""

    def __init__(self, type: str):
        self.value = args.server_type(type)


@dataclass
class Config:
    """Program configuration class."""

    github_token: str = None
    github_repository: str = None
    hetzner_token: str = None
    ssh_key: str = None
    max_runners: count = None
    default_image: image = None
    default_server_type: server_type = None
    default_location: location = None
    workers: count = None
    logger_config: path = None
    setup_script: path = None
    startup_x64_script: path = None
    startup_arm64_script: path = None
    max_powered_off_time: count = None
    max_idle_runner_time: count = None
    max_runner_registration_time: count = None
    max_server_ready_time: count = None
    scale_up_interval: count = None
    scale_down_interval: count = None
