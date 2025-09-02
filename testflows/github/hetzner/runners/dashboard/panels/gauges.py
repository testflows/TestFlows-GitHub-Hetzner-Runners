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
import logging
import streamlit as st
from .. import metrics

logger = logging.getLogger(__name__)


def render():
    """Render the metrics gauges section displaying key system metrics."""
    try:
        # Get metrics data
        heartbeat_status, _ = metrics.heartbeat.status()
        cost_summary = metrics.cost.summary()
        servers_summary = metrics.servers.summary()
        volumes_summary = metrics.volumes.summary()
        runners_summary = metrics.runners.summary()
        jobs_summary = metrics.jobs.summary()
        scale_up_errors_summary = metrics.errors.scale_up_summary()
        scale_down_errors_summary = metrics.errors.scale_down_summary()

        # Gauges in columns
        col1, col2, col3, col4, col5, col6, col7, col8, col9 = st.columns(
            9, gap="medium"
        )

        with col1:
            st.caption("Heartbeat")
            # Use st.text instead of st.markdown for heartbeat
            if heartbeat_status:
                st.metric(label="Heartbeat", value="🟢", label_visibility="collapsed")
            else:
                st.metric(label="Heartbeat", value="🔴", label_visibility="collapsed")

        with col2:
            st.caption("Cost (€/h)")
            st.metric(
                label="Cost (€/h)",
                value=f"{cost_summary['hourly']:.3f}",
                label_visibility="collapsed",
            )

        with col3:
            st.caption("Servers")
            st.metric(
                label="Servers",
                value=servers_summary["total"],
                label_visibility="collapsed",
            )

        with col4:
            st.caption("Volumes")
            st.metric(
                label="Volumes",
                value=volumes_summary["total"],
                label_visibility="collapsed",
            )

        with col5:
            st.caption("Runners")
            st.metric(
                label="Runners",
                value=runners_summary["total"],
                label_visibility="collapsed",
            )

        with col6:
            st.caption("Queued Jobs")
            st.metric(
                label="Queued Jobs",
                value=jobs_summary["queued"],
                label_visibility="collapsed",
            )

        with col7:
            st.caption("Running Jobs")
            st.metric(
                label="Running Jobs",
                value=jobs_summary["running"],
                label_visibility="collapsed",
            )

        with col8:
            st.caption("Scale Up Errors")
            st.metric(
                label="Scale Up Errors",
                value=scale_up_errors_summary["last_hour"],
                label_visibility="collapsed",
            )

        with col9:
            st.caption("Scale Down Errors")
            st.metric(
                label="Scale Down Errors",
                value=scale_down_errors_summary["last_hour"],
                label_visibility="collapsed",
            )

        st.divider()

    except Exception as e:
        logger.exception(f"Error fetching metrics: {e}")
        st.error(f"Error fetching metrics: {e}")
