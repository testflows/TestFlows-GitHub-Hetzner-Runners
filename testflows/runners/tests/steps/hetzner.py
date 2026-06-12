"""Shared @TestStep(Given) fixtures for Hetzner-provider tests.

Each step patches HClient inside the provider module so no real API calls
are made. Call from a scenario inside ``with Given("..."):`` to receive
the yielded value.
"""
from unittest.mock import MagicMock, patch

from testflows.core import *

from testflows.runners.providers.hetzner.provider import HetznerCloudProvider


@TestStep(Given)
def mock_hclient(self):
    """Patch HClient inside the provider module and yield the mock instance."""
    with patch(
        "testflows.runners.providers.hetzner.provider.HClient"
    ) as MockHClient:
        client = MagicMock()
        MockHClient.return_value = client
        yield client


@TestStep(Given)
def hetzner_provider(self):
    """Yield (hclient_mock, HetznerCloudProvider) with HClient patched."""
    with Given("mocked HClient"):
        hclient = mock_hclient()
    provider = HetznerCloudProvider(
        token="test-token", ssh_key_path="/tmp/id_rsa.pub"
    )
    yield hclient, provider
