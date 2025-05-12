set -x

{
    echo "Create and configure ubuntu user"
    adduser ubuntu --disabled-password --gecos ""

    echo "%wheel   ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
    addgroup wheel
    usermod -aG wheel ubuntu
    usermod -aG sudo ubuntu
}

{ 
    echo "Install fail2ban"
    apt-get update
    apt-get install --yes --no-install-recommends \
        fail2ban 
    
    echo "Launch fail2ban"
    systemctl start fail2ban
}

{
    echo "Install Docker Engine"
    apt-get -y update
    apt-get -y install ca-certificates curl gnupg

    echo "Add Docker’s official GPG key"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc

    echo "Set up Docker's repository"
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null

    echo "Install Docker Engine and containerd"
    apt-get -y update
    apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    echo "Add ubuntu user to docker group"
    usermod -aG docker ubuntu
}
