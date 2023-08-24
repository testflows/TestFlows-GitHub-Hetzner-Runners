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
import time

from threading import Event
from github import Github

from .actions import Action


def api_watch(terminate: Event, github_token: str, interval: int = 60):
    """Watch API calls consumption."""

    with Action("Logging in to GitHub"):
        github = Github(login_or_token=github_token)

    with Action("Checking current API calls consumption rate"):
        calls, total = github.rate_limiting
        with Action(f"Consumed {total-calls} calls out of {total}"):
            pass

    i = 0
    while True:
        if terminate.is_set():
            with Action("Terminating rate limit watch service"):
                break

        if i >= interval:
            with Action("Logging in to GitHub"):
                github = Github(login_or_token=github_token)
                github.get_rate_limit
            with Action("Checking current API calls consumption rate"):
                current, total = github.rate_limiting
                next_resettime = github.rate_limiting_resettime

                with Action(
                    f"Consumed {(calls-current) if not calls < current else (total-current)} calls in {interval} sec, {current} calls left, reset in {int(next_resettime - time.time())} sec"
                ):
                    calls = current
            i = 0

        time.sleep(1)
        i += 1
