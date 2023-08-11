# Copyright 2023 Katteli Inc.
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
import os
import json
import logging
import logging.handlers
import tempfile

logger = logging.getLogger("testflows.github.runners")


class StdoutHandler(logging.StreamHandler):
    def emit(self, record):
        if record.msg.startswith("__json__:"):
            try:
                record.msg = json.loads(record.msg[9:])
            except Exception:
                # ignore any errors
                pass
        return super(StdoutHandler, self).emit(record)


class RotatingFileHandler(logging.handlers.RotatingFileHandler):
    pass


class LoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        if kwargs.get("extra") is None:
            kwargs["extra"] = self.extra
        else:
            extra = {}
            for k, v in self.extra.items():
                extra[k] = kwargs["extra"].get(k, v)
            kwargs["extra"] = extra

        if kwargs.get("extra"):
            if kwargs["extra"].get("server_name"):
                server_name = kwargs["extra"]["server_name"]
                try:
                    run_id, job_id = server_name.rsplit("-", 2)[-2:]
                    if kwargs["extra"]["run_id"] in ("-", ""):
                        kwargs["extra"]["run_id"] = int(run_id)
                    if kwargs["extra"]["job_id"] in ("-", ""):
                        kwargs["extra"]["job_id"] = int(job_id)
                except Exception:
                    pass

        msg = "__json__:" + json.dumps(str(msg))
        return msg, kwargs


logger = LoggerAdapter(
    logger,
    {
        "run_id": "-",
        "job_id": "-",
        "server_name": "-",
        "interval": "-",
    },
)

#: default logger format
default_format = {
    "default": [
        {"column": "time"},
        {"column": "funcName"},
        {"column": "level"},
        {"column": "message"},
    ],
    "delimiter": ",",
    "columns": {
        "date": (0, 10),
        "time": (1, 8),
        "interval": (2, 5),
        "level": (3, 8),
        "run_id": (4, 11),
        "job_id": (5, 11),
        "server_name": (6, 36),
        "threadName": (7, 20),
        "funcName": (8, 14),
        "message": (9, 90),
    },
}


def configure(config, level=logging.INFO, service_mode=False):
    """Apply logging configuration."""

    default_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "stdout": {
                "format": "%(asctime)s %(message)s",
                "datefmt": "%H:%M:%S",
            },
            "rotating_file": {
                "format": (
                    "%(asctime)s,%(interval)s,%(levelname)s,"
                    "%(run_id)s,%(job_id)s,%(server_name)s,"
                    "%(threadName)s,%(funcName)s,%(message)s"
                ),
                "datefmt": "%Y-%m-%d,%H:%M:%S",
            },
        },
        "handlers": {
            "stdout": {
                "level": str(level),
                "formatter": "stdout",
                "class": "testflows.github.runners.logger.StdoutHandler",
                "stream": "ext://sys.stdout",
            },
            "rotating_service_logfile": {
                "level": str(level),
                "formatter": "rotating_file",
                "class": "testflows.github.runners.logger.RotatingFileHandler",
                "filename": os.path.join(tempfile.gettempdir(), "github-runners.log"),
                "maxBytes": 52428800,  # 50MB 50*2**20
                "backupCount": 10,
            },
        },
        "loggers": {
            "testflows.github.runners": {
                "level": str(level),
                "handlers": ["stdout", "rotating_service_logfile"],
            }
        },
    }

    level = logging.getLevelName(level)

    if config.logger_config is None:
        config.logger_config = default_config

    logger_config = config.logger_config

    if not service_mode:
        handlers = set(logger_config["loggers"]["testflows.github.runners"]["handlers"])
        handlers.discard("rotating_service_logfile")
        logger_config["loggers"]["testflows.github.runners"]["handlers"] = list(
            handlers
        )
    else:
        if (
            "rotating_service_logfile"
            not in logger_config["loggers"]["testflows.github.runners"]["handlers"]
        ):
            logger_config["loggers"]["testflows.github.runners"]["handlers"].append(
                "rotating_service_logfile"
            )

    for handler in logger_config["handlers"].values():
        handler["level"] = level

    logger_config["loggers"]["testflows.github.runners"]["level"] = level

    logging.config.dictConfig(logger_config)
