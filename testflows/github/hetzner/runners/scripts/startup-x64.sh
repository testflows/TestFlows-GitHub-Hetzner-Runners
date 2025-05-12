set -x
echo "Install runner"
cd /home/ubuntu

ACTIONS_RUNNER_FILE="actions-runner-linux-x64-2.306.0.tar.gz"
ACTIONS_RUNNER_SHA256="b0a090336f0d0a439dac7505475a1fb822f61bbb36420c7b3b3fe6b1bdc4dbaa"
ACTIONS_RUNNER_URL="https://github.com/actions/runner/releases/download/v2.306.0/$ACTIONS_RUNNER_FILE"
CACHE_DIR="/mnt/cache"
CACHE_DIR_GITHUB="$CACHE_DIR/github"

download_and_verify() {
    echo "Downloading actionsrunner package from GitHub..."
    curl -o "$ACTIONS_RUNNER_FILE" -L "$ACTIONS_RUNNER_URL"
    echo "$ACTIONS_RUNNER_SHA256  $ACTIONS_RUNNER_FILE" | shasum -a 256 -c
}

# Try to use cache volume if available
if [ -d "$CACHE_DIR" ]; then
    if [ -f "$CACHE_DIR_GITHUB/$ACTIONS_RUNNER_FILE" ]; then
        echo "Found runner package in cache, verifying checksum..."
        if echo "$ACTIONS_RUNNER_SHA256  $CACHE_DIR_GITHUB/$ACTIONS_RUNNER_FILE" | shasum -a 256 -c; then
            echo "Checksum verified, copying from cache..."
            cp "$CACHE_DIR_GITHUB/$ACTIONS_RUNNER_FILE" .
        else
            echo "Cache file checksum mismatch"
            download_and_verify
            # Save to cache for future use
            mkdir -p "$CACHE_DIR_GITHUB"
            cp "$ACTIONS_RUNNER_FILE" "$CACHE_DIR_GITHUB/"
        fi
    else
        echo "Runner package not found in cache"
        download_and_verify
        # Save to cache for future use
        mkdir -p "$CACHE_DIR_GITHUB"
        cp "$ACTIONS_RUNNER_FILE" "$CACHE_DIR_GITHUB/"
    fi
else
    echo "Cache directory not available, downloading directly..."
    download_and_verify
fi

tar xzf ./actions-runner-linux-x64-2.306.0.tar.gz

echo "Configure runner"
./config.sh --unattended --replace --url https://github.com/${GITHUB_REPOSITORY} --token ${GITHUB_RUNNER_TOKEN} --name "$(hostname)-${SERVER_TYPE_NAME}-${SERVER_LOCATION_NAME}" --runnergroup "${GITHUB_RUNNER_GROUP}" --labels "${GITHUB_RUNNER_LABELS}" --work _work --ephemeral

echo "Start runner"
bash -c "screen -d -m bash -c './run.sh; sudo poweroff'"
