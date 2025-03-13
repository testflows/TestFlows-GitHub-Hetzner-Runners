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

from datetime import datetime, timedelta
from dash import html, dcc

from ..colors import COLORS
from ..metrics import get_metric_value, metric_history, get_metric_info


def create_job_list():
    """Create a list of jobs with their descriptions."""
    queued_jobs_info = get_metric_info("github_hetzner_runners_queued_job")
    running_jobs_info = get_metric_info("github_hetzner_runners_running_job")
    queued_count = get_metric_value("github_hetzner_runners_queued_jobs") or 0
    running_count = get_metric_value("github_hetzner_runners_running_jobs") or 0

    if queued_count == 0 and running_count == 0:
        return html.Div(
            "No jobs",
            style={
                "color": COLORS["text"],
                "padding": "10px",
                "fontFamily": "JetBrains Mono, Fira Code, Consolas, monospace",
            },
        )

    job_items = []
    # Process both queued and running jobs
    for jobs_info, is_running in [(queued_jobs_info, False), (running_jobs_info, True)]:
        if not jobs_info:
            continue

        for key, _ in jobs_info.items():
            try:
                # Parse the key string into a dictionary
                info = {}
                for item in key.split(","):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        info[k] = v

                job_id = info.get("job_id")
                run_id = info.get("run_id")
                if not job_id or not run_id:
                    continue

                # Get wait time for this job
                metric_name = (
                    "github_hetzner_runners_running_job_time_seconds"
                    if is_running
                    else "github_hetzner_runners_queued_job_wait_time_seconds"
                )
                time_value = get_metric_value(
                    metric_name,
                    {"job_id": job_id, "run_id": run_id},
                )
                time_str = f"{int(time_value)} seconds" if time_value else "unknown"
                time_label = "Run time: " if is_running else "Wait time: "

                # Get labels for this job
                job_labels_info = get_metric_info(
                    "github_hetzner_runners_queued_job_labels"
                    if not is_running
                    else "github_hetzner_runners_running_job_labels"
                )
                job_labels_list = []
                for label_key, label_value in job_labels_info.items():
                    if (
                        label_value == 1.0
                        and job_id in label_key
                        and run_id in label_key
                    ):
                        # Parse the raw key-value pairs
                        label_dict = {}
                        for item in label_key.split(","):
                            if "=" in item:
                                k, v = item.split("=", 1)
                                label_dict[k] = v
                        if "label" in label_dict:
                            job_labels_list.append(label_dict["label"])

                status_color = COLORS["success"] if is_running else COLORS["warning"]
                status_text = "Running" if is_running else "Queued"

                job_items.append(
                    html.Div(
                        className="job-item",
                        style={
                            "borderLeft": f"4px solid {status_color}",
                            "padding": "10px",
                            "marginBottom": "10px",
                            "backgroundColor": COLORS["paper"],
                        },
                        children=[
                            html.Div(
                                [
                                    html.Span(
                                        f"Job: {info.get('name', 'Unknown')}",
                                        style={
                                            "color": COLORS["accent"],
                                            "fontWeight": "bold",
                                        },
                                    ),
                                    html.Span(
                                        f" ({status_text})",
                                        style={
                                            "color": status_color,
                                            "marginLeft": "10px",
                                        },
                                    ),
                                ],
                                style={"marginBottom": "5px"},
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        "Job ID: ",
                                        style={"color": COLORS["text"]},
                                    ),
                                    html.Span(
                                        f"{info.get('job_id', 'Unknown')} (attempt {info.get('run_attempt', '1')})",
                                        style={"color": COLORS["warning"]},
                                    ),
                                    html.A(
                                        " (View on GitHub)",
                                        href=f"https://github.com/{info.get('repository', '')}/actions/runs/{info.get('run_id', '')}/job/{info.get('job_id', '')}",
                                        target="_blank",
                                        style={
                                            "color": COLORS["accent"],
                                            "marginLeft": "10px",
                                            "textDecoration": "none",
                                        },
                                    ),
                                ],
                                style={"marginBottom": "2px"},
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        "Run ID: ",
                                        style={"color": COLORS["text"]},
                                    ),
                                    html.Span(
                                        info.get("run_id", "Unknown"),
                                        style={"color": COLORS["warning"]},
                                    ),
                                    html.A(
                                        " (View on GitHub)",
                                        href=f"https://github.com/{info.get('repository', '')}/actions/runs/{info.get('run_id', '')}",
                                        target="_blank",
                                        style={
                                            "color": COLORS["accent"],
                                            "marginLeft": "10px",
                                            "textDecoration": "none",
                                        },
                                    ),
                                ],
                                style={"marginBottom": "2px"},
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        "Workflow: ",
                                        style={"color": COLORS["text"]},
                                    ),
                                    html.Span(
                                        info.get("workflow_name", "Unknown"),
                                        style={"color": COLORS["warning"]},
                                    ),
                                ],
                                style={"marginBottom": "2px"},
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        "Repository: ",
                                        style={"color": COLORS["text"]},
                                    ),
                                    html.Span(
                                        info.get("repository", "Unknown"),
                                        style={"color": COLORS["warning"]},
                                    ),
                                ],
                                style={"marginBottom": "2px"},
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        "Branch: ",
                                        style={"color": COLORS["text"]},
                                    ),
                                    html.Span(
                                        info.get("head_branch", "Unknown"),
                                        style={"color": COLORS["warning"]},
                                    ),
                                ],
                                style={"marginBottom": "2px"},
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        time_label,
                                        style={"color": COLORS["text"]},
                                    ),
                                    html.Span(
                                        time_str,
                                        style={"color": status_color},
                                    ),
                                ],
                                style={"marginBottom": "2px"},
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        "Labels: ",
                                        style={"color": COLORS["text"]},
                                    ),
                                    html.Span(
                                        ", ".join(job_labels_list) or "None",
                                        style={"color": COLORS["warning"]},
                                    ),
                                ],
                            ),
                        ],
                    )
                )
            except (ValueError, KeyError, AttributeError) as e:
                logging.exception(f"Error processing job info {info}")
                continue

    # If we have queued jobs but no details, show a simple message
    if queued_count > 0 and not job_items:
        job_items.append(
            html.Div(
                f"Queued jobs: {int(queued_count)} (details not available)",
                style={
                    "color": COLORS["warning"],
                    "padding": "10px",
                    "fontFamily": "JetBrains Mono, Fira Code, Consolas, monospace",
                },
            )
        )

    return html.Div(
        children=job_items,
        style={
            "maxHeight": "400px",
            "overflowY": "auto",
            "marginTop": "20px",
            "paddingRight": "4px",
            "backgroundColor": COLORS["background"],
            "border": f"1px solid {COLORS['grid']}",
            "borderRadius": "4px",
        },
    )


def create_panel():
    """Create jobs panel."""
    return html.Div(
        className="tui-container",
        children=[
            html.H3(
                "jobs",
                style={
                    "color": COLORS["accent"],
                    "marginBottom": "20px",
                    "borderBottom": f"1px solid {COLORS['accent']}",
                    "paddingBottom": "10px",
                },
            ),
            # Time graph
            dcc.Graph(
                id="jobs-graph",
                style={"height": "300px"},
            ),
            # Job list
            html.Div(
                id="jobs-list",
                style={
                    "marginTop": "20px",
                    "borderTop": f"1px solid {COLORS['accent']}",
                    "paddingTop": "20px",
                },
            ),
            # Interval component
            dcc.Interval(
                id="interval-component-jobs",
                n_intervals=0,
            ),
        ],
    )


def update_graph(n):
    """Update jobs graph."""
    current_time = datetime.now()
    queued_jobs = get_metric_value("github_hetzner_runners_queued_jobs") or 0
    running_jobs = get_metric_value("github_hetzner_runners_running_jobs") or 0

    # Update history for both metrics
    metrics = {
        "queued": {
            "name": "github_hetzner_runners_queued_jobs",
            "value": queued_jobs,
            "color": COLORS["warning"],
        },
        "running": {
            "name": "github_hetzner_runners_running_jobs",
            "value": running_jobs,
            "color": COLORS["success"],
        },
    }

    traces = []
    for status, metric in metrics.items():
        key = metric["name"]
        if key not in metric_history:
            metric_history[key] = {"timestamps": [], "values": []}

        # Convert timestamps to strings to avoid NumPy dependency
        timestamps = [
            ts.strftime("%Y-%m-%d %H:%M:%S") for ts in metric_history[key]["timestamps"]
        ]
        timestamps.append(current_time.strftime("%Y-%m-%d %H:%M:%S"))
        values = list(metric_history[key]["values"])
        values.append(metric["value"])

        # Update history
        metric_history[key]["timestamps"].append(current_time)
        metric_history[key]["values"].append(metric["value"])

        # Remove old data points
        cutoff_time = current_time - timedelta(minutes=15)
        while (
            metric_history[key]["timestamps"]
            and metric_history[key]["timestamps"][0] < cutoff_time
        ):
            metric_history[key]["timestamps"].pop(0)
            metric_history[key]["values"].pop(0)

        traces.append(
            {
                "type": "scatter",
                "x": timestamps,
                "y": values,
                "name": f"{status} ({int(metric['value'])})",
                "mode": "lines",
                "line": {"width": 2, "shape": "hv", "color": metric["color"]},
                "text": status,
                "hoverinfo": "y+text",
            }
        )

    common_style = {
        "font": {
            "family": "JetBrains Mono, Fira Code, Consolas, monospace",
            "color": COLORS["text"],
        },
        "gridcolor": COLORS["grid"],
        "showgrid": True,
        "fixedrange": True,
    }

    return {
        "data": traces,
        "layout": {
            "title": {
                "text": "jobs over time",
                "font": {"size": 16, "weight": "bold", **common_style["font"]},
                "x": 0.5,
                "y": 0.95,
            },
            "height": 300,
            "plot_bgcolor": COLORS["background"],
            "paper_bgcolor": COLORS["paper"],
            "font": common_style["font"],
            "xaxis": {
                "title": "Time",
                "range": [
                    (current_time - timedelta(minutes=15)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    current_time.strftime("%Y-%m-%d %H:%M:%S"),
                ],
                "tickformat": "%H:%M",
                **common_style,
            },
            "yaxis": {
                "title": "Number of Jobs",
                "range": [
                    0,
                    max(
                        2,
                        max(
                            max(
                                metric_history["github_hetzner_runners_queued_jobs"][
                                    "values"
                                ]
                            ),
                            max(
                                metric_history["github_hetzner_runners_running_jobs"][
                                    "values"
                                ]
                            ),
                        )
                        + 1,
                    ),
                ],
                "tickformat": "d",
                "dtick": 1,
                **common_style,
            },
            "margin": {"t": 60, "b": 50, "l": 50, "r": 50},
            "showlegend": True,
            "legend": {
                "x": 0,
                "y": 1,
                "xanchor": "left",
                "yanchor": "top",
                "bgcolor": COLORS["paper"],
                "font": {"size": 10},
            },
            "dragmode": False,
        },
        "config": {
            "displayModeBar": False,
            "staticPlot": True,
            "displaylogo": False,
        },
    }
