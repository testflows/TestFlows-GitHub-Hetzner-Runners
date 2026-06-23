#!/usr/bin/env bash
# recycle.sh - Cleanup script executed when recycling a server without rebuilding the image.
#
# This script runs after the server is powered on and before the runner is registered
# for the next job. Use it to clean up state left by the previous job, for example:
#
#   - Remove workspace files
#   - Prune Docker containers, images, and volumes
#   - Clear credentials or secrets written by the previous job
#   - Reset any other job-specific state
#
echo "Executing recycle clean up"

# Example cleanup steps (uncomment and adapt as needed):
#
#   # Remove GitHub Actions runner work directory
#   rm -rf /home/ubuntu/_work/*
#
#   # Prune all unused Docker resources
#   docker system prune -af --volumes
#
#   # Remove any credentials written to the home directory
#   rm -f /home/ubuntu/.netrc /home/ubuntu/.docker/config.json

# Fully remove any previous runner registration and local runner state.
RUNNER_HOME="/home/ubuntu"
if [ -d "${RUNNER_HOME}" ]; then
  # Stop any leftover listener process/session from the previous run.
  pkill -f '[r]un.sh' 2>/dev/null || true
  screen -wipe >/dev/null 2>&1 || true

  if [ -x "${RUNNER_HOME}/config.sh" ]; then
    (
      cd "${RUNNER_HOME}" || exit 0
      sudo -H -u ubuntu ./config.sh remove --local || echo "warn: failed to deregister runner locally" >&2
    )
  fi

  # Remove local runner metadata so next startup always re-registers cleanly.
  rm -f \
    "${RUNNER_HOME}/.runner" \
    "${RUNNER_HOME}/.credentials" \
    "${RUNNER_HOME}/.credentials_rsaparams" \
    "${RUNNER_HOME}/.env" || echo "warn: failed to remove local runner metadata" >&2
fi

# Stop and remove any leftover containers first so bind mounts are released.
docker ps -q | xargs -r sudo docker stop || echo "warn: docker stop failed" >&2
docker ps -aq | xargs -r sudo docker rm -f || echo "warn: docker rm failed" >&2

# Remove all contents of runner work dir, including hidden files/dirs, but keep root dir.
if [ -d /home/ubuntu/_work ]; then
  sudo rm -rf /home/ubuntu/_work/* /home/ubuntu/_work/.[!.]* /home/ubuntu/_work/..?* || echo "warn: failed to clean _work directory" >&2
fi

# Prune all unused Docker containers
docker container prune -f || echo "warn: docker container prune failed" >&2

# Prune all unused Docker volumes
docker volume prune -f || echo "warn: docker volume prune failed" >&2

# Prune Docker build cache. This is reported separately by `docker system df`
# and is not removed by image/container/volume prune commands.
docker builder prune -af || echo "warn: docker builder prune failed" >&2

# Prune all dangling Docker images.
# Intentionally keeping tagged/base images for reuse.
docker image prune -f || echo "warn: docker image prune failed" >&2

# Remove any credentials written to the home directory
rm -f /home/ubuntu/.netrc /home/ubuntu/.docker/config.json || echo "warn: failed to remove credential files" >&2
