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
import streamlit as st
from datetime import datetime

from testflows.github.hetzner.runners import __version__
from .. import renderers


def render():
    """Render the footer section with copyright and version information."""

    with renderers.errors("rendering footer"):
        with st.container(border=False, horizontal_alignment="center"):
            st.caption(
                f"© 2023-{datetime.now().year} Katteli Inc. All rights reserved.",
                width="content",
            )
            st.caption(
                f"TestFlows GitHub Hetzner Runners v{__version__}", width="content"
            )
