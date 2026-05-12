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

"""Tests for HetznerCloudProvider.

All hcloud I/O is mocked at the HClient level so no real API calls are made.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

from testflows.runners.cloud_provider import CloudProvider, ProviderServer
from testflows.runners.providers.hetzner.provider import HetznerCloudProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_bound_server(
    id=1,
    name="github-hetzner-runner-123",
    status="running",
    labels=None,
    server_type_name="cx23",
    location_name="nbg1",
):
    """Build a minimal mock that looks like an hcloud BoundServer."""
    server = MagicMock()
    server.id = id
    server.name = name
    server.status = status
    server.labels = labels or {"github-hetzner-runner": "active"}
    server.public_net = MagicMock()
    server.public_net.ipv4 = MagicMock()
    server.public_net.ipv4.ip = "1.2.3.4"
    server.public_net.ipv6 = MagicMock()
    server.private_net = []
    server.server_type = MagicMock()
    server.server_type.name = server_type_name
    server.datacenter = MagicMock()
    server.datacenter.location = MagicMock()
    server.datacenter.location.name = location_name
    server.created = datetime(2024, 1, 1, tzinfo=timezone.utc)
    server.volumes = []
    return server


@pytest.fixture
def mock_hclient():
    """Patch HClient inside the provider module and return the mock instance."""
    with patch(
        "testflows.runners.providers.hetzner.provider.HClient"
    ) as MockHClient:
        mock_instance = MagicMock()
        MockHClient.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def provider(mock_hclient):
    """Return a HetznerCloudProvider with a mocked HClient."""
    p = HetznerCloudProvider(token="test-token", ssh_key_path="/tmp/id_rsa.pub")
    return p


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_name(self, provider):
        assert provider.name == "hetzner"

    def test_supports_recycling(self, provider):
        assert provider.supports_recycling is True

    def test_name_is_string(self, provider):
        assert isinstance(provider.name, str)


# ---------------------------------------------------------------------------
# list_runner_servers
# ---------------------------------------------------------------------------


class TestListRunnerServers:
    def test_uses_correct_label_selector(self, provider, mock_hclient):
        mock_hclient.servers.get_all.return_value = []
        provider.list_runner_servers()
        mock_hclient.servers.get_all.assert_called_once_with(
            label_selector="github-hetzner-runner=active"
        )

    def test_returns_provider_server_objects(self, provider, mock_hclient):
        bound = _make_bound_server()
        mock_hclient.servers.get_all.return_value = [bound]

        result = provider.list_runner_servers()

        assert len(result) == 1
        ps = result[0]
        assert isinstance(ps, ProviderServer)
        assert ps.name == bound.name
        assert ps._native is bound

    def test_maps_status_to_abstract_constant(self, provider, mock_hclient):
        bound = _make_bound_server(status="running")
        mock_hclient.servers.get_all.return_value = [bound]

        result = provider.list_runner_servers()
        assert result[0].status == CloudProvider.STATUS_RUNNING

    def test_maps_off_status(self, provider, mock_hclient):
        bound = _make_bound_server(status="off")
        mock_hclient.servers.get_all.return_value = [bound]

        result = provider.list_runner_servers()
        assert result[0].status == CloudProvider.STATUS_OFF


# ---------------------------------------------------------------------------
# create_server
# ---------------------------------------------------------------------------


class TestCreateServer:
    def test_passes_correct_args_to_hcloud(self, provider, mock_hclient):
        bound = _make_bound_server()
        mock_response = MagicMock()
        mock_response.server = bound
        mock_hclient.servers.create.return_value = mock_response

        server_type = MagicMock()
        location = MagicMock()
        image = MagicMock()
        ssh_keys = [MagicMock()]
        labels = {"github-hetzner-runner": "active"}
        public_net = MagicMock()

        result = provider.create_server(
            name="test-server",
            server_type=server_type,
            location=location,
            image=image,
            ssh_keys=ssh_keys,
            labels=labels,
            volumes=[],
            automount=False,
            public_net=public_net,
        )

        mock_hclient.servers.create.assert_called_once_with(
            name="test-server",
            server_type=server_type,
            location=location,
            image=image,
            ssh_keys=ssh_keys,
            labels=labels,
            volumes=[],
            automount=False,
            public_net=public_net,
        )
        assert isinstance(result, ProviderServer)
        assert result._native is bound

    def test_returns_provider_server(self, provider, mock_hclient):
        bound = _make_bound_server(name="new-runner")
        mock_response = MagicMock()
        mock_response.server = bound
        mock_hclient.servers.create.return_value = mock_response

        result = provider.create_server(
            name="new-runner",
            server_type=MagicMock(),
            location=MagicMock(),
            image=MagicMock(),
            ssh_keys=[MagicMock()],
            labels={},
        )

        assert result.name == "new-runner"


# ---------------------------------------------------------------------------
# get_or_create_ssh_key
# ---------------------------------------------------------------------------


class TestGetOrCreateSSHKey:
    # A minimal valid RSA public key fragment for testing.
    _FAKE_PUBLIC_KEY = (
        "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC3test+fake/key== test@test"
    )

    def _provider_with_fake_key(self, mock_hclient, public_key):
        """Helper: return provider that uses public_key as a string."""
        import base64
        import hashlib

        # Encode a minimal valid base64 blob so fingerprint() doesn't crash.
        raw = b"\x00\x00\x00\x07ssh-rsa" + b"\x00" * 20
        b64 = base64.b64encode(raw).decode()
        key_str = f"ssh-rsa {b64} test@host"
        return key_str

    def test_creates_key_when_missing(self, provider, mock_hclient):
        import base64

        raw = b"\x00\x00\x00\x07ssh-rsa" + b"\x00" * 20
        b64 = base64.b64encode(raw).decode()
        key_str = f"ssh-rsa {b64} test@host"

        mock_hclient.ssh_keys.get_by_fingerprint.return_value = None
        created_key = MagicMock()
        mock_hclient.ssh_keys.create.return_value = created_key

        result = provider.get_or_create_ssh_key(public_key=key_str, is_file=False)

        mock_hclient.ssh_keys.create.assert_called_once()
        assert result is created_key

    def test_returns_existing_key_when_present(self, provider, mock_hclient):
        import base64

        raw = b"\x00\x00\x00\x07ssh-rsa" + b"\x00" * 20
        b64 = base64.b64encode(raw).decode()
        key_str = f"ssh-rsa {b64} test@host"

        existing_key = MagicMock()
        mock_hclient.ssh_keys.get_by_fingerprint.return_value = existing_key

        result = provider.get_or_create_ssh_key(public_key=key_str, is_file=False)

        mock_hclient.ssh_keys.create.assert_not_called()
        assert result is existing_key

    def test_reads_file_when_is_file_true(self, provider, mock_hclient):
        import base64

        raw = b"\x00\x00\x00\x07ssh-rsa" + b"\x00" * 20
        b64 = base64.b64encode(raw).decode()
        key_str = f"ssh-rsa {b64} test@host"

        existing_key = MagicMock()
        mock_hclient.ssh_keys.get_by_fingerprint.return_value = existing_key

        with patch("builtins.open", MagicMock()) as mock_open:
            mock_open.return_value.__enter__ = MagicMock(
                return_value=MagicMock(read=MagicMock(return_value=key_str))
            )
            mock_open.return_value.__exit__ = MagicMock(return_value=False)

            result = provider.get_or_create_ssh_key(
                public_key="/path/to/key.pub", is_file=True
            )

        mock_open.assert_called_once_with("/path/to/key.pub", "r", encoding="utf-8")
        assert result is existing_key


# ---------------------------------------------------------------------------
# get_server_tag / set_server_tags
# ---------------------------------------------------------------------------


class TestTagOperations:
    def test_get_server_tag_returns_value(self, provider):
        ps = ProviderServer(
            id=1,
            name="srv",
            status="running",
            public_ipv4=None,
            private_ipv4=None,
            labels={"my-key": "my-value"},
            server_type="cx23",
            location="nbg1",
            created=datetime.now(timezone.utc),
        )
        assert provider.get_server_tag(ps, "my-key") == "my-value"

    def test_get_server_tag_returns_none_for_missing(self, provider):
        ps = ProviderServer(
            id=1,
            name="srv",
            status="running",
            public_ipv4=None,
            private_ipv4=None,
            labels={},
            server_type="cx23",
            location="nbg1",
            created=datetime.now(timezone.utc),
        )
        assert provider.get_server_tag(ps, "missing") is None

    def test_set_server_tags_merges_and_updates(self, provider):
        native = MagicMock()
        native.labels = {"existing-key": "existing-val"}
        native.update = MagicMock()

        ps = ProviderServer(
            id=1,
            name="srv",
            status="running",
            public_ipv4=None,
            private_ipv4=None,
            labels={"existing-key": "existing-val"},
            server_type="cx23",
            location="nbg1",
            created=datetime.now(timezone.utc),
            _native=native,
        )

        provider.set_server_tags(ps, {"new-key": "new-val"})

        expected = {"existing-key": "existing-val", "new-key": "new-val"}
        native.update.assert_called_once_with(labels=expected)
        assert ps.labels == expected

    def test_set_server_tags_overwrites_existing_key(self, provider):
        native = MagicMock()
        native.labels = {"k": "old"}
        native.update = MagicMock()

        ps = ProviderServer(
            id=1,
            name="srv",
            status="running",
            public_ipv4=None,
            private_ipv4=None,
            labels={"k": "old"},
            server_type="cx23",
            location="nbg1",
            created=datetime.now(timezone.utc),
            _native=native,
        )

        provider.set_server_tags(ps, {"k": "new"})
        assert ps.labels["k"] == "new"


# ---------------------------------------------------------------------------
# power_off_server / delete_server
# ---------------------------------------------------------------------------


class TestServerLifecycle:
    def _make_provider_server(self):
        native = MagicMock()
        ps = ProviderServer(
            id=1,
            name="srv",
            status="running",
            public_ipv4="1.2.3.4",
            private_ipv4=None,
            labels={},
            server_type="cx23",
            location="nbg1",
            created=datetime.now(timezone.utc),
            _native=native,
        )
        return ps, native

    def test_power_off_calls_native(self, provider):
        ps, native = self._make_provider_server()
        provider.power_off_server(ps)
        native.power_off.assert_called_once()

    def test_delete_server_calls_native(self, provider):
        ps, native = self._make_provider_server()
        provider.delete_server(ps)
        native.delete.assert_called_once()

    def test_power_on_calls_native(self, provider):
        ps, native = self._make_provider_server()
        provider.power_on_server(ps)
        native.power_on.assert_called_once()


# ---------------------------------------------------------------------------
# expand_location_label
# ---------------------------------------------------------------------------


class TestExpandLocationLabel:
    """Tests for HetznerCloudProvider.expand_location_label (pure method)."""

    def _expand(self, name):
        return HetznerCloudProvider.expand_location_label(None, name)

    def test_simple_label_returned_as_single_element(self):
        assert self._expand("nbg1") == ["nbg1"]

    def test_composite_three_parts_expanded(self):
        assert self._expand("hel1-fsn1-nbg1") == ["hel1", "fsn1", "nbg1"]

    def test_composite_two_parts_expanded(self):
        assert self._expand("hel1-fsn1") == ["hel1", "fsn1"]

    def test_aws_az_not_expanded(self):
        """AWS AZ names like us-east-1a must not be treated as composite."""
        assert self._expand("us-east-1a") == ["us-east-1a"]

    def test_aws_region_not_expanded(self):
        assert self._expand("eu-west-1") == ["eu-west-1"]

    def test_label_without_dash_returned_as_is(self):
        assert self._expand("nbg1") == ["nbg1"]

    def test_digits_only_part_not_treated_as_dc_code(self):
        """A segment like '1a' does not match the pure-digit suffix pattern."""
        assert self._expand("us-east-1a") == ["us-east-1a"]
