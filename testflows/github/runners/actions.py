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
    ):
        self.name = name
        self.ignore_fail = ignore_fail
        self.level = level

    def __enter__(self):
        logger.log(msg=f"🍀 {self.name}", stacklevel=2, level=self.level)
        return self

    def note(self, message):
        logger.log(msg=f"   {message}", stacklevel=2, level=self.level)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_value is not None:
            msg = f"❌ Error: {exc_type.__name__} {exc_value}"
            if not self.debug:
                logger.log(msg=msg, stacklevel=2, level=logging.ERROR)
            else:
                logger.exception(msg=msg, stacklevel=3)
            if self.ignore_fail:
                return True
            raise
