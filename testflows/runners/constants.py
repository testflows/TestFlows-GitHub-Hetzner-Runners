# Server and runner name prefixes
server_name_prefix = "github-hetzner-runner-"
runner_name_prefix = server_name_prefix
standby_server_name_prefix = f"{server_name_prefix}standby-"
standby_runner_name_prefix = standby_server_name_prefix
recycle_server_name_prefix = f"{server_name_prefix}recycle-"

# Server SSH key label
server_ssh_key_label = "github-hetzner-runner-ssh-key"
# Server runner label
github_runner_label = "github-hetzner-runner"
# Recycle timestamp label (stores epoch seconds when server was marked for recycling)
recycle_timestamp_label = "github-hetzner-recycle-timestamp"
