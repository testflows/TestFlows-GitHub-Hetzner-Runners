set -x

{
    echo "Configuring IPv6 DNS by adding entries to the top of /etc/resolv.conf..."
    # Define the IPv6 DNS servers to add at the top.
    # Use public NAT64 service (https://nat64.net/)
    # to be able to connect to IPv4 only services like https://github.com
    DNS_ENTRIES=(
        "nameserver 2a01:4f9:c010:3f02::1"
        "nameserver 2a00:1098:2b::1"
        "nameserver 2a00:1098:2c::1"
    )
    # Create a temporary file to store the new configuration
    TEMP_FILE=$(mktemp)
    # Add only missing entries at the top of the file
    for dns in "${DNS_ENTRIES[@]}"; do
        if ! grep -Fxq "$dns" /etc/resolv.conf; then
            echo "$dns" | sudo tee -a "$TEMP_FILE" > /dev/null
            echo "Added: $dns"
        else
            echo "Already exists: $dns"
        fi
    done
    # Append the existing content back to preserve other nameservers
    sudo cat /etc/resolv.conf >> "$TEMP_FILE"
    # Move the updated content back to /etc/resolv.conf
    sudo mv "$TEMP_FILE" /etc/resolv.conf
    sudo chmod 644 /etc/resolv.conf
    # Verify the changes
    echo "Updated /etc/resolv.conf:"
    cat /etc/resolv.conf
    # Test DNS resolution
    echo "Testing DNS resolution..."
    curl -6 https://github.com >/dev/null 2>&1
    echo "IPv6 DNS setup completed."
}

{
    echo "Create and configure ubuntu user"
    adduser ubuntu --disabled-password --gecos ""
    echo "%wheel   ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
    addgroup wheel
    addgroup docker
    usermod -aG wheel ubuntu
    usermod -aG sudo ubuntu
    usermod -aG docker ubuntu
}

{
    echo "Install fail2ban"
    apt-get update
    apt-get install --yes --no-install-recommends \
        fail2ban 
    echo "Launch fail2ban"
    systemctl start fail2ban
}
