import os
import stat
import yaml
import glob


def ensure_secure_permissions(path):
    """Ensure file has secure permissions (readable only by owner)."""
    if os.path.exists(path):
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def get_project_dir():
    """Get the path to the projects directory."""
    project_dir = os.path.expanduser("~/.github-hetzner-runners/projects")
    os.makedirs(project_dir, exist_ok=True)
    os.chmod(project_dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return project_dir


def get_project_file(name):
    """Get the path to a project's YAML file."""
    project_dir = get_project_dir()
    return os.path.join(project_dir, f"{name}.yaml")


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
        return os.path.expanduser(f"~/.github-hetzner-runners/.current-{shell_pid}")
    return None


def process_exists(pid):
    """Check if a process exists using standard library."""
    try:
        # On Unix-like systems, sending signal 0 to a process checks if it exists
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def cleanup_stale_current_files():
    """Clean up stale current project files for shells that no longer exist."""
    current_dir = os.path.expanduser("~/.github-hetzner-runners")
    os.makedirs(current_dir, exist_ok=True)

    # Find all current project files
    for current_file in glob.glob(os.path.join(current_dir, ".current-*")):
        try:
            # Extract PID from filename
            pid = int(os.path.basename(current_file).split("-")[1])

            # Check if process exists
            if not process_exists(pid):
                # Process doesn't exist, remove the file
                os.remove(current_file)
        except (ValueError, IndexError, OSError):
            # If there's any error, just skip this file
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


def list(args, config):
    """List all configured projects."""
    project_dir = get_project_dir()
    if not os.path.exists(project_dir):
        print("No projects configured")
        return

    projects = []
    for project_file in os.listdir(project_dir):
        if project_file.endswith(".yaml"):
            project_name = project_file[:-5]  # Remove .yaml extension
            project_path = os.path.join(project_dir, project_file)
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
