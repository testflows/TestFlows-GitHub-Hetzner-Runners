"""CLI smoke tests and config-layer regression tests.

Covers:
- CLI --help exits 0 and produces output (smoke test)
- provider_type() accepts valid providers (hetzner/aws/scaleway) and rejects
  not-yet-implemented ones (azure/gcp)
- Config parser rejects azure/gcp with a clear message
- schema.json lists hetzner, aws and scaleway under providers.properties
- Config.check() startup gate
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from argparse import ArgumentTypeError
from importlib.machinery import SourceFileLoader
from types import SimpleNamespace
from unittest.mock import patch

from testflows.core import *

from testflows.github.runners.args import provider_type
from testflows.github.runners.config.config import (
    Config,
    hetzner_provider,
    aws_provider,
    scaleway_provider,
    provider_defaults,
    dedicated_static_provider,
    dedicated_static_group,
    provider_list,
    apply_args,
)
from testflows.github.runners.config.parse import parse_config
from testflows.github.runners.config.factory import provider_factory
from testflows.github.runners.errors import ConfigError
from testflows.github.runners.service import command_options
import testflows.github.runners.service as service
import testflows.github.runners.cloud as cloud
from testflows.github.runners.tests.unit.steps.scaleway import mock_scaleway_sdk
from testflows.github.runners.tests.unit.steps.aws import mock_ec2

# Repo root so the CLI subprocess can find the package without an install.
_REPO_ROOT = os.path.abspath(os.path.join(current_dir(), "..", "..", "..", "..", "..", ".."))
_CLI_SCRIPT = os.path.join(_REPO_ROOT, "testflows", "github", "runners", "bin", "tfs-github-runners")
_SCHEMA_PATH = os.path.join(_REPO_ROOT, "testflows", "github", "runners", "config", "schema.json")


def _cli_module():
    """Import the CLI entrypoint (no .py suffix) so tests hit the real parser."""
    loader = SourceFileLoader("tfs_cli_entrypoint", _CLI_SCRIPT)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _run_help():
    env = os.environ.copy()
    env["PYTHONPATH"] = _REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, _CLI_SCRIPT, "--help"],
        capture_output=True,
        text=True,
        env=env,
    )


def _run_cli(argv):
    """Run the real entry point as a subprocess (not by import: the __main__
    block only runs that way) and return the CompletedProcess."""
    env = os.environ.copy()
    env["PYTHONPATH"] = _REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, _CLI_SCRIPT] + argv,
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# 1. CLI smoke test
# ---------------------------------------------------------------------------


@TestScenario
def cli_help_exits_zero(self):
    with When("I run `tfs-github-runners --help`"):
        result = _run_help()
    with Then("it exits with code 0"):
        assert result.returncode == 0, f"--help exited {result.returncode}:\n{result.stderr}"


@TestScenario
def cli_help_mentions_known_providers(self):
    with When("I run `tfs-github-runners --help`"):
        result = _run_help()
    with Then("the output mentions hetzner, aws, scaleway and dedicated_static"):
        output = result.stdout + result.stderr
        assert "hetzner" in output
        assert "aws" in output
        assert "scaleway" in output
        assert "dedicated_static" in output


@TestScenario
def cli_help_does_not_mention_removed_providers(self):
    with When("I run `tfs-github-runners --help`"):
        result = _run_help()
    with Then("the output does not mention azure / gcp"):
        output = result.stdout + result.stderr
        for removed in ("azure", "gcp"):
            assert removed not in output, f"removed provider '{removed}' still appears in --help"


@TestScenario
def cli_help_uses_provider_specific_rebuild_option(self):
    with When("I run `tfs-github-runners --help`"):
        result = _run_help()
    with Then("the new Hetzner option is present and the global option is absent"):
        output = result.stdout + result.stderr
        assert "--hetzner-recycle-with-rebuild" in output
        assert "--recycle-without-rebuild" not in output


@TestScenario
def hetzner_rebuild_cli_override_updates_nested_config(self):
    cfg = Config(
        providers=provider_list(
            hetzner=hetzner_provider(token="token", recycle_with_rebuild=False)
        )
    )
    with When("the provider-specific CLI override is applied"):
        apply_args(cfg, SimpleNamespace(hetzner_recycle_with_rebuild=True))
    with Then("the nested Hetzner setting is overridden"):
        assert cfg.providers.hetzner.recycle_with_rebuild is True


@TestScenario
def service_command_omits_provider_specific_flags(self):
    """Provider config reaches the service through --config, not re-emitted as
    per-provider flags — uniform across providers."""
    cfg = Config(
        github_token="token",
        github_repository="owner/repo",
        providers=provider_list(
            hetzner=hetzner_provider(token="token", recycle_with_rebuild=True)
        ),
    )
    with When("service command options are rendered"):
        command = command_options(cfg)
    with Then("no --hetzner-* flags are emitted even though Hetzner is configured"):
        assert "--hetzner" not in command, command


@TestScenario
def service_command_does_not_inject_hetzner_provider(self):
    cfg = Config(
        github_token="token",
        github_repository="owner/repo",
        providers=provider_list(),
    )
    command = command_options(cfg)
    assert "--hetzner-token" not in command
    assert "--hetzner-recycle-with-rebuild" not in command


@TestScenario
def service_command_emits_provider_flag_when_set(self):
    """Re-emit --provider: it has no config-file seam."""
    cfg = Config(
        github_token="token",
        github_repository="owner/repo",
        providers=provider_list(hetzner=hetzner_provider(token="token")),
        enabled_providers=["hetzner", "aws"],
    )
    with When("service command options are rendered"):
        command = command_options(cfg)
    with Then("--provider carries the enabled providers"):
        assert '--provider "hetzner,aws"' in command, command


@TestScenario
def service_command_omits_provider_flag_when_unset(self):
    cfg = Config(
        github_token="token",
        github_repository="owner/repo",
        providers=provider_list(hetzner=hetzner_provider(token="token")),
    )
    with When("service command options are rendered"):
        command = command_options(cfg)
    with Then("--provider is absent"):
        assert "--provider" not in command, command


@TestScenario
def optional_hetzner_flag_does_not_create_provider(self):
    cfg = Config(providers=provider_list())
    apply_args(cfg, SimpleNamespace(hetzner_recycle_with_rebuild=False))
    assert cfg.providers.hetzner is None


@TestScenario
def explicit_hetzner_token_creates_provider(self):
    cfg = Config(providers=provider_list())
    apply_args(cfg, SimpleNamespace(hetzner_token="token"))
    assert cfg.providers.hetzner.token == "token"


@TestScenario
def unset_boolean_flag_does_not_clobber_yaml_value(self):
    """A store_true flag left unset (None) must not overwrite the YAML value.

    Regression: --delete-random lacked default=None, so argparse defaulted it to
    False and apply_args reset `delete_random: true` on every CLI run.
    """
    with Given("delete_random enabled from YAML"):
        cfg = Config()
        cfg.delete_random = True
    with When("apply_args runs with the flag unset (None)"):
        apply_args(cfg, SimpleNamespace(delete_random=None))
    with Then("the YAML value survives"):
        assert cfg.delete_random is True, cfg.delete_random
    with And("an explicitly passed flag still overrides"):
        cfg2 = Config()
        cfg2.delete_random = False
        apply_args(cfg2, SimpleNamespace(delete_random=True))
        assert cfg2.delete_random is True, cfg2.delete_random


@TestScenario
def apply_args_allow_list_overrides_a_scalar_field(self):
    """A listed field takes the CLI value; unrelated fields are untouched."""
    with Given("a default config"):
        cfg = Config()
        cfg.max_runners = 10
    with When("apply_args runs with max_runners set and nothing else"):
        apply_args(cfg, SimpleNamespace(max_runners=99))
    with Then("the listed field is overridden"):
        assert cfg.max_runners == 99, cfg.max_runners
    with And("an unset field keeps its default"):
        assert cfg.workers == Config().workers, cfg.workers


@TestScenario
def apply_args_never_touches_structural_fields(self):
    """Structural/nested fields must never be in the scalar allow-list.

    They carry their own apply seams (providers, cloud) or must not be
    CLI-overridable at all (server_prices, standby_runners, config_file).
    Listing one here would let a stray same-named arg clobber it.
    """
    from testflows.github.runners.config.config import _CLI_OVERRIDABLE_FIELDS

    structural = {
        "providers",
        "cloud",
        "standby_runners",
        "additional_ssh_keys",
        "server_prices",
        "logger_config",
        "logger_format",
        "config_file",
    }
    with Then("no structural field appears in the allow-list"):
        overlap = structural & set(_CLI_OVERRIDABLE_FIELDS)
        assert not overlap, overlap


@TestScenario
def apply_args_allow_list_names_only_real_fields(self):
    """Every allow-listed name must be an actual Config field (drift guard)."""
    import dataclasses
    from testflows.github.runners.config.config import _CLI_OVERRIDABLE_FIELDS

    field_names = {f.name for f in dataclasses.fields(Config)}
    with Then("each allow-listed name resolves to a Config field"):
        unknown = set(_CLI_OVERRIDABLE_FIELDS) - field_names
        assert not unknown, unknown


# ---------------------------------------------------------------------------
# 2. provider_type() whitelist
# ---------------------------------------------------------------------------


@TestScenario
def provider_type_accepts_valid(self):
    for value in (
        "hetzner",
        "aws",
        "scaleway",
        "dedicated_static",
        "hetzner,aws",
        "aws,scaleway",
        "scaleway,dedicated_static",
    ):
        with When(f"I parse provider_type({value!r})"):
            result = provider_type(value)
        with Then("the result is a list of known providers"):
            assert isinstance(result, list)
            assert all(
                p in {"hetzner", "aws", "scaleway", "dedicated_static"}
                for p in result
            ), f"unexpected for {value}: {result}"


@TestScenario
def provider_type_rejects_removed_providers(self):
    for removed in ("azure", "gcp"):
        with When(f"I parse provider_type({removed!r})"):
            try:
                provider_type(removed)
                raised_msg = None
            except ArgumentTypeError as e:
                raised_msg = str(e)
        with Then(f"ArgumentTypeError is raised and mentions {removed!r}"):
            assert raised_msg is not None
            assert removed in raised_msg


@TestScenario
def provider_type_error_message_lists_valid_providers(self):
    with When("I parse provider_type('azure')"):
        try:
            provider_type("azure")
            msg = None
        except ArgumentTypeError as e:
            msg = str(e)
    with Then("the error message lists hetzner and aws"):
        assert msg is not None
        assert "hetzner" in msg
        assert "aws" in msg


@TestScenario
def provider_type_deduplicates(self):
    with When("I parse provider_type('hetzner,hetzner')"):
        result = provider_type("hetzner,hetzner")
    with Then("the result contains hetzner only once"):
        assert result.count("hetzner") == 1


# ---------------------------------------------------------------------------
# 3. hetzner_token is not auto-discovered from the environment
# ---------------------------------------------------------------------------


@TestScenario
def hetzner_token_not_read_from_env(self):
    """An ambient HETZNER_TOKEN must not configure Hetzner.

    Hetzner must be configured explicitly (--hetzner-token or
    providers.hetzner.token); a stray env var must not silently create a
    Hetzner provider. config.hetzner_token is a read-only accessor derived from
    providers.hetzner.token, so with no provider it resolves to None.
    """
    from testflows.github.runners.config.config import Config

    saved = os.environ.get("HETZNER_TOKEN")
    os.environ["HETZNER_TOKEN"] = "ambient-should-be-ignored"
    try:
        with When("I build a Config with HETZNER_TOKEN set in the environment"):
            cfg = Config(github_token="t", github_repository="o/r")
        with Then("config.hetzner_token is not populated from the env"):
            assert cfg.hetzner_token is None, cfg.hetzner_token
    finally:
        if saved is None:
            os.environ.pop("HETZNER_TOKEN", None)
        else:
            os.environ["HETZNER_TOKEN"] = saved


# ---------------------------------------------------------------------------
# 4. Config parser rejects removed providers
# ---------------------------------------------------------------------------


_MINIMAL_BASE = """
config:
  github_token: token
  github_repository: owner/repo
  ssh_key: /tmp/key
"""


def _write_minimal_with_provider(provider_name):
    import tempfile
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(_MINIMAL_BASE + f"  providers:\n    {provider_name}:\n      dummy: value\n")
    f.close()
    return f.name


@TestScenario
def meta_label_preserves_declaration_order(self):
    """Meta-label values parse to an ordered list, not a set.

    scale_up consumes the order as the cross-provider fallback priority, so a
    set (hash-randomized per process) would make routing nondeterministic.
    """
    import os
    import tempfile

    cfg = _MINIMAL_BASE + (
        "  meta_label:\n"
        "    build:\n"
        "      - type-hetzner-cx41\n"
        "      - type-scaleway-dev1.m\n"
        "      - type-aws-m8g.xlarge\n"
    )
    with Given("a config whose meta_label lists types in a specific order"):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        f.write(cfg)
        f.close()
    try:
        with When("parse_config runs"):
            parsed = parse_config(f.name)
        with Then("the value is a list in declaration order"):
            assert parsed.meta_label["build"] == [
                "type-hetzner-cx41",
                "type-scaleway-dev1.m",
                "type-aws-m8g.xlarge",
            ], parsed.meta_label["build"]
    finally:
        os.unlink(f.name)


@TestScenario
def config_rejects_removed_providers(self):
    for provider_name in ("azure", "gcp"):
        with Given(f"a config referencing the removed provider {provider_name!r}"):
            cfg_file = _write_minimal_with_provider(provider_name)
        try:
            with When("I call parse_config"):
                try:
                    parse_config(cfg_file)
                    raised = None
                except (AssertionError, SystemExit) as e:
                    raised = e
            with Then("a clear rejection error is raised"):
                assert raised is not None, f"expected rejection for {provider_name}"
                msg = str(raised).lower()
                assert "not yet implemented" in msg or provider_name in msg, (
                    f"Expected clear rejection message, got: {raised!r}"
                )
        finally:
            os.unlink(cfg_file)


@TestScenario
def factory_loops_registry_and_from_config_gates_on_config(self):
    """Factory returns only configured providers, in precedence order, via from_config."""
    from testflows.github.runners.config.factory import provider_factory, PROVIDER_REGISTRY

    cfg = Config(providers=provider_list(hetzner=hetzner_provider(token="t")))
    with Then("only the configured provider is built; others from_config -> None"):
        assert [p.name for p in provider_factory(cfg)] == ["hetzner"]
    with And("registry is ordered by precedence"):
        precs = [c.precedence for c in PROVIDER_REGISTRY]
        assert precs == sorted(precs), precs


@TestScenario
def apply_args_wires_provider_flag_into_enabled_providers(self):
    """--provider (dest=enabled_providers) reaches Config through apply_args."""
    with Given("a default config"):
        cfg = Config()
    with When("apply_args runs with enabled_providers set (as --provider would parse it)"):
        apply_args(cfg, SimpleNamespace(enabled_providers=["hetzner", "aws"]))
    with Then("the field is set on Config"):
        assert cfg.enabled_providers == ["hetzner", "aws"], cfg.enabled_providers


@TestScenario
def apply_args_leaves_enabled_providers_alone_when_flag_unset(self):
    with Given("a default config"):
        cfg = Config()
    with When("apply_args runs with enabled_providers unset (None)"):
        apply_args(cfg, SimpleNamespace(enabled_providers=None))
    with Then("enabled_providers stays None"):
        assert cfg.enabled_providers is None, cfg.enabled_providers


@TestScenario
def provider_factory_filters_to_enabled_providers(self):
    """enabled_providers restricts the factory to a subset of what's configured."""
    with Given("hetzner and aws both configured, but only hetzner enabled"):
        cfg = Config(
            providers=provider_list(
                hetzner=hetzner_provider(token="t"),
                aws=aws_provider(access_key_id="k", secret_access_key="s"),
            ),
            enabled_providers=["hetzner"],
        )
    with When("provider_factory runs"):
        providers = provider_factory(cfg)
    with Then("only hetzner is built, aws is excluded despite being configured"):
        assert [p.name for p in providers] == ["hetzner"], [p.name for p in providers]


@TestScenario
def provider_factory_none_enabled_providers_builds_everything_configured(self):
    """None (no --provider) still builds every configured provider."""
    with Given("mocked EC2 client"):
        mock_ec2()
    with Given("hetzner and aws both configured, enabled_providers left at None"):
        cfg = Config(
            providers=provider_list(
                hetzner=hetzner_provider(token="t"),
                aws=aws_provider(access_key_id="k", secret_access_key="s"),
            ),
        )
    with Then("enabled_providers defaults to None"):
        assert cfg.enabled_providers is None
    with When("provider_factory runs"):
        providers = provider_factory(cfg)
    with Then("both configured providers are built"):
        assert sorted(p.name for p in providers) == ["aws", "hetzner"], [
            p.name for p in providers
        ]


@TestScenario
def provider_factory_raises_for_unconfigured_requested_provider(self):
    """A requested provider with no config section must fail, not silently drop."""
    with Given("only hetzner configured, but aws requested via enabled_providers"):
        cfg = Config(
            providers=provider_list(hetzner=hetzner_provider(token="t")),
            enabled_providers=["hetzner", "aws"],
        )
    with When("provider_factory runs"):
        try:
            provider_factory(cfg)
            raised = None
        except ConfigError as e:
            raised = e
    with Then("a ConfigError names the missing provider's actual config section"):
        assert raised is not None
        message = str(raised)
        assert "providers.aws" in message, message
    with And("no leftover <name> placeholder remains in the message"):
        assert "<name>" not in message, message
    with And("the message says what was built instead"):
        assert "Built: hetzner" in message, message


@TestScenario
def provider_factory_never_constructs_an_excluded_provider(self):
    """The returned list can't tell skip from build-then-drop; spy on from_config."""
    from unittest.mock import patch
    from testflows.github.runners.providers.aws.provider import AWSCloudProvider

    with Given("hetzner and aws both configured, but only hetzner enabled"):
        cfg = Config(
            providers=provider_list(
                hetzner=hetzner_provider(token="t"),
                aws=aws_provider(access_key_id="k", secret_access_key="s"),
            ),
            enabled_providers=["hetzner"],
        )
    with When("provider_factory runs with AWSCloudProvider.from_config spied on"):
        with patch.object(
            AWSCloudProvider, "from_config", wraps=AWSCloudProvider.from_config
        ) as spy:
            providers = provider_factory(cfg)
    with Then("only hetzner is returned"):
        assert [p.name for p in providers] == ["hetzner"], [p.name for p in providers]
    with And("AWSCloudProvider.from_config was never called -- aws was never built"):
        assert spy.call_count == 0, spy.call_count


@TestScenario
def provider_factory_raises_for_requested_provider_missing_credentials(self):
    """A present-but-incomplete section must fail the same as a missing one."""
    with Given("an aws section with only a partial credential set"):
        cfg = Config(
            providers=provider_list(
                hetzner=hetzner_provider(token="t"),
                aws=aws_provider(access_key_id="k"),  # secret_access_key missing
            ),
            enabled_providers=["hetzner", "aws"],
        )
    with When("provider_factory runs"):
        try:
            provider_factory(cfg)
            raised = None
        except ConfigError as e:
            raised = e
    with Then("a ConfigError names providers.aws, even though the section exists"):
        assert raised is not None
        message = str(raised)
        assert "providers.aws" in message, message
    with And("no leftover <name> placeholder remains in the message"):
        assert "<name>" not in message, message


@TestScenario
def provider_factory_raises_when_nothing_could_be_built_at_all(self):
    """When nothing builds, the error must say 'Built: none', not 'Built: '."""
    with Given("no providers configured at all, but aws and scaleway requested"):
        cfg = Config(
            providers=provider_list(),
            enabled_providers=["aws", "scaleway"],
        )
    with When("provider_factory runs"):
        try:
            provider_factory(cfg)
            raised = None
        except ConfigError as e:
            raised = e
    with Then("a ConfigError names both requested providers' config sections"):
        assert raised is not None
        message = str(raised)
        assert "providers.aws" in message, message
        assert "providers.scaleway" in message, message
    with And("no leftover <name> placeholder remains in the message"):
        assert "<name>" not in message, message
    with And("the message says plainly that nothing was built"):
        assert "Built: none" in message, message


@TestScenario
def config_rejects_removed_top_level_defaults(self):
    """Top-level default_image/default_server_type/... are gone; they hard-error."""
    import tempfile

    for key, value in (
        ("default_image", "x86:system:ubuntu-22.04"),
        ("default_server_type", "cx23"),
        ("default_location", "nbg1"),
        ("default_volume_location", "nbg1"),
        ("default_volume_size", 20),
    ):
        text = _MINIMAL_BASE + f"  {key}: {value}\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(text)
            path = f.name
        try:
            with When(f"I parse a config with top-level {key}"):
                try:
                    parse_config(path)
                    raised = None
                except (AssertionError, SystemExit, TypeError) as e:
                    raised = e
            with Then("parsing is rejected pointing at providers.hetzner.defaults"):
                assert raised is not None, f"expected rejection for {key}"
                assert "providers.hetzner.defaults" in str(raised), str(raised)
        finally:
            os.unlink(path)


@TestScenario
def config_rejects_enabled_providers_key(self):
    """enabled_providers is CLI-only; YAML must not set it."""
    import tempfile

    text = _MINIMAL_BASE + "  enabled_providers:\n    - hetzner\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        with When("I parse a config with an enabled_providers key"):
            try:
                parse_config(path)
                raised = None
            except AssertionError as e:
                raised = e
        with Then("parsing is rejected and points at --provider"):
            assert raised is not None
            assert "--provider" in str(raised), str(raised)
    finally:
        os.unlink(path)


@TestScenario
def config_rejects_bare_provider_key(self):
    """A bare `provider:` key is rejected the same way as enabled_providers."""
    import tempfile

    text = _MINIMAL_BASE + "  provider: hetzner\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        with When("I parse a config with a bare provider key"):
            try:
                parse_config(path)
                raised = None
            except AssertionError as e:
                raised = e
        with Then("parsing is rejected and points at --provider"):
            assert raised is not None
            assert "--provider" in str(raised), str(raised)
    finally:
        os.unlink(path)


@TestScenario
def config_rejects_removed_recycle_without_rebuild(self):
    import tempfile

    text = _MINIMAL_BASE + "  recycle_without_rebuild: true\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        with When("I parse the removed global setting"):
            try:
                parse_config(path)
                raised = None
            except AssertionError as exc:
                raised = exc
        with Then("the error explains the provider-specific migration"):
            assert raised is not None
            message = str(raised)
            assert "providers.hetzner.recycle_with_rebuild" in message
            assert "inverse semantics" in message
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# 3b. dedicated_static type validation must honor label_prefix
# ---------------------------------------------------------------------------


_LABEL_PREFIX_STATIC_CONFIG = """
config:
  github_token: token
  github_repository: owner/repo
  ssh_key: /tmp/key
  label_prefix: "{prefix}"
  providers:
    dedicated_static:
      ssh_defaults:
        user: runner
        key: /tmp/key
        port: 22
      groups:
        metal-large-dc1:
          labels:
            - tfs-self-hosted
            - tfs-type-metallarge
            - tfs-in-dc1
          hosts:
            - 203.0.113.10
"""

_LABEL_PREFIX_STATIC_CONFIG_WITH_TTL = """
config:
  github_token: token
  github_repository: owner/repo
  ssh_key: /tmp/key
  label_prefix: "tfs-"
  providers:
    dedicated_static:
      claim_ttl_minutes: 720
      ssh_defaults:
        user: runner
        key: /tmp/key
        port: 22
      groups:
        metal-large-dc1:
          labels:
            - tfs-self-hosted
            - tfs-type-metallarge
            - tfs-in-dc1
          hosts:
            - 203.0.113.10
"""


@TestScenario
def dedicated_static_type_label_honors_label_prefix(self):
    """A prefixed type label (`<label_prefix>type-*`) must satisfy the
    dedicated_static 'at least one type-*' validation — the same way
    get_server_types resolves types at runtime (it prepends label_prefix).
    Bare `startswith("type-")` in the validator wrongly rejects it.

    Covers both the conventional trailing-dash form (`tfs-`) and the bare form
    (`tfs`), which get_server_types normalizes identically to `tfs-type-`.
    """
    import tempfile

    for prefix in ("tfs-", "tfs"):
        with Given(f"a static config with label_prefix {prefix!r} and a prefixed type label"):
            f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
            f.write(_LABEL_PREFIX_STATIC_CONFIG.format(prefix=prefix))
            f.close()
        try:
            with When(f"I parse it (label_prefix={prefix!r})"):
                raised = None
                try:
                    parse_config(f.name)
                except (AssertionError, SystemExit) as e:
                    raised = e
            with Then("parse_config accepts it — the prefixed type label counts"):
                assert raised is None, (
                    f"label_prefix={prefix!r}: 'tfs-type-metallarge' wrongly rejected: {raised}"
                )
        finally:
            os.unlink(f.name)


@TestScenario
def dedicated_static_factory_wires_label_prefix_and_claim_ttl(self):
    """parse_config + provider_factory pass label_prefix and claim_ttl_minutes
    into DedicatedStaticCloudProvider."""
    import tempfile

    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(_LABEL_PREFIX_STATIC_CONFIG.format(prefix="tfs-"))
    f.close()
    try:
        with When("I build providers from the parsed config"):
            providers = provider_factory(parse_config(f.name))
        with Then("the dedicated_static provider received the wired knobs"):
            static = next(p for p in providers if p.name == "dedicated_static")
            assert static._claim_ttl_minutes == 360, static._claim_ttl_minutes
            assert static._type_label_prefix == "tfs-type-", static._type_label_prefix
    finally:
        os.unlink(f.name)


@TestScenario
def dedicated_static_factory_wires_non_default_claim_ttl(self):
    """A configured claim_ttl_minutes value is preserved and wired to provider."""
    import tempfile

    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(_LABEL_PREFIX_STATIC_CONFIG_WITH_TTL)
    f.close()
    try:
        with When("I build providers from parsed config with claim_ttl_minutes=720"):
            providers = provider_factory(parse_config(f.name))
        with Then("dedicated_static provider gets claim_ttl_minutes=720"):
            static = next(p for p in providers if p.name == "dedicated_static")
            assert static._claim_ttl_minutes == 720, static._claim_ttl_minutes
    finally:
        os.unlink(f.name)


# ---------------------------------------------------------------------------
# 4. Schema regression: only hetzner and aws under providers
# ---------------------------------------------------------------------------


def _providers_properties(schema):
    """Navigate to schema.properties.config.properties.providers.properties."""
    return (
        schema
        .get("properties", {})
        .get("config", {})
        .get("properties", {})
        .get("providers", {})
        .get("properties", {})
    )


@TestScenario
def schema_implemented_providers_defined(self):
    with Given("the schema.json file"):
        with open(_SCHEMA_PATH) as f:
            schema = json.load(f)
    with Then("hetzner, aws, scaleway and dedicated_static are defined under providers"):
        props = _providers_properties(schema)
        assert set(props.keys()) == {
            "hetzner",
            "aws",
            "scaleway",
            "dedicated_static",
        }, (
            f"Unexpected providers in schema: {set(props.keys())}"
        )


@TestScenario
def schema_removed_provider_absent(self):
    with Given("the schema.json file"):
        with open(_SCHEMA_PATH) as f:
            schema = json.load(f)
    with Then("azure / gcp are absent from providers"):
        props = _providers_properties(schema)
        for removed in ("azure", "gcp"):
            assert removed not in props, f"removed provider '{removed}' still in schema"


@TestScenario
def schema_places_rebuild_setting_under_hetzner(self):
    with open(_SCHEMA_PATH) as f:
        schema = json.load(f)
    config_properties = schema["properties"]["config"]["properties"]
    with Then("only the provider-specific rebuild setting is defined"):
        hetzner_properties = (
            config_properties["providers"]["properties"]["hetzner"]["properties"]
        )
        assert "recycle_with_rebuild" in hetzner_properties
        assert "recycle_without_rebuild" not in config_properties


@TestScenario
def schema_places_hetzner_defaults_under_provider(self):
    """Default image/type/location/volume live under providers.hetzner.defaults,
    not as top-level config keys."""
    with open(_SCHEMA_PATH) as f:
        schema = json.load(f)
    config_properties = schema["properties"]["config"]["properties"]
    with Then("the top-level default_* keys are gone"):
        for removed in (
            "default_image",
            "default_server_type",
            "default_location",
            "default_volume_size",
            "default_volume_location",
        ):
            assert removed not in config_properties, removed
    with And("providers.hetzner.defaults defines them instead"):
        hetzner_defaults = (
            config_properties["providers"]["properties"]["hetzner"]["properties"][
                "defaults"
            ]["properties"]
        )
        assert set(hetzner_defaults.keys()) == {
            "image",
            "server_type",
            "location",
            "volume_size",
            "volume_location",
        }, set(hetzner_defaults.keys())


@TestScenario
def version_is_valid_and_not_a_placeholder(self):
    """__version__ is valid PEP 440, not the unsubstituted placeholder."""
    from packaging.version import Version
    from testflows.github.runners import __version__

    with Then("the version carries no leftover build placeholder"):
        assert "__VERSION__" not in __version__, __version__
    with And("it parses as a valid PEP 440 version"):
        assert Version(__version__), __version__


# ---------------------------------------------------------------------------
# Config.check() — startup gate
# ---------------------------------------------------------------------------


def _minimal_config(**overrides):
    """Config with github fields set and no providers, unless overridden."""
    kwargs = dict(github_token="tok", github_repository="owner/repo")
    kwargs.update(overrides)
    return Config(**kwargs)


def _check(cfg, *parameters):
    """Returns (exit_code_or_None, stderr). None means check() passed."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf):
            cfg.check(*parameters)
        return None, buf.getvalue()
    except SystemExit as e:
        return e.code, buf.getvalue()


@TestScenario
def check_requires_github_token(self):
    with Given("a config missing github_token but with everything else valid"):
        cfg = Config(
            # Field defaults to $GITHUB_TOKEN; None keeps a set env from hiding this.
            github_token=None,
            github_repository="owner/repo",
            providers=provider_list(hetzner=hetzner_provider(token="t")),
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it exits 1"):
        assert code == 1, code
    with And("the message names --github-token"):
        assert "argument error: --github-token is not defined" in stderr, stderr


@TestScenario
def check_requires_github_repository(self):
    with Given("a config missing github_repository but with everything else valid"):
        cfg = Config(
            github_token="tok",
            github_repository=None,
            providers=provider_list(hetzner=hetzner_provider(token="t")),
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it exits 1"):
        assert code == 1, code
    with And("the message names --github-repository"):
        assert "argument error: --github-repository is not defined" in stderr, stderr


@TestScenario
def check_requires_at_least_one_provider(self):
    with Given("a config with the mandatory fields but no providers configured"):
        cfg = _minimal_config()
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it exits 1"):
        assert code == 1, code
    with And("the message guides toward configuring a provider"):
        assert "no cloud provider configured" in stderr, stderr
        assert "providers.hetzner.token" in stderr, stderr
        assert "providers.aws" in stderr, stderr
        assert "providers.scaleway" in stderr, stderr
        assert "providers.dedicated_static.groups" in stderr, stderr


@TestScenario
def check_passes_with_hetzner_fully_credentialed(self):
    with Given("a config with only hetzner.token set"):
        cfg = _minimal_config(providers=provider_list(hetzner=hetzner_provider(token="t")))
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it returns without exiting"):
        assert code is None, (code, stderr)


@TestScenario
def check_passes_with_aws_fully_credentialed(self):
    with Given("a config with both aws credential fields set"):
        cfg = _minimal_config(
            providers=provider_list(
                aws=aws_provider(access_key_id="k", secret_access_key="s")
            )
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it returns without exiting"):
        assert code is None, (code, stderr)


@TestScenario
def check_passes_with_scaleway_fully_credentialed(self):
    with Given("a config with all three scaleway credential fields set"):
        cfg = _minimal_config(
            providers=provider_list(
                scaleway=scaleway_provider(access_key="k", secret_key="s", project_id="p")
            )
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it returns without exiting"):
        assert code is None, (code, stderr)


@TestScenario
def check_passes_with_dedicated_static_fully_credentialed(self):
    with Given("a config with a non-empty dedicated_static.groups"):
        cfg = _minimal_config(
            providers=provider_list(
                dedicated_static=dedicated_static_provider(
                    groups={
                        "g1": dedicated_static_group(
                            labels=["type-metal"], hosts=["10.0.0.1"]
                        )
                    }
                )
            )
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it returns without exiting"):
        assert code is None, (code, stderr)


@TestScenario
def check_rejects_aws_missing_secret_access_key(self):
    """A partial credential set must not count as configured."""
    with Given("a config with aws.access_key_id set but secret_access_key missing"):
        cfg = _minimal_config(
            providers=provider_list(aws=aws_provider(access_key_id="k"))
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it exits 1"):
        assert code == 1, (code, stderr)
    with And("the message reports no provider configured"):
        assert "no cloud provider configured" in stderr, stderr


@TestScenario
def check_rejects_aws_subnets_without_location(self):
    """subnets without location must fail at check() before any AWS call:
    the region would silently default to us-east-1 and other regions'
    subnets would fail with InvalidSubnetID.NotFound."""
    with Given("a config with aws.subnets set and defaults.location unset"):
        cfg = _minimal_config(
            providers=provider_list(
                aws=aws_provider(
                    access_key_id="k",
                    secret_access_key="s",
                    subnets=["subnet-0396ff8bbdcebd35d"],
                )
            )
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it exits 1"):
        assert code == 1, (code, stderr)
    with And("the message is the exact what/why/next-step text"):
        assert (
            "argument error: providers.aws.subnets requires "
            "providers.aws.defaults.location. AWS derives the region "
            "from that field, defaulting to us-east-1, so subnets in "
            "other regions fail with InvalidSubnetID.NotFound. Set it "
            "to their availability zone, e.g. "
            "providers.aws.defaults.location: us-west-2a"
        ) in stderr, stderr


@TestScenario
def check_passes_with_aws_subnets_and_location_set(self):
    """The subnets-without-location gate must not fire once location is set."""
    with Given("a config with aws.subnets and defaults.location both set"):
        cfg = _minimal_config(
            providers=provider_list(
                aws=aws_provider(
                    access_key_id="k",
                    secret_access_key="s",
                    subnets=["subnet-0396ff8bbdcebd35d"],
                    defaults=provider_defaults(location="us-west-2a"),
                )
            )
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it returns without exiting"):
        assert code is None, (code, stderr)


@TestScenario
def check_passes_with_uncredentialed_aws_subnets_when_hetzner_is_complete(self):
    """A dormant aws section with no credentials must not block startup
    when another provider is configured: no AWSCloudProvider is built,
    so the gate must not fire."""
    with Given("hetzner fully credentialed and an uncredentialed aws.subnets section"):
        cfg = _minimal_config(
            providers=provider_list(
                hetzner=hetzner_provider(token="t"),
                aws=aws_provider(subnets=["subnet-0396ff8bbdcebd35d"]),
            )
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it returns without exiting"):
        assert code is None, (code, stderr)


@TestScenario
def check_passes_with_uncredentialed_aws_subnets_when_provider_excludes_aws(self):
    """The same dormant section, now also filtered out by --provider
    hetzner. The gate must still not fire."""
    with Given("hetzner-only --provider filtering plus a dormant aws.subnets section"):
        cfg = _minimal_config(
            providers=provider_list(
                hetzner=hetzner_provider(token="t"),
                aws=aws_provider(subnets=["subnet-0396ff8bbdcebd35d"]),
            ),
            enabled_providers=["hetzner"],
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it returns without exiting"):
        assert code is None, (code, stderr)


@TestScenario
def check_passes_with_credentialed_aws_subnets_when_provider_excludes_aws(self):
    """Credentialed AWS filtered out by --provider hetzner: only the
    enabled_providers check can stop the gate here."""
    with Given("a credentialed aws.subnets section filtered out by --provider hetzner"):
        cfg = _minimal_config(
            providers=provider_list(
                hetzner=hetzner_provider(token="t"),
                aws=aws_provider(
                    access_key_id="k",
                    secret_access_key="s",
                    subnets=["subnet-0396ff8bbdcebd35d"],
                ),
            ),
            enabled_providers=["hetzner"],
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it returns without exiting"):
        assert code is None, (code, stderr)


@TestScenario
def check_rejects_aws_subnets_without_location_when_provider_selects_aws(self):
    """--provider aws with subnets and no location must still fail, even
    with other providers configured."""
    with Given("hetzner configured, --provider aws, and aws.subnets without location"):
        cfg = _minimal_config(
            providers=provider_list(
                hetzner=hetzner_provider(token="t"),
                aws=aws_provider(
                    access_key_id="k",
                    secret_access_key="s",
                    subnets=["subnet-0396ff8bbdcebd35d"],
                ),
            ),
            enabled_providers=["aws"],
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it exits 1"):
        assert code == 1, (code, stderr)
    with And("the message is the exact what/why/next-step text"):
        assert (
            "argument error: providers.aws.subnets requires "
            "providers.aws.defaults.location. AWS derives the region "
            "from that field, defaulting to us-east-1, so subnets in "
            "other regions fail with InvalidSubnetID.NotFound. Set it "
            "to their availability zone, e.g. "
            "providers.aws.defaults.location: us-west-2a"
        ) in stderr, stderr


@TestScenario
def check_rejects_scaleway_missing_any_one_field(self):
    with Given("scaleway configs each missing exactly one of its three required fields"):
        variants = {
            "missing access_key": scaleway_provider(secret_key="s", project_id="p"),
            "missing secret_key": scaleway_provider(access_key="k", project_id="p"),
            "missing project_id": scaleway_provider(access_key="k", secret_key="s"),
        }
    for label, scaleway in variants.items():
        with Check(label):
            cfg = _minimal_config(providers=provider_list(scaleway=scaleway))
            with When("check() runs with no arguments"):
                code, stderr = _check(cfg)
            with Then("it exits 1"):
                assert code == 1, (label, code, stderr)
            with And("the message reports no provider configured"):
                assert "no cloud provider configured" in stderr, (label, stderr)


@TestScenario
def check_rejects_hetzner_empty_token(self):
    with Given("a hetzner section present but with an empty token"):
        cfg = _minimal_config(providers=provider_list(hetzner=hetzner_provider(token="")))
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it exits 1"):
        assert code == 1, (code, stderr)
    with And("the message reports no provider configured"):
        assert "no cloud provider configured" in stderr, stderr


@TestScenario
def check_rejects_dedicated_static_empty_groups(self):
    with Given("a dedicated_static section present but with empty groups"):
        cfg = _minimal_config(
            providers=provider_list(dedicated_static=dedicated_static_provider(groups={}))
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it exits 1"):
        assert code == 1, (code, stderr)
    with And("the message reports no provider configured"):
        assert "no cloud provider configured" in stderr, stderr


@TestScenario
def check_named_parameter_passes_when_set(self):
    with Given("a config with ssh_key set"):
        cfg = _minimal_config(ssh_key="/home/user/.ssh/id_rsa.pub")
    with When('check("ssh_key") runs'):
        code, stderr = _check(cfg, "ssh_key")
    with Then("it returns without exiting"):
        assert code is None, (code, stderr)


@TestScenario
def check_named_parameter_fails_when_unset(self):
    with Given("a config with ssh_key explicitly cleared"):
        cfg = _minimal_config(ssh_key=None)
    with When('check("ssh_key") runs'):
        code, stderr = _check(cfg, "ssh_key")
    with Then("it exits 1"):
        assert code == 1, (code, stderr)
    with And("the message names --ssh-key"):
        assert "argument error: --ssh-key is not defined" in stderr, stderr


@TestScenario
def check_named_parameter_fails_when_empty_string(self):
    with Given("a config with ssh_key set to an empty string"):
        cfg = _minimal_config(ssh_key="")
    with When('check("ssh_key") runs'):
        code, stderr = _check(cfg, "ssh_key")
    with Then("it exits 1"):
        assert code == 1, (code, stderr)
    with And("the message names --ssh-key"):
        assert "argument error: --ssh-key is not defined" in stderr, stderr


@TestScenario
def check_fully_valid_config_returns_none(self):
    with Given("a fully valid config with github fields and a credentialed provider"):
        cfg = _minimal_config(
            providers=provider_list(hetzner=hetzner_provider(token="t"))
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it returns without exiting and without printing anything"):
        assert code is None, (code, stderr)
        assert stderr == "", stderr


@TestScenario
def check_enabled_providers_rejects_provider_not_credentialed(self):
    """Install gate: --provider aws with only Hetzner credentialed must fail check()."""
    with Given("hetzner fully credentialed, but enabled_providers requests aws"):
        cfg = _minimal_config(
            providers=provider_list(hetzner=hetzner_provider(token="t")),
            enabled_providers=["aws"],
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it exits 1"):
        assert code == 1, (code, stderr)
    with And("the message names aws and its config section"):
        assert "aws" in stderr, stderr
        assert "providers.aws" in stderr, stderr


@TestScenario
def check_enabled_providers_rejects_present_but_incomplete_provider(self):
    """A present-but-incomplete aws section must fail the same as an absent one."""
    with Given("an aws section missing secret_access_key, requested via --provider"):
        cfg = _minimal_config(
            providers=provider_list(aws=aws_provider(access_key_id="k")),
            enabled_providers=["aws"],
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it exits 1"):
        assert code == 1, (code, stderr)
    with And("the message names aws and its config section"):
        assert "aws" in stderr, stderr
        assert "providers.aws" in stderr, stderr


@TestScenario
def check_enabled_providers_rejects_when_one_of_several_is_missing(self):
    """hetzner and aws are both requested; only hetzner is credentialed."""
    with Given("hetzner credentialed, aws requested but not configured at all"):
        cfg = _minimal_config(
            providers=provider_list(hetzner=hetzner_provider(token="t")),
            enabled_providers=["hetzner", "aws"],
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it exits 1"):
        assert code == 1, (code, stderr)
    with And("the message names the missing provider, not the satisfied one"):
        assert "aws" in stderr, stderr
        assert "providers.aws" in stderr, stderr


@TestScenario
def check_enabled_providers_passes_when_each_named_provider_is_complete(self):
    with Given("hetzner and aws both fully credentialed and both requested"):
        cfg = _minimal_config(
            providers=provider_list(
                hetzner=hetzner_provider(token="t"),
                aws=aws_provider(access_key_id="k", secret_access_key="s"),
            ),
            enabled_providers=["hetzner", "aws"],
        )
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it returns without exiting"):
        assert code is None, (code, stderr)


@TestScenario
def check_enabled_providers_none_behaves_exactly_as_before(self):
    """No --provider: any one complete provider still passes."""
    with Given("only hetzner configured, enabled_providers left at None"):
        cfg = _minimal_config(
            providers=provider_list(hetzner=hetzner_provider(token="t")),
        )
    with Then("enabled_providers defaults to None"):
        assert cfg.enabled_providers is None
    with When("check() runs with no arguments"):
        code, stderr = _check(cfg)
    with Then("it returns without exiting"):
        assert code is None, (code, stderr)


# ---------------------------------------------------------------------------
# argparse round-trip through the real parser (SimpleNamespace skips type=)
# ---------------------------------------------------------------------------


@TestScenario
def argv_round_trip_sets_hetzner_provider_fields(self):
    cli = _cli_module()
    with When("real argv is parsed for hetzner"):
        parsed = cli.argparser().parse_args(
            [
                "--github-token", "t",
                "--github-repository", "o/r",
                "--hetzner-token", "htok",
            ]
        )
    with And("apply_args runs on a fresh Config"):
        cfg = Config(providers=provider_list())
        apply_args(cfg, parsed)
    with Then("the value lands on the config as a plain string"):
        assert cfg.providers.hetzner.token == "htok", cfg.providers.hetzner.token
        assert isinstance(cfg.providers.hetzner.token, str)


@TestScenario
def argv_round_trip_sets_aws_provider_fields(self):
    """AWS default flags use provider-local type= validators; hit argparse."""
    cli = _cli_module()
    with When("real argv is parsed for aws"):
        parsed = cli.argparser().parse_args(
            [
                "--github-token", "t",
                "--github-repository", "o/r",
                "--aws-access-key-id", "k",
                "--aws-secret-access-key", "s",
                "--aws-default-image", "ami-0abcdef1234567890",
                "--aws-default-server-type", "t3.medium",
                "--aws-default-location", "us-east-1a",
            ]
        )
    with And("apply_args runs on a fresh Config"):
        cfg = Config(providers=provider_list())
        apply_args(cfg, parsed)
    with Then("the aws provider section is created with plain-string values"):
        defaults = cfg.providers.aws.defaults
        assert defaults.image == "ami-0abcdef1234567890", defaults.image
        assert defaults.server_type == "t3.medium", defaults.server_type
        assert defaults.location == "us-east-1a", defaults.location
        assert all(
            isinstance(v, str)
            for v in (defaults.image, defaults.server_type, defaults.location)
        )
    with And("provider_factory builds it"):
        mock_ec2()
        assert [p.name for p in provider_factory(cfg)] == ["aws"]


@TestScenario
def argv_round_trip_sets_scaleway_provider_fields(self):
    cli = _cli_module()
    with When("real argv is parsed for scaleway"):
        parsed = cli.argparser().parse_args(
            [
                "--github-token", "t",
                "--github-repository", "o/r",
                "--scaleway-access-key", "k",
                "--scaleway-secret-key", "s",
                "--scaleway-project-id", "p",
                "--scaleway-default-image", "ubuntu_jammy",
                "--scaleway-default-server-type", "dev1.m",
                "--scaleway-default-location", "fr-par-1",
            ]
        )
    with And("apply_args runs on a fresh Config"):
        cfg = Config(providers=provider_list())
        apply_args(cfg, parsed)
    with Then("the scaleway provider section is created with plain-string values"):
        defaults = cfg.providers.scaleway.defaults
        assert defaults.image == "ubuntu_jammy", defaults.image
        assert defaults.server_type == "dev1.m", defaults.server_type
        assert defaults.location == "fr-par-1", defaults.location
        assert all(
            isinstance(v, str)
            for v in (defaults.image, defaults.server_type, defaults.location)
        )
    with And("provider_factory builds it (scaleway SDK is optional -> faked)"):
        mock_scaleway_sdk()
        assert [p.name for p in provider_factory(cfg)] == ["scaleway"]


@TestScenario
def argv_round_trip_sets_provider_flag(self):
    cli = _cli_module()
    with When("real argv is parsed with --provider"):
        parsed = cli.argparser().parse_args(
            [
                "--github-token", "t",
                "--github-repository", "o/r",
                "--provider", "hetzner,aws",
            ]
        )
    with And("apply_args runs on a fresh Config"):
        cfg = Config(providers=provider_list())
        apply_args(cfg, parsed)
    with Then("enabled_providers lands on the config as a plain string list"):
        assert cfg.enabled_providers == ["hetzner", "aws"], cfg.enabled_providers
        assert all(isinstance(p, str) for p in cfg.enabled_providers)


# ---------------------------------------------------------------------------
# 5. service install / cloud install refuse provider settings passed as flags
# ---------------------------------------------------------------------------


@TestScenario
def cli_provider_flags_detects_configured_prefixes(self):
    from testflows.github.runners.service import cli_provider_flags

    ns = SimpleNamespace(
        aws_access_key_id="K",
        aws_secret_access_key="S",
        aws_default_location=None,
        hetzner_token=None,
        scaleway_access_key=None,
        enabled_providers=["aws"],
        github_token="t",
    )
    with When("cli_provider_flags scans the namespace"):
        flags = cli_provider_flags(ns)
    with Then("only the set provider-prefixed flags are reported"):
        assert flags == {"--aws-access-key-id": "K", "--aws-secret-access-key": "S"}, flags


@TestScenario
def cli_provider_flags_ignores_the_global_provider_flag(self):
    """--provider (dest enabled_providers) is already written into the unit by
    command_options(); it must not be treated as a dropped provider setting."""
    from testflows.github.runners.service import cli_provider_flags

    ns = SimpleNamespace(enabled_providers=["hetzner", "aws"], github_token="t")
    with Then("no flags are reported"):
        assert cli_provider_flags(ns) == {}


@TestScenario
def cli_provider_flags_covers_a_flag_added_later(self):
    """Detection is by dest prefix, not a hardcoded flag list: a brand new
    --aws-* flag is picked up with no change to this detection code."""
    from testflows.github.runners.service import cli_provider_flags

    ns = SimpleNamespace(aws_brand_new_setting="value", enabled_providers=None)
    with Then("the new flag is still detected"):
        assert cli_provider_flags(ns) == {"--aws-brand-new-setting": "value"}


@TestScenario
def check_no_provider_flags_names_each_providers_own_section(self):
    """The message names the real providers.<x> section per flag, not a
    "providers.<name>" placeholder, and lists every provider involved when
    flags from more than one are passed together."""
    ns = SimpleNamespace(
        aws_access_key_id="K",
        aws_secret_access_key="S",
        scaleway_access_key="k",
        enabled_providers=None,
    )
    with Then("both real sections are named and no placeholder leaks"):
        try:
            service.check_no_provider_flags(ns)
            assert False, "expected ValueError"
        except ValueError as exc:
            msg = str(exc)
        assert "providers.aws" in msg, msg
        assert "providers.scaleway" in msg, msg
        assert "providers.<name>" not in msg, msg


@TestScenario
def service_install_refuses_provider_flag_from_cli(self):
    """An AWS config built from flags alone passes config.check(), but
    command_options() never writes provider flags into the unit, so the
    installed service would start with no provider. service install must
    refuse before touching the filesystem."""
    cli = _cli_module()
    with When("`service install` is parsed with AWS credential flags"):
        parsed = cli.argparser().parse_args(
            [
                "--github-token", "t",
                "--github-repository", "o/r",
                "--aws-access-key-id", "K",
                "--aws-secret-access-key", "S",
                "service", "install",
            ]
        )
    cfg = Config(providers=provider_list())
    with And("apply_args runs, configuring AWS purely from the flags"):
        apply_args(cfg, parsed)
        assert cfg.providers.aws is not None

    with patch("testflows.github.runners.service.os.system") as mock_system, patch(
        "testflows.github.runners.service.os.path.exists", return_value=False
    ):
        with Then("service.install refuses and never touches the filesystem"):
            try:
                service.install(parsed, cfg)
                assert False, "expected ValueError"
            except ValueError as exc:
                msg = str(exc)
            assert "--aws-access-key-id" in msg, msg
            assert "--aws-secret-access-key" in msg, msg
            assert "providers.aws" in msg, msg
            assert "providers.<name>" not in msg, msg
            mock_system.assert_not_called()


@TestScenario
def service_install_allows_config_file_only_providers(self):
    """No provider flags on the command line: the gate must not fire even
    though a provider is configured (from the config file)."""
    cli = _cli_module()
    with When("`service install` is parsed with no provider flags"):
        parsed = cli.argparser().parse_args(
            ["--github-token", "t", "--github-repository", "o/r", "service", "install"]
        )
    cfg = Config(
        github_token="t",
        github_repository="o/r",
        ssh_key="/tmp/key",
        providers=provider_list(aws=aws_provider(access_key_id="K", secret_access_key="S")),
    )
    cfg.logger_config = {
        "handlers": {"rotating_logfile": {"filename": "/tmp/tfs-test.log"}}
    }
    with patch("testflows.github.runners.service.os.system") as mock_system, patch(
        "testflows.github.runners.service.os.path.exists", return_value=False
    ), patch("testflows.github.runners.service.config_vars", {}):
        with Then("service.install proceeds (no ValueError from the gate)"):
            service.install(parsed, cfg)
            assert mock_system.called


@TestScenario
def cloud_install_refuses_provider_flag_from_cli(self):
    """Same gap, different transport: `cloud install`/`cloud deploy` push the
    unit over ssh via command_options() + 'service install -f', so a provider
    flag given here would vanish the same way."""
    cli = _cli_module()
    with When("`cloud install` is parsed with Scaleway credential flags"):
        parsed = cli.argparser().parse_args(
            [
                "--github-token", "t",
                "--github-repository", "o/r",
                "--scaleway-access-key", "k",
                "--scaleway-secret-key", "s",
                "--scaleway-project-id", "p",
                "cloud", "install",
            ]
        )
    cfg = Config(providers=provider_list())
    with Then("cloud.install refuses, naming the flags, before resolving a server"):
        try:
            cloud.install(parsed, cfg)
            assert False, "expected ValueError"
        except ValueError as exc:
            msg = str(exc)
        assert "--scaleway-access-key" in msg, msg
        assert "--scaleway-secret-key" in msg, msg
        assert "--scaleway-project-id" in msg, msg
        assert "providers.scaleway" in msg, msg
        assert "providers.<name>" not in msg, msg


@TestScenario
def cloud_deploy_refuses_provider_flag_before_provisioning(self):
    """cloud deploy must fail before spinning up a server, not after."""
    cli = _cli_module()
    with When("`cloud deploy` is parsed with AWS credential flags"):
        parsed = cli.argparser().parse_args(
            [
                "--github-token", "t",
                "--github-repository", "o/r",
                "--aws-access-key-id", "K",
                "--aws-secret-access-key", "S",
                "cloud", "deploy",
            ]
        )
    cfg = Config(providers=provider_list())
    with patch.object(cloud, "deploy_provider") as mock_deploy_provider:
        with Then("cloud.deploy refuses and never resolves a deploy provider"):
            try:
                cloud.deploy(parsed, cfg)
                assert False, "expected ValueError"
            except ValueError as exc:
                msg = str(exc)
            assert "--aws-access-key-id" in msg, msg
            assert "providers.aws" in msg, msg
            assert "providers.<name>" not in msg, msg
            mock_deploy_provider.assert_not_called()


# ---------------------------------------------------------------------------
# 6. cloud deploy -l/-t/-i are provider-native strings, coerced only for Hetzner
# ---------------------------------------------------------------------------


@TestScenario
def argv_deploy_type_location_image_parse_as_plain_strings(self):
    """-l/-t/-i must not be Hetzner-typed at parse time: an AWS AMI ID used to
    be rejected outright by the Hetzner image_type validator."""
    cli = _cli_module()
    with When("cloud deploy -t/-l/-i are parsed with AWS-shaped values"):
        parsed = cli.argparser().parse_args(
            [
                "--github-token", "t",
                "--github-repository", "o/r",
                "cloud", "deploy",
                "-t", "t3.medium",
                "-l", "us-east-1a",
                "-i", "ami-0abcdef1234567890",
            ]
        )
    with Then("all three parse as plain strings, not hcloud objects"):
        assert parsed.cloud_deploy_server_type == "t3.medium"
        assert parsed.cloud_deploy_location == "us-east-1a"
        assert parsed.cloud_deploy_image == "ami-0abcdef1234567890"


@TestScenario
def apply_args_keeps_aws_deploy_specs_as_strings(self):
    cli = _cli_module()
    parsed = cli.argparser().parse_args(
        [
            "--github-token", "t",
            "--github-repository", "o/r",
            "cloud", "deploy",
            "-t", "t3.medium",
            "-l", "us-east-1a",
            "-i", "ami-0abcdef1234567890",
        ]
    )
    cfg = Config(providers=provider_list())
    cfg.cloud.provider = "aws"
    with When("apply_args merges -l/-t/-i against an AWS cloud.provider"):
        apply_args(cfg, parsed)
    with Then("the deploy spec stays provider-native strings"):
        assert cfg.cloud.deploy.server_type == "t3.medium", cfg.cloud.deploy.server_type
        assert cfg.cloud.deploy.location == "us-east-1a", cfg.cloud.deploy.location
        assert cfg.cloud.deploy.image == "ami-0abcdef1234567890", cfg.cloud.deploy.image


@TestScenario
def apply_args_coerces_hetzner_deploy_specs(self):
    from hcloud.images.domain import Image
    from hcloud.locations.domain import Location
    from hcloud.server_types.domain import ServerType

    cli = _cli_module()
    parsed = cli.argparser().parse_args(
        [
            "--github-token", "t",
            "--github-repository", "o/r",
            "cloud", "deploy",
            "-t", "cx23",
            "-l", "nbg1",
            "-i", "x86:system:ubuntu-22.04",
        ]
    )
    cfg = Config(providers=provider_list())  # cloud.provider defaults to "hetzner"
    with When("apply_args merges -l/-t/-i against the (default) Hetzner cloud.provider"):
        apply_args(cfg, parsed)
    with Then("the deploy spec is coerced into hcloud types, same as the config-file path"):
        assert isinstance(cfg.cloud.deploy.server_type, ServerType), cfg.cloud.deploy.server_type
        assert cfg.cloud.deploy.server_type.name == "cx23"
        assert isinstance(cfg.cloud.deploy.location, Location), cfg.cloud.deploy.location
        assert cfg.cloud.deploy.location.name == "nbg1"
        assert isinstance(cfg.cloud.deploy.image, Image), cfg.cloud.deploy.image
        assert cfg.cloud.deploy.image.name == "ubuntu-22.04"


@TestScenario
def apply_args_rejects_bad_hetzner_image_with_clear_error(self):
    """A bad Hetzner -i value raises ArgumentTypeError naming the option, so the
    __main__ block reports it through parser.error() instead of a traceback."""
    cli = _cli_module()
    parsed = cli.argparser().parse_args(
        [
            "--github-token", "t",
            "--github-repository", "o/r",
            "cloud", "deploy",
            "-i", "not-a-valid-image-spec",
        ]
    )
    cfg = Config(providers=provider_list())  # defaults to hetzner
    with Then("apply_args raises ArgumentTypeError naming -i/--image"):
        try:
            apply_args(cfg, parsed)
            assert False, "expected ArgumentTypeError for a bad Hetzner -i value"
        except ArgumentTypeError as exc:
            assert "-i/--image" in str(exc), exc


@TestScenario
def cloud_deploy_bad_hetzner_image_is_a_clean_usage_error_not_a_traceback(self):
    """The __main__ block calls apply_args() at top level with no handler
    around it; importing the module skips __main__ entirely, so only running
    the real entry point as a subprocess can prove the user-facing behavior.

    Regression: before routing this through parser.error(), a bad Hetzner -i
    value raised ValueError out of apply_args() and the user saw a full
    Python traceback (that happened to end in a well-worded message) instead
    of a normal argparse usage error.

    `cloud deploy` fails while merging arguments, before dispatch, so no
    cloud/ssh/systemd call is reachable on any branch.
    """
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(_MINIMAL_BASE)
        cfg_path = f.name
    try:
        with When("cloud deploy is run with a bad Hetzner -i value"):
            result = _run_cli(
                [
                    "--config", cfg_path,
                    "cloud", "deploy",
                    "-i", "not-a-valid-image-spec",
                ]
            )
        with Then("it exits 2 with a clean usage error, not a traceback"):
            assert result.returncode == 2, result
            assert "error:" in result.stderr, result.stderr
            assert "-i/--image" in result.stderr, result.stderr
            assert "Traceback" not in result.stderr, result.stderr
            assert "Traceback" not in result.stdout, result.stdout
    finally:
        os.unlink(cfg_path)


# ---------------------------------------------------------------------------
# 7. cloud deploy --help reflects real (multi-provider) behavior
# ---------------------------------------------------------------------------


@TestScenario
def cloud_deploy_help_describes_real_provider_routing(self):
    cli = _cli_module()
    parser = cli.argparser()
    buf = io.StringIO()
    with When("`cloud deploy --help` is rendered"), contextlib.redirect_stdout(buf):
        try:
            parser.parse_args(["cloud", "deploy", "--help"])
        except SystemExit:
            pass
    help_text = buf.getvalue()
    with Then("it no longer claims deploy is Hetzner-only"):
        assert "currently provisions the host on Hetzner Cloud" not in help_text
        assert "Hetzner location/type/image formats" not in help_text
    with And("it names the real routing and per-provider -l/-t/-i formats"):
        assert "config.cloud.provider" in help_text
        assert "aws" in help_text.lower()
        assert "scaleway" in help_text.lower()


def _help_text(argv):
    cli = _cli_module()
    parser = cli.argparser()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            parser.parse_args(argv)
        except SystemExit:
            pass
    return buf.getvalue()


@TestScenario
def service_install_help_names_the_provider_flag_refusal(self):
    """`service install --help` used to claim every option is carried into
    the installed unit, which is no longer true for provider flags: they are
    refused outright."""
    with When("`service install --help` is rendered"):
        help_text = _help_text(["service", "install", "--help"])
    with Then("it does not claim every option is carried into the unit"):
        assert "will be the same options with which the service will be executed" not in help_text
    with And("it names the config-file seam, the refusal, and the --provider exception"):
        assert "--config" in help_text
        assert "refused" in help_text
        assert "--provider" in help_text


@TestScenario
def cloud_install_help_names_the_provider_flag_refusal(self):
    """Same claim, same fix, on the `cloud install` path."""
    with When("`cloud install --help` is rendered"):
        help_text = _help_text(["cloud", "install", "--help"])
    with Then("it does not claim every option is carried into the unit"):
        assert "will be the same options with which the service will be executed" not in help_text
    with And("it names the config-file seam, the refusal, and the --provider exception"):
        assert "--config" in help_text
        assert "refused" in help_text
        assert "--provider" in help_text


# ---------------------------------------------------------------------------
# 8. coerce_deploy_field errors name only the bad value; callers add context
# ---------------------------------------------------------------------------


@TestScenario
def yaml_deploy_image_error_does_not_mention_a_cli_flag(self):
    """coerce_deploy_field() is shared by the CLI path (apply_args) and the
    config-file path (parse.py). A bad value from the YAML file must not be
    reported as a bad CLI option: the user never passed one."""
    text = _MINIMAL_BASE.replace(
        "ssh_key: /tmp/key\n",
        "ssh_key: /tmp/key\n  cloud:\n    provider: hetzner\n    deploy:\n      image: not-a-valid-image-spec\n",
    )
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(text)
        cfg_path = f.name
    try:
        with When("a bad Hetzner image spec is parsed from the config file"):
            try:
                parse_config(cfg_path)
                assert False, "expected AssertionError for a bad image spec"
            except AssertionError as exc:
                msg = str(exc)
        with Then("the message names the config path but no CLI flag"):
            assert "config.cloud.deploy.image" in msg, msg
            assert "-i/--image" not in msg, msg
            assert "--image" not in msg, msg
    finally:
        os.unlink(cfg_path)


# ---------------------------------------------------------------------------
# Feature entry point
# ---------------------------------------------------------------------------


@TestFeature
@Name("cli and config")
def feature(self):
    """CLI smoke + provider whitelist + schema regression tests."""
    for scenario in loads(current_module(), Scenario):
        scenario()
