#!/bin/sh
# */30 * * * *  /opt/scripts/disk_alert.sh
# Pings the team chat webhook when the root disk is over 90% full.
USAGE=$(df / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$USAGE" -gt 90 ]; then
  curl -s -X POST -H 'Content-Type: application/json' \
    -d "{\"text\": \"Disk on $(hostname) is ${USAGE}% full\"}" \
    https://chat.example.com/hooks/ops-alerts
fi
