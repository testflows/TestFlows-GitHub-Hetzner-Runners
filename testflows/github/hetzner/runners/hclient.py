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
            token=token,
            api_endpoint=api_endpoint,
            application_name=project_name,
            application_version=project_version,
            poll_interval=poll_interval,
        )
