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


def check(args):
    """Check mandatory arguments."""

    def _check(name, value):
        if value:
            return
        value = "is not defined"
        print(
            f"argument error: --{name.lower().replace('_','-')} {value}",
            file=sys.stderr,
        )
        sys.exit(1)

    _check("GITHUB_TOKEN", args.github_token)
    _check("GITHUB_REPOSITORY", args.github_repository)
    _check("HETZNER_TOKEN", args.hetzner_token)
