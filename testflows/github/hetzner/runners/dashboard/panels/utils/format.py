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

"""Utility functions for dashboard panels."""

import time
from datetime import datetime


def format_duration(seconds):
    """Format duration in seconds to human-readable format.

    Args:
        seconds: Duration in seconds (int or float)

    Returns:
        str: Formatted duration like "30s", "1m 30s", "2h 30m", "1d 2h 30m"
    """
    if not seconds or seconds <= 0:
        return "0s"

    seconds = int(seconds)

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60

    parts = []

    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if remaining_seconds > 0 or not parts:
        parts.append(f"{remaining_seconds}s")

    return " ".join(parts)


def format_created_time(created_time):
    """Format creation time with duration.

    Args:
        created_time: ISO format timestamp string (can be with or without timezone)

    Returns:
        str: Formatted timestamp with duration like "2025-01-02 17:53:46 UTC (10d 2h 30m)"
    """
    if not created_time:
        return ""

    try:
        # Handle different timestamp formats
        if "Z" in created_time or "+" in created_time:
            # ISO format with timezone (servers)
            created_dt = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
        else:
            # Simple format without timezone (volumes) - assume UTC
            created_dt = datetime.fromisoformat(created_time + "+00:00")

        # Format the creation time with UTC
        created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Calculate duration
        lifetime_seconds = time.time() - created_dt.timestamp()
        duration_str = format_duration(lifetime_seconds)

        return f"{created_str} ({duration_str})"
    except (ValueError, TypeError):
        return created_time  # Fallback to original string
