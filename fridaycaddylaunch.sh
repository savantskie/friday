#!/bin/bash
echo -ne "\033]0;Friday Caddy\007"
# Linux version of Friday Caddy Launch
sleep 5

cd /media/nate/Friday/Friday/caddy || { echo "Error: Failed to change directory."; exit 1; }

while true; do
    error_count=0
    while IFS= read -r line; do
        echo "$line"
        if echo "$line" | grep -qi "error"; then
            ((error_count++))
            if [ "$error_count" -ge 15 ]; then
                echo "$(date): 15 errors hit, restarting Caddy..."
                error_count=0
                break
            fi
        fi
    done < <(/usr/bin/caddy run --config Caddyfile --watch 2>&1)
    
    sleep 2
done
