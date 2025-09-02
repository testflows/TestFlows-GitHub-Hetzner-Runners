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

import testflows.github.hetzner.runners.dashboard.panels.update_interval as update_interval


@st.fragment()
def render():
    """Render a modern, compact header section with logo, title, and update interval selector."""

    if update_interval.update_interval != st.session_state.update_interval:
        update_interval.update_interval = st.session_state.update_interval
        st.rerun()

    # Top row: Logo and title
    col1, col2 = st.columns([5, 1])

    with col1:
        logo_col, title_col = st.columns([1, 9], vertical_alignment="center")
        with logo_col:
            st.markdown(
                '<a href="https://testflows.com" target="_blank"><img src="https://raw.githubusercontent.com/testflows/TestFlows-ArtWork/refs/heads/master/images/logo_multicolor.png" width="150" style="cursor: pointer;"></a>',
                unsafe_allow_html=True,
            )

        with title_col:
            st.subheader("GitHub Hetzner Runners")

    with col2:
        st.selectbox(
            "Update Interval",
            options=[5, 10, 15, 30, 60, 300],
            format_func=lambda x: (
                f"{x} seconds"
                if x < 60
                else f"{x//60} minute{'s' if x//60 > 1 else ''}"
            ),
            index=0,
            key="update_interval",
            label_visibility="collapsed",
        )
