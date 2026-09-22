"""Integration tests: YAML config -> parse_config -> provider_factory propagation.

These tests exercise the full pipeline from YAML text through parse_config()
and provider_factory() to verify that config values reach AWSCloudProvider.
No real AWS calls are made; boto3 is patched at the Session level.
"""
from testflows.core import *

from testflows.github.runners.config.parse import parse_config
from testflows.github.runners.config.factory import provider_factory
from testflows.github.runners.utils import derive_runner_tag
from testflows.github.runners.providers.aws.provider import AWSCloudProvider
from testflows.github.runners.tests.unit.steps.aws import mock_ec2
from testflows.github.runners.tests.unit.steps.config import write_config


# ---------------------------------------------------------------------------
# parse_config: AWS credentials and simple fields
# ---------------------------------------------------------------------------


@TestScenario
def access_key_and_secret_parsed(self):
    """access_key_id and secret_access_key in YAML reach cfg.providers.aws."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AKIATEST
                secret_access_key: s3cr3t
        """)
    with When("I parse the config"):
        cfg = parse_config(path)
    with Then("access_key_id and secret_access_key match"):
        assert cfg.providers.aws.access_key_id == "AKIATEST"
        assert cfg.providers.aws.secret_access_key == "s3cr3t"


@TestScenario
def security_group_and_subnets_parsed(self):
    """security_group and subnets list reach cfg.providers.aws."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                security_group: sg-abc
                subnets:
                  - subnet-xyz
                  - subnet-abc
        """)
    with When("I parse the config"):
        cfg = parse_config(path)
    with Then("security_group and subnets match"):
        assert cfg.providers.aws.security_group == "sg-abc"
        assert cfg.providers.aws.subnets == ["subnet-xyz", "subnet-abc"]


@TestScenario
def subnets_accepts_single_string(self):
    """A scalar `subnets:` value is normalised into a single-element list."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                subnets: subnet-xyz
        """)
    with Then("subnets is a single-element list"):
        cfg = parse_config(path)
        assert cfg.providers.aws.subnets == ["subnet-xyz"]


@TestScenario
def ssh_user_parsed(self):
    """ssh_user in YAML reaches cfg.providers.aws."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                ssh_user: ec2-user
        """)
    with Then("ssh_user matches"):
        cfg = parse_config(path)
        assert cfg.providers.aws.ssh_user == "ec2-user"


@TestScenario
def ssh_user_defaults_to_ubuntu(self):
    """When ssh_user is unspecified, the dataclass default 'ubuntu' is used."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
        """)
    with Then("ssh_user defaults to ubuntu"):
        cfg = parse_config(path)
        assert cfg.providers.aws.ssh_user == "ubuntu"


# ---------------------------------------------------------------------------
# parse_config: AWS defaults section
# ---------------------------------------------------------------------------


@TestScenario
def defaults_image_parsed(self):
    """defaults.image in YAML reaches cfg.providers.aws.defaults.image."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  image: ami-custom123
        """)
    with Then("defaults.image matches"):
        cfg = parse_config(path)
        assert cfg.providers.aws.defaults.image == "ami-custom123"


@TestScenario
def defaults_location_parsed(self):
    """defaults.location in YAML reaches cfg.providers.aws.defaults.location."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  location: eu-west-1b
        """)
    with Then("defaults.location matches"):
        cfg = parse_config(path)
        assert cfg.providers.aws.defaults.location == "eu-west-1b"


@TestScenario
def defaults_server_type_parsed(self):
    """defaults.server_type in YAML reaches cfg.providers.aws.defaults.server_type."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  server_type: c6g.large
        """)
    with Then("defaults.server_type matches"):
        cfg = parse_config(path)
        assert cfg.providers.aws.defaults.server_type == "c6g.large"


@TestScenario
def unspecified_defaults_keep_dataclass_values(self):
    """Fields not present in YAML defaults must fall back to dataclass defaults."""
    from testflows.github.runners.config.config import aws_provider

    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file with one override"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  image: ami-override
        """)
    with Then("only the overridden field changes; others keep dataclass defaults"):
        cfg = parse_config(path)
        base = aws_provider().defaults
        assert cfg.providers.aws.defaults.image == "ami-override"
        assert cfg.providers.aws.defaults.server_type == base.server_type
        assert cfg.providers.aws.defaults.location == base.location
        assert cfg.providers.aws.defaults.disk_size == base.disk_size
        assert cfg.providers.aws.defaults.disk_type == base.disk_type


@TestScenario
def no_defaults_section_uses_dataclass_defaults(self):
    """Without a `defaults:` section, dataclass defaults are used."""
    from testflows.github.runners.config.config import aws_provider

    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file with no defaults section"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
        """)
    with Then("defaults match dataclass values"):
        cfg = parse_config(path)
        base = aws_provider().defaults
        assert cfg.providers.aws.defaults.image == base.image
        assert cfg.providers.aws.defaults.location == base.location


# ---------------------------------------------------------------------------
# provider_factory: YAML values reach AWSCloudProvider
# ---------------------------------------------------------------------------


@TestScenario
def factory_sets_isolation_runner_tag(self):
    """from_config computes the discovery-tag value from repo + with_label, and
    build_server_labels writes it (per-controller isolation)."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config with a custom with_label set"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            with_label:
              - self-hosted
              - gpu
            providers:
              aws:
                access_key_id: AKIATEST
                secret_access_key: s3cr3t
        """)
    with Then("the provider's discovery tag matches derive_runner_tag(config)"):
        cfg = parse_config(path)
        provider = provider_factory(cfg)[0]
        expected = derive_runner_tag(cfg.github_repository, cfg.with_label)
        assert provider._runner_tag == expected, provider._runner_tag
    with And("build_server_labels writes the id under github-runner"):
        labels = provider.build_server_labels(["self-hosted"])
        assert labels["github-runner"] == expected, labels


@TestScenario
def factory_produces_aws_provider(self):
    """provider_factory returns exactly one AWSCloudProvider."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AKIATEST
                secret_access_key: s3cr3t
        """)
    with Then("provider_factory returns one AWSCloudProvider"):
        cfg = parse_config(path)
        providers = provider_factory(cfg)
        assert len(providers) == 1
        assert isinstance(providers[0], AWSCloudProvider)


@TestScenario
def factory_passes_ssh_user(self):
    """ssh_user from YAML reaches AWSCloudProvider._ssh_user."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                ssh_user: ec2-user
        """)
    with Then("provider._ssh_user matches"):
        cfg = parse_config(path)
        provider = provider_factory(cfg)[0]
        assert provider._ssh_user == "ec2-user"


@TestScenario
def factory_passes_default_location(self):
    """defaults.location from YAML reaches AWSCloudProvider._default_location."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  location: ap-southeast-1a
        """)
    with Then("provider._default_location matches"):
        cfg = parse_config(path)
        provider = provider_factory(cfg)[0]
        assert provider._default_location == "ap-southeast-1a"


@TestScenario
def factory_default_location_falls_back_when_unset(self):
    """With no providers.aws.defaults.location in YAML, the provider must still
    behave exactly as when the dataclass default was the literal "us-east-1a"
    string: the region derived for the boto3 client and the AZ used for jobs
    with no in- label both resolve to us-east-1a/us-east-1, not None."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file with no defaults.location"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
        """)
    with When("I parse the config and build the provider"):
        cfg = parse_config(path)
        provider = provider_factory(cfg)[0]
    with Then("the config field itself stays None (distinguishable from 'set')"):
        assert cfg.providers.aws.defaults.location is None, cfg.providers.aws.defaults.location
    with And("the provider's resolved default_location is still us-east-1a"):
        assert provider.default_location == "us-east-1a", provider.default_location
    with And("the region used for the boto3 client is still us-east-1"):
        assert provider._region == "us-east-1", provider._region


@TestScenario
def factory_passes_default_image(self):
    """defaults.image from YAML reaches AWSCloudProvider._default_image."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  image: ami-custom
        """)
    with Then("provider._default_image matches"):
        cfg = parse_config(path)
        provider = provider_factory(cfg)[0]
        assert provider._default_image == "ami-custom"


@TestScenario
def factory_derives_region_from_location(self):
    """region is derived from the trailing-letter-stripped AZ in defaults.location."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  location: eu-central-1b
        """)
    with Then("provider._region is the AZ minus the trailing letter"):
        cfg = parse_config(path)
        provider = provider_factory(cfg)[0]
        assert provider._region == "eu-central-1"


# ---------------------------------------------------------------------------
# parse_config_section: direct unit tests of providers/aws/config.py
# ---------------------------------------------------------------------------


@TestScenario
def aws_parse_section_validates(self):
    """parse_config_section coerces a valid section and rejects an invalid one."""
    from testflows.github.runners.providers.aws import config as aws_config

    with Then("a valid section coerces into the dataclass"):
        cfg = aws_config.parse_config_section(
            {
                "access_key_id": "AK",
                "secret_access_key": "SK",
                "security_group": "sg-1",
            }
        )
        assert cfg.access_key_id == "AK", cfg
    with And("max_runners 0 allowed; negatives rejected"):
        base = {
            "access_key_id": "AK",
            "secret_access_key": "SK",
            "security_group": "sg-1",
        }
        assert (
            aws_config.parse_config_section({**base, "max_runners": 0}).max_runners == 0
        )
        rejected = False
        try:
            aws_config.parse_config_section({**base, "max_runners": -1})
        except AssertionError:
            rejected = True
        assert rejected, "expected rejection of negative max_runners"
    with And("an invalid field is rejected"):
        try:
            aws_config.parse_config_section({"access_key_id": 123})
            assert False, "expected rejection"
        except AssertionError:
            pass


# ---------------------------------------------------------------------------
# update_from_args: CLI overrides reach cfg.providers.aws
# ---------------------------------------------------------------------------


@TestScenario
def update_from_args_overrides_each_field(self):
    """Every --aws-* flag lands on its matching aws_provider field."""
    from types import SimpleNamespace
    from testflows.github.runners.config.config import aws_provider
    from testflows.github.runners.providers.aws import config as aws_config

    cfg = aws_provider()
    args = SimpleNamespace(
        aws_access_key_id="AK",
        aws_secret_access_key="SK",
        aws_security_group="sg-1",
        aws_subnets=["subnet-1", "subnet-2"],
        aws_key_name="keypair-1",
        aws_default_image="ami-0abcdef1234567890",
        aws_default_server_type="c6g.large",
        aws_default_location="us-east-1b",
        aws_default_disk_size=50,
        aws_default_disk_type="gp2",
    )
    with When("update_from_args runs"):
        aws_config.update_from_args(cfg, args)
    with Then("every field is overridden"):
        assert cfg.access_key_id == "AK", cfg
        assert cfg.secret_access_key == "SK", cfg
        assert cfg.security_group == "sg-1", cfg
        assert cfg.subnets == ["subnet-1", "subnet-2"], cfg
        assert cfg.key_name == "keypair-1", cfg
        assert cfg.defaults.image == "ami-0abcdef1234567890", cfg
        assert cfg.defaults.server_type == "c6g.large", cfg
        assert cfg.defaults.location == "us-east-1b", cfg
        assert cfg.defaults.disk_size == 50, cfg
        assert cfg.defaults.disk_type == "gp2", cfg


@TestScenario
def update_from_args_leaves_unset_fields_alone(self):
    """An unset (None) CLI arg must not clobber an already-configured value."""
    from types import SimpleNamespace
    from testflows.github.runners.config.config import aws_provider, provider_defaults
    from testflows.github.runners.providers.aws import config as aws_config

    cfg = aws_provider(
        access_key_id="configured-key",
        secret_access_key="configured-secret",
        security_group="sg-configured",
        subnets=["subnet-configured"],
        key_name="configured-keypair",
        defaults=provider_defaults(
            image="ami-configured",
            server_type="t3.large",
            location="us-east-1a",
            disk_size=30,
            disk_type="gp3",
        ),
    )
    with When("update_from_args runs with every arg unset (None)"):
        aws_config.update_from_args(cfg, SimpleNamespace())
    with Then("every configured value survives untouched"):
        assert cfg.access_key_id == "configured-key", cfg
        assert cfg.secret_access_key == "configured-secret", cfg
        assert cfg.security_group == "sg-configured", cfg
        assert cfg.subnets == ["subnet-configured"], cfg
        assert cfg.key_name == "configured-keypair", cfg
        assert cfg.defaults.image == "ami-configured", cfg
        assert cfg.defaults.server_type == "t3.large", cfg
        assert cfg.defaults.location == "us-east-1a", cfg
        assert cfg.defaults.disk_size == 30, cfg
        assert cfg.defaults.disk_type == "gp3", cfg


# ---------------------------------------------------------------------------
# apply_args: create-from-flags-alone path (mirrors Hetzner's)
# ---------------------------------------------------------------------------


@TestScenario
def apply_args_creates_aws_provider_from_flags_alone(self):
    """With no providers.aws section, both credential flags create one that
    provider_factory (from_config) would actually build."""
    from types import SimpleNamespace
    from testflows.github.runners.config.config import Config, provider_list, apply_args

    cfg = Config(providers=provider_list())
    with When("apply_args runs with both AWS credential flags set"):
        apply_args(
            cfg,
            SimpleNamespace(aws_access_key_id="AK", aws_secret_access_key="SK"),
        )
    with Then("a providers.aws section is created with those credentials"):
        assert cfg.providers.aws is not None, cfg.providers.aws
        assert cfg.providers.aws.access_key_id == "AK", cfg.providers.aws
        assert cfg.providers.aws.secret_access_key == "SK", cfg.providers.aws


@TestScenario
def apply_args_does_not_create_aws_provider_from_partial_flags(self):
    """Only one of the two required credential flags must not create a
    provider — it would never pass AWSCloudProvider.from_config's guard."""
    from types import SimpleNamespace
    from testflows.github.runners.config.config import Config, provider_list, apply_args

    cfg = Config(providers=provider_list())
    with When("apply_args runs with only aws_access_key_id set"):
        apply_args(cfg, SimpleNamespace(aws_access_key_id="AK"))
    with Then("no providers.aws section is created"):
        assert cfg.providers.aws is None, cfg.providers.aws


@TestScenario
def apply_args_overrides_existing_aws_provider_section(self):
    """A CLI flag must win over an already-present providers.aws section,
    the same as the Hetzner nested-override case (hetzner_rebuild_cli_override_
    updates_nested_config in cli_and_config.py) -- only the from-flags-alone
    path had coverage for aws."""
    from types import SimpleNamespace
    from testflows.github.runners.config.config import (
        Config,
        provider_list,
        apply_args,
        aws_provider as aws_provider_config,
    )

    cfg = Config(
        providers=provider_list(
            aws=aws_provider_config(access_key_id="configured-key", secret_access_key="configured-secret")
        )
    )
    with When("apply_args runs with --aws-access-key-id set"):
        apply_args(cfg, SimpleNamespace(aws_access_key_id="AK-override"))
    with Then("the flag overrides the configured value"):
        assert cfg.providers.aws.access_key_id == "AK-override", cfg.providers.aws
    with And("the untouched field survives"):
        assert cfg.providers.aws.secret_access_key == "configured-secret", cfg.providers.aws


# ---------------------------------------------------------------------------
# Feature entry point
# ---------------------------------------------------------------------------


@TestFeature
@Name("aws config")
def feature(self):
    """parse_config -> provider_factory integration for AWS."""
    for scenario in loads(current_module(), Scenario):
        scenario()
