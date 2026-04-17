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

"""Tests for AWSCloudProvider.

boto3 is mocked at the Session level so no real API calls are made.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

from testflows.runners.cloud_provider import CloudProvider, ProviderServer, ProviderServerType
from testflows.runners.providers.aws.provider import (
    AWSCloudProvider,
    AWSKeyPair,
    _az_to_region,
    _tags_to_dict,
    _instance_to_provider,
    _ARM64_RE,
)
from testflows.runners.errors import ServerTypeError, ImageError, LocationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instance(
    instance_id="i-1234567890abcdef0",
    name="github-runner-123",
    state="running",
    public_ip="1.2.3.4",
    private_ip="10.0.0.1",
    instance_type="t3.medium",
    az="us-east-1a",
    tags=None,
):
    """Build a minimal boto3 EC2 instance dict."""
    if tags is None:
        tags = [{"Key": "Name", "Value": name}, {"Key": "github-runner", "Value": "active"}]
    return {
        "InstanceId": instance_id,
        "State": {"Name": state},
        "PublicIpAddress": public_ip,
        "PrivateIpAddress": private_ip,
        "InstanceType": instance_type,
        "Placement": {"AvailabilityZone": az},
        "LaunchTime": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "Tags": tags,
        "NetworkInterfaces": [],
    }


@pytest.fixture
def mock_ec2():
    """Patch boto3.Session and return a mock EC2 client."""
    with patch("boto3.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value = mock_session
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        yield mock_client


@pytest.fixture
def provider(mock_ec2):
    """Return an AWSCloudProvider with a mocked boto3 Session."""
    p = AWSCloudProvider(
        access_key_id="AKIATEST",
        secret_access_key="secret",
        region="us-east-1",
        security_group="sg-12345",
        subnet="subnet-12345",
    )
    return p


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestAzToRegion:
    def test_strips_trailing_letter(self):
        assert _az_to_region("us-east-1a") == "us-east-1"

    def test_strips_trailing_letter_b(self):
        assert _az_to_region("eu-west-2b") == "eu-west-2"

    def test_empty_string_returns_default(self):
        assert _az_to_region("") == "us-east-1"

    def test_none_returns_default(self):
        assert _az_to_region(None) == "us-east-1"


class TestTagsToDict:
    def test_converts_list_to_dict(self):
        tags = [{"Key": "Name", "Value": "my-server"}, {"Key": "env", "Value": "prod"}]
        assert _tags_to_dict(tags) == {"Name": "my-server", "env": "prod"}

    def test_empty_list_returns_empty_dict(self):
        assert _tags_to_dict([]) == {}

    def test_none_returns_empty_dict(self):
        assert _tags_to_dict(None) == {}


class TestInstanceToProvider:
    def test_basic_conversion(self):
        instance = _make_instance()
        ps = _instance_to_provider(instance)
        assert isinstance(ps, ProviderServer)
        assert ps.id == "i-1234567890abcdef0"
        assert ps.name == "github-runner-123"
        assert ps.status == CloudProvider.STATUS_RUNNING
        assert ps.public_ipv4 == "1.2.3.4"
        assert ps.private_ipv4 == "10.0.0.1"
        assert ps.server_type == "t3.medium"
        assert ps.location == "us-east-1a"

    def test_name_falls_back_to_instance_id_when_no_name_tag(self):
        instance = _make_instance(
            instance_id="i-abc",
            tags=[{"Key": "github-runner", "Value": "active"}],
        )
        ps = _instance_to_provider(instance)
        assert ps.name == "i-abc"

    def test_ipv6_extracted_from_network_interfaces(self):
        instance = _make_instance()
        instance["NetworkInterfaces"] = [
            {"Ipv6Addresses": [{"Ipv6Address": "2001:db8::1"}]}
        ]
        ps = _instance_to_provider(instance)
        assert ps.public_ipv6 == "2001:db8::1"

    def test_state_mapping(self):
        for state, expected in [
            ("pending", CloudProvider.STATUS_STARTING),
            ("running", CloudProvider.STATUS_RUNNING),
            ("stopping", CloudProvider.STATUS_STOPPING),
            ("stopped", CloudProvider.STATUS_OFF),
            ("shutting-down", CloudProvider.STATUS_DELETING),
            ("terminated", CloudProvider.STATUS_DELETING),
        ]:
            instance = _make_instance(state=state)
            ps = _instance_to_provider(instance)
            assert ps.status == expected, f"state={state}"


class TestArm64Re:
    def test_t4g_matches(self):
        assert _ARM64_RE.match("t4g.micro") is not None

    def test_m6g_matches(self):
        assert _ARM64_RE.match("m6g.large") is not None

    def test_c7g_matches(self):
        assert _ARM64_RE.match("c7g.xlarge") is not None

    def test_r6g_matches(self):
        assert _ARM64_RE.match("r6g.2xlarge") is not None

    def test_a1_matches(self):
        assert _ARM64_RE.match("a1.medium") is not None

    def test_t3_does_not_match(self):
        assert _ARM64_RE.match("t3.medium") is None

    def test_m5_does_not_match(self):
        assert _ARM64_RE.match("m5.large") is None


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_name(self, provider):
        assert provider.name == "aws"

    def test_supports_recycling_is_false(self, provider):
        assert provider.supports_recycling is False

    def test_rebuild_raises_not_implemented(self, provider):
        ps = MagicMock(spec=ProviderServer)
        with pytest.raises(NotImplementedError):
            provider.rebuild_server(ps, "ami-12345")

    def test_default_image_is_none_when_not_set(self, mock_ec2):
        p = AWSCloudProvider("key", "secret", "us-east-1")
        assert p.default_image is None

    def test_default_image_returned_when_set(self, mock_ec2):
        p = AWSCloudProvider(
            "key", "secret", "us-east-1", default_image_spec="ami-abc123"
        )
        assert p.default_image == "ami-abc123"


# ---------------------------------------------------------------------------
# list_servers / list_runner_servers
# ---------------------------------------------------------------------------


class TestListServers:
    def _paginated(self, instances):
        return {"Reservations": [{"Instances": instances}]}

    def test_list_servers_calls_describe_with_active_states(self, provider, mock_ec2):
        mock_ec2.describe_instances.return_value = {"Reservations": []}
        provider.list_servers()
        mock_ec2.describe_instances.assert_called_once()
        filters = mock_ec2.describe_instances.call_args[1]["Filters"]
        state_filter = next(f for f in filters if f["Name"] == "instance-state-name")
        assert set(state_filter["Values"]) == {"pending", "running", "stopping", "stopped"}

    def test_list_servers_with_label_selector(self, provider, mock_ec2):
        mock_ec2.describe_instances.return_value = {"Reservations": []}
        provider.list_servers(label_selector="github-runner=active")
        filters = mock_ec2.describe_instances.call_args[1]["Filters"]
        tag_filter = next(f for f in filters if f["Name"] == "tag:github-runner")
        assert tag_filter["Values"] == ["active"]

    def test_list_servers_returns_provider_server_list(self, provider, mock_ec2):
        mock_ec2.describe_instances.return_value = self._paginated(
            [_make_instance(), _make_instance(instance_id="i-other", name="other")]
        )
        result = provider.list_servers()
        assert len(result) == 2
        assert all(isinstance(s, ProviderServer) for s in result)

    def test_list_runner_servers_uses_runner_tag(self, provider, mock_ec2):
        mock_ec2.describe_instances.return_value = {"Reservations": []}
        provider.list_runner_servers()
        filters = mock_ec2.describe_instances.call_args[1]["Filters"]
        tag_filter = next(f for f in filters if f["Name"] == "tag:github-runner")
        assert tag_filter["Values"] == ["active"]


# ---------------------------------------------------------------------------
# get_server
# ---------------------------------------------------------------------------


class TestGetServer:
    def test_returns_provider_server_when_found(self, provider, mock_ec2):
        mock_ec2.describe_instances.return_value = {
            "Reservations": [{"Instances": [_make_instance(name="my-runner")]}]
        }
        result = provider.get_server("my-runner")
        assert isinstance(result, ProviderServer)
        assert result.name == "my-runner"

    def test_returns_none_when_not_found(self, provider, mock_ec2):
        mock_ec2.describe_instances.return_value = {"Reservations": []}
        result = provider.get_server("missing-runner")
        assert result is None


# ---------------------------------------------------------------------------
# create_server
# ---------------------------------------------------------------------------


class TestCreateServer:
    def test_calls_run_instances_with_correct_args(self, provider, mock_ec2):
        instance = _make_instance()
        mock_ec2.run_instances.return_value = {"Instances": [instance]}

        server_type = ProviderServerType(name="t3.medium")
        ssh_key = AWSKeyPair(name="my-key-pair")

        result = provider.create_server(
            name="test-runner",
            server_type=server_type,
            location="us-east-1a",
            image="ami-12345",
            ssh_keys=[ssh_key],
            labels={"github-runner": "active"},
        )

        call_kwargs = mock_ec2.run_instances.call_args[1]
        assert call_kwargs["ImageId"] == "ami-12345"
        assert call_kwargs["InstanceType"] == "t3.medium"
        assert call_kwargs["KeyName"] == "my-key-pair"
        assert call_kwargs["Placement"] == {"AvailabilityZone": "us-east-1a"}
        # When a subnet is configured, subnet and security group go into
        # NetworkInterfaces so AssociatePublicIpAddress can be set.
        iface = call_kwargs["NetworkInterfaces"][0]
        assert iface["SubnetId"] == "subnet-12345"
        assert iface["Groups"] == ["sg-12345"]
        assert iface["AssociatePublicIpAddress"] is True
        assert "SubnetId" not in call_kwargs
        assert "SecurityGroupIds" not in call_kwargs

        assert isinstance(result, ProviderServer)

    def test_no_ssh_key_skips_key_name(self, provider, mock_ec2):
        mock_ec2.run_instances.return_value = {"Instances": [_make_instance()]}
        provider.create_server(
            name="test",
            server_type=ProviderServerType(name="t3.micro"),
            location=None,
            image="ami-abc",
            ssh_keys=[],
            labels={},
        )
        call_kwargs = mock_ec2.run_instances.call_args[1]
        assert "KeyName" not in call_kwargs


# ---------------------------------------------------------------------------
# delete_server / power_off / power_on
# ---------------------------------------------------------------------------


class TestServerLifecycle:
    def _make_ps(self, instance_id="i-abc"):
        ps = ProviderServer(
            id=instance_id,
            name="runner",
            status=CloudProvider.STATUS_RUNNING,
            public_ipv4="1.2.3.4",
            private_ipv4=None,
            labels={},
            server_type="t3.medium",
            location="us-east-1a",
            created=datetime.now(timezone.utc),
        )
        return ps

    def test_delete_server_calls_terminate(self, provider, mock_ec2):
        ps = self._make_ps("i-del")
        provider.delete_server(ps)
        mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=["i-del"])

    def test_power_off_calls_stop(self, provider, mock_ec2):
        ps = self._make_ps("i-stop")
        provider.power_off_server(ps)
        mock_ec2.stop_instances.assert_called_once_with(InstanceIds=["i-stop"])

    def test_power_on_calls_start(self, provider, mock_ec2):
        ps = self._make_ps("i-start")
        provider.power_on_server(ps)
        mock_ec2.start_instances.assert_called_once_with(InstanceIds=["i-start"])


# ---------------------------------------------------------------------------
# get_runner_labels
# ---------------------------------------------------------------------------


class TestGetRunnerLabels:
    def test_extracts_runner_labels(self, provider):
        ps = ProviderServer(
            id="i-1",
            name="r",
            status="running",
            public_ipv4=None,
            private_ipv4=None,
            labels={
                "github-runner-label-0": "self-hosted",
                "github-runner-label-1": "Linux",
                "github-runner": "active",
            },
            server_type="t3.medium",
            location="us-east-1a",
            created=datetime.now(timezone.utc),
        )
        labels = provider.get_runner_labels(ps)
        assert labels == {"self-hosted", "linux"}

    def test_ignores_non_label_tags(self, provider):
        ps = ProviderServer(
            id="i-1",
            name="r",
            status="running",
            public_ipv4=None,
            private_ipv4=None,
            labels={"github-runner": "active", "Name": "my-server"},
            server_type="t3.medium",
            location="us-east-1a",
            created=datetime.now(timezone.utc),
        )
        assert provider.get_runner_labels(ps) == set()


# ---------------------------------------------------------------------------
# build_server_labels / build_volume_labels
# ---------------------------------------------------------------------------


class TestBuildLabels:
    def test_build_server_labels_includes_runner_tag(self, provider):
        labels = provider.build_server_labels(["self-hosted", "linux"])
        assert labels["github-runner"] == "active"

    def test_build_server_labels_stores_each_label_under_numbered_key(self, provider):
        labels = provider.build_server_labels(["self-hosted", "linux", "x64"])
        assert labels["github-runner-label-0"] == "self-hosted"
        assert labels["github-runner-label-1"] == "linux"
        assert labels["github-runner-label-2"] == "x64"

    def test_build_server_labels_includes_ssh_key(self, provider):
        labels = provider.build_server_labels(["self-hosted"], ssh_key_name="my-key")
        assert labels["github-runner-ssh-key"] == "my-key"

    def test_build_server_labels_no_ssh_key_when_none(self, provider):
        labels = provider.build_server_labels(["self-hosted"])
        assert "github-runner-ssh-key" not in labels

    def test_build_volume_labels(self, provider):
        labels = provider.build_volume_labels("x64", "ubuntu", "22.04")
        assert labels["github-runner-volume"] == "active"
        assert labels["github-runner-arch"] == "x64"
        assert labels["github-runner-os"] == "ubuntu"
        assert labels["github-runner-os-version"] == "22.04"


# ---------------------------------------------------------------------------
# validate_labels
# ---------------------------------------------------------------------------


class TestValidateLabels:
    def test_valid_labels_return_true(self, provider):
        ok, msg = provider.validate_labels({"Name": "runner", "env": "test"})
        assert ok is True
        assert msg == ""

    def test_key_too_long_returns_false(self, provider):
        long_key = "k" * 129
        ok, msg = provider.validate_labels({long_key: "val"})
        assert ok is False
        assert "128" in msg

    def test_value_too_long_returns_false(self, provider):
        ok, msg = provider.validate_labels({"key": "v" * 257})
        assert ok is False
        assert "256" in msg

    def test_reserved_aws_prefix_returns_false(self, provider):
        ok, msg = provider.validate_labels({"aws:internal": "val"})
        assert ok is False
        assert "aws:" in msg.lower()


# ---------------------------------------------------------------------------
# update_server
# ---------------------------------------------------------------------------


class TestUpdateServer:
    def _make_ps(self, labels):
        return ProviderServer(
            id="i-1",
            name="old-name",
            status="running",
            public_ipv4=None,
            private_ipv4=None,
            labels=labels,
            server_type="t3.medium",
            location="us-east-1a",
            created=datetime.now(timezone.utc),
        )

    def _mock_ec2_instance_tags(self, mock_ec2, tags):
        mock_ec2.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1",
                            "Tags": [{"Key": k, "Value": v} for k, v in tags.items()],
                        }
                    ]
                }
            ]
        }

    def test_updates_name_and_labels(self, provider, mock_ec2):
        ps = self._make_ps({"old-key": "old-val"})
        self._mock_ec2_instance_tags(mock_ec2, {"Name": "old-name", "old-key": "old-val"})
        new_labels = {"github-runner": "active"}
        result = provider.update_server(ps, name="new-name", labels=new_labels)

        mock_ec2.create_tags.assert_called_once()
        call_kwargs = mock_ec2.create_tags.call_args[1]
        assert call_kwargs["Resources"] == ["i-1"]
        tag_dict = {t["Key"]: t["Value"] for t in call_kwargs["Tags"]}
        assert tag_dict["Name"] == "new-name"
        assert tag_dict["github-runner"] == "active"

        assert result.name == "new-name"
        assert result is ps

    def test_deletes_tags_not_in_new_set(self, provider, mock_ec2):
        """Old tags absent from the new label dict must be removed from EC2."""
        ps = self._make_ps({"stale-key": "stale-val", "keep-key": "keep-val"})
        self._mock_ec2_instance_tags(
            mock_ec2, {"Name": "old-name", "stale-key": "stale-val", "keep-key": "keep-val"}
        )
        result = provider.update_server(ps, name="new-name", labels={"keep-key": "keep-val"})

        mock_ec2.delete_tags.assert_called_once()
        del_kwargs = mock_ec2.delete_tags.call_args[1]
        deleted_keys = {t["Key"] for t in del_kwargs["Tags"]}
        assert deleted_keys == {"stale-key"}

    def test_no_delete_call_when_no_tags_removed(self, provider, mock_ec2):
        """delete_tags should not be called when no old tags are dropped."""
        ps = self._make_ps({"keep-key": "keep-val"})
        self._mock_ec2_instance_tags(mock_ec2, {"Name": "old-name", "keep-key": "keep-val"})
        provider.update_server(ps, name="new-name", labels={"keep-key": "new-val"})
        mock_ec2.delete_tags.assert_not_called()

    def test_in_memory_labels_reflect_new_set(self, provider, mock_ec2):
        ps = self._make_ps({"stale": "gone", "k": "v"})
        self._mock_ec2_instance_tags(mock_ec2, {"Name": "old-name", "stale": "gone", "k": "v"})
        provider.update_server(ps, name="new-name", labels={"k": "v2"})
        assert "stale" not in ps.labels
        assert ps.labels["k"] == "v2"
        assert ps.labels["Name"] == "new-name"

    def test_deletes_stale_remote_tags_even_if_local_snapshot_missing(self, provider, mock_ec2):
        """Cleanup uses EC2 tag state, not only the local ProviderServer snapshot."""
        ps = self._make_ps({"keep-key": "keep-val"})  # stale-key missing locally
        self._mock_ec2_instance_tags(
            mock_ec2, {"Name": "old-name", "stale-key": "stale-val", "keep-key": "keep-val"}
        )

        provider.update_server(ps, name="new-name", labels={"keep-key": "keep-val"})

        mock_ec2.delete_tags.assert_called_once()
        del_kwargs = mock_ec2.delete_tags.call_args[1]
        deleted_keys = {t["Key"] for t in del_kwargs["Tags"]}
        assert deleted_keys == {"stale-key"}

    def test_does_not_try_to_delete_reserved_aws_tags(self, provider, mock_ec2):
        ps = self._make_ps({"keep-key": "keep-val"})
        self._mock_ec2_instance_tags(
            mock_ec2, {"Name": "old-name", "aws:managed": "1", "keep-key": "keep-val"}
        )

        provider.update_server(ps, name="new-name", labels={"keep-key": "keep-val"})

        mock_ec2.delete_tags.assert_not_called()


# ---------------------------------------------------------------------------
# get_server_arch
# ---------------------------------------------------------------------------


class TestGetServerArch:
    def test_x64_for_t3(self, provider):
        assert provider.get_server_arch(ProviderServerType(name="t3.medium")) == "x64"

    def test_arm64_for_t4g(self, provider):
        assert provider.get_server_arch(ProviderServerType(name="t4g.medium")) == "arm64"

    def test_arm64_for_m6g(self, provider):
        assert provider.get_server_arch(ProviderServerType(name="m6g.large")) == "arm64"

    def test_x64_for_m5(self, provider):
        assert provider.get_server_arch(ProviderServerType(name="m5.large")) == "x64"


# ---------------------------------------------------------------------------
# get_server_type
# ---------------------------------------------------------------------------


class TestGetServerType:
    def test_returns_provider_server_type(self, provider, mock_ec2):
        mock_ec2.describe_instance_types.return_value = {
            "InstanceTypes": [{"InstanceType": "t3.medium"}]
        }
        result = provider.get_server_type("t3.medium")
        assert isinstance(result, ProviderServerType)
        assert result.name == "t3.medium"

    def test_raises_server_type_error_when_not_found(self, provider, mock_ec2):
        from botocore.exceptions import ClientError

        error_response = {
            "Error": {"Code": "InvalidInstanceType", "Message": "Not found"}
        }
        mock_ec2.describe_instance_types.side_effect = ClientError(
            error_response, "DescribeInstanceTypes"
        )
        with pytest.raises(ServerTypeError):
            provider.get_server_type("invalid-type")

    def test_raises_server_type_error_when_empty_response(self, provider, mock_ec2):
        mock_ec2.describe_instance_types.return_value = {"InstanceTypes": []}
        with pytest.raises(ServerTypeError):
            provider.get_server_type("t3.medium")


# ---------------------------------------------------------------------------
# get_location
# ---------------------------------------------------------------------------


class TestGetLocation:
    def test_returns_az_name(self, provider, mock_ec2):
        mock_ec2.describe_availability_zones.return_value = {
            "AvailabilityZones": [{"ZoneName": "us-east-1a"}]
        }
        result = provider.get_location("us-east-1a")
        assert result == "us-east-1a"

    def test_returns_none_when_name_is_none_and_not_required(self, provider, mock_ec2):
        result = provider.get_location(None, required=False)
        assert result is None

    def test_raises_location_error_when_required_and_none(self, provider, mock_ec2):
        with pytest.raises(LocationError):
            provider.get_location(None, required=True)

    def test_raises_location_error_when_not_found(self, provider, mock_ec2):
        mock_ec2.describe_availability_zones.return_value = {"AvailabilityZones": []}
        with pytest.raises(LocationError):
            provider.get_location("invalid-az")


# ---------------------------------------------------------------------------
# get_image
# ---------------------------------------------------------------------------


class TestGetImage:
    def test_returns_ami_id_for_direct_spec(self, provider, mock_ec2):
        mock_ec2.describe_images.return_value = {
            "Images": [{"ImageId": "ami-12345"}]
        }
        result = provider.get_image("ami-12345")
        assert result == "ami-12345"

    def test_resolves_ssm_path(self, provider, mock_ec2):
        mock_session = provider._session
        mock_ssm = MagicMock()
        mock_session.client.return_value = mock_ssm
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": "ami-resolved"}
        }
        mock_ec2.describe_images.return_value = {"Images": [{"ImageId": "ami-resolved"}]}

        result = provider.get_image("resolve:ssm:/aws/service/canonical/ubuntu/22.04")
        assert result == "ami-resolved"

    def test_raises_image_error_for_unsupported_spec(self, provider, mock_ec2):
        with pytest.raises(ImageError):
            provider.get_image("ubuntu-22.04")

    def test_raises_image_error_when_none(self, provider, mock_ec2):
        with pytest.raises(ImageError):
            provider.get_image(None)

    def test_raises_image_error_when_ami_not_found(self, provider, mock_ec2):
        mock_ec2.describe_images.return_value = {"Images": []}
        with pytest.raises(ImageError):
            provider.get_image("ami-missing")


# ---------------------------------------------------------------------------
# get_or_create_ssh_key
# ---------------------------------------------------------------------------


class TestGetOrCreateSSHKey:
    _FAKE_KEY = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB test@host"

    def test_imports_key_when_not_found(self, provider, mock_ec2):
        from botocore.exceptions import ClientError

        error_response = {
            "Error": {"Code": "InvalidKeyPair.NotFound", "Message": "Not found"}
        }
        mock_ec2.describe_key_pairs.side_effect = ClientError(
            error_response, "DescribeKeyPairs"
        )
        mock_ec2.import_key_pair.return_value = {}

        result = provider.get_or_create_ssh_key(self._FAKE_KEY)
        assert isinstance(result, AWSKeyPair)
        mock_ec2.import_key_pair.assert_called_once()
        call_kwargs = mock_ec2.import_key_pair.call_args[1]
        assert call_kwargs["PublicKeyMaterial"] == self._FAKE_KEY.strip().encode("utf-8")

    def test_returns_existing_key_when_found(self, provider, mock_ec2):
        mock_ec2.describe_key_pairs.return_value = {"KeyPairs": [{"KeyName": "abc"}]}

        result = provider.get_or_create_ssh_key(self._FAKE_KEY)
        assert isinstance(result, AWSKeyPair)
        mock_ec2.import_key_pair.assert_not_called()

    def test_key_name_is_md5_of_key(self, provider, mock_ec2):
        import hashlib

        mock_ec2.describe_key_pairs.return_value = {"KeyPairs": []}
        # Make describe succeed (no exception) so it returns immediately.
        mock_ec2.describe_key_pairs.side_effect = None
        mock_ec2.describe_key_pairs.return_value = {"KeyPairs": [{"KeyName": "existing"}]}

        result = provider.get_or_create_ssh_key(self._FAKE_KEY)
        expected_name = hashlib.md5(self._FAKE_KEY.strip().encode("utf-8")).hexdigest()
        assert result.name == expected_name

    def test_reads_file_when_is_file_true(self, provider, mock_ec2):
        mock_ec2.describe_key_pairs.return_value = {"KeyPairs": [{"KeyName": "k"}]}

        with patch("builtins.open", MagicMock()) as mock_open:
            mock_open.return_value.__enter__ = MagicMock(
                return_value=MagicMock(read=MagicMock(return_value=self._FAKE_KEY))
            )
            mock_open.return_value.__exit__ = MagicMock(return_value=False)

            result = provider.get_or_create_ssh_key("/path/to/key.pub", is_file=True)

        mock_open.assert_called_once_with("/path/to/key.pub", "r", encoding="utf-8")
        assert isinstance(result, AWSKeyPair)
