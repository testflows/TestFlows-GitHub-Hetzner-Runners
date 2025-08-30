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
import os
from ...config import Config
from ...logger import decode_message
from ..colors import COLORS


def format_log(lines, columns, delimiter):
    """Format log lines for dashboard display.

    Args:
        lines: List of log lines to format
        columns: Dictionary mapping column names to (index, width) tuples
        delimiter: Column delimiter in the log line

    Returns:
        List of dictionaries containing formatted log entries
    """
    formatted_lines = []

    # Reverse lines to show most recent first
    for line in reversed(lines):
        # Split the line by delimiter and decode each part
        parts = line.strip().split(delimiter)
        if len(parts) < len(columns):  # Skip invalid lines
            continue

        # Decode all parts
        decoded_parts = [decode_message(part) for part in parts]

        # Format each column
        formatted_parts = {}
        for name, (index, _) in columns.items():
            value = decoded_parts[index]
            formatted_parts[name] = value

        formatted_lines.append(formatted_parts)

    return formatted_lines


def get_level_color(level):
    """Get color for log level.

    Args:
        level: Log level string

    Returns:
        str: Color code for the level
    """
    level_colors = {
        "DEBUG": COLORS["accent"],
        "INFO": COLORS["success"],
        "WARNING": COLORS["warning"],
        "ERROR": COLORS["error"],
        "CRITICAL": COLORS["error"],
    }
    return level_colors.get(level, COLORS["accent"])


def create_log_dataframe(formatted_lines):
    """Create a pandas DataFrame from formatted log lines.

    Args:
        formatted_lines: List of dictionaries containing formatted log entries

    Returns:
        pandas.DataFrame: DataFrame with log data
    """
    import pandas as pd

    # Convert to DataFrame
    df = pd.DataFrame(formatted_lines)

    # Combine date and time into one column
    if "date" in df.columns and "time" in df.columns:
        df["datetime"] = df["date"] + " " + df["time"]
        df = df.drop(["date", "time"], axis=1)

    # Reorder columns to put important ones first
    column_order = [
        "datetime",
        "level",
        "message",
        "run_id",
        "job_id",
        "server_name",
        "threadName",
        "funcName",
        "interval",
    ]
    existing_columns = [col for col in column_order if col in df.columns]
    other_columns = [col for col in df.columns if col not in column_order]

    # Reorder DataFrame
    df = df[existing_columns + other_columns]

    return df


def create_download_button(config: Config):
    """Create download button for full log file.

    Args:
        config: Configuration object containing logger settings
    """
    try:
        rotating_logfile = config.logger_config["handlers"]["rotating_logfile"][
            "filename"
        ]

        if os.path.exists(rotating_logfile):
            with open(rotating_logfile, "r") as f:
                log_content = f.read()

            st.download_button(
                label="Download Full Log",
                data=log_content,
                file_name="github-hetzner-runners.log",
                mime="text/plain",
                use_container_width=False,
                help="Download the complete log file",
            )
        else:
            st.warning("Log file not found")
    except Exception as e:
        st.error(f"Error creating download button: {str(e)}")


@st.fragment(run_every=st.session_state.update_interval)
def render(config: Config):
    """Render the log messages panel.

    Args:
        config: Configuration object containing logger settings
    """
    # Add CSS styling for dataframe
    st.markdown(
        """
    <style>
    .stDataFrame {
        font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace !important;
        font-size: 11px !important;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.header("Log Messages (Last 100 lines)")

    if config is None:
        st.warning("Configuration not available")
        return

    try:
        logger_format = config.logger_format
        rotating_logfile = config.logger_config["handlers"]["rotating_logfile"][
            "filename"
        ]

        columns = logger_format["columns"]
        delimiter = logger_format["delimiter"]

        # Read last 100 lines from log file
        if os.path.exists(rotating_logfile):
            with open(rotating_logfile, "r") as f:
                lines = f.readlines()[-100:]

            # Format log lines
            formatted_lines = format_log(lines, columns, delimiter)

            # Add download button at the top for better visibility
            create_download_button(config)
            st.markdown("<br>", unsafe_allow_html=True)

            # Create log dataframe
            if formatted_lines:
                df = create_log_dataframe(formatted_lines)

                # Display dataframe with sorting and filtering capabilities
                st.dataframe(
                    df,
                    use_container_width=True,
                    height=400,
                    hide_index=True,
                    column_config={
                        "message": st.column_config.TextColumn(
                            "Message", width="large", help="Log message content"
                        ),
                        "level": st.column_config.TextColumn(
                            "Level", width="small", help="Log level"
                        ),
                        "datetime": st.column_config.DatetimeColumn(
                            "DateTime", width="medium", help="Log date and time"
                        ),
                    },
                )
            else:
                st.info("No log messages available")
        else:
            st.warning("Log file not found")

    except Exception as e:
        st.error(f"Error reading log file: {str(e)}")
