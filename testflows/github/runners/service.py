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
import sys
import textwrap

NAME = "tfs-github-runners"
SERVICE = f"/etc/systemd/system/{NAME}.service"

from .actions import Action
from .logger import decode_message
from .config import config_vars


# Provider CLI flags share a "<provider>_" argparse-dest prefix, one per
# providers/*/args.py module (--aws-access-key-id -> aws_access_key_id, etc).
# Matching on the prefix covers a flag added to a provider later without
# touching this code. No other flag in this parser shares these prefixes (the
# `projects add/update` subcommands have their own separate --hetzner-token,
# on a different args namespace that never reaches here).
PROVIDER_ARG_PREFIXES = ("hetzner_", "aws_", "scaleway_")


def cli_provider_flags(args):
    """Provider-setting flags actually supplied on the command line.

    Returns {"--dashed-flag-name": value}, empty if none were passed. --provider
    (dest enabled_providers) is not a provider setting in this sense: it is
    already written into the unit by command_options() and must keep working.
    """
    flags = {}
    for dest, value in vars(args).items():
        if value is None:
            continue
        if not dest.startswith(PROVIDER_ARG_PREFIXES):
            continue
        flags["--" + dest.replace("_", "-")] = value
    return flags


def check_no_provider_flags(args):
    """Refuse to proceed when provider settings were passed as CLI flags.

    ExecStart is visible to anyone on the host (`ps`, `systemctl status`), so
    command_options() deliberately never writes provider credentials into the
    unit — the service reads them from --config instead. A provider flag given
    here would silently vanish from the installed unit, and if it was the only
    source of that provider's configuration, the service would start with no
    provider configured and exit; systemd gives up after a few quick restarts
    and leaves the unit failed.
    """
    flags = cli_provider_flags(args)
    if not flags:
        return
    # Each flag's provider is its own dashed-name prefix (--aws-... -> aws),
    # so this names the real config section for each one involved.
    providers = sorted({flag[2:].split("-", 1)[0] for flag in flags})
    sections = ", ".join(f"providers.{p}" for p in providers)
    raise ValueError(
        "provider settings were passed as command-line flags: "
        f"{', '.join(sorted(flags))}. "
        "ExecStart is visible to anyone on the host (via 'ps' or 'systemctl "
        "status'), so credentials must not go there. "
        "The installed service reads provider settings only from its config "
        "file, so these would be dropped and the service could start with no "
        f"provider. Put them under {sections} in the --config file, then retry."
    )


def command_options(
    config,
    github_token="$GITHUB_TOKEN",
    github_repository="$GITHUB_REPOSITORY",
):
    """Build service install command options not including:

    --github-token
    --github-repository
    --ssh-key

    Provider credentials come from ``--config``. Re-emit --provider:
    it is CLI-only, so without it the unit would run every configured provider.
    """
    command = ""
    command += f" --github-token {github_token}"
    command += f" --github-repository {github_repository}"
    command += f" --config {config.config_file}" if config.config_file else ""
    if config.enabled_providers:
        command += f" --provider \"{','.join(config.enabled_providers)}\""
    command += f" --recycle " + ("on" if config.recycle else "off")
    command += f" --end-of-life {config.end_of_life}" if config.end_of_life else ""
    for l in config.with_label:
        command += f' --with-label "{l}"' if l else ""
    for k in config.meta_label:
        command += (
            f" --meta-label \"{k}\" \"{','.join(config.meta_label[k])}\""
            if config.meta_label[k]
            else ""
        )
    command += f" --workers {config.workers}"
    command += f" --max-runners {config.max_runners}" if config.max_runners else ""
    command += (
        f" --max-runners-in-workflow-run {config.max_runners_in_workflow_run}"
        if config.max_runners_in_workflow_run
        else ""
    )
    command += f" --scripts {config.scripts}" if config.scripts else ""
    command += (
        f" --max-powered-off-time {config.max_powered_off_time}"
        f" --max-unused-runner-time {config.max_unused_runner_time}"
        f" --max-runner-registration-time {config.max_runner_registration_time}"
        f" --max-server-ready-time {config.max_server_ready_time}"
        f" --scale-up-interval {config.scale_up_interval}"
        f" --scale-down-interval {config.scale_down_interval}"
    )
    command += f" --debug" if config.debug else ""

    return command


def install(args, config):
    """Install service."""
    check_no_provider_flags(args)
    config.check()
    force = args.force

    with Action("Checking if service is already installed"):
        if os.path.exists(SERVICE):
            if not force:
                raise ValueError("service has already been installed")
            with Action("Stopping service"):
                os.system(f"sudo service {NAME} stop")

    with Action(f"Deleting old rotating log files"):
        os.system(
            f"rm -rf {config.logger_config['handlers']['rotating_logfile']['filename']}*"
        )

    with Action(f"Installing {SERVICE}"):
        # Run under this process's interpreter — the deploy invokes the venv's
        # tfs-github-runners, so sys.executable is the venv python and the unit picks
        # up the venv's package.
        tfs_runners = os.path.join(os.path.dirname(sys.executable), "tfs-github-runners")
        binary = f"{sys.executable} {tfs_runners} --service-mode"
        contents = (
            "[Unit]\n"
            "Description=Autoscaling GitHub Actions Runners\n"
            "After=multi-user.target\n"
            "[Service]\n"
            f"User={os.getuid()}\n"
            f"Group={os.getgid()}\n"
            "Type=simple\n"
            "Restart=always\n"
            "KillSignal=SIGINT\n"
            "TimeoutStopSec=90\n"
            f"Environment=GITHUB_TOKEN={config.github_token}\n"
            f"Environment=GITHUB_REPOSITORY={config.github_repository}\n"
        )
        # Provider credentials (Hetzner, AWS, Scaleway, ...) reach the service via
        # the config file's ${ENV} references; bake them from config_vars like any
        # other environment variable used in the config.
        for var, value in config_vars.items():
            if var in ["GITHUB_TOKEN", "GITHUB_REPOSITORY"]:
                continue
            contents += f"Environment={var}={value}\n"

        contents += f"ExecStart={binary}"
        contents += f" --ssh-key {config.ssh_key}"
        contents += command_options(config)
        contents += "\n" "[Install]\n" "WantedBy=multi-user.target\n"

        os.system(f"sudo bash -c \"cat > {SERVICE}\" <<'EOF'\n{contents}\nEOF")
        os.system(f"sudo chmod 700 {SERVICE}")

    with Action("Reloading systemd"):
        os.system("sudo systemctl daemon-reload")

    with Action("Enabling service"):
        os.system(f"sudo systemctl enable {NAME}.service")

    with Action("Starting service"):
        os.system(f"sudo service {NAME} start")


def uninstall(args, config=None):
    """Uninstall service."""
    with Action("Stopping service"):
        os.system(f"sudo service {NAME} stop")

    with Action("Disabling service"):
        os.system(f"sudo systemctl disable {NAME}.service")

    with Action(f"Removing {SERVICE}"):
        os.system(f"sudo rm -f {SERVICE}")

    with Action("Reloading systemd"):
        os.system("sudo systemctl daemon-reload")


def log(args, config=None):
    """Get service log."""
    logger_columns = config.logger_format["columns"]
    format = ""
    if not args.raw:
        # Venv-local path; bare name is not on PATH under systemd/su.
        tfs_runners = os.path.join(
            os.path.dirname(sys.executable), "tfs-github-runners"
        )
        format = f" | {tfs_runners} --embedded-mode"
        if config.debug:
            format += " --debug"
        if config.config_file:
            format += f" -c {config.config_file}"
        format += " service log"
        if args.columns:
            format += f" --columns"
            columns = []
            for c in args.columns:
                assert (
                    c["column"] in logger_columns
                ), f"column {c['column']} is not valid"
                columns.append(
                    f"{c['column']}" + (f":{c['width']}" if c.get("width") else "")
                )
            format += f" {','.join(columns)}"
        format += " format -"

    rotating_logfile = config.logger_config["handlers"]["rotating_logfile"]["filename"]

    if args.follow:
        lines = "10" if not args.lines else args.lines
        os.system(f'bash -c "tail -n {lines} -f {rotating_logfile} | tee{format}"')
    else:
        lines = "+0" if not args.lines else args.lines
        os.system(
            f'bash -c "ls -tr {rotating_logfile}* | xargs tail -n {lines}{format}"'
        )


def delete_log(args, config=None):
    """Delete log."""
    with Action(f"Deleting log files"):
        os.system(
            f"rm -rf {config.logger_config['handlers']['rotating_logfile']['filename']}*"
        )


def format_log(args, config=None):
    """Format raw log."""
    columns = config.logger_format["columns"]
    delimiter = config.logger_format["delimiter"]
    default = args.columns or config.logger_format["default"]

    class Wrapper(textwrap.TextWrapper):
        """Custom wrapper that preserves new lines."""

        def wrap(self, text):
            split_text = text.split("\n")
            lines = [
                line
                for para in split_text
                for line in textwrap.TextWrapper.wrap(self, para)
            ]
            return lines

    for c in default:
        assert c["column"] in columns, f"{c['column']} is not valid"

    # name, index, width
    selected = [
        (
            c["column"],
            columns[c["column"]][0],
            (columns[c["column"]][1] if c.get("width") is None else c.get("width")),
        )
        for c in default
    ]

    while True:
        line = args.input.readline()
        if not line:
            break

        columns = line.split(delimiter, len(columns) - 1)
        for i, c in enumerate(columns):
            columns[i] = decode_message(c)

        wrapped = [
            (width, Wrapper(width).wrap(columns[index])) for _, index, width in selected
        ]
        max_lines = max(len(lines) for width, lines in wrapped)
        for m in range(max_lines):
            for width, c in wrapped:
                v = ""
                if m < len(c):
                    v = c[m]
                sys.stdout.write(f"{v:<{width}} ")
            sys.stdout.write("\n")
        sys.stdout.flush()


def start(args, config=None):
    """Start service."""
    with Action(f"Starting service {NAME}"):
        os.system(f"sudo service {NAME} start")


def stop(args, config=None):
    """Stop service."""
    with Action(f"Stopping service {NAME}"):
        os.system(f"sudo service {NAME} stop")


def status(args, config=None):
    """Get service status."""
    with Action(f"Getting service {NAME} status"):
        os.system(f"sudo service {NAME} status")
