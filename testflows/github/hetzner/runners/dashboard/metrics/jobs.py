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

from . import get


def summary():
    """Get jobs summary data.

    Returns:
        dict: Summary of jobs data
    """
    queued_jobs = get.metric_value("github_hetzner_runners_queued_jobs") or 0
    running_jobs = get.metric_value("github_hetzner_runners_running_jobs") or 0

    return {
        "queued": int(queued_jobs),
        "running": int(running_jobs),
        "total": int(queued_jobs + running_jobs),
    }
