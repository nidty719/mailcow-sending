#!/bin/bash
set -e

CSV_FILE="sample-domains.csv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Testing mailcow domain setup with CSV file: $CSV_FILE"
echo "Working directory: $SCRIPT_DIR"

if [ ! -f "$SCRIPT_DIR/$CSV_FILE" ]; then
    echo "Error: $CSV_FILE not found in $SCRIPT_DIR"
    exit 1
fi

echo "CSV file contents:"
cat "$SCRIPT_DIR/$CSV_FILE"
echo ""

echo "Domains to test:"
tail -n +2 "$SCRIPT_DIR/$CSV_FILE" | cut -d',' -f1 | sort -u

echo ""
echo "Users to create:"
tail -n +2 "$SCRIPT_DIR/$CSV_FILE" | while IFS=',' read -r domain username firstname lastname dailylimit trackingdomain; do
    echo "  $username@$domain (Daily limit: $dailylimit, Tracking: $trackingdomain)"
done

echo ""
echo "Ready to proceed with mailcow setup using this data."