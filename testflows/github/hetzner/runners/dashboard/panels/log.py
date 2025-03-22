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
from dash import html
from flask import send_file

from ..colors import COLORS
from ...logger import decode_message
from . import panel


def create_panel():
    """Create the log panel."""
    return panel.create_panel("Log Messages (Last 100 lines)", with_graph=False)


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


def create_log_list(formatted_lines):
    """Create a list of log messages.

    Args:
        formatted_lines: List of dictionaries containing formatted log entries

    Returns:
        HTML div containing the log messages list
    """
    messages = []

    for entry in formatted_lines:
        message_parts = []

        # Special handling for level column to set color
        level_color = {
            "DEBUG": COLORS["accent"],
            "INFO": COLORS["success"],
            "WARNING": COLORS["warning"],
            "ERROR": COLORS["error"],
            "CRITICAL": COLORS["error"],
        }.get(entry.get("level", ""), COLORS["accent"])

        # Process each column in the entry
        for key, value in entry.items():
            if key == "level":
                # Special formatting for level column
                message_parts.append(
                    html.Span(
                        f"[{value}] ",
                        style={"color": level_color, "fontWeight": "bold"},
                    )
                )
            elif key in ["date", "time"]:
                # Special formatting for date/time columns
                message_parts.append(
                    html.Span(
                        f"{value} ",
                        style={"color": COLORS["accent"]},
                    )
                )
            elif key == "message":
                # Special formatting for message column
                message_parts.append(
                    html.Span(
                        f"{value}",
                        style={"color": COLORS["text"]},
                    )
                )
            elif key in ["run_id", "job_id"]:
                # Special formatting for run and job IDs
                message_parts.append(
                    html.Span(
                        f"[{key}: {value}] ",
                        style={"color": COLORS["success"]},
                    )
                )
            elif key in ["threadName", "funcName"]:
                # Special formatting for thread and function names
                message_parts.append(
                    html.Span(
                        f"[{key}: {value}] ",
                        style={"color": COLORS["warning"]},
                    )
                )
            elif key == "server_name":
                # Special formatting for server name
                message_parts.append(
                    html.Span(
                        f"[{key}: {value}] ",
                        style={"color": COLORS["accent"], "fontWeight": "bold"},
                    )
                )
            elif key == "interval":
                # Special formatting for interval
                message_parts.append(
                    html.Span(
                        f"[{key}: {value}] ",
                        style={"color": COLORS["accent"]},
                    )
                )
            else:
                # Default formatting for any other columns
                message_parts.append(
                    html.Span(
                        f"[{key}: {value}] ",
                        style={"color": COLORS["accent"]},
                    )
                )

        messages.append(
            html.Div(
                message_parts,
                style={"marginBottom": "5px"},
            )
        )

    # Create the scrolling list
    list_div = panel.create_list(
        "log-messages", len(formatted_lines), messages, "No log messages"
    )

    # Create the download button div
    download_div = html.Div(
        style={
            "textAlign": "center",
            "padding-top": "20px",
        },
        children=[
            html.A(
                "Download Full Log",
                id="log-messages-download",
                href="/download-log",
                download="github_hetzner_runners.log",
                style={
                    "color": COLORS["accent"],
                    "textDecoration": "none",
                    "padding": "8px 16px 8px 16px",
                    "border": f"1px solid {COLORS['accent']}",
                    "borderRadius": "4px",
                    "fontFamily": "JetBrains Mono, Fira Code, Consolas, monospace",
                },
            ),
        ],
    )

    # Return both divs wrapped in a container
    return html.Div([list_div, download_div])


def update_log_messages(n, github_hetzner_runners_config):
    """Update log messages display.

    Args:
        n: Number of intervals
        flask_config: Flask config object containing logger format settings

    Returns:
        list: List of HTML elements for log messages
    """
    try:
        logger_format = github_hetzner_runners_config.logger_format
        rotating_logfile = github_hetzner_runners_config.logger_config["handlers"][
            "rotating_logfile"
        ]["filename"]

        columns = logger_format["columns"]
        delimiter = logger_format["delimiter"]

        # Read last 100 lines from log file
        with open(rotating_logfile, "r") as f:
            lines = f.readlines()[-100:]

        # Format log lines
        formatted_lines = format_log(lines, columns, delimiter)

        # Create HTML elements for log messages
        return create_log_list(formatted_lines)
    except Exception as e:
        return [html.Div(f"Error reading log file: {str(e)}", style={"color": "red"})]


def download_log(github_hetzner_runners_config):
    """Download the full log file.

    Args:
        github_hetzner_runners_config: Configuration object containing logger settings

    Returns:
        flask.Response: Response object containing the log file
    """
    try:
        rotating_logfile = github_hetzner_runners_config.logger_config["handlers"][
            "rotating_logfile"
        ]["filename"]
        return send_file(
            rotating_logfile,
            as_attachment=True,
            download_name="github-hetzner-runners.log",
            mimetype="text/plain",
        )
    except Exception as e:
        return str(e), 500
