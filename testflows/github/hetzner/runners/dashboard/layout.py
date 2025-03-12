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
from .colors import COLORS

# Layout configuration that will be used across all plots
LAYOUT_STYLE = {
    "paper_bgcolor": COLORS["paper"],
    "plot_bgcolor": COLORS["background"],
    "font": {
        "color": COLORS["text"],
        "family": "JetBrains Mono, Fira Code, Consolas, monospace",
        "size": 11,
    },
    "xaxis": {
        "gridcolor": COLORS["grid"],
        "showgrid": True,
        "title_font": {
            "family": "JetBrains Mono, Fira Code, Consolas, monospace",
            "size": 12,
        },
        "tickfont": {
            "family": "JetBrains Mono, Fira Code, Consolas, monospace",
            "size": 10,
        },
    },
    "yaxis": {
        "gridcolor": COLORS["grid"],
        "showgrid": True,
        "title_font": {
            "family": "JetBrains Mono, Fira Code, Consolas, monospace",
            "size": 12,
        },
        "tickfont": {
            "family": "JetBrains Mono, Fira Code, Consolas, monospace",
            "size": 10,
        },
    },
}
