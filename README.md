# Mailcow Cold Email Infrastructure

Automated setup for mailcow instances with custom nameservers for cold email campaigns.

## Quick Start

### 1. VPS Setup

SSH into your fresh RackNerd Ubuntu 22.04 VPS and run:

```bash
curl -sSL https://raw.githubusercontent.com/nidty719/mailcow-sending/master/install-mailcow-vps.sh | bash
```

This installs:
- Docker & Docker Compose v2 (latest)
- BIND9 DNS server
- Mailcow mail server
- Python management tools
- Firewall configuration

### 2. Register Nameservers

After installation, register nameservers at Namecheap:
- Go to Domain List → Manage → Private Nameservers
- Register: `ns1.yourdomain.com` → Your VPS IP
- Register: `ns2.yourdomain.com` → Your VPS IP

### 3. Configure PTR Record

At RackNerd, set PTR record:
- Your VPS IP → `mail.yourdomain.com`

### 4. Setup Mailcow API

1. Access Mailcow: `https://mail.yourdomain.com`
2. Login: `admin` / `moohoo`
3. Generate API key: Configuration → Access → API
4. Update config: `/opt/mailcow-management/config.py`

```python
MAILCOW_API_KEY = "your-api-key-here"
```

### 5. Bulk Domain Setup

Create a CSV file with your domains:

```csv
Domain,Username,First Name,Last Name,Daily Limit,Tracking Domain
yourdomain1.com,john,John,Doe,50,track.yourdomain1.com
yourdomain1.com,jane,Jane,Smith,30,track.yourdomain1.com
yourdomain2.com,mike,Mike,Johnson,40,track.yourdomain2.com
```

Run bulk setup:

```bash
python3 /opt/mailcow-management/bulk-setup.py domains.csv
```

This will:
- Create domains in Mailcow
- Generate secure mailbox passwords
- Setup DNS records (MX, SPF, DKIM, DMARC)
- Export ReachInbox.ai compatible CSV

## Files Structure

```
mailcow-sending/
├── install-mailcow-vps.sh      # Main installation script
├── scripts/
│   ├── bulk-setup.py           # Bulk domain/mailbox creation
│   └── dns-manager.py          # DNS management utility
├── sample-domains.csv          # Example CSV format
├── specs/
│   └── mailcow-instance.md     # Complete technical specs
└── README.md                   # This file
```

## Management Commands

### DNS Management

```bash
# Create DNS records for a domain
python3 /opt/mailcow-management/dns-manager.py create example.com

# List all configured domains
python3 /opt/mailcow-management/dns-manager.py list

# Verify DNS resolution
python3 /opt/mailcow-management/dns-manager.py verify example.com

# Remove domain DNS
python3 /opt/mailcow-management/dns-manager.py remove example.com

# Reload BIND9
python3 /opt/mailcow-management/dns-manager.py reload
```

### Bulk Operations

```bash
# Process domains from CSV
python3 /opt/mailcow-management/bulk-setup.py domains.csv output.csv

# Use custom output filename
python3 /opt/mailcow-management/bulk-setup.py domains.csv my-mailboxes.csv
```

## Configuration

Main config file: `/opt/mailcow-management/config.py`

```python
# VPS Configuration
VPS_IP = "1.2.3.4"
NS_BASE = "yourdomain.com"
MAILCOW_API_URL = "https://mail.yourdomain.com/api/v1"
MAILCOW_API_KEY = "your-api-key"

# DNS Configuration
BIND_CONFIG_PATH = "/etc/bind/named.conf.local"
BIND_ZONES_PATH = "/etc/bind"
DEFAULT_TTL = 300
```

## Output Format

The bulk setup generates a CSV compatible with ReachInbox.ai and similar cold email tools:

```csv
Email,First Name,Last Name,IMAP Username,IMAP Password,IMAP Host,IMAP Port,SMTP Username,SMTP Password,SMTP Host,SMTP Port,Daily Limit,Warmup Enabled,Warmup Limit,Warmup Increment,Tracking Domain,Warmup Filter Tag,Warmup On Weekdays,Warmup Open Rate,Warmup Spam Protection Rate,Warmup Mark As Important Rate
john@example1.com,John,Doe,john@example1.com,SecurePass123,mail.yourdomain.com,993,john@example1.com,SecurePass123,mail.yourdomain.com,587,50,TRUE,20,1,track.example1.com,shadow,TRUE,95,85,90
```

## DNS Records Created

For each domain, the following records are automatically created:

```
@ IN A 1.2.3.4
mail IN A 1.2.3.4
@ IN MX 10 mail.example.com.
@ IN TXT "v=spf1 ip4:1.2.3.4 mx ~all"
dkim._domainkey IN TXT "v=DKIM1; k=rsa; p=..."
_dmarc IN TXT "v=DMARC1; p=quarantine; rua=mailto:dmarc@example.com"
autodiscover IN CNAME mail
autoconfig IN CNAME mail
```

## Troubleshooting

### Check Mailcow Status
```bash
cd /opt/mailcow-dockerized
docker-compose ps
docker-compose logs -f

# Check Docker Compose version
docker-compose --version
# Should show version 2.x.x or higher
```

### Check BIND9 Status
```bash
systemctl status named
named-checkconf
dig @localhost example.com
```

### Test Email Connectivity
```bash
# Test SMTP
telnet mail.yourdomain.com 587

# Test IMAP
telnet mail.yourdomain.com 993
```

### DNS Propagation
```bash
# Check external DNS
dig example.com @8.8.8.8
dig MX example.com @8.8.8.8
dig TXT example.com @8.8.8.8
```

## Security Considerations

- Firewall is configured to allow only necessary ports
- BIND9 configured with security best practices
- Strong passwords generated automatically
- DKIM/SPF/DMARC properly configured
- SSL certificates via Let's Encrypt

## Scaling

- Each VPS supports ~100-200 domains
- Use different nameserver pairs per VPS
- Isolate customers by VPS for better deliverability
- Monitor reputation per IP/nameserver

## Support

Check the logs for detailed error messages:
- Mailcow: `/opt/mailcow-dockerized/`
- BIND9: `/var/log/syslog`
- Scripts: Console output during execution