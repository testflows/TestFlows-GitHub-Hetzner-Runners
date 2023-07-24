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
import subprocess

logger = logging.getLogger("testflows.github.runners")


def shell(cmd: str, shell: bool = True, check: bool = True):
    """Execute command."""
    p = subprocess.run(
        cmd,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
        bufsize=1,
        universal_newlines=True,
    )
    for line in p.stdout.splitlines():
        logger.info(f"   > {line}", stacklevel=2)

    return p.returncode
