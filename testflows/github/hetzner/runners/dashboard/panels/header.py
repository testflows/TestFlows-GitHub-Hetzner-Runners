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
    """Render the header section with logo, title, and update interval selector."""

    if update_interval.update_interval != st.session_state.update_interval:
        update_interval.update_interval = st.session_state.update_interval
        st.rerun()

    # Logo using HTML img tag for full styling control with clickable link
    st.markdown(
        f'<a href="https://testflows.com" target="_blank"><img src="https://raw.githubusercontent.com/testflows/TestFlows-ArtWork/refs/heads/master/images/logo.png" width="120" style="border-radius: 0; border: none; box-shadow: none; cursor: pointer;"></a>',
        unsafe_allow_html=True,
    )

    # Header section
    col1, col2 = st.columns([3, 1], gap="medium")

    with col1:
        st.markdown("### GitHub Hetzner Runners Dashboard")

    with col2:
        st.caption("update interval:")
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

    st.divider()
