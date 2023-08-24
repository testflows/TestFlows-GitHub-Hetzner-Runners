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
import copy
import logging
import logging.handlers
import tempfile

logger = logging.getLogger("testflows.github.hetzner.runners")

encoded_message_prefix = "✉ "


def decode_message(msg):
    """Decode encoded message."""
    if msg.startswith(encoded_message_prefix):
        try:
            return json.loads(msg[len(encoded_message_prefix) :])
        except Exception:
            # ignore any errors if we failed to decode column as json
            pass
    return msg


def encode_message(msg):
    """Encode message."""
    return json.dumps(msg)


class RotatingFileFormatter(logging.Formatter):
    def format(self, record):
        """Format record and convert multi-line message to text which includes exception or stacktrace if present."""
        message = record.getMessage()

        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)

        if record.exc_text:
            if message[-1:] != "\n":
                message = message + "\n"
            message = message + record.exc_text
        if record.stack_info:
            if message[-1:] != "\n":
                message = message + "\n"
            message = message + self.formatStack(record.stack_info)

        record.message = encoded_message_prefix + encode_message(message)
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)

        s = self.formatMessage(record)
        return s


class RotatingFileHandler(logging.handlers.RotatingFileHandler):
    pass


class StdoutHandler(logging.StreamHandler):
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
                "class": "testflows.github.hetzner.runners.logger.RotatingFileFormatter",
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
                "class": "testflows.github.hetzner.runners.logger.StdoutHandler",
                "stream": "ext://sys.stdout",
            },
            "rotating_service_logfile": {
                "level": str(level),
                "formatter": "rotating_file",
                "class": "testflows.github.hetzner.runners.logger.RotatingFileHandler",
                "filename": os.path.join(
                    tempfile.gettempdir(), "github-hetzner-runners.log"
                ),
                "maxBytes": 52428800,  # 50MB 50*2**20
                "backupCount": 10,
            },
        },
        "loggers": {
            "testflows.github.hetzner.runners": {
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
        handlers = set(
            logger_config["loggers"]["testflows.github.hetzner.runners"]["handlers"]
        )
        handlers.discard("rotating_service_logfile")
        logger_config["loggers"]["testflows.github.hetzner.runners"]["handlers"] = list(
            handlers
        )
    else:
        if (
            "rotating_service_logfile"
            not in logger_config["loggers"]["testflows.github.hetzner.runners"][
                "handlers"
            ]
        ):
            logger_config["loggers"]["testflows.github.hetzner.runners"][
                "handlers"
            ].append("rotating_service_logfile")

    for handler in logger_config["handlers"].values():
        handler["level"] = level

    logger_config["loggers"]["testflows.github.hetzner.runners"]["level"] = level

    logging.config.dictConfig(logger_config)
