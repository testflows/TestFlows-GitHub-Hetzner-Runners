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

"""Tests for pure helper functions in scale_up.py."""

import pytest
from unittest.mock import MagicMock

from testflows.runners.cloud_provider import CloudProvider
from testflows.runners.scale_up import (
    RunnerServer,
    check_max_servers_for_label_reached,
    count_available,
    count_available_runners,
    count_present,
    get_job_labels,
    get_runner_server_type_and_location,
    get_server_count_with_labels,
    get_total_server_count,
    get_volume_name,
    job_matches_labels,
    recyclable_server_match,
    set_future_attributes,
)
from testflows.runners.constants import runner_name_prefix, server_ssh_key_label


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RUNNER_PREFIX = runner_name_prefix  # "github-hetzner-runner-"


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
        name=f"{RUNNER_PREFIX}run1-0-{server_type_name}-{server_location_name}",
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


class TestGetVolumeName:
    def test_strips_everything_after_first_dash(self):
        assert get_volume_name("cache-x86-ubuntu-22.04-1234567") == "cache"

    def test_name_without_dash_returned_as_is(self):
        assert get_volume_name("mydata") == "mydata"

    def test_only_first_segment_taken(self):
        assert get_volume_name("a-b-c") == "a"


# ---------------------------------------------------------------------------
# get_runner_server_type_and_location
# ---------------------------------------------------------------------------


class TestGetRunnerServerTypeAndLocation:
    def _name(self, server_type, location):
        # prefix has 3 dashes → "github-hetzner-runner-{run}-{idx}-{type}-{loc}" = 7 parts
        return f"{RUNNER_PREFIX}run1-0-{server_type}-{location}"

    def test_valid_name_returns_type_and_location(self):
        stype, sloc = get_runner_server_type_and_location(self._name("cx22", "nbg1"))
        assert stype == "cx22"
        assert sloc == "nbg1"

    def test_wrong_prefix_returns_none_none(self):
        stype, sloc = get_runner_server_type_and_location("other-runner-run1-0-cx22-nbg1")
        assert stype is None
        assert sloc is None

    def test_too_few_segments_returns_none_none(self):
        # Only 6 parts — missing one field
        stype, sloc = get_runner_server_type_and_location(f"{RUNNER_PREFIX}run1-cx22-nbg1")
        assert stype is None
        assert sloc is None

    def test_empty_string_returns_none_none(self):
        stype, sloc = get_runner_server_type_and_location("")
        assert stype is None
        assert sloc is None

    def test_none_returns_none_none(self):
        stype, sloc = get_runner_server_type_and_location(None)
        assert stype is None
        assert sloc is None


# ---------------------------------------------------------------------------
# get_job_labels
# ---------------------------------------------------------------------------


class TestGetJobLabels:
    def _job(self, labels):
        j = MagicMock()
        j.raw_data = {"labels": labels}
        return j

    def test_returns_lowercased_labels(self):
        assert get_job_labels(self._job(["Self-Hosted", "Linux"])) == [
            "self-hosted",
            "linux",
        ]

    def test_deduplicates_preserving_order(self):
        result = get_job_labels(self._job(["linux", "self-hosted", "linux"]))
        assert result == ["linux", "self-hosted"]

    def test_empty_labels(self):
        assert get_job_labels(self._job([])) == []

    def test_case_insensitive_dedup(self):
        result = get_job_labels(self._job(["Linux", "linux"]))
        assert result == ["linux"]


# ---------------------------------------------------------------------------
# job_matches_labels
# ---------------------------------------------------------------------------


class TestJobMatchesLabels:
    def test_none_with_label_always_matches(self):
        assert job_matches_labels(["linux"], with_label=None) is True

    def test_all_required_labels_present(self):
        assert job_matches_labels(["linux", "self-hosted"], with_label=["linux"]) is True

    def test_missing_required_label_returns_false_tuple(self):
        result = job_matches_labels(["linux"], with_label=["arm64"])
        assert result == (False, "arm64")

    def test_empty_with_label_always_matches(self):
        assert job_matches_labels(["linux"], with_label=[]) is True

    def test_multiple_required_all_present(self):
        assert (
            job_matches_labels(
                ["linux", "self-hosted", "arm64"],
                with_label=["linux", "arm64"],
            )
            is True
        )

    def test_multiple_required_one_missing(self):
        result = job_matches_labels(["linux"], with_label=["linux", "arm64"])
        assert result == (False, "arm64")


# ---------------------------------------------------------------------------
# count_available_runners
# ---------------------------------------------------------------------------


class TestCountAvailableRunners:
    def test_empty_runners(self):
        assert count_available_runners([], ["linux"]) == 0

    def test_online_not_busy_matching_labels(self):
        r = _gh_runner(status="online", busy=False, labels=["linux", "self-hosted"])
        assert count_available_runners([r], ["linux"]) == 1

    def test_offline_runner_not_counted(self):
        r = _gh_runner(status="offline", busy=False, labels=["linux"])
        assert count_available_runners([r], ["linux"]) == 0

    def test_busy_runner_not_counted(self):
        r = _gh_runner(status="online", busy=True, labels=["linux"])
        assert count_available_runners([r], ["linux"]) == 0

    def test_runner_missing_required_label_not_counted(self):
        r = _gh_runner(status="online", busy=False, labels=["linux"])
        assert count_available_runners([r], ["linux", "arm64"]) == 0

    def test_superset_labels_count(self):
        r = _gh_runner(status="online", busy=False, labels=["linux", "arm64", "self-hosted"])
        assert count_available_runners([r], ["linux", "arm64"]) == 1

    def test_multiple_runners_mixed(self):
        runners = [
            _gh_runner(status="online", busy=False, labels=["linux"]),
            _gh_runner(status="online", busy=True, labels=["linux"]),
            _gh_runner(status="offline", busy=False, labels=["linux"]),
        ]
        assert count_available_runners(runners, ["linux"]) == 1


# ---------------------------------------------------------------------------
# count_available / count_present
# ---------------------------------------------------------------------------


class TestCountAvailable:
    def test_empty(self):
        assert count_available([], ["linux"]) == 0

    def test_ready_server_with_matching_labels(self):
        s = _runner_server(labels=["linux"], status="ready")
        assert count_available([s], ["linux"]) == 1

    def test_initializing_server_counted(self):
        s = _runner_server(labels=["linux"], status="initializing")
        assert count_available([s], ["linux"]) == 1

    def test_busy_server_not_counted(self):
        s = _runner_server(labels=["linux"], status="busy")
        assert count_available([s], ["linux"]) == 0

    def test_powered_off_server_not_counted(self):
        s = _runner_server(labels=["linux"], server_status=CloudProvider.STATUS_OFF)
        assert count_available([s], ["linux"]) == 0

    def test_label_mismatch_not_counted(self):
        s = _runner_server(labels=["linux"], status="ready")
        assert count_available([s], ["arm64"]) == 0


class TestCountPresent:
    def test_empty(self):
        assert count_present([], ["linux"]) == 0

    def test_running_server_counted(self):
        s = _runner_server(labels=["linux"])
        assert count_present([s], ["linux"]) == 1

    def test_powered_off_not_counted(self):
        s = _runner_server(labels=["linux"], server_status=CloudProvider.STATUS_OFF)
        assert count_present([s], ["linux"]) == 0

    def test_any_non_off_status_counted(self):
        for status in ("ready", "busy", "initializing"):
            s = _runner_server(labels=["linux"], status=status)
            assert count_present([s], ["linux"]) == 1

    def test_label_mismatch_not_counted(self):
        s = _runner_server(labels=["linux"])
        assert count_present([s], ["arm64"]) == 0


# ---------------------------------------------------------------------------
# get_total_server_count / get_server_count_with_labels
# ---------------------------------------------------------------------------


class TestGetTotalServerCount:
    def test_no_futures(self):
        assert get_total_server_count(["a", "b", "c"]) == 3

    def test_with_futures(self):
        assert get_total_server_count(["a"], ["f1", "f2"]) == 3

    def test_empty(self):
        assert get_total_server_count([]) == 0

    def test_none_futures(self):
        assert get_total_server_count(["a", "b"], None) == 2


class TestGetServerCountWithLabels:
    def test_no_servers(self):
        assert get_server_count_with_labels([], {"linux"}) == 0

    def test_matching_server_counted(self):
        s = _runner_server(labels=["linux", "self-hosted"])
        assert get_server_count_with_labels([s], {"linux"}) == 1

    def test_non_matching_not_counted(self):
        s = _runner_server(labels=["linux"])
        assert get_server_count_with_labels([s], {"arm64"}) == 0

    def test_future_with_matching_labels_counted(self):
        f = MagicMock()
        f.server_labels = {"linux", "self-hosted"}
        assert get_server_count_with_labels([], {"linux"}, futures=[f]) == 1

    def test_future_without_server_labels_attr_skipped(self):
        f = MagicMock(spec=[])  # no attributes
        assert get_server_count_with_labels([], {"linux"}, futures=[f]) == 0

    def test_combined_servers_and_futures(self):
        s = _runner_server(labels=["linux"])
        f = MagicMock()
        f.server_labels = {"linux"}
        assert get_server_count_with_labels([s], {"linux"}, futures=[f]) == 2


# ---------------------------------------------------------------------------
# check_max_servers_for_label_reached
# ---------------------------------------------------------------------------


class TestCheckMaxServersForLabelReached:
    def test_no_limits_configured(self):
        reached, info = check_max_servers_for_label_reached([], {"linux"}, [])
        assert reached is False
        assert info is None

    def test_under_limit(self):
        servers = [_runner_server(labels=["linux"])]
        reached, _ = check_max_servers_for_label_reached(
            [(frozenset(["linux"]), 3)], {"linux"}, servers
        )
        assert reached is False

    def test_at_limit_returns_true(self):
        servers = [_runner_server(labels=["linux"]), _runner_server(labels=["linux"])]
        reached, info = check_max_servers_for_label_reached(
            [(frozenset(["linux"]), 2)], {"linux"}, servers
        )
        assert reached is True
        assert info[2] == 2  # max_count

    def test_job_labels_not_subset_of_limit_set_skipped(self):
        # The limit is for {"linux", "arm64"} but job only has {"linux"}
        servers = [_runner_server(labels=["linux"])] * 5
        reached, _ = check_max_servers_for_label_reached(
            [(frozenset(["linux", "arm64"]), 1)], {"linux"}, servers
        )
        assert reached is False

    def test_futures_counted_toward_limit(self):
        f = MagicMock()
        f.server_labels = {"linux"}
        reached, info = check_max_servers_for_label_reached(
            [(frozenset(["linux"]), 1)], {"linux"}, [], futures=[f]
        )
        assert reached is True


# ---------------------------------------------------------------------------
# set_future_attributes
# ---------------------------------------------------------------------------


class TestSetFutureAttributes:
    def test_attributes_set_on_future(self):
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
# recyclable_server_match
# ---------------------------------------------------------------------------


class TestRecyclableServerMatch:
    def _make_server(
        self,
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
            server_volumes=[self._vol(n) for n in (volume_names or [])],
            native=native,
        )

    def _vol(self, name):
        v = MagicMock()
        v.name = name
        return v

    def _net(self, ipv4=True, ipv6=False):
        n = MagicMock(spec=["enable_ipv4", "enable_ipv6"])
        n.enable_ipv4 = ipv4
        n.enable_ipv6 = ipv6
        return n

    def _ssh_key(self, name="mykey"):
        k = MagicMock()
        k.name = name
        return k

    def test_full_match(self):
        server = self._make_server()
        assert (
            recyclable_server_match(
                server=server,
                server_type="cx22",
                server_location="nbg1",
                server_volumes=[],
                server_net_config=self._net(ipv4=True, ipv6=False),
                ssh_key=self._ssh_key("mykey"),
            )
            is True
        )

    def test_type_mismatch(self):
        server = self._make_server(type_name="cx22")
        assert (
            recyclable_server_match(
                server=server,
                server_type="cx32",
                server_location="nbg1",
                server_volumes=[],
                server_net_config=self._net(),
                ssh_key=self._ssh_key("mykey"),
            )
            is False
        )

    def test_location_mismatch(self):
        server = self._make_server(location_name="nbg1")
        assert (
            recyclable_server_match(
                server=server,
                server_type="cx22",
                server_location="fsn1",
                server_volumes=[],
                server_net_config=self._net(),
                ssh_key=self._ssh_key("mykey"),
            )
            is False
        )

    def test_none_location_skips_location_check(self):
        server = self._make_server(location_name="nbg1")
        assert (
            recyclable_server_match(
                server=server,
                server_type="cx22",
                server_location=None,
                server_volumes=[],
                server_net_config=self._net(),
                ssh_key=self._ssh_key("mykey"),
            )
            is True
        )

    def test_volume_mismatch(self):
        server = self._make_server(volume_names=["data"])
        assert (
            recyclable_server_match(
                server=server,
                server_type="cx22",
                server_location="nbg1",
                server_volumes=[self._vol("other")],
                server_net_config=self._net(),
                ssh_key=self._ssh_key("mykey"),
            )
            is False
        )

    def test_ipv4_required_but_server_has_none(self):
        server = self._make_server(ipv4=False)
        assert (
            recyclable_server_match(
                server=server,
                server_type="cx22",
                server_location="nbg1",
                server_volumes=[],
                server_net_config=self._net(ipv4=True),
                ssh_key=self._ssh_key("mykey"),
            )
            is False
        )

    def test_ipv4_not_required_but_server_has_it(self):
        server = self._make_server(ipv4=True)
        assert (
            recyclable_server_match(
                server=server,
                server_type="cx22",
                server_location="nbg1",
                server_volumes=[],
                server_net_config=self._net(ipv4=False),
                ssh_key=self._ssh_key("mykey"),
            )
            is False
        )

    def test_ipv6_required_but_server_has_none(self):
        server = self._make_server(ipv4=True, ipv6=False)
        assert (
            recyclable_server_match(
                server=server,
                server_type="cx22",
                server_location="nbg1",
                server_volumes=[],
                server_net_config=self._net(ipv4=True, ipv6=True),
                ssh_key=self._ssh_key("mykey"),
            )
            is False
        )

    def test_ipv6_not_required_but_server_has_it(self):
        server = self._make_server(ipv4=True, ipv6=True)
        assert (
            recyclable_server_match(
                server=server,
                server_type="cx22",
                server_location="nbg1",
                server_volumes=[],
                server_net_config=self._net(ipv4=True, ipv6=False),
                ssh_key=self._ssh_key("mykey"),
            )
            is False
        )

    def test_ssh_key_mismatch(self):
        server = self._make_server(ssh_key_label="oldkey")
        assert (
            recyclable_server_match(
                server=server,
                server_type="cx22",
                server_location="nbg1",
                server_volumes=[],
                server_net_config=self._net(),
                ssh_key=self._ssh_key("newkey"),
            )
            is False
        )
