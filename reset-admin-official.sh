#!/bin/bash
# reset-admin-official.sh - Use mailcow's official admin reset script

echo "=== Using Mailcow's Official Admin Reset Script ==="

cd /opt/mailcow-dockerized

echo "Checking if mailcow-reset-admin.sh exists..."

if [ -f "./helper-scripts/mailcow-reset-admin.sh" ]; then
    echo "Found official reset script in helper-scripts/"
    echo "Running mailcow's official admin reset..."
    ./helper-scripts/mailcow-reset-admin.sh
elif [ -f "./mailcow-reset-admin.sh" ]; then
    echo "Found reset script in root directory (older installation)"
    echo "Running mailcow's official admin reset..."
    ./mailcow-reset-admin.sh
else
    echo "Official reset script not found. Let's try manual method..."
    echo ""
    echo "Manual admin reset using mailcow's documented method:"
    
    # Source the config
    source mailcow.conf
    
    # Reset admin using the official documented SQL method
    docker compose exec mysql-mailcow mysql -u${DBUSER} -p${DBPASS} ${DBNAME} -e "UPDATE admin SET password = '{SSHA256}K8eVJ6YsZbQCfuJvSUbaQRLr0HPLz5rC9IAp0PAFl0tmNDBkMDc0' WHERE username = 'admin';"
    
    echo "✅ Admin password reset to: moohoo"
    echo "Username: admin"
    echo "Password: moohoo"
fi

echo ""
echo "If the official script was used, it provided you with a new random password."
echo "Make sure to save that password securely!"