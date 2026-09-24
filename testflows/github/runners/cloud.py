# Copyright 2023 Katteli Inc.
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
import os
import tempfile
import webbrowser
import time

from .actions import Action
from .config import Config, write as write_config, read as read_config
from .config.factory import provider_factory
from .cloud_provider import CloudProvider, ProviderServer
from . import __version__

from .server import wait_ssh, ssh, scp, ip_address, ssh_tunnel
from .servers import ssh_client as server_ssh_client
from .servers import ssh_client_command as server_ssh_client_command
from .service import command_options, check_no_provider_flags

current_dir = os.path.dirname(__file__)
deploy_scripts_folder = "/home/ubuntu/.tfs-runners/scripts/"
deploy_configs_folder = "/home/ubuntu/.tfs-runners/"

# The service is installed into a virtualenv (Ubuntu 24.04 blocks system-wide
# pip); setup.sh creates it.
deploy_venv = "/home/ubuntu/.tfs-runners/venv"
deploy_pip = f"{deploy_venv}/bin/pip"
deploy_tfs_runners = f"{deploy_venv}/bin/tfs-github-runners"

# The deployed controller service runs as this Linux user (created by setup.sh on
# images that don't already have it) and its home holds the deploy folders above.
service_user = "ubuntu"

# Labels for the controller host itself. It is found by name for
# redeploy/delete, so it needs no discovery label — and must not have one, or the
# controller running on it would reap it as a zombie runner (self-delete).
controller_host_labels = {"tfs-github-runners-role": "controller"}


def pip_install_args(version: str, redeploy: bool) -> tuple[str, str]:
    """Return ``(pip flags, requirement)`` for ``deploy --version``.

    Accepts ``latest``, a PyPI pin, or a full pip spec. Ref redeploys use
    ``--force-reinstall --no-deps`` — the ref moves but the dev version does not.
    """
    v = version.strip()
    is_latest = v.lower() == "latest"
    is_spec = (
        "git+" in v
        or "://" in v
        or " @ " in v
        or v.endswith((".whl", ".tar.gz"))
        or v.startswith(("/", ".", "~"))
    )

    if is_spec and " " in v:
        # Spaces word-split over ssh/su; use a bare git URL.
        raise ValueError(
            f"deploy version spec must be a single token with no spaces: {v!r}. "
            f"Use the bare git URL, e.g. git+https://github.com/owner/repo@branch"
        )

    if is_latest:
        requirement = "testflows.github.runners"
    elif is_spec:
        requirement = v
    else:
        requirement = f"testflows.github.runners=={v}"

    flags = ""
    if redeploy and is_latest:
        flags = "--upgrade"
    elif redeploy and is_spec:
        flags = "--force-reinstall --no-deps"
    return flags, requirement


def deploy_provider(config: Config) -> CloudProvider:
    """Resolve the CloudProvider that hosts the controller for cloud deploy.

    Selected by ``config.cloud.provider`` (default 'hetzner'). All provisioning
    (create/get/delete server, image/location/type/ssh-key resolution) routes
    through this provider's CloudProvider interface, so cloud deploy is not tied
    to any one cloud.
    """
    name = getattr(config.cloud, "provider", None) or "hetzner"
    for provider in provider_factory(config):
        if provider.name == name:
            return provider
    raise ValueError(
        f"cloud.provider {name!r} is not configured; add its credentials under "
        f"providers.{name} (or set config.cloud.provider)"
    )


def _optional_provider_ssh_user(config: Config) -> str:
    """The configured cloud.provider's ssh_user, or None if it isn't configured.

    Direct --host connections shouldn't require a provider, but when one is
    configured we still honor its ssh_user for backward compatibility.
    """
    try:
        return deploy_provider(config).ssh_user
    except ValueError:
        return None


def as_service_user(server: ProviderServer, inner: str) -> str:
    """Wrap a command so it runs as the service user (``ubuntu``).

    When we already log in as that user (e.g. AWS Ubuntu AMIs) run it directly
    to avoid a ``su`` self-switch; otherwise (root login, e.g. Hetzner) drop into
    the service user. Returns a shell-quoted argument for ``ssh``.
    """
    if server.ssh_user == service_user:
        return f"'{inner}'"
    return f"\"su - {service_user} -c '{inner}'\""


def sudo_if_needed(server: ProviderServer, cmd: str) -> str:
    """Prefix ``sudo`` when the login user is not root (e.g. AWS 'ubuntu')."""
    return cmd if server.ssh_user == "root" else f"sudo {cmd}"


def get_server(config: Config, provider: CloudProvider = None) -> ProviderServer:
    """Get the deploy host as a ProviderServer, from a direct host or the provider API.

    Args:
        config: Configuration object.
        provider: Deploy provider (resolved from config.cloud.provider if omitted).

    Returns:
        A ProviderServer for the deploy host.

    Raises:
        ValueError: If the server is not found via the provider API.
    """
    server_name = config.cloud.server_name
    server_host = config.cloud.host

    if server_host:
        # Direct host needs no provider (no provisioning). Login user: explicit
        # config.cloud.ssh_user, else the given/configured provider's ssh_user,
        # else None so ssh resolves it (e.g. from ~/.ssh/config for an alias).
        ssh_user = config.cloud.ssh_user
        if ssh_user is None:
            ssh_user = (
                provider.ssh_user
                if provider is not None
                else _optional_provider_ssh_user(config)
            )
        return ProviderServer(
            id=server_name,
            name=server_name,
            status=CloudProvider.STATUS_RUNNING,
            public_ipv4=server_host,
            private_ipv4=None,
            labels={},
            server_type="",
            location="",
            created=None,
            ssh_user=ssh_user,
        )

    if provider is None:
        provider = deploy_provider(config)

    with Action(f"Getting server {server_name}"):
        server = provider.get_server(server_name)
        if not server:
            raise ValueError(f"server {server_name} not found")
        return server


def deploy(args, config: Config, redeploy=False):
    """Deploy or redeploy tfs-github-runners as a service to a cloud server instance."""
    # Check before provisioning: install() at the end of this function checks
    # too, but only after a server would already have been created and set up.
    check_no_provider_flags(args)

    version = args.version or __version__
    server_name = config.cloud.server_name
    provider = deploy_provider(config)

    with Action(f"Checking if SSH key exists ({provider.name})"):
        ssh_keys = [provider.get_or_create_ssh_key(config.ssh_key, is_file=True)]
        if config.additional_ssh_keys:
            for key in config.additional_ssh_keys:
                ssh_keys.append(provider.get_or_create_ssh_key(key, is_file=False))

    if redeploy:
        with Action(f"Getting server {server_name}"):
            server = provider.get_server(server_name)
            if not server:
                raise ValueError(f"server {server_name} not found")

        uninstall(args=args, config=config, server=server)

        with Action("Cleaning copied scripts"):
            ssh(server, f"rm -rf {deploy_scripts_folder}*", stacklevel=4)

        with Action("Cleaning copied configs"):
            ssh(server, f"rm -rf {deploy_configs_folder}*.yaml", stacklevel=4)

    else:
        deploy_setup_script = config.cloud.deploy.setup_script or os.path.join(
            current_dir, "scripts", "deploy", "setup.sh"
        )

        if args.force:
            with Action(
                f"Checking if server {server_name} already exists", ignore_fail=True
            ):
                server = provider.get_server(server_name)
                if server is not None:
                    with Action(f"Deleting server {server_name}"):
                        provider.delete_server(server)

        # Resolve the deploy host's image/type/location through the provider.
        # Each provider's get_* accepts its own spec form (Hetzner also accepts
        # its native objects); fall back to the provider's own defaults when the
        # cloud.deploy.* fields are unset (e.g. a non-Hetzner deploy).
        with Action(f"Resolving deploy server spec ({provider.name})"):
            if not config.cloud.deploy.server_type:
                raise ValueError(
                    f"cloud.deploy.server_type is required for provider "
                    f"{provider.name!r}"
                )
            image = provider.get_image(
                config.cloud.deploy.image or provider.default_image
            )
            server_type = provider.get_server_type(config.cloud.deploy.server_type)
            location = provider.get_location(
                config.cloud.deploy.location or provider.default_location
            )

        with Action(f"Creating new server ({provider.name})"):
            # create_server blocks until the instance is running and returns a
            # ProviderServer with its public IP + ssh_user, so no separate
            # wait-for-ready is needed (only wait-for-SSH below).
            server = provider.create_server(
                name=server_name,
                server_type=server_type,
                location=location,
                image=image,
                ssh_keys=ssh_keys,
                # The controller host is NOT a runner. It must not carry the
                # runner discovery label: the controller runs the same config, so
                # its own runtime scan would find this host under its own id, see
                # no registered runner, and reap it as a zombie (self-delete).
                labels=controller_host_labels,
            )

        with Action("Wait for SSH connection to be ready"):
            wait_ssh(server=server, timeout=config.max_server_ready_time)

        with Action("Executing setup.sh script"):
            # setup.sh needs root (apt-get, adduser, sudoers); sudo when the login
            # user isn't root (e.g. AWS 'ubuntu'). The `< file` redirection is local
            # (pipes the script into ssh stdin), so it stays outside the remote cmd.
            ssh(
                server,
                f"{sudo_if_needed(server, 'bash -s')}  < {deploy_setup_script}",
                stacklevel=4,
            )

    with Action(f"Installing tfs-github-runners {version}"):
        flags, requirement = pip_install_args(version, redeploy)
        pip_cmd = f"{deploy_pip} install {flags}".rstrip()
        ssh(server, as_service_user(server, f"{pip_cmd} {requirement}"), stacklevel=4)

    with Action("Copying any custom scripts"):
        ip = ip_address(server)

        if config.scripts:
            with Action(f"Copying custom scripts {config.scripts}"):
                scp(
                    source=os.path.join(config.scripts, "*.sh"),
                    destination=f"{server.ssh_user}@{ip}:{deploy_scripts_folder}.",
                    server=server,
                )
                config.scripts = deploy_scripts_folder

    with Action("Fixing ownership of any copied scripts"):
        ssh(
            server,
            sudo_if_needed(
                server, f"chown -R {service_user}:{service_user} {deploy_scripts_folder}"
            ),
            stacklevel=4,
        )
        ssh(
            server,
            f'"find {deploy_scripts_folder} -type f -exec chmod +rx {{}} \;"',
            stacklevel=4,
        )

    with Action(
        f"Copying config file{(' ' + config.config_file) if config.config_file else ''}"
    ):
        with tempfile.NamedTemporaryFile("w") as file:
            with Action(
                f"{'Modifying' if config.config_file else 'Creating'} "
                "config file and adding this SSH key to the SSH keys list"
            ):
                raw_config = {"config": {}}
                if config.config_file:
                    raw_config = read_config(config.config_file)
                additional_ssh_keys = raw_config["config"].get(
                    "additional_ssh_keys", []
                )
                # Read the deploy public key material from the local key file
                # (provider key objects don't uniformly expose it — AWS key pairs
                # carry only a name), so the deployed controller trusts this key.
                with open(config.ssh_key, "r", encoding="utf-8") as key_file:
                    additional_ssh_keys.append(key_file.read().strip())
                raw_config["config"]["additional_ssh_keys"] = list(
                    set(additional_ssh_keys)
                )
                write_config(file, raw_config)
                file.flush()
            scp(
                source=file.name,
                destination=f"{server.ssh_user}@{ip}:{deploy_configs_folder}config.yaml",
                server=server,
            )
            config.config_file = os.path.join(
                deploy_configs_folder,
                "config.yaml",
            )

    with Action("Fixing ownership of any copied configs"):
        ssh(
            server,
            sudo_if_needed(
                server, f"chown -R {service_user}:{service_user} {deploy_configs_folder}"
            ),
            stacklevel=4,
        )

    install(args, config=config, server=server)


def redeploy(args, config: Config):
    """Redeploy service on a existing cloud instance."""
    deploy(args=args, config=config, redeploy=True)


def install(args, config: Config, server: ProviderServer = None):
    """Install service on a cloud instance."""
    # This runs `service install -f` on the remote host over ssh, built from
    # command_options() (no provider flags) plus the config file copied to
    # the remote — never from these local CLI args — so a provider flag given
    # here would reach neither and must be refused just like service install.
    check_no_provider_flags(args)

    if server is None:
        server = get_server(config)

    with Action("Installing service"):
        inner = (
            deploy_tfs_runners
            + command_options(
                config,
                github_token=config.github_token,
                github_repository=config.github_repository,
            )
            + " service install -f"
        )
        ssh(server, as_service_user(server, inner))


def upgrade(args, config: Config, server: ProviderServer = None):
    """Upgrade tfs-github-runners application on a cloud instance."""
    if server is None:
        server = get_server(config)

    upgrade_version = args.upgrade_version

    stop(args, config=config, server=server)

    if upgrade_version:
        with Action(f"Upgrading tfs-github-runners to version {upgrade_version}"):
            ssh(
                server,
                as_service_user(
                    server, f"{deploy_pip} install testflows.github.runners=={upgrade_version}"
                ),
                stacklevel=4,
            )
    else:
        with Action(f"Upgrading tfs-github-runners the latest version"):
            ssh(
                server,
                as_service_user(server, f"{deploy_pip} install --upgrade testflows.github.runners"),
                stacklevel=4,
            )

    start(args, config=config, server=server)


def uninstall(args, config: Config, server: ProviderServer = None):
    """Uninstall tfs-github-runners service from a cloud instance."""
    if server is None:
        server = get_server(config)

    with Action("Uninstalling service"):
        ssh(
            server,
            as_service_user(server, f"{deploy_tfs_runners} service uninstall"),
            stacklevel=4,
        )


def delete(args, config: Config, server: ProviderServer = None):
    """Delete the tfs-github-runners service host: uninstall the service then delete the
    cloud server."""
    provider = deploy_provider(config)
    if server is None:
        server = get_server(config, provider)

    with Action("Uninstalling service", ignore_fail=True):
        ssh(
            server,
            as_service_user(server, f"{deploy_tfs_runners} service uninstall"),
            stacklevel=4,
        )

    with Action(f"Deleting server {server.name}"):
        provider.delete_server(server)


def log(args, config: Config, server: ProviderServer = None):
    """Get cloud server service log."""
    if server is None:
        server = get_server(config)

    inner = (
        f"{deploy_tfs_runners} service log"
        + (" -f" if args.follow else "")
        + (f" -c {args.columns.value}" if args.columns else "")
        + (f" -n {args.lines}" if args.lines else "")
        + (" --raw" if args.raw else "")
    )
    ssh(server, as_service_user(server, inner), use_logger=False, stacklevel=4)


def download_log(args, config: Config, server: ProviderServer = None):
    """Download cloud server service log."""
    if server is None:
        server = get_server(config)

    ip = ip_address(server)
    host = f"{server.ssh_user}@{ip}" if server.ssh_user else f"{ip}"
    with Action(f"Downloading log from {server.name} to {args.output}"):
        scp(
            source=f"{host}:{os.path.join(tempfile.gettempdir(), 'tfs-github-runners.log')}",
            destination=args.output,
            server=server,
        )


def delete_log(args, config: Config, server: ProviderServer = None):
    """Delete cloud server service log."""
    if server is None:
        server = get_server(config)

    ssh(
        server,
        as_service_user(server, f"{deploy_tfs_runners} service log delete"),
        use_logger=False,
        stacklevel=4,
    )


def status(args, config: Config, server: ProviderServer = None):
    """Get cloud server service status."""
    if server is None:
        server = get_server(config)

    with Action("Getting status"):
        ssh(server, as_service_user(server, f"{deploy_tfs_runners} service status"), stacklevel=4)


def start(args, config: Config, server: ProviderServer = None):
    """Start cloud server service."""
    if server is None:
        server = get_server(config)

    with Action("Starting service"):
        ssh(server, as_service_user(server, f"{deploy_tfs_runners} service start"), stacklevel=4)


def stop(args, config: Config, server: ProviderServer = None):
    """Stop cloud server service."""
    if server is None:
        server = get_server(config)

    with Action("Stopping service"):
        ssh(server, as_service_user(server, f"{deploy_tfs_runners} service stop"), stacklevel=4)


def ssh_client(args, config: Config, server: ProviderServer = None):
    """Open ssh client to tfs-github-runners service running
    on Hetzner server instance.
    """
    if server is None:
        server = get_server(config)

    server_ssh_client(args=args, config=config, server_name=server.name, server=server)


def ssh_client_command(args, config: Config, server: ProviderServer = None):
    """Return ssh command to connect to tfs-github-runners service running
    on Hetzner server instance.
    """
    if server is None:
        server = get_server(config)

    server_ssh_client_command(
        args=args, config=config, server_name=server.name, server=server
    )


def cloud_dashboard(args, config: Config, server: ProviderServer = None):
    """Open dashboard through SSH tunnel to cloud service."""
    local_port = args.local_port
    remote_port = args.remote_port if args.remote_port else config.dashboard_port
    timeout = args.timeout if args.timeout else 30.0

    if server is None:
        server = get_server(config)

    with Action(f"Creating SSH tunnel on port {local_port}") as action:
        with ssh_tunnel(
            server=server,
            local_port=local_port,
            remote_port=remote_port,
            action=action,
        ) as tunnel:
            if not tunnel.wait_ready(timeout=timeout):
                raise TimeoutError(
                    f"Failed to establish SSH tunnel from {server.name}:{remote_port} to local port {local_port}"
                )

            with Action("Opening dashboard in browser"):
                time.sleep(1)
                webbrowser.open(f"http://localhost:{local_port}", 1)
                action.note("Press Ctrl+C to exit and close the tunnel")
                try:
                    while True:
                        time.sleep(10)
                except KeyboardInterrupt:
                    pass
