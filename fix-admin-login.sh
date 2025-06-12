#!/bin/bash
# fix-admin-login.sh - Fix mailcow admin login issues

echo "=== Fixing Mailcow Admin Login ==="

cd /opt/mailcow-dockerized

echo "Step 1: Checking if MySQL is running..."
if ! docker compose ps | grep -q mysql-mailcow; then
    echo "Starting mailcow containers..."
    docker compose up -d
    sleep 20
fi

echo "Step 2: Getting database password..."
DB_PASS=$(grep DBPASS mailcow.conf | cut -d= -f2)
echo "Database password found: ${DB_PASS:0:4}****"

echo "Step 3: Checking current admin users..."
docker compose exec -T mysql-mailcow mysql -umailcow -p"$DB_PASS" mailcow -e "SELECT username, active FROM admin;" 2>/dev/null || echo "Could not query admin table"

echo "Step 4: Deleting existing admin user..."
docker compose exec -T mysql-mailcow mysql -umailcow -p"$DB_PASS" mailcow -e "DELETE FROM admin WHERE username = 'admin';" 2>/dev/null

echo "Step 5: Creating new admin user with password 'moohoo'..."
docker compose exec -T mysql-mailcow mysql -umailcow -p"$DB_PASS" mailcow -e "
INSERT INTO admin (username, password, superadmin, created, modified, active) 
VALUES ('admin', '{SSHA256}K8eVJ6YsZbQCfuJvSUbaQRLr0HPLz5rC9IAp0PAFl0tmNDBkMDc0', 1, NOW(), NOW(), 1);
" 2>/dev/null

echo "Step 6: Verifying admin user creation..."
docker compose exec -T mysql-mailcow mysql -umailcow -p"$DB_PASS" mailcow -e "SELECT username, superadmin, active FROM admin WHERE username = 'admin';" 2>/dev/null

echo "Step 7: Restarting web containers..."
docker compose restart nginx-mailcow php-fpm-mailcow

echo ""
echo "✅ Admin login fix completed!"
echo ""
echo "Wait 30 seconds, then try logging in with:"
echo "Username: admin"
echo "Password: moohoo"
echo ""
echo "Access: https://198.46.215.234"
echo ""
echo "If login still fails, check the logs:"
echo "docker compose logs nginx-mailcow php-fpm-mailcow"