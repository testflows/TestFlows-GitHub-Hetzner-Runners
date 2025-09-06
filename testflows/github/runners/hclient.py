from hcloud import Client

from . import __version__ as project_version, __name__ as project_name


class HClient(Client):

    def __init__(
        self,
        token,
        api_endpoint="https://api.hetzner.cloud/v1",
        poll_interval=1,
    ):
        super().__init__(
            token, api_endpoint, project_name, project_version, poll_interval
        )
