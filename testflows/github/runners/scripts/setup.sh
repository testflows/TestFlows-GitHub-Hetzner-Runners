set -x

echo "Create and configure runner user"

adduser runner --disabled-password --gecos ""
echo "%wheel   ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
addgroup wheel
usermod -aG wheel runner
usermod -aG sudo runner
