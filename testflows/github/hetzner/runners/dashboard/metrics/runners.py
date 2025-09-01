# Copyright 2025 Katteli Inc.
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

from collections import defaultdict
from . import get
from . import utils


def summary():
    """Get runners summary data.

    Returns:
        dict: Summary of runners data
    """
    total_runners = get.metric_value("github_hetzner_runners_runners_total_count") or 0
    runners_info = get.metric_info("github_hetzner_runners_runner")

    return {
        "total": int(total_runners),
        "details": runners_info,
        "by_status": utils.count_by_status(runners_info, "status"),
    }


def standby_summary():
    """Get standby runners summary data.

    Returns:
        dict: Summary of standby runners data
    """
    runners_info = get.metric_info("github_hetzner_runners_runner")

    # Filter for standby runners
    standby_runners = [
        r
        for r in runners_info
        if r.get("name", "").startswith("github-hetzner-runner-standby-")
    ]

    # Calculate totals by status
    standby_by_status = defaultdict(int)
    total_standby = len(standby_runners)

    for runner in standby_runners:
        status = runner.get("status", "unknown")
        standby_by_status[status] += 1

    return {
        "total": total_standby,
        "details": standby_runners,
        "by_status": dict(standby_by_status),
    }
