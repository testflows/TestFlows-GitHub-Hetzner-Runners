"""Tests for pure helper functions in scale_up.py."""
from unittest.mock import MagicMock

from testflows.core import *

from testflows.runners.cloud_provider import CloudProvider
from testflows.runners.scale_up import (
    RunnerServer,
    check_max_servers_for_label_reached,
    count_available,
    count_available_runners,
    count_present,
    get_job_labels,
    get_runner_server_type,
    get_server_count_with_labels,
    get_total_server_count,
    get_volume_name,
    job_matches_labels,
    recyclable_server_match,
    set_future_attributes,
)
from testflows.runners.constants import runner_name_prefix, server_ssh_key_label


# ---------------------------------------------------------------------------
# Helpers (plain Python, not @TestStep — they just build objects)
# ---------------------------------------------------------------------------

RUNNER_PREFIX = runner_name_prefix  # "github-runner-"


def _runner_server(
    labels=None,
    server_status=CloudProvider.STATUS_RUNNING,
    status="ready",
    server_type_name="cx22",
    server_location_name="nbg1",
    server_volumes=None,
    native=None,
):
    """Build a minimal RunnerServer for tests."""
    ps = MagicMock()  # ProviderServer
    ps._native = native or MagicMock()
    return RunnerServer(
        name=f"{RUNNER_PREFIX}run1-0-{server_type_name}",
        labels=set(labels or []),
        server_type=server_type_name,
        server_location=server_location_name,
        server_volumes=server_volumes or [],
        server_status=server_status,
        runner_status=status,
        server=ps,
    )


def _gh_runner(status="online", busy=False, labels=None):
    """Build a minimal GitHub SelfHostedActionsRunner mock."""
    r = MagicMock()
    r.status = status
    r.busy = busy
    r.labels = [{"name": lbl} for lbl in (labels or [])]
    return r


# ---------------------------------------------------------------------------
# get_volume_name
# ---------------------------------------------------------------------------


@TestScenario
def get_volume_name_strips_everything_after_first_dash(self):
    assert get_volume_name("cache-x86-ubuntu-22.04-1234567") == "cache"


@TestScenario
def get_volume_name_returned_as_is_without_dash(self):
    assert get_volume_name("mydata") == "mydata"


@TestScenario
def get_volume_name_takes_only_first_segment(self):
    assert get_volume_name("a-b-c") == "a"


# ---------------------------------------------------------------------------
# get_runner_server_type
# ---------------------------------------------------------------------------


def _runner_name(server_type):
    return f"{RUNNER_PREFIX}run1-0-{server_type}"


@TestScenario
def get_runner_server_type_valid(self):
    assert get_runner_server_type(_runner_name("cx22")) == "cx22"


@TestScenario
def get_runner_server_type_aws_with_dot(self):
    assert get_runner_server_type(_runner_name("c8g.2xlarge")) == "c8g.2xlarge"


@TestScenario
def get_runner_server_type_wrong_prefix(self):
    assert get_runner_server_type("other-runner-run1-0-cx22") is None


@TestScenario
def get_runner_server_type_too_few_segments(self):
    assert get_runner_server_type(f"{RUNNER_PREFIX}run1-cx22") is None


@TestScenario
def get_runner_server_type_empty(self):
    assert get_runner_server_type("") is None


@TestScenario
def get_runner_server_type_none(self):
    assert get_runner_server_type(None) is None


# ---------------------------------------------------------------------------
# get_job_labels
# ---------------------------------------------------------------------------


def _job(labels):
    j = MagicMock()
    j.raw_data = {"labels": labels}
    return j


@TestScenario
def get_job_labels_lowercases(self):
    assert get_job_labels(_job(["Self-Hosted", "Linux"])) == ["self-hosted", "linux"]


@TestScenario
def get_job_labels_deduplicates_preserving_order(self):
    assert get_job_labels(_job(["linux", "self-hosted", "linux"])) == ["linux", "self-hosted"]


@TestScenario
def get_job_labels_empty(self):
    assert get_job_labels(_job([])) == []


@TestScenario
def get_job_labels_case_insensitive_dedup(self):
    assert get_job_labels(_job(["Linux", "linux"])) == ["linux"]


# ---------------------------------------------------------------------------
# job_matches_labels
# ---------------------------------------------------------------------------


@TestScenario
def job_matches_labels_none_with_label_matches(self):
    assert job_matches_labels(["linux"], with_label=None) is True


@TestScenario
def job_matches_labels_all_required_present(self):
    assert job_matches_labels(["linux", "self-hosted"], with_label=["linux"]) is True


@TestScenario
def job_matches_labels_missing_required(self):
    result = job_matches_labels(["linux"], with_label=["arm64"])
    assert result == (False, "arm64")


@TestScenario
def job_matches_labels_empty_with_label_matches(self):
    assert job_matches_labels(["linux"], with_label=[]) is True


@TestScenario
def job_matches_labels_multiple_required_all_present(self):
    assert (
        job_matches_labels(["linux", "self-hosted", "arm64"], with_label=["linux", "arm64"]) is True
    )


@TestScenario
def job_matches_labels_multiple_required_one_missing(self):
    result = job_matches_labels(["linux"], with_label=["linux", "arm64"])
    assert result == (False, "arm64")


# ---------------------------------------------------------------------------
# count_available_runners
# ---------------------------------------------------------------------------


@TestScenario
def count_available_runners_empty(self):
    assert count_available_runners([], ["linux"]) == 0


@TestScenario
def count_available_runners_online_not_busy(self):
    r = _gh_runner(status="online", busy=False, labels=["linux", "self-hosted"])
    assert count_available_runners([r], ["linux"]) == 1


@TestScenario
def count_available_runners_offline_not_counted(self):
    r = _gh_runner(status="offline", busy=False, labels=["linux"])
    assert count_available_runners([r], ["linux"]) == 0


@TestScenario
def count_available_runners_busy_not_counted(self):
    r = _gh_runner(status="online", busy=True, labels=["linux"])
    assert count_available_runners([r], ["linux"]) == 0


@TestScenario
def count_available_runners_missing_required_label(self):
    r = _gh_runner(status="online", busy=False, labels=["linux"])
    assert count_available_runners([r], ["linux", "arm64"]) == 0


@TestScenario
def count_available_runners_superset_labels_count(self):
    r = _gh_runner(status="online", busy=False, labels=["linux", "arm64", "self-hosted"])
    assert count_available_runners([r], ["linux", "arm64"]) == 1


@TestScenario
def count_available_runners_multiple_mixed(self):
    runners = [
        _gh_runner(status="online", busy=False, labels=["linux"]),
        _gh_runner(status="online", busy=True, labels=["linux"]),
        _gh_runner(status="offline", busy=False, labels=["linux"]),
    ]
    assert count_available_runners(runners, ["linux"]) == 1


# ---------------------------------------------------------------------------
# count_available / count_present
# ---------------------------------------------------------------------------


@TestScenario
def count_available_empty(self):
    assert count_available([], ["linux"]) == 0


@TestScenario
def count_available_ready_matching(self):
    s = _runner_server(labels=["linux"], status="ready")
    assert count_available([s], ["linux"]) == 1


@TestScenario
def count_available_initializing_counted(self):
    s = _runner_server(labels=["linux"], status="initializing")
    assert count_available([s], ["linux"]) == 1


@TestScenario
def count_available_busy_not_counted(self):
    s = _runner_server(labels=["linux"], status="busy")
    assert count_available([s], ["linux"]) == 0


@TestScenario
def count_available_powered_off_not_counted(self):
    s = _runner_server(labels=["linux"], server_status=CloudProvider.STATUS_OFF)
    assert count_available([s], ["linux"]) == 0


@TestScenario
def count_available_label_mismatch(self):
    s = _runner_server(labels=["linux"], status="ready")
    assert count_available([s], ["arm64"]) == 0


@TestScenario
def count_present_empty(self):
    assert count_present([], ["linux"]) == 0


@TestScenario
def count_present_running_counted(self):
    s = _runner_server(labels=["linux"])
    assert count_present([s], ["linux"]) == 1


@TestScenario
def count_present_powered_off_not_counted(self):
    s = _runner_server(labels=["linux"], server_status=CloudProvider.STATUS_OFF)
    assert count_present([s], ["linux"]) == 0


@TestScenario
def count_present_any_non_off_status(self):
    for status in ("ready", "busy", "initializing"):
        s = _runner_server(labels=["linux"], status=status)
        assert count_present([s], ["linux"]) == 1


@TestScenario
def count_present_label_mismatch(self):
    s = _runner_server(labels=["linux"])
    assert count_present([s], ["arm64"]) == 0


# ---------------------------------------------------------------------------
# get_total_server_count / get_server_count_with_labels
# ---------------------------------------------------------------------------


@TestScenario
def get_total_server_count_no_futures(self):
    assert get_total_server_count(["a", "b", "c"]) == 3


@TestScenario
def get_total_server_count_with_futures(self):
    assert get_total_server_count(["a"], ["f1", "f2"]) == 3


@TestScenario
def get_total_server_count_empty(self):
    assert get_total_server_count([]) == 0


@TestScenario
def get_total_server_count_none_futures(self):
    assert get_total_server_count(["a", "b"], None) == 2


@TestScenario
def get_server_count_with_labels_no_servers(self):
    assert get_server_count_with_labels([], {"linux"}) == 0


@TestScenario
def get_server_count_with_labels_matching_counted(self):
    s = _runner_server(labels=["linux", "self-hosted"])
    assert get_server_count_with_labels([s], {"linux"}) == 1


@TestScenario
def get_server_count_with_labels_non_matching(self):
    s = _runner_server(labels=["linux"])
    assert get_server_count_with_labels([s], {"arm64"}) == 0


@TestScenario
def get_server_count_with_labels_future_matching_counted(self):
    f = MagicMock()
    f.server_labels = {"linux", "self-hosted"}
    assert get_server_count_with_labels([], {"linux"}, futures=[f]) == 1


@TestScenario
def get_server_count_with_labels_future_without_attr_skipped(self):
    f = MagicMock(spec=[])
    assert get_server_count_with_labels([], {"linux"}, futures=[f]) == 0


@TestScenario
def get_server_count_with_labels_combined(self):
    s = _runner_server(labels=["linux"])
    f = MagicMock()
    f.server_labels = {"linux"}
    assert get_server_count_with_labels([s], {"linux"}, futures=[f]) == 2


# ---------------------------------------------------------------------------
# check_max_servers_for_label_reached
# ---------------------------------------------------------------------------


@TestScenario
def check_max_no_limits_configured(self):
    reached, info = check_max_servers_for_label_reached([], {"linux"}, [])
    assert reached is False
    assert info is None


@TestScenario
def check_max_under_limit(self):
    servers = [_runner_server(labels=["linux"])]
    reached, _ = check_max_servers_for_label_reached(
        [(frozenset(["linux"]), 3)], {"linux"}, servers
    )
    assert reached is False


@TestScenario
def check_max_at_limit_returns_true(self):
    servers = [_runner_server(labels=["linux"]), _runner_server(labels=["linux"])]
    reached, info = check_max_servers_for_label_reached(
        [(frozenset(["linux"]), 2)], {"linux"}, servers
    )
    assert reached is True
    assert info[2] == 2


@TestScenario
def check_max_job_labels_not_subset_skipped(self):
    servers = [_runner_server(labels=["linux"])] * 5
    reached, _ = check_max_servers_for_label_reached(
        [(frozenset(["linux", "arm64"]), 1)], {"linux"}, servers
    )
    assert reached is False


@TestScenario
def check_max_futures_counted(self):
    f = MagicMock()
    f.server_labels = {"linux"}
    reached, info = check_max_servers_for_label_reached(
        [(frozenset(["linux"]), 1)], {"linux"}, [], futures=[f]
    )
    assert reached is True


# ---------------------------------------------------------------------------
# set_future_attributes
# ---------------------------------------------------------------------------


@TestScenario
def set_future_attributes_sets_all(self):
    future = MagicMock()
    loc = MagicMock()
    st = MagicMock()
    set_future_attributes(future, "myserver", st, loc, [], {"linux"})
    assert future.server_name == "myserver"
    assert future.server_type is st
    assert future.server_location is loc
    assert future.server_volumes == []
    assert future.server_labels == {"linux"}


# ---------------------------------------------------------------------------
# recyclable_server_match — helpers + scenarios
# ---------------------------------------------------------------------------


def _vol(name):
    v = MagicMock()
    v.name = name
    return v


def _net(ipv4=True, ipv6=False):
    n = MagicMock(spec=["enable_ipv4", "enable_ipv6"])
    n.enable_ipv4 = ipv4
    n.enable_ipv6 = ipv6
    return n


def _ssh_key(name="mykey"):
    k = MagicMock()
    k.name = name
    return k


def _recyclable_server(
    type_name="cx22",
    location_name="nbg1",
    volume_names=None,
    ipv4=True,
    ipv6=False,
    ssh_key_label="mykey",
):
    native = MagicMock()
    native.public_net.ipv4 = MagicMock() if ipv4 else None
    native.public_net.ipv6 = MagicMock() if ipv6 else None
    native.labels = {server_ssh_key_label: ssh_key_label}
    return _runner_server(
        server_type_name=type_name,
        server_location_name=location_name,
        server_volumes=[_vol(n) for n in (volume_names or [])],
        native=native,
    )


@TestScenario
def recyclable_full_match(self):
    server = _recyclable_server()
    assert recyclable_server_match(
        server=server,
        server_type="cx22",
        server_location="nbg1",
        server_volumes=[],
        server_net_config=_net(ipv4=True, ipv6=False),
        ssh_key=_ssh_key("mykey"),
    ) is True


@TestScenario
def recyclable_type_mismatch(self):
    server = _recyclable_server(type_name="cx22")
    assert recyclable_server_match(
        server=server,
        server_type="cx32",
        server_location="nbg1",
        server_volumes=[],
        server_net_config=_net(),
        ssh_key=_ssh_key("mykey"),
    ) is False


@TestScenario
def recyclable_location_mismatch(self):
    server = _recyclable_server(location_name="nbg1")
    assert recyclable_server_match(
        server=server,
        server_type="cx22",
        server_location="fsn1",
        server_volumes=[],
        server_net_config=_net(),
        ssh_key=_ssh_key("mykey"),
    ) is False


@TestScenario
def recyclable_none_location_skips_check(self):
    server = _recyclable_server(location_name="nbg1")
    assert recyclable_server_match(
        server=server,
        server_type="cx22",
        server_location=None,
        server_volumes=[],
        server_net_config=_net(),
        ssh_key=_ssh_key("mykey"),
    ) is True


@TestScenario
def recyclable_volume_mismatch(self):
    server = _recyclable_server(volume_names=["data"])
    assert recyclable_server_match(
        server=server,
        server_type="cx22",
        server_location="nbg1",
        server_volumes=[_vol("other")],
        server_net_config=_net(),
        ssh_key=_ssh_key("mykey"),
    ) is False


@TestScenario
def recyclable_ipv4_required_but_missing(self):
    server = _recyclable_server(ipv4=False)
    assert recyclable_server_match(
        server=server,
        server_type="cx22",
        server_location="nbg1",
        server_volumes=[],
        server_net_config=_net(ipv4=True),
        ssh_key=_ssh_key("mykey"),
    ) is False


@TestScenario
def recyclable_ipv4_not_required_but_present(self):
    server = _recyclable_server(ipv4=True)
    assert recyclable_server_match(
        server=server,
        server_type="cx22",
        server_location="nbg1",
        server_volumes=[],
        server_net_config=_net(ipv4=False),
        ssh_key=_ssh_key("mykey"),
    ) is False


@TestScenario
def recyclable_ipv6_required_but_missing(self):
    server = _recyclable_server(ipv4=True, ipv6=False)
    assert recyclable_server_match(
        server=server,
        server_type="cx22",
        server_location="nbg1",
        server_volumes=[],
        server_net_config=_net(ipv4=True, ipv6=True),
        ssh_key=_ssh_key("mykey"),
    ) is False


@TestScenario
def recyclable_ipv6_not_required_but_present(self):
    server = _recyclable_server(ipv4=True, ipv6=True)
    assert recyclable_server_match(
        server=server,
        server_type="cx22",
        server_location="nbg1",
        server_volumes=[],
        server_net_config=_net(ipv4=True, ipv6=False),
        ssh_key=_ssh_key("mykey"),
    ) is False


@TestScenario
def recyclable_ssh_key_mismatch(self):
    server = _recyclable_server(ssh_key_label="oldkey")
    assert recyclable_server_match(
        server=server,
        server_type="cx22",
        server_location="nbg1",
        server_volumes=[],
        server_net_config=_net(),
        ssh_key=_ssh_key("newkey"),
    ) is False


# ---------------------------------------------------------------------------
# Feature entry point
# ---------------------------------------------------------------------------


@TestFeature
@Name("scale_up helpers")
def feature(self):
    """Pure helper functions in scale_up.py."""
    for scenario in loads(current_module(), Scenario):
        scenario()
