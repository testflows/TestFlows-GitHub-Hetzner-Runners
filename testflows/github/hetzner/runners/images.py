#!/usr/bin/env python3
# Copyright 2024 Katteli Inc.
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
from hcloud import Client
from hcloud.servers.client import BoundServer

from .actions import Action
from .config import Config, check_ssh_key, check_setup_script
from .server import wait_ready, wait_ssh, ssh


def delete(args, config: Config):
    """Delete an image."""

    config.check("hetzner_token")

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action(f"Deleting image {args.delete_image_id}"):
        client.images.get_by_id(args.delete_image_id).delete()


def list(args, config: Config):
    """List available images."""

    config.check("hetzner_token")

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action("List images"):
        images = client.images.get_all(
            name=args.list_images_name,
            label_selector=args.list_images_label_selector,
            bound_to=args.list_images_bound_to,
            type=args.list_images_type,
            architecture=args.list_images_architecture,
            status=args.list_images_status,
            sort=args.list_images_sort,
            include_deprecated=args.list_images_include_deprecated,
        )

        for image in images:
            print(
                f"id: {image.id}\n  "
                + f"name: {image.name}\n  "
                + f"description: {image.description}\n  "
                + f"type: {image.type}\n  "
                + f"created: {image.created}\n  "
                + f"status: {image.status}\n  "
                + f"architecture: {image.architecture}\n  "
                + f"labels: {image.labels}\n  "
                + f"image size: {image.image_size or 0:.02f}GB\n  "
                + f"disk size: {image.disk_size or 0:.02f}GB\n  "
                + (f"bound to: ")
                + ("None" if not image.bound_to else f"{image.bound_to.name}")
                + ("\n  ")
                + (f"created from: ")
                + ("None" if not image.created_from else f"{image.created_from.name}")
                + ("\n  ")
                + f"rapid deploy: {image.rapid_deploy}\n  "
                + f"os flavor: {image.os_flavor}\n  "
                + f"os version: {image.os_version}\n  "
                + f"deprecated: {image.deprecated}"
            )


def create_snapshot(args, config: Config, timeout=60):
    """Create custom snapshot image."""

    snapshot_name = args.create_snapshot_name

    config.check("hetzner_token")
    check_setup_script(args.create_snapshot_setup_script)

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action("Check SSH key"):
        ssh_keys = [check_ssh_key(client, config.ssh_key)]

    with Action(f"Creating server {args.create_snapshot_server_name}"):
        response = client.servers.create(
            name=args.create_snapshot_server_name,
            location=args.create_snapshot_server_location,
            server_type=args.create_snapshot_server_type,
            image=args.create_snapshot_server_image,
            ssh_keys=ssh_keys,
        )
        server: BoundServer = response.server

    try:
        with Action(f"Waiting for server {server.name} to be ready"):
            wait_ready(server=server, timeout=timeout)

        with Action("Wait for SSH connection to be ready"):
            wait_ssh(server=server, timeout=timeout)

        with Action("Executing setup script"):
            ssh(server, f"bash -s  < {args.create_snapshot_setup_script}")

        with Action("Power off the server"):
            server.shutdown().wait_until_finished()

        with Action(f"Generate snapshot {snapshot_name}"):
            server.create_image(description=snapshot_name)

    finally:
        with Action(f"Remove {server.name} server instance"):
            server.delete()
