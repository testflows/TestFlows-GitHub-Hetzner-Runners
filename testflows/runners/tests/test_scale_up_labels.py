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

"""Tests for label-parsing helpers in scale_up.py.

All functions under test are pure (no I/O, no API calls).
"""

import pytest
from unittest.mock import MagicMock

from hcloud.server_types.domain import ServerType

from testflows.runners.scale_up import (
    _resolve_provider,
    expand_meta_label,
    get_server_locations,
    get_server_net_config,
    get_server_types,
    get_server_image,
    get_server_volumes,
    parse_volume_size,
)
from testflows.runners.cloud_provider import ProviderServerType
from testflows.runners.errors import ServerTypeError


# ---------------------------------------------------------------------------
# parse_volume_size
# ---------------------------------------------------------------------------


class TestParseVolumeSize:
    def test_plain_integer(self):
        assert parse_volume_size("20", 10) == 20

    def test_gb_suffix(self):
        assert parse_volume_size("50GB", 10) == 50

    def test_gb_suffix_case_insensitive(self):
        assert parse_volume_size("50gb", 10) == 50

    def test_invalid_returns_default(self):
        assert parse_volume_size("notanumber", 10) == 10

    def test_empty_string_returns_default(self):
        assert parse_volume_size("", 15) == 15

    def test_negative_value_returns_abs(self):
        assert parse_volume_size("-20", 10) == 20


# ---------------------------------------------------------------------------
# get_server_arch — tested via HetznerCloudProvider (the canonical implementation)
# ---------------------------------------------------------------------------

from testflows.runners.providers.hetzner.provider import (
    HetznerCloudProvider as _HetznerProvider,
)


class TestGetServerArch:
    """Test HetznerCloudProvider.get_server_arch.

    get_server_arch is a pure method (no self._client access) so we call it
    as an unbound function.
    """

    def _arch(self, name):
        return _HetznerProvider.get_server_arch(None, ProviderServerType(name=name))

    def test_x64_for_standard_type(self):
        assert self._arch("cx23") == "x64"

    def test_arm64_for_ca_prefix(self):
        assert self._arch("cax11") == "arm64"

    def test_arm64_uppercase(self):
        assert self._arch("CAX31") == "arm64"

    def test_x64_for_ccx_type(self):
        assert self._arch("ccx13") == "x64"


# ---------------------------------------------------------------------------
# get_server_types
# ---------------------------------------------------------------------------


class TestGetServerTypes:
    def test_single_type_label(self):
        result = get_server_types(["type-cx23"], default="cx11")
        assert result == ["cx23"]

    def test_multiple_type_labels(self):
        result = get_server_types(["type-cx23", "type-cx33"], default="cx11")
        assert result == ["cx23", "cx33"]

    def test_falls_back_to_default_when_no_type_label(self):
        result = get_server_types(["self-hosted", "linux"], default="cx11")
        assert result == ["cx11"]

    def test_default_servertype_object_extracts_name(self):
        # Config may still hold a validated ServerType object during startup.
        default = ServerType(name="cx11")
        result = get_server_types(["self-hosted"], default=default)
        assert result == ["cx11"]

    def test_composite_type_labels_are_skipped(self):
        # "type-cx23-cx33" is a composite label — it should be ignored here
        result = get_server_types(["type-cx23-cx33"], default="cx11")
        assert result == ["cx11"]

    def test_label_prefix(self):
        result = get_server_types(["myprefix-type-cx23"], default="cx11", label_prefix="myprefix")
        assert result == ["cx23"]

    def test_case_insensitive(self):
        result = get_server_types(["TYPE-CX23"], default="cx11")
        assert result == ["cx23"]

    def test_unrelated_labels_ignored(self):
        result = get_server_types(["self-hosted", "linux", "type-cx23"], default="cx11")
        assert result == ["cx23"]


# ---------------------------------------------------------------------------
# get_server_locations
# ---------------------------------------------------------------------------


class TestGetServerLocations:
    def test_single_location_label(self):
        result = get_server_locations(["in-nbg1"])
        assert result == ["nbg1"]

    def test_multiple_location_labels(self):
        result = get_server_locations(["in-nbg1", "in-fsn1"])
        assert result == ["nbg1", "fsn1"]

    def test_falls_back_to_default_when_no_in_label(self):
        result = get_server_locations(["self-hosted"], default="hel1")
        assert result == ["hel1"]

    def test_default_none_when_no_label(self):
        result = get_server_locations(["self-hosted"])
        assert result == [None]

    def test_aws_az_style_location(self):
        """AWS AZ names like us-east-1a contain dashes and must not be dropped."""
        result = get_server_locations(["in-us-east-1a"])
        assert result == ["us-east-1a"]

    def test_hetzner_location_with_dash_passthrough(self):
        """A location name that contains a dash is returned as-is."""
        result = get_server_locations(["in-nbg1-fsn1"])
        assert result == ["nbg1-fsn1"]

    def test_label_prefix(self):
        result = get_server_locations(["myprefix-in-nbg1"], label_prefix="myprefix")
        assert result == ["nbg1"]

    def test_case_insensitive(self):
        result = get_server_locations(["IN-NBG1"])
        assert result == ["nbg1"]


# ---------------------------------------------------------------------------
# get_server_volumes
# ---------------------------------------------------------------------------


class TestGetServerVolumes:
    def test_volume_without_size_uses_default(self):
        result = get_server_volumes(["volume-mydata"], default=10)
        assert len(result) == 1
        assert result[0].name == "mydata"
        assert result[0].size == 10

    def test_volume_with_explicit_size(self):
        result = get_server_volumes(["volume-mydata-20"], default=10)
        assert result[0].size == 20

    def test_volume_with_gb_suffix(self):
        result = get_server_volumes(["volume-mydata-50gb"], default=10)
        assert result[0].size == 50

    def test_multiple_volumes(self):
        result = get_server_volumes(["volume-data-20", "volume-cache-5"], default=10)
        names = {v.name: v.size for v in result}
        assert names == {"data": 20, "cache": 5}

    def test_duplicate_volume_name_last_wins(self):
        # dict deduplication: last occurrence of the name wins
        result = get_server_volumes(["volume-data-20", "volume-data-30"], default=10)
        assert len(result) == 1
        assert result[0].size == 30

    def test_no_volume_labels_returns_empty(self):
        result = get_server_volumes(["self-hosted", "linux"])
        assert result == []

    def test_label_prefix(self):
        result = get_server_volumes(["myprefix-volume-mydata-20"], default=10, label_prefix="myprefix")
        assert result[0].name == "mydata"
        assert result[0].size == 20


# ---------------------------------------------------------------------------
# get_server_net_config
# ---------------------------------------------------------------------------


class TestGetServerNetConfig:
    def test_defaults_to_both_ipv4_and_ipv6(self):
        cfg = get_server_net_config([])
        assert cfg.enable_ipv4 is True
        assert cfg.enable_ipv6 is True

    def test_ipv4_only(self):
        cfg = get_server_net_config(["net-ipv4"])
        assert cfg.enable_ipv4 is True
        assert cfg.enable_ipv6 is False

    def test_ipv6_only(self):
        cfg = get_server_net_config(["net-ipv6"])
        assert cfg.enable_ipv4 is False
        assert cfg.enable_ipv6 is True

    def test_both_explicit(self):
        cfg = get_server_net_config(["net-ipv4", "net-ipv6"])
        assert cfg.enable_ipv4 is True
        assert cfg.enable_ipv6 is True

    def test_label_prefix(self):
        cfg = get_server_net_config(["myprefix-net-ipv4"], label_prefix="myprefix")
        assert cfg.enable_ipv4 is True
        assert cfg.enable_ipv6 is False


# ---------------------------------------------------------------------------
# expand_meta_label
# ---------------------------------------------------------------------------


class TestExpandMetaLabel:
    def test_no_meta_labels_returns_input(self):
        result = expand_meta_label({}, ["self-hosted", "linux"])
        assert result == ["self-hosted", "linux"]

    def test_expands_known_meta_label(self):
        meta = {"standard-linux": {"type-cx23", "self-hosted"}}
        result = expand_meta_label(meta, ["standard-linux"])
        assert "standard-linux" in result
        assert "type-cx23" in result
        assert "self-hosted" in result

    def test_composite_type_label_is_expanded(self):
        # "type-cx23-cx33" should expand to ["type-cx23", "type-cx33"]
        result = expand_meta_label({}, ["type-cx23-cx33"])
        assert "type-cx23" in result
        assert "type-cx33" in result

    def test_composite_in_label_is_expanded(self):
        result = expand_meta_label({}, ["in-nbg1-fsn1"])
        assert "in-nbg1" in result
        assert "in-fsn1" in result

    def test_original_composite_label_preserved(self):
        result = expand_meta_label({}, ["type-cx23-cx33"])
        assert "type-cx23-cx33" in result

    def test_deduplication(self):
        meta = {"standard-linux": {"type-cx23"}}
        result = expand_meta_label(meta, ["standard-linux", "type-cx23"])
        assert result.count("type-cx23") == 1

    def test_label_prefix(self):
        meta = {}
        result = expand_meta_label(meta, ["myprefix-type-cx23-cx33"], label_prefix="myprefix")
        assert "myprefix-type-cx23" in result
        assert "myprefix-type-cx33" in result

    def test_empty_labels(self):
        result = expand_meta_label({}, [])
        assert result == []


# ---------------------------------------------------------------------------
# get_server_image
# ---------------------------------------------------------------------------


class TestGetServerImage:
    def _make_provider(self, image):
        provider = MagicMock()
        provider.get_image.return_value = image
        return provider

    def test_returns_image_for_matching_label(self):
        img = MagicMock()
        provider = self._make_provider(img)

        result = get_server_image(provider, ["image-x86-system-ubuntu-22.04"], default=None)

        provider.get_image.assert_called_once()
        assert result is img

    def test_falls_back_to_default_when_no_image_label(self):
        default = MagicMock()
        provider = MagicMock()

        result = get_server_image(provider, ["self-hosted", "linux"], default=default)

        provider.get_image.assert_not_called()
        assert result is default

    def test_last_image_label_wins(self):
        img1, img2 = MagicMock(), MagicMock()
        provider = MagicMock()
        provider.get_image.side_effect = [img1, img2]

        result = get_server_image(
            provider,
            ["image-x86-system-ubuntu-22.04", "image-x86-system-ubuntu-24.04"],
            default=None,
        )

        assert provider.get_image.call_count == 2
        assert result is img2

    def test_label_prefix(self):
        img = MagicMock()
        provider = self._make_provider(img)

        result = get_server_image(
            provider,
            ["myprefix-image-x86-system-ubuntu-22.04"],
            default=None,
            label_prefix="myprefix",
        )

        provider.get_image.assert_called_once()
        assert result is img


# ---------------------------------------------------------------------------
# _resolve_provider
# ---------------------------------------------------------------------------


class TestResolveProvider:
    """Tests for _resolve_provider(server_type, providers)."""

    def _make_provider(self, supports_type=True):
        p = MagicMock()
        if supports_type:
            p.get_server_type.return_value = MagicMock()
        else:
            p.get_server_type.side_effect = ServerTypeError("unknown type")
        return p

    def test_single_provider_match(self):
        provider = self._make_provider(supports_type=True)
        resolved_p, resolved_st = _resolve_provider("cx22", [provider])
        assert resolved_p is provider
        provider.get_server_type.assert_called_once_with("cx22")

    def test_returns_validated_server_type(self):
        validated = MagicMock()
        provider = MagicMock()
        provider.get_server_type.return_value = validated
        _, resolved_st = _resolve_provider("cx22", [provider])
        assert resolved_st is validated

    def test_first_matching_provider_wins(self):
        p1 = self._make_provider(supports_type=True)
        p2 = self._make_provider(supports_type=True)
        resolved_p, _ = _resolve_provider("cx22", [p1, p2])
        assert resolved_p is p1
        p2.get_server_type.assert_not_called()

    def test_skips_provider_that_raises(self):
        p1 = self._make_provider(supports_type=False)
        p2 = self._make_provider(supports_type=True)
        resolved_p, _ = _resolve_provider("cx22", [p1, p2])
        assert resolved_p is p2

    def test_raises_server_type_error_when_no_match(self):
        p1 = self._make_provider(supports_type=False)
        p2 = self._make_provider(supports_type=False)
        with pytest.raises(ServerTypeError, match="unknown-type"):
            _resolve_provider("unknown-type", [p1, p2])

    def test_raises_when_providers_empty(self):
        with pytest.raises(ServerTypeError):
            _resolve_provider("cx22", [])

    def test_non_server_type_error_propagates(self):
        """Auth/network errors must not be swallowed as 'type unsupported'."""
        p = MagicMock()
        p.get_server_type.side_effect = ConnectionError("network failure")
        with pytest.raises(ConnectionError):
            _resolve_provider("cx22", [p])
