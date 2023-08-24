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
import sys
import time
import subprocess

from .logger import logger


def shell(
    cmd: str,
    shell: bool = True,
    check: bool = True,
    use_logger=True,
    stacklevel=2,
    server_name=None,
):
    """Execute command."""
    p = subprocess.Popen(
        cmd,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=True,
        text=True,
        encoding="utf-8",
    )

    for line in iter(p.stdout.readline, ""):
        if line == "":
            time.sleep(0.1)
            continue
        if use_logger:
            logger.info(
                f"   > {line.rstrip()}",
                stacklevel=stacklevel,
                extra={"server_name": server_name},
            )
        else:
            sys.stdout.write(line.rstrip())
            sys.stdout.write("\n")
            sys.stdout.flush()

    p.wait()

    if check:
        assert p.returncode == 0, f"{cmd} returned non-zero exit code {p.returncode}"

    return p.returncode
