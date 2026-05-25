"""Provider factory: construct CloudProvider instances from Config."""

import dataclasses
import logging

from .config import Config, hetzner_provider as HetznerProviderConfig, aws_provider as AWSProviderConfig
from ..cloud_provider import CloudProvider

logger = logging.getLogger("testflows.runners")


def provider_factory(config: Config) -> list[CloudProvider]:
    """Construct and return all configured CloudProvider instances.

    Handles the backwards-compatible ``hetzner_token`` flat field: if it is
    set and no ``providers.hetzner.token`` has been supplied, the token is
    synced into ``config.providers.hetzner`` with a deprecation warning.

    Args:
        config: Populated Config object.

    Returns:
        List of CloudProvider instances in configuration order.
    """
    from ..providers.hetzner.provider import HetznerCloudProvider

    # Backwards compat: hetzner_token → providers.hetzner.token
    # Only auto-wire if the user has not configured any provider via the new
    # providers block. If they have (e.g. providers.aws), the env var
    # HETZNER_TOKEN is ambient noise and should not silently create a provider.
    if config.hetzner_token:
        if config.providers.hetzner is None or not config.providers.hetzner.token:
            has_explicit_provider = config.providers.aws is not None and bool(
                config.providers.aws.access_key_id
            )
            if not has_explicit_provider:
                logger.warning(
                    "hetzner_token is deprecated; use providers.hetzner.token instead"
                )
                if config.providers.hetzner is None:
                    config.providers.hetzner = HetznerProviderConfig(
                        token=config.hetzner_token
                    )
                else:
                    config.providers.hetzner = dataclasses.replace(
                        config.providers.hetzner, token=config.hetzner_token
                    )

    providers: list[CloudProvider] = []

    if config.providers.hetzner and config.providers.hetzner.token:
        providers.append(
            HetznerCloudProvider(
                token=config.providers.hetzner.token,
                ssh_key_path=config.ssh_key,
                max_runners=config.providers.hetzner.max_runners,
                end_of_life=config.providers.hetzner.end_of_life,
            )
        )

    aws_cfg = config.providers.aws
    if aws_cfg and aws_cfg.access_key_id and aws_cfg.secret_access_key:
        from ..providers.aws.provider import AWSCloudProvider, _az_to_region

        location = aws_cfg.defaults.location or "us-east-1a"
        region = _az_to_region(location)
        providers.append(
            AWSCloudProvider(
                access_key_id=aws_cfg.access_key_id,
                secret_access_key=aws_cfg.secret_access_key,
                region=region,
                security_group=aws_cfg.security_group,
                subnets=aws_cfg.subnets,
                default_image_spec=aws_cfg.defaults.image,
                default_location_spec=aws_cfg.defaults.location,
                ssh_user=aws_cfg.ssh_user,
                root_volume_size=aws_cfg.defaults.volume_size,
                root_volume_type=aws_cfg.defaults.volume_type,
                max_runners=aws_cfg.max_runners,
                end_of_life=aws_cfg.end_of_life,
            )
        )

    return providers
