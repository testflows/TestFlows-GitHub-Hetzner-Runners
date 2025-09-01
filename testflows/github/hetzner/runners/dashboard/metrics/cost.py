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
    """Get cost summary data.

    Returns:
        dict: Summary of cost data
    """
    servers_info = get.metric_info("github_hetzner_runners_server")
    current_hourly_cost = 0.0

    if servers_info:
        for info in servers_info:
            try:
                cost_hourly = float(info.get("cost_hourly", 0))
                current_hourly_cost += cost_hourly
            except (ValueError, TypeError):
                continue

    return {
        "hourly": current_hourly_cost,
        "daily": current_hourly_cost * 24,
        "monthly": current_hourly_cost * 24 * 30,
    }
