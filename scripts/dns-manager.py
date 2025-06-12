#!/usr/bin/env python3
"""
DNS Manager for Mailcow BIND9 Integration
Automatically creates and manages BIND9 zone files for domains
"""

import os
import sys
import time
import subprocess
import re
from pathlib import Path

class DNSManager:
    def __init__(self, config_path="/opt/mailcow-management/config.py"):
        self.config = self.load_config(config_path)
        self.bind_config_path = self.config.get('BIND_CONFIG_PATH', '/etc/bind/named.conf.local')
        self.zones_path = self.config.get('BIND_ZONES_PATH', '/etc/bind')
        self.vps_ip = self.config.get('VPS_IP')
        self.ns_base = self.config.get('NS_BASE')
        self.default_ttl = self.config.get('DEFAULT_TTL', 300)
        
    def load_config(self, config_path):
        """Load configuration from config.py file"""
        if not os.path.exists(config_path):
            print(f"Error: Config file not found at {config_path}")
            sys.exit(1)
            
        config = {}
        with open(config_path, 'r') as f:
            content = f.read()
            # Simple config parser - extract key = value pairs
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"\'')
                    if value == 'None':
                        value = None
                    config[key] = value
        return config
    
    def create_zone_file(self, domain, dkim_key=None):
        """Create BIND9 zone file for a domain"""
        serial = int(time.time())
        
        # Basic zone template
        zone_content = f"""$TTL    {self.default_ttl}
@       IN      SOA     ns1.{self.ns_base}. admin.{domain}. (
                     {serial}           ; Serial (timestamp)
                         {self.default_ttl}         ; Refresh
                         {self.default_ttl}         ; Retry
                         604800             ; Expire
                         {self.default_ttl} )       ; Negative Cache TTL

; Name servers
@       IN      NS      ns1.{self.ns_base}.
@       IN      NS      ns2.{self.ns_base}.

; Mail server
@       IN      A       {self.vps_ip}
mail    IN      A       {self.vps_ip}
@       IN      MX      10      mail.{domain}.

; Auto-discovery for mail clients
autodiscover    IN      CNAME   mail
autoconfig      IN      CNAME   mail

; SPF Record
@       IN      TXT     "v=spf1 ip4:{self.vps_ip} mx ~all"

; DMARC Record
_dmarc  IN      TXT     "v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain}; ruf=mailto:dmarc@{domain}; fo=1"
"""

        # Add DKIM record if provided
        if dkim_key:
            # Clean up DKIM key - remove headers and format properly
            clean_key = dkim_key.replace('-----BEGIN PUBLIC KEY-----', '')
            clean_key = clean_key.replace('-----END PUBLIC KEY-----', '')
            clean_key = ''.join(clean_key.split())
            
            zone_content += f"""
; DKIM Record
dkim._domainkey IN      TXT     "v=DKIM1; k=rsa; p={clean_key}"
"""
        
        # Write zone file
        zone_file_path = os.path.join(self.zones_path, f'db.{domain}')
        try:
            with open(zone_file_path, 'w') as f:
                f.write(zone_content)
            print(f"Created zone file: {zone_file_path}")
            return True
        except Exception as e:
            print(f"Error creating zone file for {domain}: {e}")
            return False
    
    def add_zone_to_config(self, domain):
        """Add zone configuration to named.conf.local"""
        zone_config = f"""
zone "{domain}" {{
    type master;
    file "/etc/bind/db.{domain}";
    allow-transfer {{ any; }};
}};
"""
        
        try:
            # Check if zone already exists
            with open(self.bind_config_path, 'r') as f:
                existing_content = f.read()
                if f'zone "{domain}"' in existing_content:
                    print(f"Zone {domain} already exists in BIND config")
                    return True
            
            # Add zone to config
            with open(self.bind_config_path, 'a') as f:
                f.write(zone_config)
            print(f"Added zone {domain} to BIND config")
            return True
        except Exception as e:
            print(f"Error adding zone {domain} to BIND config: {e}")
            return False
    
    def remove_zone(self, domain):
        """Remove zone from BIND configuration and delete zone file"""
        try:
            # Remove from named.conf.local
            with open(self.bind_config_path, 'r') as f:
                lines = f.readlines()
            
            new_lines = []
            skip_zone = False
            
            for line in lines:
                if f'zone "{domain}"' in line:
                    skip_zone = True
                elif skip_zone and '};' in line:
                    skip_zone = False
                    continue
                elif not skip_zone:
                    new_lines.append(line)
            
            with open(self.bind_config_path, 'w') as f:
                f.writelines(new_lines)
            
            # Remove zone file
            zone_file_path = os.path.join(self.zones_path, f'db.{domain}')
            if os.path.exists(zone_file_path):
                os.remove(zone_file_path)
                print(f"Removed zone file: {zone_file_path}")
            
            print(f"Removed zone {domain} from BIND config")
            return True
            
        except Exception as e:
            print(f"Error removing zone {domain}: {e}")
            return False
    
    def reload_bind(self):
        """Reload BIND9 configuration"""
        try:
            # Check configuration first
            result = subprocess.run(['named-checkconf'], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"BIND configuration error: {result.stderr}")
                return False
            
            # Reload BIND9
            result = subprocess.run(['systemctl', 'reload', 'bind9'], capture_output=True, text=True)
            if result.returncode == 0:
                print("BIND9 reloaded successfully")
                return True
            else:
                print(f"Error reloading BIND9: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Error reloading BIND9: {e}")
            return False
    
    def create_domain_dns(self, domain, dkim_key=None):
        """Complete DNS setup for a domain"""
        print(f"Creating DNS records for {domain}...")
        
        # Create zone file
        if not self.create_zone_file(domain, dkim_key):
            return False
        
        # Add to BIND config
        if not self.add_zone_to_config(domain):
            return False
        
        # Reload BIND
        if not self.reload_bind():
            return False
        
        print(f"DNS setup complete for {domain}")
        return True
    
    def list_zones(self):
        """List all configured zones"""
        zones = []
        try:
            with open(self.bind_config_path, 'r') as f:
                content = f.read()
                # Extract zone names using regex
                zone_matches = re.findall(r'zone "([^"]+)"', content)
                zones = [zone for zone in zone_matches if zone != self.ns_base]
            
            print(f"Configured zones ({len(zones)}):")
            for zone in zones:
                print(f"  - {zone}")
            return zones
            
        except Exception as e:
            print(f"Error listing zones: {e}")
            return []
    
    def verify_dns(self, domain):
        """Verify DNS resolution for a domain"""
        try:
            # Check if we can resolve the domain
            result = subprocess.run(['dig', f'@{self.vps_ip}', domain, 'A'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and self.vps_ip in result.stdout:
                print(f"✓ DNS resolution working for {domain}")
                return True
            else:
                print(f"✗ DNS resolution failed for {domain}")
                return False
                
        except Exception as e:
            print(f"Error verifying DNS for {domain}: {e}")
            return False

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 dns-manager.py create <domain> [dkim_key]")
        print("  python3 dns-manager.py remove <domain>")
        print("  python3 dns-manager.py list")
        print("  python3 dns-manager.py verify <domain>")
        print("  python3 dns-manager.py reload")
        sys.exit(1)
    
    dns = DNSManager()
    command = sys.argv[1]
    
    if command == "create":
        if len(sys.argv) < 3:
            print("Error: Domain required")
            sys.exit(1)
        domain = sys.argv[2]
        dkim_key = sys.argv[3] if len(sys.argv) > 3 else None
        dns.create_domain_dns(domain, dkim_key)
        
    elif command == "remove":
        if len(sys.argv) < 3:
            print("Error: Domain required")
            sys.exit(1)
        domain = sys.argv[2]
        dns.remove_zone(domain)
        dns.reload_bind()
        
    elif command == "list":
        dns.list_zones()
        
    elif command == "verify":
        if len(sys.argv) < 3:
            print("Error: Domain required")
            sys.exit(1)
        domain = sys.argv[2]
        dns.verify_dns(domain)
        
    elif command == "reload":
        dns.reload_bind()
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()