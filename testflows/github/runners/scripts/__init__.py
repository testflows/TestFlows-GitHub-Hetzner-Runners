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
import os

from dataclasses import dataclass
from collections import namedtuple


@dataclass
class Scripts:
    setup: str
    startup_x64: str
    startup_arm64: str


current_dir = os.path.dirname(__file__)

scripts = Scripts(
    setup=os.path.join(current_dir, "setup.sh"),
    startup_x64=os.path.join(current_dir, "startup_x64.sh"),
    startup_arm64=os.path.join(current_dir, "startup_arm64.sh"),
)
