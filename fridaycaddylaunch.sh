#!/bin/bash
# Linux version of Friday Caddy Launch

sleep 60

# Navigate to the caddy directory
cd /media/nate/Friday/Friday/caddy || { echo "Error: Failed to change directory."; exit 1; }

# Run caddy using the global path
/usr/bin/caddy run --config Caddyfile --watch