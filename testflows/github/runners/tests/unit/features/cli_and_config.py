"""CLI smoke tests and config-layer regression tests.

Covers:
- CLI --help exits 0 and produces output (smoke test)
- provider_type() accepts valid providers (hetzner/aws/scaleway) and rejects
  not-yet-implemented ones (azure/gcp)
- Config parser rejects azure/gcp with a clear message
- schema.json lists hetzner, aws and scaleway under providers.properties
"""
import json
import os
import subprocess
import sys
from argparse import ArgumentTypeError
from types import SimpleNamespace

from testflows.core import *

from testflows.github.runners.args import provider_type
from testflows.github.runners.config.config import (
    Config,
    hetzner_provider,
    aws_provider,
    scaleway_provider,
    provider_list,
    apply_args,
)
from testflows.github.runners.config.parse import parse_config
from testflows.github.runners.config.factory import provider_factory
from testflows.github.runners.errors import ConfigError
from testflows.github.runners.service import command_options

# Repo root so the CLI subprocess can find the package without an install.
_REPO_ROOT = os.path.abspath(os.path.join(current_dir(), "..", "..", "..", "..", "..", ".."))
_CLI_SCRIPT = os.path.join(_REPO_ROOT, "testflows", "github", "runners", "bin", "tfs-github-runners")
_SCHEMA_PATH = os.path.join(_REPO_ROOT, "testflows", "github", "runners", "config", "schema.json")


def _run_help():
    env = os.environ.copy()
    env["PYTHONPATH"] = _REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, _CLI_SCRIPT, "--help"],
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
    """The --provider CLI flag (dest=enabled_providers) reaches Config.enabled_providers
    through the generic apply_args allow-list loop."""
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
    """enabled_providers=None (the default) means unchanged behavior: every
    configured provider is built."""
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
    """Requesting a provider with no providers.<name> section at all must fail,
    not silently narrow to what happens to exist."""
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
    with Then("a ConfigError names the missing provider"):
        assert raised is not None
        assert "aws" in str(raised), str(raised)


@TestScenario
def provider_factory_raises_for_requested_provider_missing_credentials(self):
    """A providers.aws: section that exists but lacks credentials makes
    from_config return None -- same observable failure as no section at all,
    and must be rejected the same way, checked after building."""
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
    with Then("a ConfigError names aws, even though a providers.aws section exists"):
        assert raised is not None
        assert "aws" in str(raised), str(raised)


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
    """enabled_providers is CLI-only (--provider); it must not be settable,
    unvalidated, from the config file."""
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
    """A bare `provider:` key (the name a user would try first) is rejected
    the same way as enabled_providers."""
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
# Feature entry point
# ---------------------------------------------------------------------------


@TestFeature
@Name("cli and config")
def feature(self):
    """CLI smoke + provider whitelist + schema regression tests."""
    for scenario in loads(current_module(), Scenario):
        scenario()
