# https://github.com/testflows/testflows-github-runners
#
# TestFlows Auto-scaling GitHub Runners Using Hetzner Cloud
# Configuration File
from testflows.github.runners.config import *

# logging module config defined as a dictionary
# see https://docs.python.org/3/library/logging.config.html#logging-config-dictschema
logger_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)8s %(threadName)16s %(funcName)15s %(message)s",
            "datefmt": "%m/%d/%Y %I:%M:%S %p",
        },
    },
    "handlers": {
        "default": {
            "level": "INFO",
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "testflows.github.runners": {"level": "INFO", "handlers": ["default"]},
    },
}

# custom configuration
config = Config(
    github_token=os.getenv("GITHUB_TOKEN"),
    github_repository=os.getenv("GITHUB_REPOSITORY"),
    hetzner_token=os.getenv("HETZNER_TOKEN"),
    ssh_key=os.path.expanduser("~/.ssh/id_rsa.pub"),
    max_runners=count(10),
    recycle=True,
    end_of_life=count(50),
    default_image=image("system:ubuntu-22.04"),
    default_server_type=server_type("cpx11"),
    default_location=location("ash"),
    workers=count(10),
    setup_script=None,
    startup_x64_script=None,
    startup_arm64_script=None,
    max_powered_off_time=count(60),
    max_unused_runner_time=count(120),
    max_runner_registration_time=count(120),
    max_server_ready_time=count(120),
    scale_up_interval=count(15),
    scale_down_interval=count(15),
    debug=False,
    logger_config=logger_config,
    cloud=cloud(
        server_name="github-runners",
        deploy=deploy(
            server_type=server_type("cpx11"),
            image=image("system:ubuntu-22.04"),
            location=location("ash"),
            setup_script=None,
        ),
    ),
    standby_runners=[
        standby_runner(
            labels=["type-cpx21"], count=count(3), replenish_immediately=True
        )
    ],
)
