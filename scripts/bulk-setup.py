#!/usr/bin/env python3
"""
Bulk Setup Script for Mailcow Domains and Mailboxes
Processes CSV input and creates domains, mailboxes, and DNS records
"""

import os
import sys
import csv
import json
import time
import requests
import secrets
import string
from pathlib import Path
import subprocess

# Import our DNS manager
sys.path.append('/opt/mailcow-management')
try:
    from dns_manager import DNSManager
except ImportError:
    # If running from development, try local import
    try:
        from scripts.dns_manager import DNSManager
    except ImportError:
        print("Error: dns_manager.py not found. Make sure it's in the same directory or installed.")
        sys.exit(1)

class MailcowManager:
    def __init__(self, config_path="/opt/mailcow-management/config.py"):
        self.config = self.load_config(config_path)
        self.api_url = self.config.get('MAILCOW_API_URL')
        self.api_key = self.config.get('MAILCOW_API_KEY')
        self.vps_ip = self.config.get('VPS_IP')
        self.ns_base = self.config.get('NS_BASE')
        
        if not self.api_key:
            print("Error: MAILCOW_API_KEY not set in config.py")
            print("Please generate an API key in Mailcow admin panel and update config.py")
            sys.exit(1)
            
        self.dns_manager = DNSManager(config_path)
        
    def load_config(self, config_path):
        """Load configuration from config.py file"""
        if not os.path.exists(config_path):
            print(f"Error: Config file not found at {config_path}")
            sys.exit(1)
            
        config = {}
        with open(config_path, 'r') as f:
            content = f.read()
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
    
    def generate_password(self, length=16):
        """Generate a secure random password"""
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(characters) for _ in range(length))
    
    def api_request(self, endpoint, method='GET', data=None):
        """Make API request to Mailcow"""
        url = f"{self.api_url}/{endpoint}"
        headers = {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, verify=False, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, verify=False, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, json=data, verify=False, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            return response
            
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return None
    
    def create_domain(self, domain):
        """Create domain in Mailcow"""
        print(f"Creating domain: {domain}")
        
        data = {
            "domain": domain,
            "description": f"Domain for {domain}",
            "aliases": 400,
            "mailboxes": 10,
            "defquota": 3072,
            "maxquota": 10240,
            "quota": 10240,
            "active": 1,
            "rl_value": 10,
            "rl_frame": "s",
            "backupmx": 0,
            "relay_all_recipients": 0
        }
        
        response = self.api_request('domain', 'POST', data)
        
        if response and response.status_code == 200:
            result = response.json()
            if result[0]['type'] == 'success':
                print(f"✓ Domain {domain} created successfully")
                return True
            else:
                print(f"✗ Failed to create domain {domain}: {result[0]['msg']}")
                return False
        else:
            print(f"✗ API error creating domain {domain}: {response.status_code if response else 'No response'}")
            return False
    
    def create_mailbox(self, domain, username, first_name, last_name, daily_limit=50):
        """Create mailbox in Mailcow"""
        email = f"{username}@{domain}"
        password = self.generate_password()
        
        print(f"Creating mailbox: {email}")
        
        data = {
            "local_part": username,
            "domain": domain,
            "name": f"{first_name} {last_name}",
            "password": password,
            "password2": password,
            "quota": 3072,
            "active": 1,
            "force_pw_update": 0,
            "tls_enforce_in": 0,
            "tls_enforce_out": 0
        }
        
        response = self.api_request('mailbox', 'POST', data)
        
        if response and response.status_code == 200:
            result = response.json()
            if result[0]['type'] == 'success':
                print(f"✓ Mailbox {email} created successfully")
                return {
                    'email': email,
                    'password': password,
                    'first_name': first_name,
                    'last_name': last_name,
                    'daily_limit': daily_limit
                }
            else:
                print(f"✗ Failed to create mailbox {email}: {result[0]['msg']}")
                return None
        else:
            print(f"✗ API error creating mailbox {email}: {response.status_code if response else 'No response'}")
            return None
    
    def get_dkim_key(self, domain):
        """Get DKIM public key for domain"""
        print(f"Retrieving DKIM key for {domain}")
        
        response = self.api_request(f'dkim/{domain}')
        
        if response and response.status_code == 200:
            result = response.json()
            if result and len(result) > 0:
                dkim_data = result[0]
                if 'pubkey' in dkim_data:
                    print(f"✓ Retrieved DKIM key for {domain}")
                    return dkim_data['pubkey']
                else:
                    print(f"✗ No DKIM public key found for {domain}")
                    return None
            else:
                print(f"✗ No DKIM data found for {domain}")
                return None
        else:
            print(f"✗ API error retrieving DKIM for {domain}: {response.status_code if response else 'No response'}")
            return None
    
    def process_csv(self, csv_file_path):
        """Process CSV file and create domains/mailboxes"""
        if not os.path.exists(csv_file_path):
            print(f"Error: CSV file not found: {csv_file_path}")
            return None
        
        results = []
        domains_created = set()
        
        try:
            with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
                # Try to detect the CSV format
                sample = csvfile.read(1024)
                csvfile.seek(0)
                
                # Check if it looks like our expected format
                if 'Domain' in sample and 'Username' in sample:
                    # Our simple format: Domain,Username,First Name,Last Name,Daily Limit,Tracking Domain
                    reader = csv.DictReader(csvfile)
                    expected_columns = ['Domain', 'Username', 'First Name', 'Last Name']
                else:
                    print("Error: CSV format not recognized. Expected columns: Domain, Username, First Name, Last Name")
                    return None
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        domain = row['Domain'].strip().lower()
                        username = row['Username'].strip().lower()
                        first_name = row['First Name'].strip()
                        last_name = row['Last Name'].strip()
                        daily_limit = int(row.get('Daily Limit', 50))
                        tracking_domain = row.get('Tracking Domain', f'track.{domain}')
                        
                        if not domain or not username:
                            print(f"Skipping row {row_num}: Missing domain or username")
                            continue
                        
                        # Create domain if not already created
                        if domain not in domains_created:
                            if self.create_domain(domain):
                                domains_created.add(domain)
                                
                                # Wait a bit for domain to be ready
                                time.sleep(2)
                                
                                # Get DKIM key
                                dkim_key = self.get_dkim_key(domain)
                                
                                # Create DNS records
                                self.dns_manager.create_domain_dns(domain, dkim_key)
                                
                                # Wait for DNS propagation
                                time.sleep(1)
                            else:
                                print(f"Failed to create domain {domain}, skipping mailboxes")
                                continue
                        
                        # Create mailbox
                        mailbox_result = self.create_mailbox(domain, username, first_name, last_name, daily_limit)
                        
                        if mailbox_result:
                            # Add additional fields for export
                            mailbox_result.update({
                                'imap_host': f'mail.{self.ns_base}',
                                'imap_port': 993,
                                'smtp_host': f'mail.{self.ns_base}',
                                'smtp_port': 587,
                                'tracking_domain': tracking_domain
                            })
                            results.append(mailbox_result)
                        
                        # Small delay to avoid overwhelming the API
                        time.sleep(0.5)
                        
                    except Exception as e:
                        print(f"Error processing row {row_num}: {e}")
                        continue
                        
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return None
        
        return results
    
    def export_for_cold_email(self, results, output_file):
        """Export results in ReachInbox.ai compatible format"""
        if not results:
            print("No results to export")
            return
        
        print(f"Exporting {len(results)} mailboxes to {output_file}")
        
        # ReachInbox.ai format based on the sample CSV
        fieldnames = [
            'Email', 'First Name', 'Last Name', 'IMAP Username', 'IMAP Password',
            'IMAP Host', 'IMAP Port', 'SMTP Username', 'SMTP Password',
            'SMTP Host', 'SMTP Port', 'Daily Limit', 'Warmup Enabled',
            'Warmup Limit', 'Warmup Increment', 'Tracking Domain',
            'Warmup Filter Tag', 'Warmup On Weekdays', 'Warmup Open Rate',
            'Warmup Spam Protection Rate', 'Warmup Mark As Important Rate'
        ]
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for result in results:
                    row = {
                        'Email': result['email'],
                        'First Name': result['first_name'],
                        'Last Name': result['last_name'],
                        'IMAP Username': result['email'],
                        'IMAP Password': result['password'],
                        'IMAP Host': result['imap_host'],
                        'IMAP Port': result['imap_port'],
                        'SMTP Username': result['email'],
                        'SMTP Password': result['password'],
                        'SMTP Host': result['smtp_host'],
                        'SMTP Port': result['smtp_port'],
                        'Daily Limit': result['daily_limit'],
                        'Warmup Enabled': 'TRUE',
                        'Warmup Limit': 20,
                        'Warmup Increment': 1,
                        'Tracking Domain': result['tracking_domain'],
                        'Warmup Filter Tag': 'shadow',
                        'Warmup On Weekdays': 'TRUE',
                        'Warmup Open Rate': 95,
                        'Warmup Spam Protection Rate': 85,
                        'Warmup Mark As Important Rate': 90
                    }
                    writer.writerow(row)
            
            print(f"✓ Export completed: {output_file}")
            
        except Exception as e:
            print(f"Error exporting results: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 bulk-setup.py <csv_file> [output_file]")
        print("")
        print("CSV Format:")
        print("Domain,Username,First Name,Last Name,Daily Limit,Tracking Domain")
        print("example1.com,john,John,Doe,50,track.example1.com")
        print("example1.com,jane,Jane,Smith,30,track.example1.com")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'mailboxes_export.csv'
    
    # Check if running on VPS or development
    config_path = "/opt/mailcow-management/config.py"
    if not os.path.exists(config_path):
        print("Warning: Running in development mode")
        print("Make sure to configure Mailcow API key before running on VPS")
        # Could create a sample config here for development
    
    manager = MailcowManager(config_path)
    
    print("=== Mailcow Bulk Setup ===")
    print(f"Processing: {csv_file}")
    print(f"Output: {output_file}")
    print("")
    
    # Process CSV file
    results = manager.process_csv(csv_file)
    
    if results:
        # Export results
        manager.export_for_cold_email(results, output_file)
        
        print("")
        print("=== Summary ===")
        print(f"Total mailboxes created: {len(results)}")
        print(f"Export file: {output_file}")
        print("")
        print("Next steps:")
        print("1. Wait 10-15 minutes for DNS propagation")
        print("2. Test email connectivity with one mailbox")
        print("3. Import the CSV file into your cold email tool")
        print("4. Start email warmup process")
    else:
        print("No mailboxes were created. Check the logs above for errors.")

if __name__ == "__main__":
    main()