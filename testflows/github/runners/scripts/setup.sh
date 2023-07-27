set -x

echo "Create and configure ubuntu user"

adduser ubuntu --disabled-password --gecos ""
echo "%wheel   ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
addgroup wheel
addgroup docker
usermod -aG wheel ubuntu
usermod -aG sudo ubuntu
usermod -aG docker ubuntu
