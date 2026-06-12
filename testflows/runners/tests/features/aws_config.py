"""Integration tests: YAML config -> parse_config -> provider_factory propagation.

These tests exercise the full pipeline from YAML text through parse_config()
and provider_factory() to verify that config values reach AWSCloudProvider.
No real AWS calls are made; boto3 is patched at the Session level.
"""
from testflows.core import *

from testflows.runners.config.parse import parse_config
from testflows.runners.config.factory import provider_factory
from testflows.runners.providers.aws.provider import AWSCloudProvider
from testflows.runners.tests.steps.aws import mock_ec2
from testflows.runners.tests.steps.config import write_config


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
    from testflows.runners.config.config import aws_provider

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
        assert cfg.providers.aws.defaults.volume_size == base.volume_size
        assert cfg.providers.aws.defaults.volume_type == base.volume_type


@TestScenario
def no_defaults_section_uses_dataclass_defaults(self):
    """Without a `defaults:` section, dataclass defaults are used."""
    from testflows.runners.config.config import aws_provider

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
# Feature entry point
# ---------------------------------------------------------------------------


@TestFeature
@Name("aws config")
def feature(self):
    """parse_config -> provider_factory integration for AWS."""
    for scenario in loads(current_module(), Scenario):
        scenario()
