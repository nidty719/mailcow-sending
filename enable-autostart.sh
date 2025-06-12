#!/bin/bash
# enable-autostart.sh - Enable mailcow auto-start on existing installations

echo "=== Creating Mailcow Auto-Start Service ==="

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

echo "✅ Mailcow auto-start service created and enabled"
echo ""
echo "Commands:"
echo "  Start:  systemctl start mailcow"
echo "  Stop:   systemctl stop mailcow"
echo "  Status: systemctl status mailcow"
echo ""
echo "Mailcow will now automatically start on system reboot"