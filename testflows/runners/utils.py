from .constants import runner_name_prefix


def get_runner_server_type_and_location(runner_name: str):
    """Determine runner's server type, and location.

    Runner names follow the pattern:
      github-hetzner-runner-{run_id}-{job_id}-{server_type}-{location}

    The server type is always a single dash-free token (e.g. 'cax11', 't3.micro').
    The location may contain dashes (e.g. AWS AZ 'us-east-1a'), so everything
    after index 5 is joined back together.
    """
    server_type, server_location = None, None

    if runner_name and runner_name.startswith(runner_name_prefix):
        parts = runner_name.split("-")
        if len(parts) >= 7:
            server_type = parts[5]
            server_location = "-".join(parts[6:])

    return server_type, server_location
