"""Interface conformance tests for all active CloudProvider implementations.

Every active provider must satisfy this contract.  Add a concrete subclass
(with a ``provider`` fixture) for each new provider to catch drift early.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from testflows.runners.cloud_provider import CloudProvider, ProviderServer, ProviderServerType
from testflows.runners.providers.aws.provider import AWSCloudProvider
from testflows.runners.providers.hetzner.provider import HetznerCloudProvider


# ---------------------------------------------------------------------------
# Shared conformance suite
# ---------------------------------------------------------------------------


class ProviderConformance:
    """Mixin: subclass and provide a ``provider`` fixture to run all checks."""

    # -- identity ------------------------------------------------------------

    def test_name_is_non_empty_string(self, provider):
        assert isinstance(provider.name, str) and provider.name

    def test_supports_recycling_is_bool(self, provider):
        assert isinstance(provider.supports_recycling, bool)

    def test_status_constants_defined(self, provider):
        for attr in (
            "STATUS_RUNNING",
            "STATUS_OFF",
            "STATUS_STARTING",
            "STATUS_STOPPING",
            "STATUS_DELETING",
            "STATUS_UNKNOWN",
        ):
            assert hasattr(provider, attr), f"missing {attr}"

    # -- contract methods exist ----------------------------------------------

    def test_list_runner_servers_callable(self, provider):
        assert callable(getattr(provider, "list_runner_servers", None))

    def test_list_servers_callable(self, provider):
        assert callable(getattr(provider, "list_servers", None))

    def test_get_runner_labels_callable(self, provider):
        assert callable(getattr(provider, "get_runner_labels", None))

    def test_build_server_labels_callable(self, provider):
        assert callable(getattr(provider, "build_server_labels", None))

    def test_validate_labels_callable(self, provider):
        assert callable(getattr(provider, "validate_labels", None))

    def test_get_server_arch_callable(self, provider):
        assert callable(getattr(provider, "get_server_arch", None))

    # -- label round-trip ----------------------------------------------------

    def test_get_runner_labels_returns_iterable_of_strings(self, provider, labeled_server):
        result = provider.get_runner_labels(labeled_server)
        assert hasattr(result, "__iter__")
        assert all(isinstance(l, str) for l in result)

    def test_get_runner_labels_roundtrip(self, provider, labeled_server, sample_labels):
        """Labels stored via build_server_labels must be recoverable."""
        result = provider.get_runner_labels(labeled_server)
        assert set(result) == set(sample_labels)

    def test_build_server_labels_returns_dict(self, provider, sample_labels):
        result = provider.build_server_labels(sample_labels)
        assert isinstance(result, dict)

    def test_build_server_labels_contains_active_marker(self, provider, sample_labels, active_marker_key):
        result = provider.build_server_labels(sample_labels)
        assert active_marker_key in result, (
            f"active marker key {active_marker_key!r} missing from build_server_labels output"
        )
        assert result[active_marker_key] == "active"

    def test_build_server_labels_values_roundtrip(self, provider, sample_labels):
        """Every label passed in must appear as a value in the returned dict."""
        result = provider.build_server_labels(sample_labels)
        stored_values = set(result.values())
        for lbl in sample_labels:
            assert lbl in stored_values, (
                f"label {lbl!r} not found in build_server_labels output values: {stored_values}"
            )

    def test_validate_labels_accepts_valid(self, provider, valid_label_dict):
        """validate_labels takes a provider-format label dict, not a plain list."""
        provider.validate_labels(valid_label_dict)

    # -- arch detection (server_type string is provider-specific) ------------

    def test_get_server_arch_returns_known_value(self, provider, sample_server_type):
        arch = provider.get_server_arch(sample_server_type)
        assert arch in ("x64", "arm64"), f"unexpected arch {arch!r}"


# ---------------------------------------------------------------------------
# AWS conformance
# ---------------------------------------------------------------------------


@pytest.fixture
def _aws_mock_ec2():
    with patch("boto3.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value = mock_session
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        mock_client.describe_subnets.return_value = {
            "Subnets": [{"SubnetId": "subnet-12345", "AvailabilityZone": "us-east-1a"}]
        }
        yield mock_client


@pytest.fixture
def _aws_provider(_aws_mock_ec2):
    return AWSCloudProvider(
        access_key_id="AKIATEST",
        secret_access_key="secret",
        region="us-east-1",
        security_group="sg-12345",
        subnets=["subnet-12345"],
    )


def _make_aws_server(labels):
    """Minimal ProviderServer pre-populated with labels as EC2 tags."""
    tag_dict = {}
    for i, lbl in enumerate(labels):
        tag_dict[f"github-runner-label-{i}"] = lbl
    tag_dict["github-runner"] = "active"
    tag_dict["Name"] = "github-runner-test"
    s = MagicMock(spec=ProviderServer)
    s.labels = tag_dict
    return s


class TestAWSConformance(ProviderConformance):
    @pytest.fixture
    def provider(self, _aws_provider):
        return _aws_provider

    @pytest.fixture
    def sample_labels(self):
        return ["self-hosted", "linux", "x64"]

    @pytest.fixture
    def labeled_server(self, sample_labels):
        return _make_aws_server(sample_labels)

    @pytest.fixture
    def valid_label_dict(self, sample_labels):
        """AWS validate_labels takes a {tag-key: tag-value} dict."""
        d = {}
        for i, lbl in enumerate(sample_labels):
            d[f"github-runner-label-{i}"] = lbl
        d["github-runner"] = "active"
        return d

    @pytest.fixture
    def active_marker_key(self):
        return "github-runner"

    @pytest.fixture
    def sample_server_type(self):
        st = MagicMock(spec=ProviderServerType)
        st.name = "t3.medium"
        return st


# ---------------------------------------------------------------------------
# Hetzner conformance
# ---------------------------------------------------------------------------


@pytest.fixture
def _hetzner_mock_client():
    with patch("testflows.runners.providers.hetzner.provider.HClient") as MockHClient:
        mock_instance = MagicMock()
        MockHClient.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def _hetzner_provider(_hetzner_mock_client):
    return HetznerCloudProvider(token="test-token", ssh_key_path="/tmp/id_rsa.pub")


def _make_hetzner_server(labels):
    """Minimal ProviderServer pre-populated with labels as Hetzner label dict."""
    label_dict = {"github-hetzner-runner": "active"}
    for i, lbl in enumerate(labels):
        label_dict[f"github-hetzner-runner-label-{i}"] = lbl
    s = MagicMock(spec=ProviderServer)
    s.labels = label_dict
    return s


class TestHetznerConformance(ProviderConformance):
    @pytest.fixture
    def provider(self, _hetzner_provider):
        return _hetzner_provider

    @pytest.fixture
    def sample_labels(self):
        return ["self-hosted", "linux", "x64"]

    @pytest.fixture
    def labeled_server(self, sample_labels):
        return _make_hetzner_server(sample_labels)

    @pytest.fixture
    def valid_label_dict(self, sample_labels):
        """Hetzner validate_labels takes a {label-key: label-value} dict."""
        d = {"github-hetzner-runner": "active"}
        for i, lbl in enumerate(sample_labels):
            d[f"github-hetzner-runner-label-{i}"] = lbl
        return d

    @pytest.fixture
    def active_marker_key(self):
        return "github-hetzner-runner"

    @pytest.fixture
    def sample_server_type(self):
        st = MagicMock(spec=ProviderServerType)
        st.name = "cx23"
        return st
