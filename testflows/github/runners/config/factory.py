"""Provider factory: construct CloudProvider instances from Config."""

from .config import Config
from ..cloud_provider import CloudProvider
from ..errors import ConfigError
from ..providers.hetzner.provider import HetznerCloudProvider
from ..providers.scaleway.provider import ScalewayCloudProvider
from ..providers.aws.provider import AWSCloudProvider
from ..providers.dedicated_static.provider import DedicatedStaticCloudProvider

# The single per-provider seam. A future auto-discovery step replaces this list.
PROVIDER_REGISTRY: list[type[CloudProvider]] = sorted(
    [HetznerCloudProvider, ScalewayCloudProvider, AWSCloudProvider,
     DedicatedStaticCloudProvider],
    key=lambda c: c.precedence,
)


def provider_factory(config: Config) -> list[CloudProvider]:
    """Construct every configured provider, in precedence order.

    If ``config.enabled_providers`` (--provider) is set, the registry is
    narrowed to those classes *before* ``from_config`` runs -- an excluded
    provider is never constructed. Provider construction is not free or safe
    to attempt unconditionally (e.g. AWSCloudProvider.__init__ imports boto3
    and opens a client), so a provider the user explicitly excluded must not
    be touched at all, not built and then discarded.

    The check for a requested-but-missing provider happens after building
    the (narrowed) set, so it catches both "no providers.<name> section" and
    "a section exists but from_config rejected it" (e.g. missing
    credentials) with one error -- both mean the user will not get a
    provider they asked for.
    """
    registry = PROVIDER_REGISTRY
    if config.enabled_providers is not None:
        registry = [cls for cls in registry if cls.config_key in config.enabled_providers]

    built = [p for cls in registry if (p := cls.from_config(config)) is not None]

    if config.enabled_providers is None:
        return built

    built_names = {p.name for p in built}
    missing = [name for name in config.enabled_providers if name not in built_names]
    if missing:
        raise ConfigError(
            f"--provider requested {', '.join(missing)}, but "
            f"{'it has' if len(missing) == 1 else 'they have'} no providers.<name> "
            "section, or the section is missing required credentials; only "
            f"{', '.join(sorted(built_names)) or 'no providers'} were built. "
            "Add or complete the matching providers.<name> section in the config "
            "file, or remove it from --provider."
        )

    return built
