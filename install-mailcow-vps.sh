#!/bin/bash
# install-mailcow-vps.sh - Complete VPS setup for mailcow + BIND9
# Usage: curl -sSL https://raw.githubusercontent.com/nidty719/mailcow-sending/master/install-mailcow-vps.sh | bash

set -e

echo "=== Mailcow VPS Installation Script ==="
echo "This will install Docker, BIND9, and Mailcow"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit 1
fi

# Get VPS IP address
VPS_IP=$(curl -s ifconfig.me)
echo "Detected VPS IP: $VPS_IP"

# Get nameserver domain
if [ -z "$NS_DOMAIN" ]; then
    if [ -t 0 ]; then
        # Running interactively
        read -p "Enter your nameserver domain (e.g., ns1.yourdomain.com): " NS_DOMAIN
    else
        # Running non-interactively (curl | bash)
        echo "ERROR: Script is running non-interactively and NS_DOMAIN is not set."
        echo ""
        echo "Please either:"
        echo "1. Download and run the script manually:"
        echo "   wget https://raw.githubusercontent.com/nidty719/mailcow-sending/master/install-mailcow-vps.sh"
        echo "   chmod +x install-mailcow-vps.sh"
        echo "   ./install-mailcow-vps.sh"
        echo ""
        echo "2. Or set the NS_DOMAIN environment variable:"
        echo "   NS_DOMAIN=ns1.yourdomain.com curl -sSL https://raw.githubusercontent.com/nidty719/mailcow-sending/master/install-mailcow-vps.sh | bash"
        echo ""
        exit 1
    fi
fi

# Validate NS_DOMAIN
if [ -z "$NS_DOMAIN" ]; then
    echo "ERROR: Nameserver domain cannot be empty"
    exit 1
fi

NS_BASE=$(echo $NS_DOMAIN | sed 's/ns[0-9]*\.//')

echo "=== Step 1: System Update ==="
apt update && apt upgrade -y

echo "=== Step 2: Install Dependencies ==="
apt install -y git curl bind9 bind9utils bind9-doc python3 python3-pip ufw

echo "=== Step 2.1: Remove Old Docker Packages ==="
# Remove old Docker packages that might conflict (only if they exist)
for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do
    if dpkg -l | grep -q "^ii  $pkg "; then
        echo "Removing $pkg..."
        apt remove -y $pkg
    else
        echo "$pkg not installed, skipping..."
    fi
done

# Clean up
apt autoremove -y

echo "=== Step 2.2: Install Docker CE and Compose v2 ==="

# Install Docker's official Docker Compose plugin (recommended by mailcow)
apt update
apt install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update and install Docker CE and Docker Compose plugin
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Also install standalone docker-compose for compatibility
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create symlinks for compatibility
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

# Verify installation - both methods should work
echo "Testing Docker Compose installations:"
docker compose version
docker-compose --version

echo "=== Step 3: Configure Firewall ==="
ufw --force enable
ufw allow 22/tcp
ufw allow 25/tcp
ufw allow 53/tcp
ufw allow 53/udp
ufw allow 80/tcp
ufw allow 110/tcp
ufw allow 143/tcp
ufw allow 443/tcp
ufw allow 465/tcp
ufw allow 587/tcp
ufw allow 993/tcp
ufw allow 995/tcp

echo "=== Step 4: Configure Services ==="
systemctl enable docker
systemctl start docker
systemctl enable named
systemctl start named

# Add user to docker group (will take effect on next login)
usermod -aG docker $USER

echo "=== Step 5: Configure BIND9 Nameserver ==="
# Backup original configs
cp /etc/bind/named.conf.options /etc/bind/named.conf.options.backup
cp /etc/bind/named.conf.local /etc/bind/named.conf.local.backup

# Configure named.conf.options for security
cat > /etc/bind/named.conf.options << EOF
options {
        directory "/var/cache/bind";
        
        recursion no;
        allow-query { any; };
        allow-transfer { any; };
        
        dnssec-validation auto;
        
        listen-on-v6 { any; };
        listen-on { any; };
        
        version "Not Available";
        hostname "Not Available";
        server-id "Not Available";
        
        rate-limit {
                responses-per-second 5;
                window 5;
        };
};
EOF

# Initialize named.conf.local
cat > /etc/bind/named.conf.local << 'EOF'
//
// Local BIND configuration for mailcow domains
// Zones will be added automatically by management scripts
//
EOF

# Test BIND9 config and restart
named-checkconf
systemctl restart named

echo "=== Step 6: Install Mailcow ==="
cd /opt

# Remove existing mailcow directory if it exists
if [ -d "mailcow-dockerized" ]; then
    echo "Removing existing mailcow-dockerized directory..."
    rm -rf mailcow-dockerized
fi

git clone https://github.com/mailcow/mailcow-dockerized
cd mailcow-dockerized

# Generate mailcow config with VPS IP
cat > mailcow.conf << EOF
MAILCOW_HOSTNAME=mail.$NS_BASE
HTTP_PORT=80
HTTPS_PORT=443
HTTP_BIND=0.0.0.0
HTTPS_BIND=0.0.0.0
MAILCOW_PASS_SCHEME=BLF-CRYPT
ACL_ANYONE=disallow
SKIP_LETS_ENCRYPT=n
ENABLE_SSL_SNI=n
SKIP_IP_CHECK=n
SKIP_HTTP_VERIFICATION=n
ADDITIONAL_SAN=
ADDITIONAL_SERVER_NAMES=
COMPOSE_PROJECT_NAME=mailcowdockerized
DOCKER_COMPOSE_VERSION=native
RESTART_POLICY=unless-stopped
WATCHDOG_NOTIFY_EMAIL=
WATCHDOG_NOTIFY_BAN=Y
WATCHDOG_EXTERNAL_CHECKS=n
WATCHDOG_MYSQL_REPLICATION_CHECKS=n
SKIP_CLAMD=n
SKIP_SOLR=n
SKIP_SOGO=n
ALLOW_ADMIN_EMAIL_LOGIN=n
USE_WATCHDOG=y
WATCHDOG_VERBOSE=n
MAILDIR_GC_TIME=7200
MAILDIR_SUB=Maildir
ACL_ANYONE=disallow
MAILCOW_TZ=America/New_York
EOF

# Generate additional config
./generate_config.sh

echo "=== Step 7: Start Mailcow ==="
docker compose up -d

echo "=== Step 7.1: Enable Auto-Start on Reboot ==="
# Create systemd service for mailcow auto-start
cat > /etc/systemd/system/mailcow.service << 'EOF'
[Unit]
Description=Mailcow Dockerized
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/mailcow-dockerized
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

# Enable the service
systemctl enable mailcow.service
systemctl daemon-reload

echo "Mailcow will now auto-start on system reboot"

echo "=== Step 7.1: Wait for Mailcow to Start ==="
echo "Waiting for Mailcow containers to be ready..."
sleep 30

# Check if containers are running
docker compose ps

echo "=== Step 8: Install Management Tools ==="
pip3 install requests dnspython pyotp qrcode

# Create management directory
mkdir -p /opt/mailcow-management
cd /opt/mailcow-management

# Create configuration file
cat > config.py << EOF
# Mailcow Management Configuration
VPS_IP = "$VPS_IP"
NS_BASE = "$NS_BASE"
MAILCOW_API_URL = "https://mail.$NS_BASE/api/v1"
BIND_CONFIG_PATH = "/etc/bind/named.conf.local"
BIND_ZONES_PATH = "/etc/bind"

# Default DNS TTL
DEFAULT_TTL = 300

# Mailcow API will be configured after first login
MAILCOW_API_KEY = None
EOF

echo "=== Step 9: Download Management Scripts ==="
# Download management scripts
curl -sSL https://raw.githubusercontent.com/nidty719/mailcow-sending/master/scripts/bulk-setup.py -o bulk-setup.py
curl -sSL https://raw.githubusercontent.com/nidty719/mailcow-sending/master/scripts/dns-manager.py -o dns-manager.py

chmod +x *.py

echo "=== Step 10: Set Admin Password ==="
echo "Setting default admin password to 'moohoo'..."
cd /opt/mailcow-dockerized

# Wait for MySQL to be ready
echo "Waiting for MySQL to initialize..."
sleep 10

# Reset admin password to default 'moohoo'
docker compose exec -T mysql-mailcow mysql -umailcow -p$(grep DBPASS mailcow.conf | cut -d= -f2) mailcow -e "INSERT INTO admin (username, password, superadmin, created, modified, active) VALUES ('admin', '{SSHA256}K8eVJ6YsZbQCfuJvSUbaQRLr0HPLz5rC9IAp0PAFl0tmNDBkMDc0', 1, NOW(), NOW(), 1) ON DUPLICATE KEY UPDATE password = '{SSHA256}K8eVJ6YsZbQCfuJvSUbaQRLr0HPLz5rC9IAp0PAFl0tmNDBkMDc0';" 2>/dev/null || echo "Admin user setup will complete automatically"

cd /opt/mailcow-management

echo "=== Installation Complete ==="
echo "VPS IP: $VPS_IP"
echo "Nameserver Domain: $NS_DOMAIN"
echo "Mailcow URL: https://mail.$NS_BASE"
echo ""
echo "IMPORTANT: Next Steps:"
echo "1. Register nameservers at Namecheap:"
echo "   - ns1.$NS_BASE -> $VPS_IP"
echo "   - ns2.$NS_BASE -> $VPS_IP"
echo "2. Configure PTR record at RackNerd: $VPS_IP -> mail.$NS_BASE"
echo "3. Access Mailcow at https://mail.$NS_BASE or https://$VPS_IP"
echo "   Default login: admin / moohoo"
echo "4. Generate API key in Mailcow admin panel (Configuration → Access → API)"
echo "5. Update /opt/mailcow-management/config.py with API key"
echo ""
echo "Management tools will be downloaded when you run bulk setup."
echo "Example: python3 /opt/mailcow-management/bulk-setup.py domains.csv"
echo ""
echo "Log files: /opt/mailcow-dockerized/"