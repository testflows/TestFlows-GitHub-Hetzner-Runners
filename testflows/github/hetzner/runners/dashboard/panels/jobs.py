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
from datetime import datetime, timedelta
import plotly.graph_objs as go
from dash import html, dcc
import json
from prometheus_client.parser import text_string_to_metric_families

from ..colors import COLORS
from ..metrics import get_metric_value, metric_history, get_metric_info


def create_job_list():
    """Create a list of jobs with their descriptions."""
    queued_jobs_info = get_metric_info("github_hetzner_runners_queued_job")
    queued_count = get_metric_value("github_hetzner_runners_queued_jobs") or 0

    print(f"\nCreating job list:")
    print(f"Queued count: {queued_count}")
    print(f"Queued jobs info: {queued_jobs_info}")

    if queued_count == 0:
        return html.Div(
            "No queued jobs",
            style={
                "color": COLORS["text"],
                "padding": "10px",
                "fontFamily": "JetBrains Mono, Fira Code, Consolas, monospace",
            },
        )

    job_items = []
    if queued_jobs_info:
        for labels, info in queued_jobs_info.items():
            try:
                print(f"\nProcessing job info: {info}")
                job_id = info.get("job_id")
                run_id = info.get("run_id")
                if not job_id or not run_id:
                    print(f"Missing job_id or run_id")
                    continue

                # Get wait time for this job
                wait_time = get_metric_value(
                    "github_hetzner_runners_queued_job_wait_time_seconds",
                    {"job_id": job_id, "run_id": run_id},
                )
                print(f"Wait time: {wait_time}")
                wait_time_str = f"{int(wait_time)} seconds" if wait_time else "unknown"

                # Get labels for this job
                job_labels_info = get_metric_info(
                    "github_hetzner_runners_queued_job_labels"
                )
                print(f"Job labels info: {job_labels_info}")
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
                print(f"Final job labels list: {job_labels_list}")

                job_items.append(
                    html.Div(
                        className="job-item",
                        style={
                            "borderLeft": f"4px solid {COLORS['warning']}",
                            "padding": "10px",
                            "marginBottom": "10px",
                            "backgroundColor": COLORS["paper"],
                        },
                        children=[
                            html.Div(
                                f"Job: {info.get('name', 'Unknown')}",
                                style={
                                    "color": COLORS["accent"],
                                    "fontWeight": "bold",
                                    "marginBottom": "5px",
                                },
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
                                        "Wait time: ",
                                        style={"color": COLORS["text"]},
                                    ),
                                    html.Span(
                                        wait_time_str,
                                        style={"color": COLORS["warning"]},
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
                print(f"Error processing job info {info}: {str(e)}")
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
    total_jobs = queued_jobs + running_jobs

    print(f"\nJobs status:")
    print(f"  queued: {queued_jobs}")
    print(f"  running: {running_jobs}")
    print(f"Total jobs: {total_jobs}")

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
                "name": f"{status} ({metric['value']})",
                "mode": "lines",
                "line": {"width": 2, "shape": "hv", "color": metric["color"]},
                "hovertemplate": "%{y:.0f} %{fullData.name}<extra></extra>",
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
                "range": [0, max(2, total_jobs + 1)],
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
