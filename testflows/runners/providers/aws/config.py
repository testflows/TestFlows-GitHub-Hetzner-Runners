"""AWS provider configuration."""


def is_enabled(provider_config):
    """Check if AWS provider is enabled (has required credentials)."""
    return (
        provider_config
        and provider_config.access_key_id
        and provider_config.secret_access_key
    )


def get_cli_fields():
    """Get list of all CLI field names for AWS provider."""
    return [
        "access_key_id",
        "secret_access_key",
        "security_group",
        "subnet",
        "key_name",
        "default_image",
        "default_server_type",
        "default_location",
        "default_volume_size",
        "default_volume_location",
        "default_volume_type",
    ]


def has_cli_args(args):
    """Check if any AWS CLI arguments are provided."""
    return any(
        getattr(args, f"aws_{field}", None) is not None for field in get_cli_fields()
    )


def update_from_args(provider_config, args):
    """Update AWS provider configuration from CLI arguments."""
    if not provider_config:
        return

    # Update credentials
    if getattr(args, "aws_access_key_id", None) is not None:
        provider_config.access_key_id = args.aws_access_key_id
    if getattr(args, "aws_secret_access_key", None) is not None:
        provider_config.secret_access_key = args.aws_secret_access_key
    if getattr(args, "aws_security_group", None) is not None:
        provider_config.security_group = args.aws_security_group
    if getattr(args, "aws_subnet", None) is not None:
        provider_config.subnet = args.aws_subnet
    if getattr(args, "aws_key_name", None) is not None:
        provider_config.key_name = args.aws_key_name

    # Update defaults
    if getattr(args, "aws_default_image", None) is not None:
        provider_config.defaults.image = args.aws_default_image
    if getattr(args, "aws_default_server_type", None) is not None:
        provider_config.defaults.server_type = args.aws_default_server_type
    if getattr(args, "aws_default_location", None) is not None:
        provider_config.defaults.location = args.aws_default_location
    if getattr(args, "aws_default_volume_size", None) is not None:
        provider_config.defaults.volume_size = args.aws_default_volume_size
    if getattr(args, "aws_default_volume_location", None) is not None:
        provider_config.defaults.volume_location = args.aws_default_volume_location
    if getattr(args, "aws_default_volume_type", None) is not None:
        provider_config.defaults.volume_type = args.aws_default_volume_type
