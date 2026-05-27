"""CLI smoke tests and config-layer regression tests.

Covers:
- CLI --help exits 0 and produces output (smoke test)
- provider_type() accepts valid providers and rejects removed ones
- Config parser rejects azure/gcp/scaleway with a clear message
- schema.json only lists hetzner and aws under providers.properties
"""

import json
import os
import subprocess
import sys
import pytest
from argparse import ArgumentTypeError

from testflows.runners.args import provider_type
from testflows.runners.config.parse import parse_config

# Repo root so the CLI subprocess can find the package without an install.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_CLI_SCRIPT = os.path.join(_REPO_ROOT, "testflows", "runners", "bin", "tfs-runners")
_SCHEMA_PATH = os.path.join(_REPO_ROOT, "testflows", "runners", "config", "schema.json")


# ---------------------------------------------------------------------------
# 1. CLI smoke test
# ---------------------------------------------------------------------------


def _run_help():
    env = os.environ.copy()
    env["PYTHONPATH"] = _REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, _CLI_SCRIPT, "--help"],
        capture_output=True,
        text=True,
        env=env,
    )


class TestCLISmoke:
    def test_help_exits_zero(self):
        result = _run_help()
        assert result.returncode == 0, f"--help exited {result.returncode}:\n{result.stderr}"

    def test_help_mentions_known_providers(self):
        result = _run_help()
        output = result.stdout + result.stderr
        assert "hetzner" in output
        assert "aws" in output

    def test_help_does_not_mention_removed_providers(self):
        result = _run_help()
        output = result.stdout + result.stderr
        for removed in ("azure", "gcp", "scaleway"):
            assert removed not in output, f"removed provider '{removed}' still appears in --help"


# ---------------------------------------------------------------------------
# 2. provider_type() whitelist
# ---------------------------------------------------------------------------


class TestProviderType:
    @pytest.mark.parametrize("value", ["hetzner", "aws", "hetzner,aws", "aws,hetzner"])
    def test_accepts_valid(self, value):
        result = provider_type(value)
        assert isinstance(result, list)
        assert all(p in {"hetzner", "aws"} for p in result)

    @pytest.mark.parametrize("removed", ["azure", "gcp", "scaleway"])
    def test_rejects_removed_providers(self, removed):
        with pytest.raises(ArgumentTypeError) as exc_info:
            provider_type(removed)
        assert removed in str(exc_info.value)

    def test_error_message_lists_valid_providers(self):
        with pytest.raises(ArgumentTypeError) as exc_info:
            provider_type("azure")
        msg = str(exc_info.value)
        assert "hetzner" in msg
        assert "aws" in msg

    def test_deduplicates(self):
        result = provider_type("hetzner,hetzner")
        assert result.count("hetzner") == 1


# ---------------------------------------------------------------------------
# 3. Config parser rejects removed providers
# ---------------------------------------------------------------------------


_MINIMAL_BASE = """
config:
  github_token: token
  github_repository: owner/repo
  ssh_key: /tmp/key
"""


class TestConfigRejectsRemovedProviders:
    @pytest.mark.parametrize("provider_name", ["azure", "gcp", "scaleway"])
    def test_parse_fails_with_clear_message(self, tmp_path, provider_name):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            _MINIMAL_BASE + f"  providers:\n    {provider_name}:\n      dummy: value\n"
        )
        with pytest.raises((AssertionError, SystemExit)) as exc_info:
            parse_config(str(cfg_file))
        msg = str(exc_info.value).lower()
        assert "not yet implemented" in msg or provider_name in msg, (
            f"Expected clear rejection message, got: {exc_info.value!r}"
        )


# ---------------------------------------------------------------------------
# 4. Schema regression: only hetzner and aws under providers
# ---------------------------------------------------------------------------


class TestSchemaProviders:
    @pytest.fixture(scope="class")
    def schema(self):
        with open(_SCHEMA_PATH) as f:
            return json.load(f)

    def _providers_properties(self, schema):
        """Navigate to schema.properties.config.properties.providers.properties."""
        return (
            schema
            .get("properties", {})
            .get("config", {})
            .get("properties", {})
            .get("providers", {})
            .get("properties", {})
        )

    def test_only_hetzner_and_aws_defined(self, schema):
        props = self._providers_properties(schema)
        assert set(props.keys()) == {"hetzner", "aws"}, (
            f"Unexpected providers in schema: {set(props.keys())}"
        )

    @pytest.mark.parametrize("removed", ["azure", "gcp", "scaleway"])
    def test_removed_provider_absent(self, schema, removed):
        props = self._providers_properties(schema)
        assert removed not in props, f"removed provider '{removed}' still in schema"
