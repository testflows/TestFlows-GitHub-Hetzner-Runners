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

from . import update_interval
from ...config import Config
from ... import __version__


@st.fragment()
def render(config: Config):
    """Render a modern, compact header section with logo, title, and update interval selector."""

    if "update_interval" in st.session_state:
        # Handle the update interval change
        selected_interval = st.session_state.update_interval
        if selected_interval == "Off":
            target_interval = None
        else:
            target_interval = selected_interval

        if update_interval.update_interval != target_interval:
            update_interval.update_interval = target_interval
            st.rerun()

    # Top row: Logo and title
    # col1, col2 = st.columns([1, 1], gap="small")

    with st.container(
        border=False,
        horizontal=True,
        gap="small",
        horizontal_alignment="left",
        vertical_alignment="bottom",
    ):
        st.markdown(
            '<a href="https://testflows.com" target="_blank"><img src="https://raw.githubusercontent.com/testflows/TestFlows-ArtWork/refs/heads/master/images/logo_multicolor.png" width="100" style="cursor: pointer;"></a>',
            unsafe_allow_html=True,
            width="content",
        )
        st.link_button(
            f"**GitHub Hetzner Runners** :small[{__version__}]",
            url=f"https://github.com/testflows/github-hetzner-runners/releases/tag/v{__version__}",
            type="secondary",
            width="content",
        )

        st.link_button(
            config.github_repository,
            url=f"https://github.com/{config.github_repository}",
            type="secondary",
            icon="💎",
        )

        with st.container(horizontal=True, gap="small", horizontal_alignment="right"):
            if st.button("Refresh", type="secondary", key="refresh"):
                st.rerun()

            st.selectbox(
                "Auto Refresh",
                options=["Off", 5, 10, 15, 30, 60, 300],
                format_func=lambda x: (
                    "Off"
                    if x == "Off"
                    else (
                        f"{x} seconds"
                        if x < 60
                        else f"{x//60} minute{'s' if x//60 > 1 else ''}"
                    )
                ),
                index=2,  # Default to 10 seconds instead of "Off"
                key="update_interval",
                label_visibility="collapsed",
                width=200,
            )
