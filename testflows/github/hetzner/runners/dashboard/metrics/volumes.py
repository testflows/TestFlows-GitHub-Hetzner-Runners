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
from . import utils


def summary():
    """Get volumes summary data.

    Returns:
        dict: Summary of volumes data
    """
    total_volumes = get.metric_value("github_hetzner_runners_volumes_total_count") or 0
    volumes_info = get.metric_info("github_hetzner_runners_volume")

    return {
        "total": int(total_volumes),
        "details": volumes_info,
        "by_status": utils.count_by_status(volumes_info, "status"),
    }
