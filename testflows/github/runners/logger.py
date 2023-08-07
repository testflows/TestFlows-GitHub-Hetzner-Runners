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
import sys
import logging
import logging.handlers
import tempfile

rotating_service_logfile = os.path.join(tempfile.gettempdir(), "github-runners.log")

logger = logging.getLogger("testflows.github.runners")


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

format = {
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
}


def default_config(level=logging.INFO, service_mode=False):
    """Apply default logging configuration."""
    global logger

    logger.logger.setLevel(level)

    # stream to stdout
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt=("%(asctime)s %(message)s"),
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.logger.addHandler(handler)

    # in service mode write to rotating file
    if service_mode:
        os.system(f"rm -rf {rotating_service_logfile}*")
        maxBytes = 10485760  # 10MB
        rotating_file_handler = logging.handlers.RotatingFileHandler(
            rotating_service_logfile, maxBytes=maxBytes, backupCount=1
        )
        rotating_file_formatter = logging.Formatter(
            fmt=(
                "%(asctime)s,%(interval)s,%(levelname)s,%(run_id)s,%(job_id)s,%(server_name)s,%(threadName)s,%(funcName)s,%(message)s"
            ),
            datefmt="%Y-%m-%d,%H:%M:%S",
        )
        rotating_file_handler.setFormatter(rotating_file_formatter)
        logger.logger.addHandler(rotating_file_handler)
