# Mailcow Cold Email Infrastructure Plan

## Overview
This plan outlines how to deploy multiple mailcow instances across VPS servers with dedicated IPs for cold email campaigns, including automated domain/mailbox creation, DNS record management, and proper email authentication setup.

## Architecture

### Multi-VPS Setup
- **One VPS per nameserver cluster** to avoid customer overlap
- **Dedicated IP per VPS** for clean sender reputation
- **Isolated nameserver assignment** per VPS
- **Automated scaling** to additional VPS when needed

### DNS Strategy - Custom Nameservers Per VPS
```
VPS-1 (IP: 1.2.3.4) → ns1.yourdomain.com, ns2.yourdomain.com
VPS-2 (IP: 5.6.7.8) → ns3.yourdomain.com, ns4.yourdomain.com  
VPS-3 (IP: 9.10.11.12) → ns5.yourdomain.com, ns6.yourdomain.com
```

**Nameserver Setup Per VPS:**
- Each VPS runs BIND9 DNS server alongside mailcow
- Registered nameservers (ns1, ns2) point to VPS IP
- Domains purchased on Namecheap use VPS nameservers
- Complete DNS control per VPS instance

## Implementation Plan

### Phase 1: Single Script VPS Setup

#### 1.1 Manual VPS Setup (RackNerd)
- **Manual Steps:**
  - Deploy Ubuntu 22.04 LTS VPS via RackNerd panel
  - Minimum 4GB RAM, 2 CPU cores, 40GB SSD
  - Note dedicated IP address from RackNerd panel
  - **Manually configure PTR record** through RackNerd support/panel
  - SSH into server as root

#### 1.2 Single Installation Script
**Run one command to install everything:**
```bash
curl -sSL https://raw.githubusercontent.com/nidty719/mailcow-sending/master/install-mailcow-vps.sh | bash
```

**Complete Installation Script (install-mailcow-vps.sh):**
```bash
#!/bin/bash
# install-mailcow-vps.sh - Complete VPS setup for mailcow + BIND9
# Usage: curl -sSL https://raw.githubusercontent.com/nidty719/mailcow-sending/master/install-mailcow-vps.sh | bash

set -e

echo "=== Mailcow VPS Installation Script ==="
echo "This will install Docker, BIND9, and Mailcow"

# Get VPS IP address
VPS_IP=$(curl -s ifconfig.me)
echo "Detected VPS IP: $VPS_IP"

# Prompt for nameserver domain
read -p "Enter your nameserver domain (e.g., ns1.yourdomain.com): " NS_DOMAIN
NS_BASE=$(echo $NS_DOMAIN | sed 's/ns[0-9]*\.//')

echo "=== Step 1: System Update ==="
apt update && apt upgrade -y

echo "=== Step 2: Install Dependencies ==="
apt install -y docker.io docker-compose git curl bind9 bind9utils bind9-doc python3 python3-pip

echo "=== Step 3: Configure Services ==="
systemctl enable docker
systemctl start docker
systemctl enable named
systemctl start named
usermod -aG docker $USER

echo "=== Step 4: Configure BIND9 Nameserver ==="
# Configure named.conf.options for security
cat > /etc/bind/named.conf.options << EOF
options {
        directory "/var/cache/bind";
        
        recursion no;
        allow-query { any; };
        
        dnssec-validation auto;
        
        listen-on-v6 { any; };
        
        version "Not Available";
        hostname "Not Available";
        server-id "Not Available";
};
EOF

# Initialize named.conf.local
cat > /etc/bind/named.conf.local << 'EOF'
//
// Local BIND configuration for mailcow domains
//
EOF

systemctl restart named

echo "=== Step 5: Install Mailcow ==="
cd /opt
git clone https://github.com/mailcow/mailcow-dockerized
cd mailcow-dockerized

# Generate mailcow config with VPS IP
echo "MAILCOW_HOSTNAME=mail.$NS_BASE" > mailcow.conf
echo "HTTP_PORT=80" >> mailcow.conf
echo "HTTPS_PORT=443" >> mailcow.conf
echo "HTTP_BIND=0.0.0.0" >> mailcow.conf
echo "HTTPS_BIND=0.0.0.0" >> mailcow.conf

./generate_config.sh

echo "=== Step 6: Start Mailcow ==="
docker-compose up -d

echo "=== Step 7: Install Management Tools ==="
pip3 install requests dnspython

# Create management directory
mkdir -p /opt/mailcow-management
cd /opt/mailcow-management

# Download management scripts
curl -sSL https://raw.githubusercontent.com/nidty719/mailcow-sending/master/scripts/bulk-setup.py -o bulk-setup.py
curl -sSL https://raw.githubusercontent.com/nidty719/mailcow-sending/master/scripts/dns-manager.py -o dns-manager.py

chmod +x *.py

echo "=== Installation Complete ==="
echo "VPS IP: $VPS_IP"
echo "Nameserver Domain: $NS_DOMAIN"
echo "Mailcow URL: https://mail.$NS_BASE"
echo ""
echo "Next Steps:"
echo "1. Register nameservers ns1.$NS_BASE and ns2.$NS_BASE pointing to $VPS_IP at Namecheap"
echo "2. Configure PTR record: $VPS_IP -> mail.$NS_BASE"
echo "3. Run: python3 /opt/mailcow-management/bulk-setup.py your-domains.csv"
echo ""
echo "Management tools installed in /opt/mailcow-management/"
EOF

### Phase 2: Automation Scripts

#### 2.1 CSV Input Processing
**Input Format** (based on ReachInbox.ai structure):
```csv
Domain,Username,First Name,Last Name,Daily Limit,Tracking Domain
example1.com,john,John,Doe,50,track.example1.com
example2.com,jane,Jane,Smith,30,track.example2.com
```

#### 2.2 Domain & Mailbox Creation Script
```python
# mailcow-bulk-setup.py
def process_csv_batch(csv_file, vps_instance):
    """
    1. Read CSV input
    2. Create domains in mailcow
    3. Generate mailboxes with strong passwords
    4. Setup DNS records (MX, SPF, DKIM, DMARC)
    5. Export configuration for cold email tools
    """
```

#### 2.3 DNS Record Automation via BIND9
Python script to automatically manage BIND9 zone files:

```python
# dns-manager.py - Automate BIND9 zone file creation
def create_zone_file(domain, vps_ip, dkim_key):
    zone_content = f"""
$TTL    300
@       IN      SOA     ns1.yourdomain.com. admin.{domain}. (
                     {int(time.time())}     ; Serial (timestamp)
                         300                ; Refresh
                         300                ; Retry
                         604800             ; Expire
                         300 )              ; Negative Cache TTL

; Name servers
@       IN      NS      ns1.yourdomain.com.
@       IN      NS      ns2.yourdomain.com.

; Mail server
@       IN      A       {vps_ip}
mail    IN      A       {vps_ip}
@       IN      MX      10      mail.{domain}.

; Auto-discovery
autodiscover    IN      CNAME   mail
autoconfig      IN      CNAME   mail

; SPF Record
@       IN      TXT     "v=spf1 ip4:{vps_ip} mx ~all"

; DKIM Record
dkim._domainkey IN      TXT     "v=DKIM1; k=rsa; p={dkim_key}"

; DMARC Record
_dmarc  IN      TXT     "v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain}"
"""
    
    # Write zone file
    with open(f'/etc/bind/db.{domain}', 'w') as f:
        f.write(zone_content)
    
    # Add to named.conf.local
    zone_config = f'''
zone "{domain}" {{
    type master;
    file "/etc/bind/db.{domain}";
    allow-transfer {{ any; }};
}};
'''
    
    with open('/etc/bind/named.conf.local', 'a') as f:
        f.write(zone_config)
    
    # Reload BIND9
    subprocess.run(['systemctl', 'reload', 'named'])
```

#### 2.4 Namecheap Nameserver Registration Process

**Step 1: Register Nameservers at Namecheap**
1. Login to Namecheap account
2. Go to Domain List → Manage domain
3. Navigate to "Private Nameservers" 
4. Register new nameservers:
   - ns1.yourdomain.com → VPS IP (1.2.3.4)
   - ns2.yourdomain.com → VPS IP (1.2.3.4)

**Step 2: Point Customer Domains to Your Nameservers**
```python
# For each customer domain on Namecheap:
# 1. Change nameservers from default to custom
# 2. Set nameservers to: ns1.yourdomain.com, ns2.yourdomain.com
# 3. Domain DNS is now controlled by your VPS BIND9 server
```

### Phase 3: Integration & Export

#### 3.1 Mailcow API Integration
- Use mailcow REST API for domain/mailbox management
- Automated DKIM key generation and retrieval
- Bulk operations for efficiency

#### 3.2 Export Format
Generate CSV output compatible with cold email tools:
```csv
Email,First Name,Last Name,IMAP Username,IMAP Password,IMAP Host,IMAP Port,SMTP Username,SMTP Password,SMTP Host,SMTP Port,Daily Limit,Warmup Enabled,Warmup Limit,Warmup Increment,Tracking Domain
john@example1.com,John,Doe,john@example1.com,SecurePass123,mail.yourvps1.com,993,john@example1.com,SecurePass123,mail.yourvps1.com,587,50,TRUE,20,1,track.example1.com
```

## Technical Implementation

### 4.1 Required Components

**DNS Management:**
- PowerDNS with REST API
- Automated zone file generation
- Real-time DNS propagation monitoring

**Mailcow Customization:**
- API wrapper for bulk operations
- Custom domain validation
- Automated SSL certificate management

**Monitoring & Maintenance:**
- Health checks for all services
- Automated backup scheduling
- Performance monitoring and alerting

### 4.2 Security Considerations

**Access Control:**
- API authentication and rate limiting
- Firewall rules for mail ports only
- Regular security updates and patches

**Email Authentication:**
- Proper DKIM/SPF/DMARC setup
- Regular key rotation
- Reputation monitoring

### 4.3 Scaling Strategy

**Horizontal Scaling:**
- Add new VPS when capacity reached
- Load balancing across instances
- Geographic distribution for better deliverability

**Management:**
- Command-line scripts for VPS management
- Bulk operation via Python scripts
- Log-based status monitoring

## Simplified Workflow

### Step 1: VPS Setup (One Command)
```bash
# SSH into fresh RackNerd VPS and run:
curl -sSL https://raw.githubusercontent.com/nidty719/mailcow-sending/master/install-mailcow-vps.sh | bash
```
**This installs everything:** Docker, BIND9, Mailcow, Python tools

### Step 2: Register Nameservers at Namecheap
- Register ns1.yourdomain.com and ns2.yourdomain.com pointing to VPS IP
- Configure PTR record at RackNerd

### Step 3: Bulk Domain Setup
```bash
# Upload CSV and run bulk setup
python3 /opt/mailcow-management/bulk-setup.py your-domains.csv
```

### Step 4: Export for Cold Email Tools
Script automatically generates ReachInbox.ai compatible CSV output

## Cost Estimation

**Per VPS Monthly:**
- VPS (4GB/2CPU): $20-40
- Domain for nameservers: $10-15
- SSL certificates: $0 (Let's Encrypt)
- **Total per VPS: ~$30-55/month**

**Scaling:**
- 1 VPS = ~100-200 domains
- 10 VPS setup = ~1000-2000 domains capacity

## Deliverables

1. **Installation Scripts**: Automated VPS setup and mailcow deployment
2. **Bulk Management Tool**: Python scripts for CSV processing and mailbox creation
3. **DNS Automation**: Scripts for automatic record creation via registrar APIs
4. **Export Tool**: Generate cold email tool compatible output
5. **Monitoring Scripts**: Command-line status and health checking
6. **Documentation**: Complete setup and operational guides

This infrastructure provides a scalable, automated solution for cold email campaigns with proper email authentication and deliverability optimization.