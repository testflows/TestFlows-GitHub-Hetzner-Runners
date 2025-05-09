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
import os
import stat
import yaml
import glob
import time


PROJECTS_BASE_DIR = os.path.expanduser("~/.github-hetzner-runners")
CURRENT_PROJECT_FILE_PREFIX = ".current-project-"
SECURE_PERMISSIONS = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR


def ensure_secure_permissions(path):
    """Ensure file has secure permissions (readable only by owner)."""
    if os.path.exists(path):
        os.chmod(path, SECURE_PERMISSIONS)


def get_projects_dir():
    """Get the path to the projects directory."""
    # Ensure base directory exists with correct permissions
    os.makedirs(PROJECTS_BASE_DIR, exist_ok=True)
    os.chmod(PROJECTS_BASE_DIR, SECURE_PERMISSIONS)

    # Create and set permissions for projects directory
    project_dir = os.path.join(PROJECTS_BASE_DIR, "projects")
    os.makedirs(project_dir, exist_ok=True)
    os.chmod(project_dir, SECURE_PERMISSIONS)
    return project_dir


def get_project_file(name):
    """Get the path to a project's YAML file."""
    projects_dir = get_projects_dir()
    return os.path.join(projects_dir, f"{name}.yaml")


def read_project_file(project_file):
    """Read project configuration from a YAML file."""
    if not os.path.exists(project_file):
        return {}

    with open(project_file, "r") as f:
        return yaml.safe_load(f) or {}


def write_project_file(project_file, config):
    """Write project configuration to a YAML file."""
    with open(project_file, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)
    ensure_secure_permissions(project_file)


def get_shell_pid():
    """Get the parent process ID (shell)."""
    try:
        # Get the parent process (shell)
        return os.getppid()
    except (OSError, AttributeError):
        return None


def get_current_project_file():
    """Get the path to the current project file for this shell."""
    shell_pid = get_shell_pid()
    if shell_pid:
        return os.path.join(
            PROJECTS_BASE_DIR, f"{CURRENT_PROJECT_FILE_PREFIX}{shell_pid}"
        )
    return None


def process_exists(pid):
    """Check if a process exists using standard library."""
    try:
        # On Unix-like systems, sending signal 0 to a process checks if it exists
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def get_current_files_dir():
    """Get the directory for current project files."""
    os.makedirs(PROJECTS_BASE_DIR, exist_ok=True)
    ensure_secure_permissions(PROJECTS_BASE_DIR)
    return PROJECTS_BASE_DIR


def cleanup_stale_current_files():
    """Clean up stale current project files by removing files older
    than 1 second from processes that no longer exist, processing
    at most 5 files at a time with secure permissions.
    """
    try:
        current_files = glob.glob(
            os.path.join(get_current_files_dir(), f"{CURRENT_PROJECT_FILE_PREFIX}*")
        )

        for current_file in current_files[:5]:
            try:
                ensure_secure_permissions(current_file)
                pid = int(os.path.basename(current_file).rsplit("-", 1)[1])

                file_age = time.time() - os.path.getmtime(current_file)
                if file_age < 1:
                    continue

                if not process_exists(pid):
                    try:
                        os.unlink(current_file)
                    except FileNotFoundError:
                        pass
                    except PermissionError:
                        continue
            except (ValueError, OSError) as e:
                if isinstance(e, ValueError):
                    continue
                elif isinstance(e, OSError):
                    continue
    except Exception as e:
        pass


def get_current_project():
    """Get the name of the currently active project for this shell."""
    cleanup_stale_current_files()

    current_file = get_current_project_file()
    if current_file and os.path.exists(current_file):
        with open(current_file, "r") as f:
            return f.read().strip()
    return None


def set_current_project(name):
    """Set the current project name for this shell."""
    current_file = get_current_project_file()
    if not current_file:
        return

    if name:
        with open(current_file, "w") as f:
            f.write(name)
        ensure_secure_permissions(current_file)
    elif os.path.exists(current_file):
        os.remove(current_file)


def mask_token(token, show_full=False):
    """Mask a token, showing only first 3 and last 5 characters unless show_full is True."""
    if not token or show_full:
        return token
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:3]}...{token[-5:]}"


def list(args, config):
    """List all configured projects."""
    projects_dir = get_projects_dir()
    if not os.path.exists(projects_dir):
        print("No projects configured")
        return

    projects = []
    for project_file in os.listdir(projects_dir):
        if project_file.endswith(".yaml"):
            project_name = project_file[:-5]  # Remove .yaml extension
            project_path = os.path.join(projects_dir, project_file)
            project_config = read_project_file(project_path)
            projects.append((project_name, project_config))

    if not projects:
        print("No projects configured")
        return

    # Sort projects by name
    projects.sort(key=lambda x: x[0])

    # Print projects and their configuration
    current_project = get_current_project()
    for project_name, project_config in projects:
        current = " (current)" if project_name == current_project else ""
        print(f"\n{project_name}{current}:")
        if not project_config:
            print("  No configuration set")
        else:
            for key, value in sorted(project_config.items()):
                if key in ["github_token", "hetzner_token"]:
                    value = mask_token(value, args.show_tokens)
                print(f"  {key}: {value}")


def add(args, config):
    """Add a new project configuration."""
    project_file = get_project_file(args.name)

    # Create project configuration
    project_config = {}
    if args.hetzner_token:
        project_config["hetzner_token"] = args.hetzner_token
    if args.github_token:
        project_config["github_token"] = args.github_token
    if args.github_repository:
        project_config["github_repository"] = args.github_repository
    if args.config_file:
        project_config["config_file"] = args.config_file

    # Write YAML file
    write_project_file(project_file, project_config)
    print(f"Project '{args.name}' added successfully")


def update(args, config):
    """Update an existing project configuration."""
    project_file = get_project_file(args.name)

    if not os.path.exists(project_file):
        print(f"Project '{args.name}' does not exist")
        return

    # Load existing configuration
    project_config = read_project_file(project_file)

    # Update with new values
    if args.hetzner_token:
        project_config["hetzner_token"] = args.hetzner_token
    if args.github_token:
        project_config["github_token"] = args.github_token
    if args.github_repository:
        project_config["github_repository"] = args.github_repository
    if args.config_file:
        project_config["config_file"] = args.config_file

    # Write updated configuration
    write_project_file(project_file, project_config)
    print(f"Project '{args.name}' updated successfully")


def delete(args, config):
    """Delete a project configuration."""
    project_file = get_project_file(args.name)

    if not os.path.exists(project_file):
        print(f"Project '{args.name}' does not exist")
        return

    os.remove(project_file)

    # If this was the current project, clear it
    if get_current_project() == args.name:
        set_current_project(None)

    print(f"Project '{args.name}' deleted successfully")


def set_current(args, config):
    """Set the current project."""
    project_file = get_project_file(args.name)

    if not os.path.exists(project_file):
        print(f"Project '{args.name}' does not exist")
        return

    set_current_project(args.name)
    print(f"Project '{args.name}' set as current")


def unset_current(args, config):
    """Unset the current project."""
    current = get_current_project()
    if current:
        set_current_project(None)
        print(f"Project '{current}' unset")
    else:
        print("No current project set")


def get_project_config(name=None):
    """Get project configuration, optionally for a specific project."""
    if name is None:
        name = get_current_project()

    if name is None:
        return {}

    project_file = get_project_file(name)
    if not os.path.exists(project_file):
        return {}

    return read_project_file(project_file)
