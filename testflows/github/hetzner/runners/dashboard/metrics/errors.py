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
    """Get errors summary data.

    Returns:
        dict: Summary of errors data
    """
    error_count = (
        get.metric_value("github_hetzner_runners_scale_up_failures_last_hour") or 0
    )
    errors_info = get.metric_info("github_hetzner_runners_scale_up_failure")

    return {"last_hour": int(error_count), "details": errors_info}
