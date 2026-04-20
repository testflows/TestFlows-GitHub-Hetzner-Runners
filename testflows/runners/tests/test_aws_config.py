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

"""Integration tests: YAML config -> parse_config -> provider_factory propagation.

These tests exercise the full pipeline from YAML text through parse_config()
and provider_factory() to verify that config values reach AWSCloudProvider.
No real AWS calls are made; boto3 is patched at the Session level.
"""

import textwrap
import tempfile
import os
import pytest
from unittest.mock import patch, MagicMock

from testflows.runners.config.parse import parse_config
from testflows.runners.config.factory import provider_factory
from testflows.runners.providers.aws.provider import AWSCloudProvider


def _write_config(yaml_text: str) -> str:
    """Write yaml_text (config: section body) to a temp file and return its path."""
    # parse_config expects the entire document nested under a top-level 'config:' key.
    indented = textwrap.indent(textwrap.dedent(yaml_text), "  ")
    full_yaml = "config:\n" + indented
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    )
    f.write(full_yaml)
    f.close()
    return f.name


@pytest.fixture(autouse=True)
def patch_boto3():
    """Suppress real boto3 calls for all tests in this module."""
    with patch("boto3.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value = mock_session
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        yield mock_client


# ---------------------------------------------------------------------------
# parse_config: AWS credentials and simple fields
# ---------------------------------------------------------------------------


class TestParseConfigAWSCredentials:
    def test_access_key_and_secret_parsed(self):
        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AKIATEST
                secret_access_key: s3cr3t
        """)
        try:
            cfg = parse_config(path)
            assert cfg.providers.aws.access_key_id == "AKIATEST"
            assert cfg.providers.aws.secret_access_key == "s3cr3t"
        finally:
            os.unlink(path)

    def test_security_group_and_subnet_parsed(self):
        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                security_group: sg-abc
                subnet: subnet-xyz
        """)
        try:
            cfg = parse_config(path)
            assert cfg.providers.aws.security_group == "sg-abc"
            assert cfg.providers.aws.subnet == "subnet-xyz"
        finally:
            os.unlink(path)

    def test_ssh_user_parsed(self):
        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                ssh_user: ec2-user
        """)
        try:
            cfg = parse_config(path)
            assert cfg.providers.aws.ssh_user == "ec2-user"
        finally:
            os.unlink(path)

    def test_ssh_user_defaults_to_ubuntu(self):
        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
        """)
        try:
            cfg = parse_config(path)
            assert cfg.providers.aws.ssh_user == "ubuntu"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# parse_config: AWS defaults section
# ---------------------------------------------------------------------------


class TestParseConfigAWSDefaults:
    def test_defaults_image_parsed(self):
        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  image: ami-custom123
        """)
        try:
            cfg = parse_config(path)
            assert cfg.providers.aws.defaults.image == "ami-custom123"
        finally:
            os.unlink(path)

    def test_defaults_location_parsed(self):
        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  location: eu-west-1b
        """)
        try:
            cfg = parse_config(path)
            assert cfg.providers.aws.defaults.location == "eu-west-1b"
        finally:
            os.unlink(path)

    def test_defaults_server_type_parsed(self):
        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  server_type: c6g.large
        """)
        try:
            cfg = parse_config(path)
            assert cfg.providers.aws.defaults.server_type == "c6g.large"
        finally:
            os.unlink(path)

    def test_unspecified_defaults_keep_dataclass_values(self):
        """Fields not present in YAML defaults must fall back to dataclass defaults."""
        from testflows.runners.config.config import aws_provider

        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  image: ami-override
        """)
        try:
            cfg = parse_config(path)
            base = aws_provider().defaults
            # Override applied
            assert cfg.providers.aws.defaults.image == "ami-override"
            # Everything else unchanged
            assert cfg.providers.aws.defaults.server_type == base.server_type
            assert cfg.providers.aws.defaults.location == base.location
            assert cfg.providers.aws.defaults.volume_size == base.volume_size
            assert cfg.providers.aws.defaults.volume_type == base.volume_type
        finally:
            os.unlink(path)

    def test_no_defaults_section_uses_dataclass_defaults(self):
        from testflows.runners.config.config import aws_provider

        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
        """)
        try:
            cfg = parse_config(path)
            base = aws_provider().defaults
            assert cfg.providers.aws.defaults.image == base.image
            assert cfg.providers.aws.defaults.location == base.location
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# provider_factory: YAML values reach AWSCloudProvider
# ---------------------------------------------------------------------------


class TestProviderFactoryAWS:
    def test_factory_produces_aws_provider(self):
        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AKIATEST
                secret_access_key: s3cr3t
        """)
        try:
            cfg = parse_config(path)
            providers = provider_factory(cfg)
            assert len(providers) == 1
            assert isinstance(providers[0], AWSCloudProvider)
        finally:
            os.unlink(path)

    def test_factory_passes_ssh_user(self):
        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                ssh_user: ec2-user
        """)
        try:
            cfg = parse_config(path)
            provider = provider_factory(cfg)[0]
            assert provider._ssh_user == "ec2-user"
        finally:
            os.unlink(path)

    def test_factory_passes_default_location(self):
        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  location: ap-southeast-1a
        """)
        try:
            cfg = parse_config(path)
            provider = provider_factory(cfg)[0]
            assert provider._default_location == "ap-southeast-1a"
        finally:
            os.unlink(path)

    def test_factory_passes_default_image(self):
        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  image: ami-custom
        """)
        try:
            cfg = parse_config(path)
            provider = provider_factory(cfg)[0]
            assert provider._default_image == "ami-custom"
        finally:
            os.unlink(path)

    def test_factory_derives_region_from_location(self):
        path = _write_config("""\
            ssh_key: /dev/null
            providers:
              aws:
                access_key_id: AK
                secret_access_key: SK
                defaults:
                  location: eu-central-1b
        """)
        try:
            cfg = parse_config(path)
            provider = provider_factory(cfg)[0]
            assert provider._region == "eu-central-1"
        finally:
            os.unlink(path)
