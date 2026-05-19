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
