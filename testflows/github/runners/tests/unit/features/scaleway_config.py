"""Tests for the Scaleway provider: type translation, args validation,
config parsing/propagation, and the canonical-type runner-name round-trip.

No real Scaleway API calls are made; the optional ``scaleway`` SDK is faked via
``mock_scaleway_sdk`` for the factory-construction scenario.  Everything else is
pure logic and needs no SDK.
"""
from argparse import ArgumentTypeError

from testflows.core import *

from testflows.github.runners.config.parse import parse_config
from testflows.github.runners.config.factory import provider_factory
from testflows.github.runners.config.config import (
    Config,
    provider_list,
    scaleway_provider as scaleway_provider_config,
)
from types import SimpleNamespace

from testflows.github.runners.cloud_provider import (
    CloudProvider,
    ProviderServer,
    ProviderServerType,
)
from testflows.github.runners.errors import ImageError, ImageSpecFormatError, ServerTypeError
from testflows.github.runners.providers.scaleway import utils, args as scw_args
from testflows.github.runners.scale_up import get_server_types, get_runner_server_type
from testflows.github.runners.utils import format_runner_name
from testflows.github.runners.constants import runner_name_prefix
from testflows.github.runners.tests.unit.steps.config import write_config
from testflows.github.runners.tests.unit.steps.scaleway import mock_scaleway_sdk, scaleway_provider


class _FakeImage:
    """Minimal stand-in for a Scaleway Image (private or local marketplace)."""

    def __init__(self, id, name="", arch="x86_64"):
        self.id = id
        self.name = name
        self.arch = arch


# Native Scaleway types (dash-form) <-> canonical (dot-form) used across tests.
_TYPES = [
    ("DEV1-S", "dev1.s"),
    ("GP1-XS", "gp1.xs"),
    ("PRO2-XXS", "pro2.xxs"),
    ("POP2-2C-8G", "pop2.2c.8g"),  # multi-dash
    ("BASIC2-A8C-16G", "basic2.a8c.16g"),  # multi-dash
]


# ---------------------------------------------------------------------------
# Type translation: the dot <-> dash bijection
# ---------------------------------------------------------------------------


@TestScenario
def native_to_canonical(self):
    """Native dash-form translates to dash-free canonical dot-form."""
    for native, canonical in _TYPES:
        assert utils.canonical_type(native) == canonical, native
        assert "-" not in utils.canonical_type(native), native


@TestScenario
def canonical_to_native_roundtrip(self):
    """canonical -> native -> canonical is a clean round-trip (incl. multi-dash)."""
    for native, canonical in _TYPES:
        assert utils.native_type(canonical) == native, canonical
        assert utils.canonical_type(utils.native_type(canonical)) == canonical


# ---------------------------------------------------------------------------
# Scaleway list[str] tags <-> dict labels
# ---------------------------------------------------------------------------


@TestScenario
def tags_dict_roundtrip(self):
    """A label dict round-trips through Scaleway's list[str] tag format."""
    labels = {
        "github-runner": "active",
        "github-runner-label-0": "self-hosted",
        "bare": "",
    }
    tags = utils.dict_to_tags(labels)
    assert "bare" in tags and "bare=" not in tags, tags
    assert utils.tags_to_dict(tags) == labels, tags


# ---------------------------------------------------------------------------
# args validator: the CLI-side guard for the '-' footgun
# ---------------------------------------------------------------------------


@TestScenario
def args_server_type_rejects_dash(self):
    """Dash-form server type is rejected with a message pointing at the dot-form."""
    try:
        scw_args.server_type("DEV1-S")
        assert False, "expected ArgumentTypeError for dash-form type"
    except ArgumentTypeError as exc:
        assert "dev1.s" in str(exc), str(exc)


@TestScenario
def args_server_type_accepts_dot(self):
    """Dot-form server types (incl. multi-dot) are accepted and lower-cased."""
    assert scw_args.server_type("dev1.s") == "dev1.s"
    assert scw_args.server_type("GP1.XS") == "gp1.xs"
    assert scw_args.server_type("pop2.2c.8g") == "pop2.2c.8g"


@TestScenario
def args_zone_validation(self):
    """Zone validator accepts valid zones and rejects malformed ones."""
    assert scw_args.location_type("fr-par-1") == "fr-par-1"
    assert scw_args.location_type("nl-ams-2") == "nl-ams-2"
    try:
        scw_args.location_type("paris")
        assert False, "expected ArgumentTypeError for invalid zone"
    except ArgumentTypeError:
        pass


# ---------------------------------------------------------------------------
# The core concern: canonical types survive the runner-name encoding
# ---------------------------------------------------------------------------


@TestScenario
def get_server_types_accepts_dot_skips_dash(self):
    """type-<dot> labels are honoured; the dash-form is skipped (composite-label rule)."""
    with When("a job carries a dot-form type label"):
        types = get_server_types(["self-hosted", "type-dev1.s"], default="dev1.m")
    with Then("the dot-form type is selected"):
        assert types == ["dev1.s"], types
    with When("a job carries a dash-form type label"):
        types = get_server_types(["type-dev1-s"], default="dev1.m")
    with Then("the dash-form is skipped and the default is used"):
        assert types == ["dev1.m"], types


@TestScenario
def runner_name_roundtrip_for_dot_types(self):
    """A canonical dot-type survives the runner-name codec round-trip.

    ``format_runner_name`` builds the name and ``get_runner_server_type``
    decodes the type back out; both stay correct only because the canonical
    form is dash-free.
    """
    for _native, canonical in _TYPES:
        name = format_runner_name("run1", 0, canonical)
        with Then(f"name is built in canonical form for {canonical}"):
            assert name == f"{runner_name_prefix}run1-0-{canonical}", name
        with And(f"type decodes from name for {canonical}"):
            assert get_runner_server_type(name) == canonical, name


# ---------------------------------------------------------------------------
# parse_config: propagation and dash rejection
# ---------------------------------------------------------------------------


@TestScenario
def parse_propagates_credentials_and_defaults(self):
    """Scaleway creds and defaults in YAML reach cfg.providers.scaleway."""
    with Given("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              scaleway:
                access_key: SCWTEST
                secret_key: s3cr3t
                project_id: 11111111-1111-1111-1111-111111111111
                defaults:
                  server_type: dev1.m
                  location: fr-par-1
                  image: ubuntu_jammy
        """)
    with When("I parse the config"):
        cfg = parse_config(path)
    with Then("credentials and defaults match"):
        scw = cfg.providers.scaleway
        assert scw.access_key == "SCWTEST", scw
        assert scw.secret_key == "s3cr3t", scw
        assert scw.project_id == "11111111-1111-1111-1111-111111111111", scw
        assert scw.defaults.server_type == "dev1.m", scw
        assert scw.defaults.location == "fr-par-1", scw
        assert scw.defaults.image == "ubuntu_jammy", scw


@TestScenario
def scaleway_parse_section_validates(self):
    """parse_config_section coerces a valid section and rejects dash-form types."""
    from testflows.github.runners.providers.scaleway import config as scw_config

    with Then("a valid section coerces into the dataclass"):
        cfg = scw_config.parse_config_section(
            {
                "access_key": "k",
                "secret_key": "s",
                "project_id": "p",
                "defaults": {"server_type": "dev1.m", "location": "fr-par-1"},
            }
        )
        assert cfg.access_key == "k" and cfg.defaults.server_type == "dev1.m", cfg
    with And("max_runners 0 allowed; negatives rejected"):
        base = {
            "access_key": "k",
            "secret_key": "s",
            "project_id": "p",
            "defaults": {"server_type": "dev1.m", "location": "fr-par-1"},
        }
        assert (
            scw_config.parse_config_section({**base, "max_runners": 0}).max_runners == 0
        )
        rejected = False
        try:
            scw_config.parse_config_section({**base, "max_runners": -1})
        except AssertionError:
            rejected = True
        assert rejected, "expected rejection of negative max_runners"
    with And("a dash-form server_type is rejected"):
        try:
            scw_config.parse_config_section(
                {
                    "access_key": "k",
                    "secret_key": "s",
                    "project_id": "p",
                    "defaults": {"server_type": "DEV1-M"},
                }
            )
            assert False, "expected rejection"
        except AssertionError:
            pass


@TestScenario
def parse_rejects_dash_server_type(self):
    """A dash-form default server_type in config is rejected with guidance."""
    with Given("a config file with a dash-form server_type"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              scaleway:
                access_key: AK
                secret_key: SK
                project_id: pid
                defaults:
                  server_type: DEV1-M
        """)
    with Then("parsing raises with a dot-form hint"):
        try:
            parse_config(path)
            assert False, "expected dash-form server_type to be rejected"
        except AssertionError as exc:
            assert "dot-form" in str(exc), str(exc)


# ---------------------------------------------------------------------------
# factory: YAML -> provider_factory -> ScalewayCloudProvider (SDK faked)
# ---------------------------------------------------------------------------


@TestScenario
def factory_builds_scaleway_provider(self):
    """provider_factory constructs a ScalewayCloudProvider with config values."""
    with Given("a faked scaleway SDK"):
        mock_scaleway_sdk()
    with And("a config file"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              scaleway:
                access_key: AK
                secret_key: SK
                project_id: proj-123
                defaults:
                  location: nl-ams-1
                  image: ubuntu_jammy
        """)
    with When("I parse and build providers"):
        cfg = parse_config(path)
        providers = provider_factory(cfg)
    with Then("exactly one scaleway provider is returned with config applied"):
        scw = [p for p in providers if p.name == "scaleway"]
        assert len(scw) == 1, [p.name for p in providers]
        provider = scw[0]
        assert provider._project_id == "proj-123"
        assert provider._zone == "nl-ams-1"
        assert provider._default_image == "ubuntu_jammy"


@TestScenario
def factory_derives_scaleway_zones_from_meta_labels(self):
    """The factory passes Scaleway in- zones from meta-labels to the provider."""
    with Given("a mocked SDK and a parsed config with scaleway creds"):
        mock_scaleway_sdk()
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              scaleway:
                access_key: k
                secret_key: 11111111-1111-1111-1111-111111111111
                project_id: 22222222-2222-2222-2222-222222222222
                defaults:
                  location: fr-par-1
        """)
        cfg = parse_config(path)
    with And("meta-labels referencing Scaleway and non-Scaleway in- zones"):
        cfg.meta_label = {
            "linux-arm": {"type-basic2.a16c.32g", "in-fr-par-2", "in-nl-ams-1"},
            "x86": {"type-t3.medium", "in-us-east-1a"},
        }
    with When("the factory builds providers"):
        providers = provider_factory(cfg)
        scw = next(p for p in providers if p.name == "scaleway")
    with Then("its zone set is the default plus the Scaleway in- zones"):
        assert scw._zones == {"fr-par-1", "fr-par-2", "nl-ams-1"}, scw._zones


@TestScenario
def scaleway_recycle_override_parses_and_propagates(self):
    """providers.scaleway.recycle / recycle_grace_period parse and reach the provider,
    so recycling can be disabled per-provider (e.g. off for Scaleway)."""
    with Given("a faked scaleway SDK"):
        mock_scaleway_sdk()
    with And("a config that disables recycling for scaleway with a custom grace"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              scaleway:
                access_key: AK
                secret_key: SK
                project_id: proj-123
                recycle: false
                recycle_grace_period: 300
        """)
    with When("I parse and build providers"):
        cfg = parse_config(path)
        provider = [p for p in provider_factory(cfg) if p.name == "scaleway"][0]
    with Then("the per-provider recycle override is applied"):
        assert cfg.providers.scaleway.recycle is False
        assert provider.recycle is False
        assert provider.recycle_grace_period == 300


@TestScenario
def scaleway_recycle_defaults_to_none_for_global_fallback(self):
    """Unset per-provider recycle stays None so the global default applies."""
    with Given("a faked scaleway SDK"):
        mock_scaleway_sdk()
    with And("a config with no per-provider recycle settings"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              scaleway:
                access_key: AK
                secret_key: SK
                project_id: proj-123
        """)
    with When("I parse and build providers"):
        cfg = parse_config(path)
        provider = [p for p in provider_factory(cfg) if p.name == "scaleway"][0]
    with Then("recycle/grace are None (global default applies at runtime)"):
        assert provider.recycle is None
        assert provider.recycle_grace_period is None


@TestScenario
def scaleway_recycle_rejects_non_boolean(self):
    """A non-boolean providers.scaleway.recycle is rejected at parse."""
    with Given("a config with a non-boolean recycle value"):
        path = write_config(yaml_text="""\
            ssh_key: /dev/null
            providers:
              scaleway:
                access_key: AK
                secret_key: SK
                project_id: proj-123
                recycle: "yes"
        """)
    with Then("parsing rejects the non-boolean recycle"):
        try:
            parse_config(path)
            assert False, "expected AssertionError for non-boolean recycle"
        except AssertionError as exc:
            assert "providers.scaleway.recycle" in str(exc), exc


# ---------------------------------------------------------------------------
# get_server_type: resolved across all configured zones
# ---------------------------------------------------------------------------


@TestScenario
def get_server_type_found_in_non_default_zone(self):
    """A type offered only in a non-default zone still resolves."""
    with Given("a provider over two zones; the type exists only in nl-ams-1"):
        provider = scaleway_provider()
        provider._zones = {"fr-par-1", "nl-ams-1"}
        def _types(zone):
            servers = {"BASIC2-A16C-32G": SimpleNamespace(arch="arm64")} if zone == "nl-ams-1" else {}
            return SimpleNamespace(servers=servers)
        provider._instance.list_servers_types.side_effect = _types
    with When("resolving basic2.a16c.32g"):
        st = provider.get_server_type("basic2.a16c.32g")
    with Then("it resolves via the zone that offers it"):
        assert st.name == "basic2.a16c.32g", st.name


# ---------------------------------------------------------------------------
# get_server_arch: authoritative SDK arch, with a name fallback
# ---------------------------------------------------------------------------


@TestScenario
def get_server_arch_uses_sdk_arch(self):
    """Arch comes from the SDK ServerType.arch, not a name guess.

    Reproduces the ARM instance whose name ('basic2.a8c.16g') does not look ARM
    but whose SDK arch is arm64 — it must resolve to arm64, not x64.
    """
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with Then("arm/arm64 SDK arch -> arm64 and x86_64 -> x64, regardless of name"):
        for sdk_arch, expected in [("arm64", "arm64"), ("arm", "arm64"), ("x86_64", "x64")]:
            st = ProviderServerType(name="basic2.a8c.16g", _native=SimpleNamespace(arch=sdk_arch))
            assert provider.get_server_arch(st) == expected, (sdk_arch, expected)


@TestScenario
def get_server_arch_defaults_x64_without_sdk_type(self):
    """A bare ProviderServerType (no SDK object) defaults to x64.

    Arch is authoritative from the SDK ServerType; the name is never parsed for
    architecture (Scaleway type names do not reliably encode it).
    """
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with Then("arch defaults to x64 when there is no SDK ServerType"):
        assert provider.get_server_arch(ProviderServerType(name="dev1.s")) == "x64"
        assert provider.get_server_arch(ProviderServerType(name="basic2.a8c.16g")) == "x64"


def _scaleway_server(raw_state):
    """A ProviderServer carrying a raw Scaleway ``state`` in ``_native`` — the
    field delete_server reads to pick its removal op."""
    status = (
        CloudProvider.STATUS_RUNNING if raw_state == "running"
        else CloudProvider.STATUS_OFF
    )
    return ProviderServer(
        id="srv-1", name="github-runner-1-0-dev1.s", status=status,
        public_ipv4=None, private_ipv4=None, labels={},
        server_type="dev1.s", location="fr-par-1", created=None,
        _native=SimpleNamespace(state=raw_state),
    )


@TestScenario
def delete_server_terminates_running(self):
    """A running instance is removed with terminate; volumes reaped out of band."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with When("delete_server is called on a running instance"):
        provider.delete_server(_scaleway_server("running"))
    with Then("it terminates and never deletes the instance resource or volumes"):
        _, kwargs = provider._instance.server_action.call_args
        assert str(kwargs["action"]) == "terminate", kwargs["action"]
        provider._instance.delete_server.assert_not_called()
        provider._block.delete_volume.assert_not_called()


@TestScenario
def delete_server_stopped_uses_delete_endpoint(self):
    """A fully 'stopped' instance can't be terminated, so it's removed via DELETE.

    Regression: terminate on a stopped server is rejected with
    'resource_not_usable: invalid state stopped for the action terminate'.
    """
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with When("delete_server is called on a stopped instance"):
        provider.delete_server(_scaleway_server("stopped"))
    with Then("it uses the DELETE endpoint and does not attempt terminate"):
        provider._instance.delete_server.assert_called_once()
        _, dkwargs = provider._instance.delete_server.call_args
        assert dkwargs["server_id"] == "srv-1", dkwargs
        provider._instance.server_action.assert_not_called()
        provider._block.delete_volume.assert_not_called()


@TestScenario
def delete_server_stopped_in_place_terminates(self):
    """A 'stopped_in_place' instance still holds its reservation, so terminate —
    picked directly from the raw state (status collapses it with 'stopped')."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with When("delete_server is called on a stopped-in-place instance"):
        provider.delete_server(_scaleway_server("stopped in place"))
    with Then("it terminates in one call, without trying the DELETE endpoint"):
        provider._instance.server_action.assert_called_once()
        _, kwargs = provider._instance.server_action.call_args
        assert str(kwargs["action"]) == "terminate", kwargs["action"]
        provider._instance.delete_server.assert_not_called()


@TestScenario
def delete_server_propagates_errors(self):
    """No fallback for now: a removal error surfaces rather than self-correcting."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    from scaleway_core.api import ScalewayException

    with And("the DELETE endpoint fails"):
        provider._instance.delete_server.side_effect = ScalewayException(
            status_code=403, error_type="quotas_exceeded"
        )
    with Then("delete_server re-raises and does not try terminate as a fallback"):
        try:
            provider.delete_server(_scaleway_server("stopped"))
            assert False, "expected the error to propagate"
        except ScalewayException:
            pass
        provider._instance.server_action.assert_not_called()


def _running_native(name="github-runner-1-0", state="running"):
    """A minimal Scaleway-native server for _server_to_provider."""
    return SimpleNamespace(
        id="srv-1", name=name, state=state, zone="fr-par-1",
        commercial_type="basic2-a16c-32g", tags=[],
        public_ips=None, public_ip=None, private_ip=None,
    )


@TestScenario
def create_server_builds_tagged_boot_volume(self):
    """create_server pre-creates a tagged SBS boot volume and attaches it by id."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("an SBS custom image and stubbed volume/instance calls"):
        provider._instance.get_image.return_value = SimpleNamespace(
            image=SimpleNamespace(
                root_volume=SimpleNamespace(id="snap-1", volume_type="sbs_snapshot")
            )
        )
        provider._block.get_snapshot.return_value = SimpleNamespace(size=128849018880)
        provider._block.create_volume.return_value = SimpleNamespace(id="vol-boot")
        provider._instance._create_server.return_value = SimpleNamespace(
            server=SimpleNamespace(id="srv-1")
        )
        provider._wait_for_state = lambda *a, **k: _running_native()
    with When("create_server runs"):
        provider.create_server(
            name="github-runner-1-0",
            server_type=ProviderServerType(name="basic2-a16c-32g"),
            location="fr-par-1", image="cccccccc-cccc-cccc-cccc-cccccccccccc", ssh_keys=[],
            labels={"github-runner": "active"},
        )
    with Then("the boot volume is created from the snapshot and tagged at birth"):
        ckw = provider._block.create_volume.call_args.kwargs
        assert "github-runner-volume=active" in ckw["tags"], ckw
        assert ckw["from_snapshot"].snapshot_id == "snap-1", ckw
    with And("the instance is created from that volume, not an image"):
        skw = provider._instance._create_server.call_args.kwargs
        assert skw.get("image") is None, skw
        template = skw["volumes"]["0"]
        assert template.id == "vol-boot", template
        assert template.boot is True, template
        # Attaching by id must not send size (SDK default 0) — the API rejects
        # 'id' + 'size' together.
        assert template.size is None, template.size


@TestScenario
def create_server_resolves_image_in_target_zone(self):
    """The image spec is resolved against the create location, not self._zone."""
    with Given("a scaleway provider whose custom image resolves to a zone id"):
        provider = scaleway_provider()
        provider._instance.list_images_all.return_value = [
            SimpleNamespace(id="img-ams", name="runner-base", arch="x86_64"),
        ]
        provider._instance.get_image.return_value = SimpleNamespace(
            image=SimpleNamespace(
                root_volume=SimpleNamespace(id="snap-1", volume_type="sbs_snapshot")
            )
        )
        provider._block.get_snapshot.return_value = SimpleNamespace(size=10 * 1024**3)
        provider._block.create_volume.return_value = SimpleNamespace(id="vol-boot")
        provider._instance._create_server.return_value = SimpleNamespace(
            server=_running_native(state="running")
        )
        provider._wait_for_state = lambda *a, **k: _running_native(state="running")
    with When("create_server runs with location nl-ams-1 and a custom image name"):
        provider.create_server(
            name="r", server_type=ProviderServerType(name="basic2-a16c-32g"),
            location="nl-ams-1", image="runner-base", ssh_keys=[], labels={},
        )
    with Then("the image was resolved in nl-ams-1 and its id used for the boot volume"):
        _, ikwargs = provider._instance.list_images_all.call_args
        assert ikwargs["zone"] == "nl-ams-1", ikwargs
        assert provider._instance.get_image.call_args.kwargs["image_id"] == "img-ams"


@TestScenario
def create_server_root_disk_size_sizes_boot_volume(self):
    """A per-job root_disk_size grows the SBS boot volume above the snapshot floor."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("an SBS custom image (120 GiB snapshot) and stubbed calls"):
        provider._instance.get_image.return_value = SimpleNamespace(
            image=SimpleNamespace(
                root_volume=SimpleNamespace(id="snap-1", volume_type="sbs_snapshot")
            )
        )
        provider._block.get_snapshot.return_value = SimpleNamespace(size=120 * 1024**3)
        provider._block.create_volume.return_value = SimpleNamespace(id="vol-boot")
        provider._instance._create_server.return_value = SimpleNamespace(
            server=SimpleNamespace(id="srv-1")
        )
        provider._wait_for_state = lambda *a, **k: _running_native()
    with When("create_server runs with root_disk_size=200"):
        provider.create_server(
            name="github-runner-1-0",
            server_type=ProviderServerType(name="basic2-a16c-32g"),
            location="fr-par-1", image="cccccccc-cccc-cccc-cccc-cccccccccccc", ssh_keys=[], labels={},
            root_disk_size=200,
        )
    with Then("the boot volume is requested at 200 GiB (above the snapshot floor)"):
        ckw = provider._block.create_volume.call_args.kwargs
        assert ckw["from_snapshot"].size == 200 * 1024**3, ckw["from_snapshot"].size
    with And("the boot size is recorded as a server tag for recycle matching"):
        skw = provider._instance._create_server.call_args.kwargs
        assert f"{utils._ROOT_DISK_TAG}=200" in skw["tags"], skw["tags"]


@TestScenario
def create_server_root_disk_below_snapshot_uses_snapshot_floor(self):
    """A minimum smaller than the image snapshot is floored at the snapshot size."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("an SBS custom image (120 GiB snapshot) and stubbed calls"):
        provider._instance.get_image.return_value = SimpleNamespace(
            image=SimpleNamespace(
                root_volume=SimpleNamespace(id="snap-1", volume_type="sbs_snapshot")
            )
        )
        provider._block.get_snapshot.return_value = SimpleNamespace(size=120 * 1024**3)
        provider._block.create_volume.return_value = SimpleNamespace(id="vol-boot")
        provider._instance._create_server.return_value = SimpleNamespace(
            server=SimpleNamespace(id="srv-1")
        )
        provider._wait_for_state = lambda *a, **k: _running_native()
    with When("create_server runs with root_disk_size=50 (below the 120 GiB snapshot)"):
        provider.create_server(
            name="github-runner-1-0",
            server_type=ProviderServerType(name="basic2-a16c-32g"),
            location="fr-par-1", image="cccccccc-cccc-cccc-cccc-cccccccccccc", ssh_keys=[], labels={},
            root_disk_size=50,
        )
    with Then("the boot volume is floored at the 120 GiB snapshot size"):
        ckw = provider._block.create_volume.call_args.kwargs
        assert ckw["from_snapshot"].size == 120 * 1024**3, ckw["from_snapshot"].size


@TestScenario
def scaleway_fixed_root_disk_local_vs_sbs(self):
    """fixed_root_disk returns the local SSD cap (GB) for local types, None for SBS."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with Then("a local-bootable type reports its l_ssd cap in GB"):
        assert provider.fixed_root_disk(_local_type(l_ssd_max=50 * 1024**3)) == 50
    with And("an SBS-only type (l_ssd max 0) is resizable -> None"):
        sbs = ProviderServerType(
            name="basic2.a16c.32g",
            _native=SimpleNamespace(
                per_volume_constraint=SimpleNamespace(
                    l_ssd=SimpleNamespace(max_size=0)
                )
            ),
        )
        assert provider.fixed_root_disk(sbs) is None
    with And("a bare type with no _native is resizable -> None"):
        assert provider.fixed_root_disk(ProviderServerType(name="x")) is None


@TestScenario
def server_to_provider_reads_boot_volume_size(self):
    """_server_to_provider surfaces the boot volume size (GB) for recycle matching."""
    with Given("a native server with a 160 GiB boot volume and a data volume"):
        srv = SimpleNamespace(
            id="i", name="github-runner-1-0", state="running", zone="fr-par-1",
            commercial_type="basic2-a16c-32g",
            public_ips=[], public_ip=None, private_ip=None, tags=[], creation_date=None,
            volumes={
                "0": SimpleNamespace(boot=True, size=160 * 1024**3),
                "1": SimpleNamespace(boot=False, size=50 * 1024**3),
            },
        )
    with Then("root_disk_size is the boot volume size in GB"):
        ps = utils._server_to_provider(srv)
        assert ps.root_disk_size == 160, ps.root_disk_size


@TestScenario
def server_to_provider_root_disk_none_without_volumes(self):
    """No volumes mapping -> root_disk_size is None (unknown)."""
    with Given("a native server with no volumes"):
        srv = _running_native()
    with Then("root_disk_size is None"):
        ps = utils._server_to_provider(srv)
        assert ps.root_disk_size is None, ps.root_disk_size


@TestScenario
def server_to_provider_reads_root_disk_from_tag(self):
    """An SBS boot volume reports no size in the Instance API listing, so the
    create-time tag is the source; this is the recycle disk-safety gate's input."""
    with Given("a stopped SBS server: boot volume has no size but carries the tag"):
        srv = SimpleNamespace(
            id="i", name="github-runner-recycle-abc", state="stopped",
            zone="fr-par-1", commercial_type="basic2-a8c-16g",
            public_ips=[], public_ip=None, private_ip=None, creation_date=None,
            tags=[f"{utils._ROOT_DISK_TAG}=140"],
            volumes={"0": SimpleNamespace(boot=True, size=None)},
        )
    with Then("root_disk_size comes from the tag, not the empty volume size"):
        ps = utils._server_to_provider(srv)
        assert ps.root_disk_size == 140, ps.root_disk_size


def _local_type(name="dev1.s", l_ssd_max=50 * 1024**3):
    """A local-storage-capable ProviderServerType (l_ssd.max_size > 0)."""
    return ProviderServerType(
        name=name,
        _native=SimpleNamespace(
            per_volume_constraint=SimpleNamespace(
                l_ssd=SimpleNamespace(max_size=l_ssd_max)
            ),
            arch="x86_64",
        ),
    )


@TestScenario
def create_server_local_mode_uses_image_not_boot_volume(self):
    """A local-capable type boots via image= (instance-provisioned local disk),
    with no pre-created/tagged SBS volume."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("a running instance is created and reached"):
        provider._instance._create_server.return_value = SimpleNamespace(
            server=SimpleNamespace(id="srv-1")
        )
        provider._wait_for_state = lambda *a, **k: _running_native()
    with When("create_server runs on a local-capable type"):
        result = provider.create_server(
            name="tfs-controller",
            server_type=_local_type(),
            location="fr-par-1", image="dddddddd-dddd-dddd-dddd-dddddddddddd", ssh_keys=[],
            labels={"role": "controller"},
        )
    with Then("it launches with image= and no volumes, and creates no SBS volume"):
        skw = provider._instance._create_server.call_args.kwargs
        assert skw.get("image") == "dddddddd-dddd-dddd-dddd-dddddddddddd", skw
        assert skw.get("volumes") is None, skw
        provider._block.create_volume.assert_not_called()
    with And("it returns a ProviderServer with the Scaleway ssh_user"):
        assert result.ssh_user == "root", result.ssh_user


@TestScenario
def create_server_sbs_mode_for_sbs_only_native(self):
    """An SBS-only type (l_ssd max_size 0) takes the pre-created tagged SBS path."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("an SBS-only type and stubbed SBS/instance calls"):
        sbs_only = ProviderServerType(
            name="basic2.a16c.32g",
            _native=SimpleNamespace(
                per_volume_constraint=SimpleNamespace(
                    l_ssd=SimpleNamespace(max_size=0)
                ),
                arch="arm64",
            ),
        )
        provider._instance.get_image.return_value = SimpleNamespace(
            image=SimpleNamespace(
                root_volume=SimpleNamespace(id="snap-1", volume_type="sbs_snapshot")
            )
        )
        provider._block.get_snapshot.return_value = SimpleNamespace(size=120 * 1024**3)
        provider._block.create_volume.return_value = SimpleNamespace(id="vol-boot")
        provider._instance._create_server.return_value = SimpleNamespace(
            server=SimpleNamespace(id="srv-1")
        )
        provider._wait_for_state = lambda *a, **k: _running_native()
    with When("create_server runs"):
        provider.create_server(
            name="github-runner-1-0", server_type=sbs_only,
            location="fr-par-1", image="cccccccc-cccc-cccc-cccc-cccccccccccc", ssh_keys=[], labels={},
        )
    with Then("it pre-creates the tagged SBS volume and attaches it (no image=)"):
        provider._block.create_volume.assert_called_once()
        skw = provider._instance._create_server.call_args.kwargs
        assert skw.get("image") is None, skw
        assert skw["volumes"]["0"].id == "vol-boot", skw


@TestScenario
def create_server_local_mode_power_on_failure_removes_instance(self):
    """Local-mode boot failure removes the (stopped) instance, no SBS volume."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("the instance is created stopped but never reaches running"):
        provider._instance._create_server.return_value = SimpleNamespace(
            server=_running_native(name="tfs-controller", state="stopped")
        )

        def _boom(*a, **k):
            raise RuntimeError("boot timeout")

        provider._wait_for_state = _boom
    with Then("it removes the stopped instance via DELETE and touches no volume"):
        try:
            provider.create_server(
                name="tfs-controller", server_type=_local_type(),
                location="fr-par-1", image="dddddddd-dddd-dddd-dddd-dddddddddddd", ssh_keys=[], labels={},
            )
            assert False, "expected the boot failure to propagate"
        except RuntimeError:
            pass
        provider._instance.delete_server.assert_called_once()
        provider._block.create_volume.assert_not_called()
        provider._block.delete_volume.assert_not_called()


@TestScenario
def create_server_sizes_boot_volume_to_configured_default(self):
    """The boot volume grows to the configured default size, floored at the snapshot."""
    with Given("a scaleway provider with a 200 GB configured default disk size"):
        provider = scaleway_provider()
        provider._default_disk_size = 200
    with And("an SBS image whose snapshot is 120 GiB"):
        provider._instance.get_image.return_value = SimpleNamespace(
            image=SimpleNamespace(
                root_volume=SimpleNamespace(id="snap-1", volume_type="sbs_snapshot")
            )
        )
        provider._block.get_snapshot.return_value = SimpleNamespace(size=120 * 1024**3)
        provider._block.create_volume.return_value = SimpleNamespace(id="vol-boot")
        provider._instance._create_server.return_value = SimpleNamespace(
            server=SimpleNamespace(id="srv-1")
        )
        provider._wait_for_state = lambda *a, **k: _running_native()
    with When("create_server runs"):
        provider.create_server(
            name="github-runner-1-0",
            server_type=ProviderServerType(name="basic2-a16c-32g"),
            location="fr-par-1", image="cccccccc-cccc-cccc-cccc-cccccccccccc", ssh_keys=[], labels={},
        )
    with Then("the boot volume is created at the configured 200 GiB, above the snapshot floor"):
        ckw = provider._block.create_volume.call_args.kwargs
        assert ckw["from_snapshot"].size == 200 * 1024**3, ckw["from_snapshot"].size


@TestScenario
def create_server_local_snapshot_raises_helpful_error(self):
    """A local (l_ssd) root volume yields a helpful error and creates no volume."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("an image whose root volume is a local snapshot"):
        provider._instance.get_image.return_value = SimpleNamespace(
            image=SimpleNamespace(
                root_volume=SimpleNamespace(id="snap-local", volume_type="l_ssd")
            )
        )
    with Then("create_server raises ImageError and creates no volume"):
        try:
            provider.create_server(
                name="r", server_type=ProviderServerType(name="basic2-a16c-32g"),
                location="fr-par-1", image="dddddddd-dddd-dddd-dddd-dddddddddddd", ssh_keys=[], labels={},
            )
            assert False, "expected ImageError for a non-SBS image"
        except ImageError as exc:
            assert "SBS" in str(exc), exc
        provider._block.create_volume.assert_not_called()


@TestScenario
def create_server_cross_project_snapshot_raises_helpful_error(self):
    """A 403 from create_volume (marketplace/public snapshot) maps to a helpful error."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    # Imported after the fixture installs the faked scaleway_core into sys.modules.
    from scaleway_core.api import ScalewayException

    with And("an SBS-typed image whose snapshot is in another project"):
        provider._instance.get_image.return_value = SimpleNamespace(
            image=SimpleNamespace(
                root_volume=SimpleNamespace(id="snap-x", volume_type="sbs_snapshot")
            )
        )
        provider._block.get_snapshot.side_effect = ScalewayException(
            status_code=403, error_type="permissions_denied"
        )
        provider._block.create_volume.side_effect = ScalewayException(
            status_code=403, error_type="permissions_denied"
        )
    with Then("create_server raises ImageError mentioning the project"):
        try:
            provider.create_server(
                name="r", server_type=ProviderServerType(name="basic2-a16c-32g"),
                location="fr-par-1", image="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee", ssh_keys=[], labels={},
            )
            assert False, "expected ImageError for a cross-project snapshot"
        except ImageError as exc:
            assert "project" in str(exc), exc


@TestScenario
def create_server_quota_exceeded_propagates_not_image_error(self):
    """A 403 quotas_exceeded is a transient capacity failure, not an image problem.

    Regression: quota exhaustion also returns HTTP 403, so keying on the status
    code alone mislabeled it as 'snapshot not in your project'. It must surface
    as the original ScalewayException so scale_up treats it as a normal (retryable)
    create failure while the reaper frees SBS volumes.
    """
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    from scaleway_core.api import ScalewayException

    with And("an owned SBS image but the SBS volume quota is exhausted"):
        provider._instance.get_image.return_value = SimpleNamespace(
            image=SimpleNamespace(
                root_volume=SimpleNamespace(id="snap-1", volume_type="sbs_snapshot")
            )
        )
        provider._block.get_snapshot.return_value = SimpleNamespace(size=120 * 1024**3)
        provider._block.create_volume.side_effect = ScalewayException(
            status_code=403, error_type="quotas_exceeded"
        )
    with Then("the original ScalewayException propagates (not ImageError)"):
        try:
            provider.create_server(
                name="r", server_type=ProviderServerType(name="basic2-a16c-32g"),
                location="fr-par-1", image="cccccccc-cccc-cccc-cccc-cccccccccccc", ssh_keys=[], labels={},
            )
            assert False, "expected the quota error to propagate"
        except ImageError as exc:
            assert False, f"quota error was mislabeled as ImageError: {exc}"
        except ScalewayException:
            pass


@TestScenario
def create_server_powering_on_failure_removes_partial_instance(self):
    """If power-on/boot fails, the partial (stopped) instance is removed via the
    DELETE endpoint and re-raises; its tagged boot volume is reaper-covered."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("a created boot volume + stopped instance that never reaches running"):
        provider._instance.get_image.return_value = SimpleNamespace(
            image=SimpleNamespace(
                root_volume=SimpleNamespace(id="snap-1", volume_type="sbs_snapshot")
            )
        )
        provider._block.get_snapshot.return_value = SimpleNamespace(size=10)
        provider._block.create_volume.return_value = SimpleNamespace(id="vol-boot")
        provider._instance._create_server.return_value = SimpleNamespace(
            server=_running_native(name="r", state="stopped")
        )

        def _boom(*a, **k):
            raise RuntimeError("boot timeout")

        provider._wait_for_state = _boom
    with Then("it removes the partial instance via DELETE and re-raises"):
        try:
            provider.create_server(
                name="r", server_type=ProviderServerType(name="basic2-a16c-32g"),
                location="fr-par-1", image="ffffffff-ffff-ffff-ffff-ffffffffffff", ssh_keys=[], labels={},
            )
            assert False, "expected the boot failure to propagate"
        except RuntimeError:
            pass
        provider._instance.delete_server.assert_called_once()


@TestScenario
def reap_orphaned_volumes_deletes_detached_aged_only(self):
    """The reaper deletes detached, aged, tagged volumes; not attached or fresh ones."""
    from datetime import datetime, timezone, timedelta

    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("tagged volumes: detached+old, attached, and just-detached"):
        now = datetime.now(timezone.utc)
        old = now - timedelta(minutes=10)
        provider._block.list_volumes_all.return_value = [
            SimpleNamespace(id="orphan", references=[], last_detached_at=old, created_at=old),
            SimpleNamespace(id="attached", references=[SimpleNamespace(id="r")],
                            last_detached_at=None, created_at=old),
            SimpleNamespace(id="fresh", references=[], last_detached_at=now, created_at=now),
        ]
    with When("the scale-down post-cycle hook runs"):
        provider.after_scale_down()
    with Then("it lists tagged, non-deleted volumes"):
        _, lkwargs = provider._block.list_volumes_all.call_args
        assert lkwargs.get("include_deleted") is False, lkwargs
        assert "github-runner-volume=active" in (lkwargs.get("tags") or []), lkwargs
    with And("only the detached, aged orphan is deleted"):
        assert provider._block.delete_volume.call_count == 1, provider._block.delete_volume.call_count
        _, vkwargs = provider._block.delete_volume.call_args
        assert vkwargs["volume_id"] == "orphan", vkwargs


@TestScenario
def reap_orphaned_volumes_scans_all_zones(self):
    """The reaper scans every operating zone, not just the default.

    Regression: volumes are created in the zone the job's in-<zone> label
    selects, so a reaper scoped to self._zone leaks volumes in non-default
    zones (SbsVolumeSizeGb quota leak).
    """
    from datetime import datetime, timezone, timedelta

    with Given("a provider over two zones"):
        provider = scaleway_provider()
        provider._zones = {"fr-par-1", "nl-ams-1"}
    with And("a detached, aged orphan in the NON-default zone only"):
        old = datetime.now(timezone.utc) - timedelta(minutes=10)
        by_zone = {
            "fr-par-1": [],
            "nl-ams-1": [
                SimpleNamespace(
                    id="orphan-ams", references=[],
                    last_detached_at=old, created_at=old,
                )
            ],
        }
        provider._block.list_volumes_all.side_effect = (
            lambda zone, **k: by_zone.get(zone, [])
        )
    with When("the scale-down post-cycle hook runs"):
        provider.after_scale_down()
    with Then("both zones are listed"):
        listed = {c.kwargs["zone"] for c in provider._block.list_volumes_all.call_args_list}
        assert listed == {"fr-par-1", "nl-ams-1"}, listed
    with And("the non-default-zone orphan is deleted in its own zone"):
        assert provider._block.delete_volume.call_count == 1, provider._block.delete_volume.call_count
        _, vkwargs = provider._block.delete_volume.call_args
        assert vkwargs["volume_id"] == "orphan-ams", vkwargs
        assert vkwargs["zone"] == "nl-ams-1", vkwargs


@TestScenario
def scale_up_hook_does_not_reap_volumes(self):
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    provider.before_scale_up(frozenset())
    provider._block.list_volumes_all.assert_not_called()
    provider._block.delete_volume.assert_not_called()


@TestScenario
def scale_down_maintenance_failure_is_non_fatal(self):
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("maintenance raises unexpectedly"):
        provider._reap_orphaned_volumes = lambda: (_ for _ in ()).throw(
            RuntimeError("boom")
        )
    with Then("after_scale_down raises and is handled by orchestration"):
        try:
            provider.after_scale_down()
        except RuntimeError:
            pass
        else:
            assert False, "expected maintenance failure to propagate"


@TestScenario
def stopped_in_place_space_form_maps_to_off(self):
    """The API's space-form 'stopped in place' must map to OFF, not UNKNOWN.

    Scaleway returns the state with spaces; the SDK enum's declared value uses
    underscores and passes unknown values through as raw strings. If we don't
    normalize, the instance maps to STATUS_UNKNOWN, is excluded from listings,
    and is never reaped (quota leak).
    """
    from types import SimpleNamespace
    from testflows.github.runners.providers.scaleway import utils
    from testflows.github.runners.cloud_provider import CloudProvider

    with Then("state_key normalizes spaces to underscores"):
        assert utils.state_key("stopped in place") == "stopped_in_place"
        assert utils.state_key("STOPPED IN PLACE") == "stopped_in_place"
    with And("a server in the space-form state maps to OFF and is listable"):
        srv = SimpleNamespace(
            id="i", name="github-runner-1-0-dev1.s", state="stopped in place",
            zone="fr-par-1", commercial_type="DEV1-S",
            public_ips=[], public_ip=None, private_ip=None, tags=[], creation_date=None,
        )
        ps = utils._server_to_provider(srv)
        assert ps.status == CloudProvider.STATUS_OFF, ps.status
        assert utils.state_key(srv.state) in utils._ACTIVE_STATES


_FAKE_PUBKEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyMaterial"


def _fake_iam(provider):
    """Return the faked IamV1Alpha1API instance the provider will construct."""
    import sys

    return sys.modules["scaleway.iam.v1alpha1"].IamV1Alpha1API.return_value


@TestScenario
def ssh_key_reused_by_identity_despite_name_and_comment(self):
    """An existing key with the SAME material is reused even when it is
    registered under a different name and its stored public_key carries a
    trailing comment (the real duplicate-accumulation case: a human's key like
    'sgibb' with the same fingerprint as the controller's configured key).
    """
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("an existing key under a human name whose pubkey has a comment"):
        iam = _fake_iam(provider)
        iam.list_ssh_keys_all.return_value = [
            SimpleNamespace(
                name="sgibb",  # not our MD5 name
                id="key-human",
                public_key=_FAKE_PUBKEY + " sgibb@laptop",  # same blob, comment added
            )
        ]
    with When("get_or_create_ssh_key runs with the same key material"):
        result = provider.get_or_create_ssh_key(_FAKE_PUBKEY, is_file=False)
    with Then("the existing key is reused by identity and none is created"):
        assert result.id == "key-human", result
        iam.create_ssh_key.assert_not_called()


@TestScenario
def ssh_key_created_only_when_absent(self):
    """With no matching key present, exactly one key is created."""
    with Given("a scaleway provider with no existing keys"):
        provider = scaleway_provider()
        iam = _fake_iam(provider)
        iam.list_ssh_keys_all.return_value = []
        iam.create_ssh_key.return_value = SimpleNamespace(name="k", id="key-new")
    with When("get_or_create_ssh_key runs"):
        result = provider.get_or_create_ssh_key(_FAKE_PUBKEY, is_file=False)
    with Then("a single key is created and returned"):
        iam.create_ssh_key.assert_called_once()
        assert result.id == "key-new", result


@TestScenario
def get_server_ssh_key_name_round_trips(self):
    """get_server_ssh_key_name reads back the key name build_server_labels stored.

    Scaleway inherits the base 'github-runner-ssh-key' tag; this guards the label
    divergence that broke the scale_down ownership check for non-Hetzner servers.
    """
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with When("build_server_labels records an ssh key name"):
        labels = provider.build_server_labels(["self-hosted"], ssh_key_name="abc123")
        server = ProviderServer(
            id="i", name="github-runner-1-0-dev1.s", status="off",
            public_ipv4=None, private_ipv4=None, labels=labels,
            server_type="dev1.s", location="fr-par-1", created=None,
        )
    with Then("get_server_ssh_key_name returns that name"):
        assert provider.get_server_ssh_key_name(server) == "abc123"


# ---------------------------------------------------------------------------
# get_image: UUID / marketplace label / custom image by name
# ---------------------------------------------------------------------------


@TestScenario
def get_image_uuid_passthrough(self):
    """An image UUID is returned as-is without any API lookup."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with Then("a UUID resolves to itself"):
        uid = "33333333-3333-3333-3333-333333333333"
        assert provider.get_image(uid) == uid


@TestScenario
def get_image_rejects_foreign_specs(self):
    """Hetzner colon-form and AWS ami- specs raise ImageSpecFormatError."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with Then("foreign specs are flagged so scale_up can try another provider"):
        for foreign in ("x86:system:ubuntu-22.04", "ami-0abc123def", "resolve:ssm:/x"):
            try:
                provider.get_image(foreign)
                assert False, f"expected ImageSpecFormatError for {foreign!r}"
            except ImageSpecFormatError:
                pass


@TestScenario
def resolve_image_in_zone_marketplace_label(self):
    """A marketplace label resolves before custom images are consulted."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("marketplace resolution returns an id and custom lookup would fail"):
        provider._resolve_marketplace_image = lambda label, zone: "mkt-" + label

        def _boom(**kwargs):
            raise AssertionError("custom lookup must not run when marketplace matches")

        provider._instance.list_images_all = _boom
    with Then("the marketplace id is returned"):
        assert (
            provider._resolve_image_in_zone("ubuntu_jammy", "fr-par-1")
            == "mkt-ubuntu_jammy"
        )


@TestScenario
def resolve_image_in_zone_custom_dashed_name_skips_marketplace(self):
    """A custom name with '-'/'.' skips the marketplace lookup entirely.

    Reproduces the reported bug: a baked image name like
    'arm-ubuntu-24.04-regression-tester' must not be sent to the marketplace
    endpoint (which 404s), but resolved directly as a custom image.
    """
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("marketplace resolution would fail if called, and a private image exists"):
        def _must_not_call(label, zone):
            raise AssertionError("marketplace must not be queried for a dashed name")

        provider._resolve_marketplace_image = _must_not_call
        provider._instance.list_images_all = lambda **kwargs: [
            _FakeImage(id="img-arm", name="arm-ubuntu-24.04-regression-tester", arch="arm64"),
        ]
    with Then("the custom image id is returned without touching the marketplace"):
        assert (
            provider._resolve_image_in_zone(
                "arm-ubuntu-24.04-regression-tester", "fr-par-1"
            )
            == "img-arm"
        )


@TestScenario
def resolve_image_in_zone_marketplace_shaped_miss_falls_through_to_custom(self):
    """A marketplace-shaped spec that misses (None) falls through to custom images."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("marketplace returns None (unknown label) and a custom image matches"):
        provider._resolve_marketplace_image = lambda label, zone: None
        provider._instance.list_images_all = lambda **kwargs: [
            _FakeImage(id="img-x86", name="ubuntucustom", arch="x86_64"),
        ]
    with Then("the custom image id is returned"):
        assert (
            provider._resolve_image_in_zone("ubuntucustom", "fr-par-1") == "img-x86"
        )


@TestScenario
def resolve_image_in_zone_custom_by_name(self):
    """A custom image name resolves to its private-image UUID, preferring x86_64."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("no marketplace match, and a private image exists in two arches"):
        provider._resolve_marketplace_image = lambda label, zone: None
        provider._instance.list_images_all = lambda **kwargs: [
            _FakeImage(id="img-arm", name="runner-base", arch="arm64"),
            _FakeImage(id="img-x86", name="runner-base", arch="x86_64"),
        ]
    with Then("the x86_64 custom image id is returned"):
        assert provider._resolve_image_in_zone("runner-base", "fr-par-1") == "img-x86"


@TestScenario
def resolve_image_in_zone_custom_name_requires_exact_match(self):
    """A prefix-only name match is rejected (the API name filter is a prefix)."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with And("marketplace misses and only a prefix-match private image exists"):
        provider._resolve_marketplace_image = lambda label, zone: None
        provider._instance.list_images_all = lambda **kwargs: [
            _FakeImage(id="img-1", name="runner-base-2024", arch="x86_64"),
        ]
    with Then("_resolve_image_in_zone raises ImageError (no exact name match)"):
        try:
            provider._resolve_image_in_zone("runner-base", "fr-par-1")
            assert False, "expected ImageError for prefix-only match"
        except ImageError:
            pass


@TestScenario
def get_image_is_format_only(self):
    """get_image returns a Scaleway spec unchanged and makes no SDK call."""
    with Given("a scaleway provider"):
        provider = scaleway_provider()
    with Then("a Scaleway spec passes through untouched"):
        assert provider.get_image("ubuntu_jammy") == "ubuntu_jammy"
        assert provider.get_image("my-custom-image") == "my-custom-image"
    with And("foreign specs raise ImageSpecFormatError for fallthrough"):
        for foreign in ("x86:system:ubuntu-22.04", "ami-0abc123", "resolve:ssm:/x"):
            try:
                provider.get_image(foreign)
                assert False, f"expected reject for {foreign}"
            except ImageSpecFormatError:
                pass
    with And("no image/marketplace SDK call was made"):
        provider._instance.list_images_all.assert_not_called()


@TestScenario
def resolve_image_in_zone_uses_given_zone(self):
    """_resolve_image_in_zone resolves a custom image against the passed zone."""
    with Given("a scaleway provider whose custom-image lookup returns a match"):
        provider = scaleway_provider()
        provider._instance.list_images_all.return_value = [
            SimpleNamespace(id="img-ams", name="runner-base", arch="arm64"),
        ]
    with When("resolving a custom name in nl-ams-1"):
        uuid = provider._resolve_image_in_zone("runner-base", "nl-ams-1")
    with Then("it returns the image id and queried that zone"):
        assert uuid == "img-ams", uuid
        _, kwargs = provider._instance.list_images_all.call_args
        assert kwargs["zone"] == "nl-ams-1", kwargs


@TestScenario
def provider_sdk_calls_match_real_signatures(self):
    """Every provider SDK call binds against the real scaleway SDK signatures.

    The other tests mock the SDK with MagicMocks, which do NOT enforce argument
    signatures — so a missing required kwarg (e.g. list_volumes_all's
    include_deleted) passes the mocks but fails at runtime. This binds the exact
    kwargs the provider passes to the real signatures. Skips when the optional
    scaleway SDK is not installed.
    """
    import inspect

    try:
        from scaleway.instance.v1 import InstanceV1API
        from scaleway.block.v1 import BlockV1API
        from scaleway.marketplace.v2 import MarketplaceV2API
        from scaleway.iam.v1alpha1 import IamV1Alpha1API
    except ImportError:
        return

    calls = [
        (InstanceV1API, "_create_server", dict(zone="z", name="n", commercial_type="t", dynamic_ip_required=True, protected=False, tags=[], project="p", volumes={})),
        # LOCAL boot mode: image= form (no volumes) must also bind to the real signature.
        (InstanceV1API, "_create_server", dict(zone="z", name="n", commercial_type="t", dynamic_ip_required=True, protected=False, tags=[], project="p", image="i")),
        (InstanceV1API, "server_action", dict(server_id="s", zone="z", action="terminate")),
        (InstanceV1API, "_update_server", dict(server_id="s", zone="z", name="n", tags=[])),
        (InstanceV1API, "get_server", dict(server_id="s", zone="z")),
        (InstanceV1API, "get_image", dict(image_id="i", zone="z")),
        (InstanceV1API, "list_servers_all", dict(zone="z", tags=["x"])),
        (InstanceV1API, "list_servers_types", dict(zone="z")),
        (InstanceV1API, "list_images_all", dict(zone="z", name="n", public=False, project="p")),
        (BlockV1API, "create_volume", dict(zone="z", name="n", project_id="p", tags=[], from_snapshot=None)),
        (BlockV1API, "get_snapshot", dict(snapshot_id="s", zone="z")),
        (BlockV1API, "wait_for_volume", dict(volume_id="v", zone="z")),
        (BlockV1API, "delete_volume", dict(volume_id="v", zone="z")),
        (BlockV1API, "list_volumes_all", dict(zone="z", tags=["x"], include_deleted=False)),
        (MarketplaceV2API, "list_local_images_all", dict(image_label="l", zone="z", type_="instance_local")),
        (IamV1Alpha1API, "list_ssh_keys_all", dict(project_id="p")),
        (IamV1Alpha1API, "create_ssh_key", dict(name="n", public_key="k", project_id="p")),
    ]
    with Then("every provider SDK call binds to the real signature"):
        for api, meth, kw in calls:
            sig = inspect.signature(getattr(api, meth))
            # None stands in for self; raises TypeError if a required arg is missing
            sig.bind(None, **kw)


# ---------------------------------------------------------------------------
# Provider zone set
# ---------------------------------------------------------------------------


@TestScenario
def provider_zone_set_filters_and_includes_default(self):
    """zones is filtered to valid Scaleway zones; the default zone is always in."""
    with Given("a scaleway provider given mixed zones (incl. non-Scaleway)"):
        from testflows.github.runners.tests.unit.steps.scaleway import mock_scaleway_sdk
        mock_scaleway_sdk()
        from testflows.github.runners.providers.scaleway.provider import ScalewayCloudProvider
        provider = ScalewayCloudProvider(
            access_key="k", secret_key="11111111-1111-1111-1111-111111111111",
            project_id="22222222-2222-2222-2222-222222222222", zone="fr-par-1",
            zones=["fr-par-2", "nl-ams-1", "nbg1", "us-east-1a"],
        )
    with Then("only Scaleway zones survive and the default is included"):
        assert provider._zones == {"fr-par-1", "fr-par-2", "nl-ams-1"}, provider._zones


@TestScenario
def list_servers_fans_out_across_zones(self):
    """list_servers queries every zone in the set and merges the results."""
    with Given("a provider over two zones, each with one active server"):
        provider = scaleway_provider()
        provider._zones = {"fr-par-1", "nl-ams-1"}
        by_zone = {
            "fr-par-1": [_running_native(name="a")],
            "nl-ams-1": [_running_native(name="b")],
        }
        provider._instance.list_servers_all.side_effect = (
            lambda zone, **k: by_zone.get(zone, [])
        )
    with When("list_servers runs"):
        result = provider.list_servers()
    with Then("servers from both zones are returned"):
        names = sorted(s.name for s in result)
        assert names == ["a", "b"], names


@TestScenario
def list_servers_skips_a_failing_zone(self):
    """One zone erroring must not drop the whole listing — otherwise scale_down
    'forgets' live servers and resets their powered-off retirement grace."""
    with Given("a provider over two zones, one of which errors on list"):
        provider = scaleway_provider()
        provider._zones = {"fr-par-1", "nl-ams-1"}

        def _list(zone, **k):
            if zone == "nl-ams-1":
                raise RuntimeError("zone temporarily unavailable")
            return [_running_native(name="a")]

        provider._instance.list_servers_all.side_effect = _list
    with When("list_servers runs"):
        result = provider.list_servers()
    with Then("the healthy zone's servers are still returned"):
        assert sorted(s.name for s in result) == ["a"], result


@TestScenario
def get_server_type_missing_in_all_zones_raises(self):
    """A type offered in no configured zone raises ServerTypeError."""
    with Given("a provider over two zones that offer no matching type"):
        provider = scaleway_provider()
        provider._zones = {"fr-par-1", "nl-ams-1"}
        provider._instance.list_servers_types.return_value = SimpleNamespace(servers={})
    with Then("get_server_type raises ServerTypeError"):
        try:
            provider.get_server_type("basic2.a16c.32g")
            assert False, "expected ServerTypeError"
        except ServerTypeError:
            pass


@TestScenario
def get_prices_fans_out_across_zones(self):
    """get_prices asks the estimator for every configured zone (sorted)."""
    from unittest.mock import patch

    with Given("a provider over two zones"):
        provider = scaleway_provider()
        provider._zones = {"nl-ams-1", "fr-par-1"}
    with When("get_prices runs"), patch(
        "testflows.github.runners.providers.scaleway.estimate.check_prices",
        return_value={},
    ) as check_prices:
        provider.get_prices()
    with Then("the estimator is queried for all zones, sorted"):
        _, kwargs = check_prices.call_args
        assert kwargs["zones"] == ["fr-par-1", "nl-ams-1"], kwargs


# ---------------------------------------------------------------------------
# update_from_args: CLI overrides reach cfg.providers.scaleway
# ---------------------------------------------------------------------------


@TestScenario
def update_from_args_overrides_each_field(self):
    """Every --scaleway-* flag lands on its matching scaleway_provider field."""
    from testflows.github.runners.providers.scaleway import config as scw_config

    cfg = scaleway_provider_config()
    args = SimpleNamespace(
        scaleway_access_key="SCWK",
        scaleway_secret_key="11111111-1111-1111-1111-111111111111",
        scaleway_project_id="22222222-2222-2222-2222-222222222222",
        scaleway_organization_id="33333333-3333-3333-3333-333333333333",
        scaleway_default_image="ubuntu_jammy",
        scaleway_default_server_type="dev1.m",
        scaleway_default_location="fr-par-1",
        scaleway_default_disk_size=40,
    )
    with When("update_from_args runs"):
        scw_config.update_from_args(cfg, args)
    with Then("every field is overridden"):
        assert cfg.access_key == "SCWK", cfg
        assert cfg.secret_key == "11111111-1111-1111-1111-111111111111", cfg
        assert cfg.project_id == "22222222-2222-2222-2222-222222222222", cfg
        assert cfg.organization_id == "33333333-3333-3333-3333-333333333333", cfg
        assert cfg.defaults.image == "ubuntu_jammy", cfg
        assert cfg.defaults.server_type == "dev1.m", cfg
        assert cfg.defaults.location == "fr-par-1", cfg
        assert cfg.defaults.disk_size == 40, cfg


@TestScenario
def update_from_args_leaves_unset_fields_alone(self):
    """An unset (None) CLI arg must not clobber an already-configured value."""
    from testflows.github.runners.config.config import provider_defaults
    from testflows.github.runners.providers.scaleway import config as scw_config

    cfg = scaleway_provider_config(
        access_key="configured-key",
        secret_key="configured-secret",
        project_id="configured-project",
        organization_id="configured-org",
        defaults=provider_defaults(
            image="ubuntu_configured",
            server_type="dev1.l",
            location="nl-ams-1",
            disk_size=25,
        ),
    )
    with When("update_from_args runs with every arg unset (None)"):
        scw_config.update_from_args(cfg, SimpleNamespace())
    with Then("every configured value survives untouched"):
        assert cfg.access_key == "configured-key", cfg
        assert cfg.secret_key == "configured-secret", cfg
        assert cfg.project_id == "configured-project", cfg
        assert cfg.organization_id == "configured-org", cfg
        assert cfg.defaults.image == "ubuntu_configured", cfg
        assert cfg.defaults.server_type == "dev1.l", cfg
        assert cfg.defaults.location == "nl-ams-1", cfg
        assert cfg.defaults.disk_size == 25, cfg


# ---------------------------------------------------------------------------
# apply_args: create-from-flags-alone path (mirrors Hetzner's)
# ---------------------------------------------------------------------------


@TestScenario
def apply_args_creates_scaleway_provider_from_flags_alone(self):
    """With no providers.scaleway section, all three required credential
    flags create one that provider_factory (from_config) would build."""
    from testflows.github.runners.config.config import apply_args

    cfg = Config(providers=provider_list())
    with When("apply_args runs with all three required Scaleway flags set"):
        apply_args(
            cfg,
            SimpleNamespace(
                scaleway_access_key="SCWK",
                scaleway_secret_key="SCWS",
                scaleway_project_id="proj-1",
            ),
        )
    with Then("a providers.scaleway section is created with those credentials"):
        assert cfg.providers.scaleway is not None, cfg.providers.scaleway
        assert cfg.providers.scaleway.access_key == "SCWK", cfg.providers.scaleway
        assert cfg.providers.scaleway.secret_key == "SCWS", cfg.providers.scaleway
        assert cfg.providers.scaleway.project_id == "proj-1", cfg.providers.scaleway


@TestScenario
def apply_args_does_not_create_scaleway_provider_from_partial_flags(self):
    """Missing project_id must not create a provider — it would never pass
    ScalewayCloudProvider.from_config's guard."""
    from testflows.github.runners.config.config import apply_args

    cfg = Config(providers=provider_list())
    with When("apply_args runs with only access_key and secret_key set"):
        apply_args(
            cfg,
            SimpleNamespace(scaleway_access_key="SCWK", scaleway_secret_key="SCWS"),
        )
    with Then("no providers.scaleway section is created"):
        assert cfg.providers.scaleway is None, cfg.providers.scaleway


# ---------------------------------------------------------------------------
# Feature entry point
# ---------------------------------------------------------------------------


@TestFeature
@Name("scaleway config")
def feature(self):
    """Scaleway type translation, args validation, config parsing, and factory."""
    for scenario in loads(current_module(), Scenario):
        scenario()
