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

        arg_value = getattr(args, attr, None)

        if arg_value is not None:
            setattr(config, attr, arg_value)

    # Update cloud deployment settings
    if getattr(args, "cloud_server_name", None) is not None:
        config.cloud.server_name = args.cloud_server_name

    if getattr(args, "cloud_host", None) is not None:
        config.cloud.host = args.cloud_host

    if getattr(args, "cloud_deploy_location", None) is not None:
        config.cloud.deploy.location = args.cloud_deploy_location

    if getattr(args, "cloud_deploy_server_type", None) is not None:
        config.cloud.deploy.server_type = args.cloud_deploy_server_type

    if getattr(args, "cloud_deploy_image", None) is not None:
        config.cloud.deploy.image = args.cloud_deploy_image

    if getattr(args, "cloud_deploy_setup_script", None) is not None:
        config.cloud.deploy.setup_script = args.cloud_deploy_setup_script
