
set -x

apt-get update

apt-get -y install python3-pip
apt-get -y install openssh-client

echo "Create and configure runner user"

adduser runner --disabled-password --gecos ""
echo "%wheel   ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
addgroup wheel
usermod -aG wheel runner
usermod -aG sudo runner

echo "Generate SSH Key"
sudo -u runner ssh-keygen -t rsa -q -f "/home/runner/.ssh/id_rsa" -N ""