"""Interface conformance tests for all active CloudProvider implementations.

Every active provider must satisfy this contract. Each conformance check is
a scenario that takes a provider plus a few provider-specific test fixtures
(labeled_server, sample_labels, active_marker_key, sample_server_type) so
the SAME suite can be re-run against each provider implementation.
"""
from unittest.mock import MagicMock

from testflows.core import *

from testflows.runners.cloud_provider import CloudProvider, ProviderServer, ProviderServerType
from testflows.runners.tests.steps.aws import aws_provider
from testflows.runners.tests.steps.hetzner import hetzner_provider


# ---------------------------------------------------------------------------
# Shared conformance scenarios — each takes the provider context as args
# ---------------------------------------------------------------------------


@TestScenario
def name_is_non_empty_string(self, provider):
    assert isinstance(provider.name, str) and provider.name


@TestScenario
def supports_recycling_is_bool(self, provider):
    assert isinstance(provider.supports_recycling, bool)


@TestScenario
def status_constants_defined(self, provider):
    for attr in (
        "STATUS_RUNNING",
        "STATUS_OFF",
        "STATUS_STARTING",
        "STATUS_STOPPING",
        "STATUS_DELETING",
        "STATUS_UNKNOWN",
    ):
        assert hasattr(provider, attr), f"missing {attr}"


@TestScenario
def list_runner_servers_callable(self, provider):
    assert callable(getattr(provider, "list_runner_servers", None))


@TestScenario
def list_servers_callable(self, provider):
    assert callable(getattr(provider, "list_servers", None))


@TestScenario
def get_runner_labels_callable(self, provider):
    assert callable(getattr(provider, "get_runner_labels", None))


@TestScenario
def build_server_labels_callable(self, provider):
    assert callable(getattr(provider, "build_server_labels", None))


@TestScenario
def validate_labels_callable(self, provider):
    assert callable(getattr(provider, "validate_labels", None))


@TestScenario
def get_server_arch_callable(self, provider):
    assert callable(getattr(provider, "get_server_arch", None))


@TestScenario
def get_runner_labels_returns_iterable_of_strings(self, provider, labeled_server):
    result = provider.get_runner_labels(labeled_server)
    assert hasattr(result, "__iter__")
    assert all(isinstance(l, str) for l in result)


@TestScenario
def get_runner_labels_roundtrip(self, provider, labeled_server, sample_labels):
    """Labels stored via build_server_labels must be recoverable."""
    result = provider.get_runner_labels(labeled_server)
    assert set(result) == set(sample_labels)


@TestScenario
def build_server_labels_returns_dict(self, provider, sample_labels):
    assert isinstance(provider.build_server_labels(sample_labels), dict)


@TestScenario
def build_server_labels_contains_active_marker(self, provider, sample_labels, active_marker_key):
    result = provider.build_server_labels(sample_labels)
    assert active_marker_key in result, (
        f"active marker key {active_marker_key!r} missing from build_server_labels output"
    )
    assert result[active_marker_key] == "active"


@TestScenario
def build_server_labels_values_roundtrip(self, provider, sample_labels):
    """Every label passed in must appear as a value in the returned dict."""
    result = provider.build_server_labels(sample_labels)
    stored_values = set(result.values())
    for lbl in sample_labels:
        assert lbl in stored_values, (
            f"label {lbl!r} not found in build_server_labels output values: {stored_values}"
        )


@TestScenario
def validate_labels_accepts_valid(self, provider, valid_label_dict):
    """validate_labels takes a provider-format label dict, not a plain list."""
    provider.validate_labels(valid_label_dict)


@TestScenario
def get_server_arch_returns_known_value(self, provider, sample_server_type):
    arch = provider.get_server_arch(sample_server_type)
    assert arch in ("x64", "arm64"), f"unexpected arch {arch!r}"


_SHARED_SCENARIOS = [
    name_is_non_empty_string,
    supports_recycling_is_bool,
    status_constants_defined,
    list_runner_servers_callable,
    list_servers_callable,
    get_runner_labels_callable,
    build_server_labels_callable,
    validate_labels_callable,
    get_server_arch_callable,
    get_runner_labels_returns_iterable_of_strings,
    get_runner_labels_roundtrip,
    build_server_labels_returns_dict,
    build_server_labels_contains_active_marker,
    build_server_labels_values_roundtrip,
    validate_labels_accepts_valid,
    get_server_arch_returns_known_value,
]


def _run_shared(fixtures):
    """Call each shared conformance scenario with only the fixture kwargs
    its function actually declares."""
    for scn in _SHARED_SCENARIOS:
        params = scn.func.__code__.co_varnames
        Scenario(test=scn)(**{k: v for k, v in fixtures.items() if k in params})


# ---------------------------------------------------------------------------
# AWS-specific test data
# ---------------------------------------------------------------------------


def _make_aws_server(labels):
    tag_dict = {}
    for i, lbl in enumerate(labels):
        tag_dict[f"github-runner-label-{i}"] = lbl
    tag_dict["github-runner"] = "active"
    tag_dict["Name"] = "github-runner-test"
    s = MagicMock(spec=ProviderServer)
    s.labels = tag_dict
    return s


def _aws_fixtures(provider):
    sample_labels = ["self-hosted", "linux", "x64"]
    valid_label_dict = {f"github-runner-label-{i}": lbl for i, lbl in enumerate(sample_labels)}
    valid_label_dict["github-runner"] = "active"
    sample_server_type = MagicMock(spec=ProviderServerType)
    sample_server_type.name = "t3.medium"
    return dict(
        provider=provider,
        labeled_server=_make_aws_server(sample_labels),
        sample_labels=sample_labels,
        valid_label_dict=valid_label_dict,
        active_marker_key="github-runner",
        sample_server_type=sample_server_type,
    )


@TestFeature
@Name("aws")
def aws_conformance(self):
    """Conformance suite against AWSCloudProvider."""
    with Given("an AWS provider"):
        _, provider = aws_provider()
    _run_shared(_aws_fixtures(provider))


# ---------------------------------------------------------------------------
# Hetzner-specific test data
# ---------------------------------------------------------------------------


def _make_hetzner_server(labels):
    label_dict = {"github-hetzner-runner": "active"}
    for i, lbl in enumerate(labels):
        label_dict[f"github-hetzner-runner-label-{i}"] = lbl
    s = MagicMock(spec=ProviderServer)
    s.labels = label_dict
    return s


def _hetzner_fixtures(provider):
    sample_labels = ["self-hosted", "linux", "x64"]
    valid_label_dict = {"github-hetzner-runner": "active"}
    for i, lbl in enumerate(sample_labels):
        valid_label_dict[f"github-hetzner-runner-label-{i}"] = lbl
    sample_server_type = MagicMock(spec=ProviderServerType)
    sample_server_type.name = "cx23"
    return dict(
        provider=provider,
        labeled_server=_make_hetzner_server(sample_labels),
        sample_labels=sample_labels,
        valid_label_dict=valid_label_dict,
        active_marker_key="github-hetzner-runner",
        sample_server_type=sample_server_type,
    )


@TestFeature
@Name("hetzner")
def hetzner_conformance(self):
    """Conformance suite against HetznerCloudProvider."""
    with Given("a Hetzner provider"):
        _, provider = hetzner_provider()
    _run_shared(_hetzner_fixtures(provider))


# ---------------------------------------------------------------------------
# Feature entry point
# ---------------------------------------------------------------------------


@TestFeature
@Name("provider interface")
def feature(self):
    """Run the conformance suite against every active CloudProvider."""
    Feature(run=aws_conformance)
    Feature(run=hetzner_conformance)
