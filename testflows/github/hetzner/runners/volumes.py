#!/usr/bin/env python3
# Copyright 2025 Katteli Inc.
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
import sys

from .config import Config
from .actions import Action
from .hclient import HClient as Client
from .scale_up import get_volume_name

from hcloud.volumes.client import BoundVolume
from hcloud.volumes.domain import Volume

status_icon = {
    Volume.STATUS_AVAILABLE: "🟢",
    Volume.STATUS_CREATING: "⏳",
}


def list(args, config: Config):
    """List all volumes."""
    config.check("hetzner_token")

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action("Getting a list of volumes"):
        volumes = client.volumes.get_all(label_selector="github-hetzner-runner-volume")
        if not volumes:
            print("No volumes found", file=sys.stdout)
            return

        print(
            "  ",
            f"{'status':10}",
            "name,",
            "actual name,",
            f"size in GB,",
            "location,",
            "server,",
            "created,",
            "format",
            file=sys.stdout,
        )
        for volume in volumes:
            icon = status_icon.get(volume.status, "❓")
            volume_server = volume.server.name if volume.server else "none"
            print(
                icon,
                f"{volume.status:10}",
                get_volume_name(volume.name) + ",",
                volume.name + ",",
                f"{volume.size}GB,",
                volume.location.name + ",",
                volume_server + ",",
                volume.created.strftime("%Y-%m-%d %H:%M:%S") + ",",
                volume.format,
                file=sys.stdout,
            )


def delete(args, config: Config):
    """Delete volumes."""
    config.check("hetzner_token")

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action("Getting a list of volumes"):
        volumes: list[BoundVolume] = client.volumes.get_all(
            label_selector="github-hetzner-runner-volume"
        )
        if not volumes:
            print("No volumes found", file=sys.stdout)
            return

    delete_volumes = []

    if args.delete_volumes_name:
        delete_volumes += [
            v for v in volumes if get_volume_name(v.name) in args.delete_volumes_name
        ]

    if args.delete_volumes_volume_name:
        delete_volumes += [
            v for v in volumes if v.name in args.delete_volumes_volume_name
        ]

    if args.delete_volumes_id:
        delete_volumes += [v for v in volumes if v.id in args.delete_volumes_id]

    if args.delete_volumes_all:
        delete_volumes = volumes[:]

    if not delete_volumes:
        print("No volumes selected", file=sys.stderr)
        return

    for volume in delete_volumes:
        print(
            f"🗑️  Deleting volume {volume.name} with id {volume.id} in {volume.location.name}",
            file=sys.stdout,
        )
        if volume.server:
            if not args.delete_volumes_force:
                print(
                    f"❌  Volume {volume.name} with id {volume.id} in {volume.location.name} is attached to server {volume.server.name}, use --force to delete",
                    file=sys.stderr,
                )
                continue
            print(
                f"✂️  Detaching volume {volume.name} with id {volume.id} in {volume.location.name} from server {volume.server.name}",
                file=sys.stdout,
            )
            volume.detach()
        client.volumes.delete(volume).wait_until_finished()
        print(
            f"✅  Deleted volume {volume.name} with id {volume.id} in {volume.location.name}",
            file=sys.stdout,
        )


def resize(args, config: Config):
    """Resize volumes."""
    config.check("hetzner_token")

    with Action("Logging in to Hetzner Cloud"):
        client = Client(token=config.hetzner_token)

    with Action("Getting a list of volumes"):
        volumes: list[BoundVolume] = client.volumes.get_all(
            label_selector="github-hetzner-runner-volume"
        )
        if not volumes:
            print("No volumes found", file=sys.stdout)
            return

    resize_volumes = []

    if args.resize_volumes_name:
        resize_volumes += [
            v for v in volumes if get_volume_name(v.name) in args.resize_volumes_name
        ]

    if args.resize_volumes_volume_name:
        resize_volumes += [
            v for v in volumes if v.name in args.resize_volumes_volume_name
        ]

    if args.resize_volumes_id:
        resize_volumes += [v for v in volumes if v.id in args.resize_volumes_id]

    if args.resize_volumes_all:
        resize_volumes = volumes[:]

    if not resize_volumes:
        print("No volumes selected", file=sys.stderr)
        return

    for volume in resize_volumes:
        print(
            f"📏  Resizing volume {volume.name} with id {volume.id} in {volume.location.name}",
            f"from {volume.size}GB to {args.size}GB",
            file=sys.stdout,
        )
        if volume.size >= args.size:
            print(
                f"❌  Skipping volume {volume.name} with id {volume.id} in {volume.location.name} is already at the desired size or larger (downsizing is not supported)",
                file=sys.stderr,
            )
            continue

        volume.resize(args.size).wait_until_finished()
        print(
            f"✅  Resized  volume {volume.name} with id {volume.id} in {volume.location.name}",
            f"from {volume.size}GB to {args.size}GB",
            file=sys.stdout,
        )
