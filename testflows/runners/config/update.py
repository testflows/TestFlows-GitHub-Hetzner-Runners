from .config import Config


def update(config: Config, args):
    """Update configuration file using command line arguments."""
    for attr in vars(config):
        if attr in [
            "config_file",
            "logger_config",
            "logger_format",
            "cloud",
            "standby_runners",
            "additional_ssh_keys",
            "server_prices",
            "providers",  # Skip providers, handled separately
        ]:
            continue

        arg_value = getattr(args, attr)

        if arg_value is not None:
            setattr(config, attr, arg_value)

    # Update provider-specific settings
    update_provider_settings(config, args)


def update_provider_settings(config, args):
    """Update provider-specific settings from CLI arguments."""
    raise NotImplementedError("update_provider_settings is not implemented")
    # Create provider instances if they don't exist but have CLI args
    if not self.providers.hetzner and hetzner.config.has_cli_args(args):
        self.providers.hetzner = hetzner_provider()
    if not self.providers.aws and aws.config.has_cli_args(args):
        self.providers.aws = aws_provider()
    if not self.providers.azure and azure.config.has_cli_args(args):
        self.providers.azure = azure_provider()
    if not self.providers.gcp and gcp.config.has_cli_args(args):
        self.providers.gcp = gcp_provider()
    if not self.providers.scaleway and scaleway.config.has_cli_args(args):
        self.providers.scaleway = scaleway_provider()

    # Update each provider using their config modules
    hetzner.config.update_from_args(self.providers.hetzner, args)
    aws.config.update_from_args(self.providers.aws, args)
    azure.config.update_from_args(self.providers.azure, args)
    gcp.config.update_from_args(self.providers.gcp, args)
    scaleway.config.update_from_args(self.providers.scaleway, args)

    # Update cloud deployment settings
    if getattr(args, "cloud_server_name", None) is not None:
        self.cloud.server_name = args.cloud_server_name

    if getattr(args, "cloud_host", None) is not None:
        self.cloud.host = args.cloud_host

    if getattr(args, "cloud_deploy_location", None) is not None:
        self.cloud.deploy.location = args.cloud_deploy_location

    if getattr(args, "cloud_deploy_server_type", None) is not None:
        self.cloud.deploy.server_type = args.cloud_deploy_server_type

    if getattr(args, "cloud_deploy_image", None) is not None:
        self.cloud.deploy.image = args.cloud_deploy_image

    if getattr(args, "cloud_deploy_setup_script", None) is not None:
        self.cloud.deploy.setup_script = args.cloud_deploy_setup_script
