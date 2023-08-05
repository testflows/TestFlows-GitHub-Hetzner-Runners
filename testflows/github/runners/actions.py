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
import logging

from .logger import logger


class Action:
    """Action class."""

    debug = False

    def __init__(
        self,
        name: str,
        ignore_fail: bool = False,
        level: int = logging.INFO,
        stacklevel: int = 2,
        run_id: str = "",
        job_id: str = "",
        server_name: str = "",
        interval: int = None,
    ):
        self.name = name
        self.ignore_fail = ignore_fail
        self.level = level
        self.stacklevel = stacklevel
        # try to parse run_id and job_id from server name if not specified
        try:
            _run_id, _job_id = server_name.rsplit("-", 2)[-2:]
            _run_id = int(_run_id)
            _job_id = int(_job_id)
            run_id = _run_id if run_id is None else run_id
            job_id = _job_id if job_id is None else job_id
        except Exception:
            pass

        self.extra = {
            "job_id": job_id,
            "run_id": run_id,
            "server_name": server_name,
            "interval": str(interval) if interval is not None else "",
        }

    def __enter__(self):
        logger.log(
            msg=f"➤ {self.name}",
            stacklevel=self.stacklevel + 1,
            level=self.level,
            extra=self.extra,
        )
        return self

    def note(self, message, stacklevel=None):
        logger.log(
            msg=f"  {message}",
            stacklevel=(self.stacklevel + 1) if stacklevel is None else stacklevel,
            level=self.level,
            extra=self.extra,
        )

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_value is not None:
            msg = f"❌ Error: {exc_type.__name__} {exc_value}"
            if not self.debug:
                logger.log(
                    msg=msg,
                    stacklevel=self.stacklevel + 1,
                    level=logging.ERROR,
                    extra=self.extra,
                )
            else:
                logger.exception(
                    msg=msg, stacklevel=self.stacklevel + 1, extra=self.extra
                )
            if self.ignore_fail:
                return True
            raise
