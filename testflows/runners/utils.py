from .constants import runner_name_prefix


def get_runner_server_type(runner_name: str) -> str | None:
    """Return the server type embedded in a runner name, or None.

    Runner names follow the pattern:
      github-runner-{run_id}-{job_id}-{server_type}

    The server type may contain dots (e.g. 'c8g.2xlarge') so the split is
    capped at 4 splits to capture everything after the fourth dash as the type.
    """
    if runner_name and runner_name.startswith(runner_name_prefix):
        parts = runner_name.split("-", 4)
        if len(parts) == 5:
            return parts[4]
    return None
