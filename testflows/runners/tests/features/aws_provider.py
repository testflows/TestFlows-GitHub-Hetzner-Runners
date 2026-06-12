"""Tests for AWSCloudProvider.

boto3 is mocked at the Session level so no real API calls are made.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from testflows.core import *

from testflows.runners.cloud_provider import CloudProvider, ProviderServer, ProviderServerType
from testflows.runners.providers.aws.provider import AWSCloudProvider, AWSKeyPair
from testflows.runners.providers.aws.utils import (
    _az_to_region,
    _tags_to_dict,
    _instance_to_provider,
    _ARM64_RE,
)
from testflows.runners.errors import ServerTypeError, ImageError, LocationError
from testflows.runners.tests.steps.aws import mock_ec2, aws_provider


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


def _ps(instance_id="i-abc", labels=None):
    return ProviderServer(
        id=instance_id,
        name="runner",
        status=CloudProvider.STATUS_RUNNING,
        public_ipv4="1.2.3.4",
        private_ipv4=None,
        labels=labels or {},
        server_type="t3.medium",
        location="us-east-1a",
        created=datetime.now(timezone.utc),
    )


def _paginated(instances):
    return {"Reservations": [{"Instances": instances}]}


def _setup_create(ec2, instance):
    ec2.run_instances.return_value = {"Instances": [instance]}
    ec2.describe_instances.return_value = {
        "Reservations": [{"Instances": [instance]}]
    }


def _ps_with_labels(labels):
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


def _mock_ec2_instance_tags(ec2, tags):
    ec2.describe_instances.return_value = {
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


_FAKE_KEY = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB test@host"


# ---------------------------------------------------------------------------
# Module-level helpers: _az_to_region, _tags_to_dict, _instance_to_provider, _ARM64_RE
# ---------------------------------------------------------------------------


@TestScenario
def az_to_region_strips_trailing_letter(self):
    assert _az_to_region("us-east-1a") == "us-east-1"


@TestScenario
def az_to_region_strips_trailing_letter_b(self):
    assert _az_to_region("eu-west-2b") == "eu-west-2"


@TestScenario
def az_to_region_empty_returns_default(self):
    assert _az_to_region("") == "us-east-1"


@TestScenario
def az_to_region_none_returns_default(self):
    assert _az_to_region(None) == "us-east-1"


@TestScenario
def tags_to_dict_converts_list(self):
    tags = [{"Key": "Name", "Value": "my-server"}, {"Key": "env", "Value": "prod"}]
    assert _tags_to_dict(tags) == {"Name": "my-server", "env": "prod"}


@TestScenario
def tags_to_dict_empty_list(self):
    assert _tags_to_dict([]) == {}


@TestScenario
def tags_to_dict_none(self):
    assert _tags_to_dict(None) == {}


@TestScenario
def instance_to_provider_basic_conversion(self):
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


@TestScenario
def instance_to_provider_name_falls_back_to_id(self):
    instance = _make_instance(
        instance_id="i-abc",
        tags=[{"Key": "github-runner", "Value": "active"}],
    )
    ps = _instance_to_provider(instance)
    assert ps.name == "i-abc"


@TestScenario
def instance_to_provider_ipv6_from_network_interfaces(self):
    instance = _make_instance()
    instance["NetworkInterfaces"] = [
        {"Ipv6Addresses": [{"Ipv6Address": "2001:db8::1"}]}
    ]
    ps = _instance_to_provider(instance)
    assert ps.public_ipv6 == "2001:db8::1"


@TestScenario
def instance_to_provider_state_mapping(self):
    for state, expected in [
        ("pending", CloudProvider.STATUS_STARTING),
        ("running", CloudProvider.STATUS_RUNNING),
        ("stopping", CloudProvider.STATUS_STOPPING),
        ("stopped", CloudProvider.STATUS_OFF),
        ("shutting-down", CloudProvider.STATUS_DELETING),
        ("terminated", CloudProvider.STATUS_DELETING),
    ]:
        with When(f"state is {state!r}"):
            instance = _make_instance(state=state)
            ps = _instance_to_provider(instance)
        with Then(f"status maps to {expected}"):
            assert ps.status == expected, f"state={state}"


@TestScenario
def arm64_re_t4g_matches(self):
    assert _ARM64_RE.match("t4g.micro") is not None


@TestScenario
def arm64_re_m6g_matches(self):
    assert _ARM64_RE.match("m6g.large") is not None


@TestScenario
def arm64_re_c7g_matches(self):
    assert _ARM64_RE.match("c7g.xlarge") is not None


@TestScenario
def arm64_re_r6g_matches(self):
    assert _ARM64_RE.match("r6g.2xlarge") is not None


@TestScenario
def arm64_re_a1_matches(self):
    assert _ARM64_RE.match("a1.medium") is not None


@TestScenario
def arm64_re_t3_does_not_match(self):
    assert _ARM64_RE.match("t3.medium") is None


@TestScenario
def arm64_re_m5_does_not_match(self):
    assert _ARM64_RE.match("m5.large") is None


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


@TestScenario
def name_is_aws(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with Then("its name is 'aws'"):
        assert provider.name == "aws"


@TestScenario
def supports_recycling_is_false(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with Then("supports_recycling is False"):
        assert provider.supports_recycling is False


@TestScenario
def rebuild_raises_not_implemented(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I call rebuild_server"):
        ps = MagicMock(spec=ProviderServer)
        try:
            provider.rebuild_server(ps, "ami-12345")
            raised = False
        except NotImplementedError:
            raised = True
    with Then("NotImplementedError is raised"):
        assert raised


@TestScenario
def default_image_is_none_when_not_set(self):
    with Given("mocked EC2 client"):
        mock_ec2()
    with When("I construct a provider with no default_image_spec"):
        p = AWSCloudProvider("key", "secret", "us-east-1")
    with Then("default_image is None"):
        assert p.default_image is None


@TestScenario
def default_image_returned_when_set(self):
    with Given("mocked EC2 client"):
        mock_ec2()
    with When("I construct a provider with default_image_spec='ami-abc123'"):
        p = AWSCloudProvider("key", "secret", "us-east-1", default_image_spec="ami-abc123")
    with Then("default_image is 'ami-abc123'"):
        assert p.default_image == "ami-abc123"


# ---------------------------------------------------------------------------
# list_servers / list_runner_servers
# ---------------------------------------------------------------------------


@TestScenario
def list_servers_active_states_filter(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call list_servers"):
        ec2.describe_instances.return_value = {"Reservations": []}
        provider.list_servers()
    with Then("the describe filter restricts to active instance states"):
        ec2.describe_instances.assert_called_once()
        filters = ec2.describe_instances.call_args[1]["Filters"]
        state_filter = next(f for f in filters if f["Name"] == "instance-state-name")
        assert set(state_filter["Values"]) == {"pending", "running", "stopping", "stopped"}


@TestScenario
def list_servers_with_label_selector(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call list_servers with a label selector"):
        ec2.describe_instances.return_value = {"Reservations": []}
        provider.list_servers(label_selector="github-runner=active")
    with Then("the selector is translated to a tag filter"):
        filters = ec2.describe_instances.call_args[1]["Filters"]
        tag_filter = next(f for f in filters if f["Name"] == "tag:github-runner")
        assert tag_filter["Values"] == ["active"]


@TestScenario
def list_servers_returns_provider_servers(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call list_servers with two instances available"):
        ec2.describe_instances.return_value = _paginated(
            [_make_instance(), _make_instance(instance_id="i-other", name="other")]
        )
        result = provider.list_servers()
    with Then("two ProviderServer objects are returned"):
        assert len(result) == 2
        assert all(isinstance(s, ProviderServer) for s in result)


@TestScenario
def list_runner_servers_uses_runner_tag(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call list_runner_servers"):
        ec2.describe_instances.return_value = {"Reservations": []}
        provider.list_runner_servers()
    with Then("the describe filter is `tag:github-runner=active`"):
        filters = ec2.describe_instances.call_args[1]["Filters"]
        tag_filter = next(f for f in filters if f["Name"] == "tag:github-runner")
        assert tag_filter["Values"] == ["active"]


# ---------------------------------------------------------------------------
# get_server
# ---------------------------------------------------------------------------


@TestScenario
def get_server_returns_provider_server(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call get_server('my-runner') and EC2 returns one match"):
        ec2.describe_instances.return_value = {
            "Reservations": [{"Instances": [_make_instance(name="my-runner")]}]
        }
        result = provider.get_server("my-runner")
    with Then("a ProviderServer with the matching name is returned"):
        assert isinstance(result, ProviderServer)
        assert result.name == "my-runner"


@TestScenario
def get_server_returns_none_when_missing(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call get_server with no matching instances"):
        ec2.describe_instances.return_value = {"Reservations": []}
        result = provider.get_server("missing-runner")
    with Then("None is returned"):
        assert result is None


# ---------------------------------------------------------------------------
# create_server
# ---------------------------------------------------------------------------


@TestScenario
def create_server_correct_run_instances_args(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call create_server"):
        instance = _make_instance()
        _setup_create(ec2, instance)

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
    with Then("run_instances is called with the expected args"):
        call_kwargs = ec2.run_instances.call_args[1]
        assert call_kwargs["ImageId"] == "ami-12345"
        assert call_kwargs["InstanceType"] == "t3.medium"
        assert call_kwargs["KeyName"] == "my-key-pair"
        assert "Placement" not in call_kwargs
        iface = call_kwargs["NetworkInterfaces"][0]
        assert iface["SubnetId"] == "subnet-12345"
        assert iface["Groups"] == ["sg-12345"]
        assert iface["AssociatePublicIpAddress"] is True
        assert "SubnetId" not in call_kwargs
        assert "SecurityGroupIds" not in call_kwargs
        assert isinstance(result, ProviderServer)


@TestScenario
def create_server_waits_for_running(self):
    """create_server must wait for the instance to reach running state so
    that the re-describe can capture the public IP address."""
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call create_server"):
        instance = _make_instance(public_ip="54.1.2.3")
        _setup_create(ec2, instance)
        result = provider.create_server(
            name="test",
            server_type=ProviderServerType(name="t3.micro"),
            location=None,
            image="ami-abc",
            ssh_keys=[],
            labels={},
        )
    with Then("the provider waits for 'instance_running' and re-describes"):
        ec2.get_waiter.assert_called_once_with("instance_running")
        ec2.get_waiter.return_value.wait.assert_called_once()
        ec2.describe_instances.assert_called()
        assert result.public_ipv4 == "54.1.2.3"


@TestScenario
def create_server_no_ssh_key_skips_key_name(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call create_server with no ssh keys"):
        instance = _make_instance()
        _setup_create(ec2, instance)
        provider.create_server(
            name="test",
            server_type=ProviderServerType(name="t3.micro"),
            location=None,
            image="ami-abc",
            ssh_keys=[],
            labels={},
        )
    with Then("KeyName is omitted from the run_instances call"):
        assert "KeyName" not in ec2.run_instances.call_args[1]


# ---------------------------------------------------------------------------
# delete_server / power_off / power_on
# ---------------------------------------------------------------------------


@TestScenario
def delete_server_calls_terminate(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call delete_server"):
        provider.delete_server(_ps("i-del"))
    with Then("terminate_instances is called with the instance id"):
        ec2.terminate_instances.assert_called_once_with(InstanceIds=["i-del"])


@TestScenario
def power_off_calls_stop(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call power_off_server"):
        provider.power_off_server(_ps("i-stop"))
    with Then("stop_instances is called with the instance id"):
        ec2.stop_instances.assert_called_once_with(InstanceIds=["i-stop"])


@TestScenario
def power_on_calls_start(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call power_on_server"):
        provider.power_on_server(_ps("i-start"))
    with Then("start_instances is called with the instance id"):
        ec2.start_instances.assert_called_once_with(InstanceIds=["i-start"])


# ---------------------------------------------------------------------------
# get_runner_labels
# ---------------------------------------------------------------------------


@TestScenario
def get_runner_labels_extracts(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I call get_runner_labels on a server with numbered label tags"):
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
        result = provider.get_runner_labels(ps)
    with Then("the labels are returned lowercased"):
        assert result == {"self-hosted", "linux"}


@TestScenario
def get_runner_labels_ignores_non_label_tags(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I call get_runner_labels on a server with only non-label tags"):
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
        result = provider.get_runner_labels(ps)
    with Then("the result is an empty set"):
        assert result == set()


# ---------------------------------------------------------------------------
# build_server_labels / build_volume_labels
# ---------------------------------------------------------------------------


@TestScenario
def build_server_labels_includes_runner_tag(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I call build_server_labels"):
        labels = provider.build_server_labels(["self-hosted", "linux"])
    with Then("the active marker tag is present"):
        assert labels["github-runner"] == "active"


@TestScenario
def build_server_labels_numbered_keys(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I call build_server_labels with three labels"):
        labels = provider.build_server_labels(["self-hosted", "linux", "x64"])
    with Then("each label is stored under a numbered key"):
        assert labels["github-runner-label-0"] == "self-hosted"
        assert labels["github-runner-label-1"] == "linux"
        assert labels["github-runner-label-2"] == "x64"


@TestScenario
def build_server_labels_includes_ssh_key(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I call build_server_labels with ssh_key_name"):
        labels = provider.build_server_labels(["self-hosted"], ssh_key_name="my-key")
    with Then("the ssh-key tag is present"):
        assert labels["github-runner-ssh-key"] == "my-key"


@TestScenario
def build_server_labels_no_ssh_key_when_none(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I call build_server_labels without ssh_key_name"):
        labels = provider.build_server_labels(["self-hosted"])
    with Then("no ssh-key tag is added"):
        assert "github-runner-ssh-key" not in labels


@TestScenario
def build_volume_labels(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I call build_volume_labels"):
        labels = provider.build_volume_labels("x64", "ubuntu", "22.04")
    with Then("arch / os / version tags are set"):
        assert labels["github-runner-volume"] == "active"
        assert labels["github-runner-arch"] == "x64"
        assert labels["github-runner-os"] == "ubuntu"
        assert labels["github-runner-os-version"] == "22.04"


# ---------------------------------------------------------------------------
# validate_labels
# ---------------------------------------------------------------------------


@TestScenario
def validate_labels_valid(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I validate a label dict with valid keys and values"):
        ok, msg = provider.validate_labels({"Name": "runner", "env": "test"})
    with Then("validation passes with no message"):
        assert ok is True
        assert msg == ""


@TestScenario
def validate_labels_key_too_long(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I validate a label dict with a 129-character key"):
        ok, msg = provider.validate_labels({"k" * 129: "val"})
    with Then("validation fails with a message mentioning the 128-char limit"):
        assert ok is False
        assert "128" in msg


@TestScenario
def validate_labels_value_too_long(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I validate a label dict with a 257-character value"):
        ok, msg = provider.validate_labels({"key": "v" * 257})
    with Then("validation fails with a message mentioning the 256-char limit"):
        assert ok is False
        assert "256" in msg


@TestScenario
def validate_labels_reserved_aws_prefix(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I validate a label dict using the reserved `aws:` prefix"):
        ok, msg = provider.validate_labels({"aws:internal": "val"})
    with Then("validation fails and the message mentions the reserved prefix"):
        assert ok is False
        assert "aws:" in msg.lower()


# ---------------------------------------------------------------------------
# update_server
# ---------------------------------------------------------------------------


@TestScenario
def update_server_updates_name_and_labels(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call update_server with a new name and new labels"):
        ps = _ps_with_labels({"old-key": "old-val"})
        _mock_ec2_instance_tags(ec2, {"Name": "old-name", "old-key": "old-val"})
        result = provider.update_server(ps, name="new-name", labels={"github-runner": "active"})
    with Then("create_tags is called and the result reflects the new name"):
        ec2.create_tags.assert_called_once()
        call_kwargs = ec2.create_tags.call_args[1]
        assert call_kwargs["Resources"] == ["i-1"]
        tag_dict = {t["Key"]: t["Value"] for t in call_kwargs["Tags"]}
        assert tag_dict["Name"] == "new-name"
        assert tag_dict["github-runner"] == "active"
        assert result.name == "new-name"
        assert result is ps


@TestScenario
def update_server_deletes_stale_tags(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call update_server without a previously-present tag"):
        ps = _ps_with_labels({"stale-key": "stale-val", "keep-key": "keep-val"})
        _mock_ec2_instance_tags(
            ec2, {"Name": "old-name", "stale-key": "stale-val", "keep-key": "keep-val"}
        )
        provider.update_server(ps, name="new-name", labels={"keep-key": "keep-val"})
    with Then("delete_tags is called with the stale key only"):
        ec2.delete_tags.assert_called_once()
        deleted_keys = {t["Key"] for t in ec2.delete_tags.call_args[1]["Tags"]}
        assert deleted_keys == {"stale-key"}


@TestScenario
def update_server_no_delete_when_no_tags_removed(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I update only the value of an existing tag"):
        ps = _ps_with_labels({"keep-key": "keep-val"})
        _mock_ec2_instance_tags(ec2, {"Name": "old-name", "keep-key": "keep-val"})
        provider.update_server(ps, name="new-name", labels={"keep-key": "new-val"})
    with Then("delete_tags is not called"):
        ec2.delete_tags.assert_not_called()


@TestScenario
def update_server_in_memory_labels_reflect_new(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call update_server with a new label set"):
        ps = _ps_with_labels({"stale": "gone", "k": "v"})
        _mock_ec2_instance_tags(ec2, {"Name": "old-name", "stale": "gone", "k": "v"})
        provider.update_server(ps, name="new-name", labels={"k": "v2"})
    with Then("the ProviderServer.labels reflect the new set"):
        assert "stale" not in ps.labels
        assert ps.labels["k"] == "v2"
        assert ps.labels["Name"] == "new-name"


@TestScenario
def update_server_uses_remote_tag_state(self):
    """Cleanup uses EC2 tag state, not only the local ProviderServer snapshot."""
    with Given("an AWS provider and a server whose remote tags include a stale-key not in the local snapshot"):
        ec2, provider = aws_provider()
        ps = _ps_with_labels({"keep-key": "keep-val"})
        _mock_ec2_instance_tags(
            ec2, {"Name": "old-name", "stale-key": "stale-val", "keep-key": "keep-val"}
        )
    with When("I call update_server"):
        provider.update_server(ps, name="new-name", labels={"keep-key": "keep-val"})
    with Then("delete_tags is called for the remote-only stale tag"):
        ec2.delete_tags.assert_called_once()
        deleted_keys = {t["Key"] for t in ec2.delete_tags.call_args[1]["Tags"]}
        assert deleted_keys == {"stale-key"}


@TestScenario
def update_server_skips_reserved_aws_tags(self):
    with Given("an AWS provider and a server with an `aws:`-prefixed tag remotely"):
        ec2, provider = aws_provider()
        ps = _ps_with_labels({"keep-key": "keep-val"})
        _mock_ec2_instance_tags(
            ec2, {"Name": "old-name", "aws:managed": "1", "keep-key": "keep-val"}
        )
    with When("I call update_server"):
        provider.update_server(ps, name="new-name", labels={"keep-key": "keep-val"})
    with Then("delete_tags is not called (reserved tags are skipped)"):
        ec2.delete_tags.assert_not_called()


# ---------------------------------------------------------------------------
# get_server_arch
# ---------------------------------------------------------------------------


@TestScenario
def get_server_arch_x64_for_t3(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with Then("t3.medium maps to x64"):
        assert provider.get_server_arch(ProviderServerType(name="t3.medium")) == "x64"


@TestScenario
def get_server_arch_arm64_for_t4g(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with Then("t4g.medium maps to arm64"):
        assert provider.get_server_arch(ProviderServerType(name="t4g.medium")) == "arm64"


@TestScenario
def get_server_arch_arm64_for_m6g(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with Then("m6g.large maps to arm64"):
        assert provider.get_server_arch(ProviderServerType(name="m6g.large")) == "arm64"


@TestScenario
def get_server_arch_x64_for_m5(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with Then("m5.large maps to x64"):
        assert provider.get_server_arch(ProviderServerType(name="m5.large")) == "x64"


# ---------------------------------------------------------------------------
# get_server_type
# ---------------------------------------------------------------------------


@TestScenario
def get_server_type_returns_provider_server_type(self):
    with Given("an AWS provider"):
        ec2, provider = aws_provider()
    with When("I call get_server_type('t3.medium') and EC2 returns it"):
        ec2.describe_instance_types.return_value = {
            "InstanceTypes": [{"InstanceType": "t3.medium"}]
        }
        result = provider.get_server_type("t3.medium")
    with Then("a ProviderServerType with the matching name is returned"):
        assert isinstance(result, ProviderServerType)
        assert result.name == "t3.medium"


@TestScenario
def get_server_type_raises_when_not_found(self):
    from botocore.exceptions import ClientError

    with Given("an AWS provider whose EC2 returns InvalidInstanceType"):
        ec2, provider = aws_provider()
        error_response = {"Error": {"Code": "InvalidInstanceType", "Message": "Not found"}}
        ec2.describe_instance_types.side_effect = ClientError(
            error_response, "DescribeInstanceTypes"
        )
    with When("I call get_server_type('invalid-type')"):
        try:
            provider.get_server_type("invalid-type")
            raised = False
        except ServerTypeError:
            raised = True
    with Then("ServerTypeError is raised"):
        assert raised


@TestScenario
def get_server_type_raises_when_empty_response(self):
    with Given("an AWS provider whose EC2 returns an empty InstanceTypes list"):
        ec2, provider = aws_provider()
        ec2.describe_instance_types.return_value = {"InstanceTypes": []}
    with When("I call get_server_type"):
        try:
            provider.get_server_type("t3.medium")
            raised = False
        except ServerTypeError:
            raised = True
    with Then("ServerTypeError is raised"):
        assert raised


# ---------------------------------------------------------------------------
# get_location
# ---------------------------------------------------------------------------


@TestScenario
def get_location_returns_az_name(self):
    with Given("an AWS provider whose EC2 confirms the AZ exists"):
        ec2, provider = aws_provider()
        ec2.describe_availability_zones.return_value = {
            "AvailabilityZones": [{"ZoneName": "us-east-1a"}]
        }
    with When("I call get_location('us-east-1a')"):
        result = provider.get_location("us-east-1a")
    with Then("the AZ name is returned"):
        assert result == "us-east-1a"


@TestScenario
def get_location_returns_none_when_optional(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I call get_location(None, required=False)"):
        result = provider.get_location(None, required=False)
    with Then("None is returned"):
        assert result is None


@TestScenario
def get_location_raises_when_required_and_none(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I call get_location(None, required=True)"):
        try:
            provider.get_location(None, required=True)
            raised = False
        except LocationError:
            raised = True
    with Then("LocationError is raised"):
        assert raised


@TestScenario
def get_location_raises_when_not_found(self):
    with Given("an AWS provider whose EC2 returns no AZs"):
        ec2, provider = aws_provider()
        ec2.describe_availability_zones.return_value = {"AvailabilityZones": []}
    with When("I call get_location('invalid-az')"):
        try:
            provider.get_location("invalid-az")
            raised = False
        except LocationError:
            raised = True
    with Then("LocationError is raised"):
        assert raised


# ---------------------------------------------------------------------------
# get_image
# ---------------------------------------------------------------------------


@TestScenario
def get_image_returns_ami_id_for_direct_spec(self):
    with Given("an AWS provider whose EC2 confirms the AMI exists"):
        ec2, provider = aws_provider()
        ec2.describe_images.return_value = {"Images": [{"ImageId": "ami-12345"}]}
    with When("I call get_image('ami-12345')"):
        result = provider.get_image("ami-12345")
    with Then("the AMI id is returned unchanged"):
        assert result == "ami-12345"


@TestScenario
def get_image_resolves_ssm_path(self):
    with Given("an AWS provider with SSM and EC2 wired up"):
        ec2, provider = aws_provider()
        mock_ssm = MagicMock()
        provider._session.client.return_value = mock_ssm
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "ami-resolved"}}
        ec2.describe_images.return_value = {"Images": [{"ImageId": "ami-resolved"}]}
    with When("I call get_image with a `resolve:ssm:` spec"):
        result = provider.get_image("resolve:ssm:/aws/service/canonical/ubuntu/22.04")
    with Then("the resolved AMI id is returned"):
        assert result == "ami-resolved"


@TestScenario
def get_image_raises_for_unsupported_spec(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I call get_image with a non-AMI / non-SSM spec"):
        try:
            provider.get_image("ubuntu-22.04")
            raised = False
        except ImageError:
            raised = True
    with Then("ImageError is raised"):
        assert raised


@TestScenario
def get_image_raises_when_none(self):
    with Given("an AWS provider"):
        _, provider = aws_provider()
    with When("I call get_image(None)"):
        try:
            provider.get_image(None)
            raised = False
        except ImageError:
            raised = True
    with Then("ImageError is raised"):
        assert raised


@TestScenario
def get_image_raises_when_ami_not_found(self):
    with Given("an AWS provider whose EC2 returns no Images"):
        ec2, provider = aws_provider()
        ec2.describe_images.return_value = {"Images": []}
    with When("I call get_image with a non-existent AMI id"):
        try:
            provider.get_image("ami-missing")
            raised = False
        except ImageError:
            raised = True
    with Then("ImageError is raised"):
        assert raised


# ---------------------------------------------------------------------------
# get_or_create_ssh_key
# ---------------------------------------------------------------------------


@TestScenario
def ssh_key_imports_when_not_found(self):
    from botocore.exceptions import ClientError

    with Given("an AWS provider whose EC2 reports KeyPair NotFound"):
        ec2, provider = aws_provider()
        error_response = {"Error": {"Code": "InvalidKeyPair.NotFound", "Message": "Not found"}}
        ec2.describe_key_pairs.side_effect = ClientError(error_response, "DescribeKeyPairs")
        ec2.import_key_pair.return_value = {}
    with When("I call get_or_create_ssh_key with raw key material"):
        result = provider.get_or_create_ssh_key(_FAKE_KEY)
    with Then("import_key_pair is called with the key material"):
        assert isinstance(result, AWSKeyPair)
        ec2.import_key_pair.assert_called_once()
        assert ec2.import_key_pair.call_args[1]["PublicKeyMaterial"] == _FAKE_KEY.strip().encode("utf-8")


@TestScenario
def ssh_key_returns_existing_when_found(self):
    with Given("an AWS provider whose EC2 already has the key"):
        ec2, provider = aws_provider()
        ec2.describe_key_pairs.return_value = {"KeyPairs": [{"KeyName": "abc"}]}
    with When("I call get_or_create_ssh_key"):
        result = provider.get_or_create_ssh_key(_FAKE_KEY)
    with Then("import_key_pair is not called"):
        assert isinstance(result, AWSKeyPair)
        ec2.import_key_pair.assert_not_called()


@TestScenario
def ssh_key_name_is_md5(self):
    import hashlib

    with Given("an AWS provider whose EC2 returns an existing key"):
        ec2, provider = aws_provider()
        ec2.describe_key_pairs.return_value = {"KeyPairs": []}
        ec2.describe_key_pairs.side_effect = None
        ec2.describe_key_pairs.return_value = {"KeyPairs": [{"KeyName": "existing"}]}
    with When("I call get_or_create_ssh_key"):
        result = provider.get_or_create_ssh_key(_FAKE_KEY)
    with Then("the key name is the md5 hex of the key material"):
        expected_name = hashlib.md5(_FAKE_KEY.strip().encode("utf-8")).hexdigest()
        assert result.name == expected_name


@TestScenario
def ssh_key_reads_file_when_is_file_true(self):
    with Given("an AWS provider whose EC2 already has the key"):
        ec2, provider = aws_provider()
        ec2.describe_key_pairs.return_value = {"KeyPairs": [{"KeyName": "k"}]}
    with When("I call get_or_create_ssh_key with is_file=True"):
        with patch("builtins.open", MagicMock()) as mock_open:
            mock_open.return_value.__enter__ = MagicMock(
                return_value=MagicMock(read=MagicMock(return_value=_FAKE_KEY))
            )
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            result = provider.get_or_create_ssh_key("/path/to/key.pub", is_file=True)
    with Then("the file is read and an AWSKeyPair is returned"):
        mock_open.assert_called_once_with("/path/to/key.pub", "r", encoding="utf-8")
        assert isinstance(result, AWSKeyPair)


# ---------------------------------------------------------------------------
# Feature entry point
# ---------------------------------------------------------------------------


@TestFeature
@Name("aws provider")
def feature(self):
    """AWSCloudProvider unit tests."""
    for scenario in loads(current_module(), Scenario):
        scenario()
