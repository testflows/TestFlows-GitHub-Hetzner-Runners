import os
import sys
import time
import base64
import hashlib
import datetime
import subprocess

from hcloud import Client
from hcloud.ssh_keys.domain import SSHKey
from hcloud.server_types.domain import ServerType
from hcloud.servers.client import BoundServer
from hcloud.images.domain import Image

from argparse import ArgumentParser, RawTextHelpFormatter

HETZNER_TOKEN = os.getenv(
    "HETZNER_TOKEN",
)

description = """Hetzner snapshot creation script.

    Creates a Hetzner snapshot image based on the server type, image, and setup script provided.
"""


def argparser():
    """Command line argument parser."""
    parser = ArgumentParser(
        "Altinity Heztner snapshot generator",
        description=description,
        formatter_class=RawTextHelpFormatter,
    )

    parser.add_argument(
        "--server-type",
        action="store",
        help="Server type. Ex: cpx51",
        default="cpx51",
        required=False,
    )

    parser.add_argument(
        "--server-image",
        action="store",
        help="Server image. Ex: system-ubuntu-22.04",
        default="system-ubuntu-22.04",
        required=False,
    )

    parser.add_argument(
        "--setup-script-path",
        action="store",
        help="Path to the script that will execute on the server",
        required=True,
    )

    parser.add_argument(
        "--snapshot-name",
        action="store",
        help="Name of the snapshot",
        default=None,
        required=False,
    )

    parser.add_argument(
        "--ssh-key-path",
        action="store",
        help="Path to the pubkey used to upload and execute setup script on the server",
        required=True,
    )

    return parser


class Action:
    """Action wrapper."""

    debug = True

    @staticmethod
    def timestamp():
        """Return timestamp string."""
        dt = datetime.datetime.now(datetime.timezone.utc)
        return dt.astimezone().strftime("%b %d,%Y %H:%M:%S.%f %Z")

    def __init__(self, name, ignore_fail=False):
        self.name = name
        self.ignore_fail = ignore_fail

    def __enter__(self):
        print(f"{self.timestamp()} \u270D  {self.name}")

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_value is not None:
            print(f"{self.timestamp()} \u274C Error", exc_value)
            if self.ignore_fail:
                return
            if self.debug:
                raise
            sys.exit(1)
        else:
            print(f"{self.timestamp()} \u2705 OK")


def shell(cmd, shell=True, check=True):
    """Execute command."""
    p = subprocess.run(
        cmd, shell=shell, stdout=sys.stdout, stderr=sys.stdout, check=check
    )
    return p.returncode


def wait_ready(server: BoundServer, timeout: float):
    """Wait for server to be ready."""
    start_time = time.time()

    while True:
        status = server.status
        if status == server.STATUS_RUNNING:
            break
        if time.time() - start_time >= timeout:
            raise TimeoutError("waiting for server to start running")
        time.sleep(1)
        server.reload()


def ip_address(server: BoundServer):
    """Return IPv4 address of the server."""
    return server.public_net.primary_ipv4.ip


def wait_ssh(server: BoundServer, timeout: float):
    """Wait until SSH connection is ready."""
    ip = ip_address(server=server)

    attempt = -1
    start_time = time.time()

    while True:
        attempt += 1
        with Action(
            f"Trying to connect to {server.name}@{ip}...{attempt}",
            ignore_fail=True,
        ):
            returncode = ssh(server, "hostname", check=False)
            if returncode == 0:
                break
        if time.time() - start_time >= timeout:
            ssh(server, "hostname")
        else:
            time.sleep(5)


def ssh_command(server: BoundServer):
    """Return ssh command."""
    ip = ip_address(server=server)
    return f'ssh -q -o "StrictHostKeyChecking no" -o UserKnownHostsFile=/dev/null root@{ip}'


def ssh(server: BoundServer, cmd: str, *args, **kwargs):
    """Execute command over SSH."""
    return shell(
        f"{ssh_command(server=server)} {cmd}",
        *args,
        **kwargs,
    )


def fingerprint(ssh_key):
    """Calculate fingerprint of a public SSH key."""
    encoded_key = base64.b64decode(ssh_key.strip().split()[1].encode("utf-8"))
    md5_digest = hashlib.md5(encoded_key).hexdigest()

    return ":".join(a + b for a, b in zip(md5_digest[::2], md5_digest[1::2]))


def generate_snapshot(
    snapshot_name: str,
    server_type: str,
    server_image: Image,
    setup_script: str,
    ssh_key: SSHKey,
    timeout=60,
):
    """Create specified number of server instances."""
    client = Client(token=HETZNER_TOKEN)

    image_type, image_name = server_image.split("-", 1)
    image = Image(name=image_name, type=image_type)
    server_name = "snapshot-generator"
    ssh_key = client.ssh_keys.get_by_fingerprint(fingerprint=ssh_key.fingerprint)
    type = ServerType(name=server_type)

    with Action(f"Creating server {server_name}"):
        response = client.servers.create(
            name=server_name,
            server_type=type,
            image=image,
            ssh_keys=[ssh_key],
        )
        server: BoundServer = response.server

    try:
        with Action(f"Waiting for server {server.name} to be ready"):
            wait_ready(server=server, timeout=timeout)

        with Action("Wait for SSH connection to be ready"):
            wait_ssh(server=server, timeout=timeout)

        with Action("Executing setup script"):
            ssh(server, f"bash -s  < {setup_script}")

        with Action("Power off the server"):
            server.shutdown().wait_until_finished()

        with Action("Generate snapshot"):
            server.create_image(description=snapshot_name)

    finally:
        with Action("Remove server instance"):
            server.delete()


if __name__ == "__main__":
    args = argparser().parse_args(None if sys.argv[1:] else ["-h"])

    snapshot_name = args.snapshot_name
    if not snapshot_name:
        snapshot_name = f"snapshot-{args.server_type}-{args.server_image}"

    with open(args.ssh_key_path, "r", encoding="utf-8") as ssh_key_file:
        public_key = ssh_key_file.read()

    ssh_key = SSHKey(
        name=hashlib.md5(public_key.encode("utf-8")).hexdigest(),
        public_key=public_key,
        fingerprint=fingerprint(public_key),
    )

    generate_snapshot(
        snapshot_name,
        args.server_type,
        args.server_image,
        args.setup_script_path,
        ssh_key,
    )
