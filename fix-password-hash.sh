#!/bin/bash
# fix-password-hash.sh - Fix the specific password hash issue

echo "=== Fixing Mailcow Admin Password Hash ==="

cd /opt/mailcow-dockerized

# Get the database password
DB_PASS=$(grep DBPASS mailcow.conf | cut -d= -f2)

echo "Current admin user status:"
docker compose exec -T mysql-mailcow mysql -umailcow -p"$DB_PASS" mailcow -e "SELECT username, LEFT(password, 20) as password_preview, active FROM admin WHERE username = 'admin';"

echo ""
echo "Updating password hash for admin user..."

# Use the correct SSHA256 hash for 'moohoo'
docker compose exec -T mysql-mailcow mysql -umailcow -p"$DB_PASS" mailcow -e "UPDATE admin SET password = '{SSHA256}K8eVJ6YsZbQCfuJvSUbaQRLr0HPLz5rC9IAp0PAFl0tmNDBkMDc0', modified = NOW() WHERE username = 'admin';"

echo "Updated admin user status:"
docker compose exec -T mysql-mailcow mysql -umailcow -p"$DB_PASS" mailcow -e "SELECT username, LEFT(password, 20) as password_preview, active, modified FROM admin WHERE username = 'admin';"

echo ""
echo "✅ Password hash updated!"
echo "Try logging in now with:"
echo "Username: admin"
echo "Password: moohoo"