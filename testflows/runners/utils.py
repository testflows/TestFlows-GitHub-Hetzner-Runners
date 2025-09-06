from .constants import runner_name_prefix


def get_runner_server_type_and_location(runner_name: str):
    """Determine runner's server type, and location."""
    server_type, server_location = None, None

    if runner_name and runner_name.startswith(runner_name_prefix):
        if len(runner_name.split("-")) == 7:
            server_type, server_location = runner_name.split("-")[5:]

    return server_type, server_location
