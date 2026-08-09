#!/bin/bash
# friday_cleanup.sh
# Recovery script for llama.cpp context overflow / GPU crash events

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/friday_recovery.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "=== Friday Recovery Script ==="
echo "Timestamp: $TIMESTAMP"
echo ""

# Log the recovery event
echo "[$TIMESTAMP] Recovery script triggered" >> "$LOG_FILE"

# RAM status before
BEFORE=$(free -h | awk '/^Mem:/ {print $3 " used of " $2}')
echo "[BEFORE] RAM: $BEFORE"
echo "[$TIMESTAMP] RAM before: $BEFORE" >> "$LOG_FILE"

# Kill llama.cpp if still running
if pgrep -x "llama-server" > /dev/null 2>&1; then
    echo "[INFO] llama-server still running, killing..."
    sudo pkill -9 -x "llama-server"
    sleep 2
    echo "[INFO] llama-server killed"
    echo "[$TIMESTAMP] llama-server was still running, killed" >> "$LOG_FILE"
else
    echo "[INFO] llama-server not running, skipping kill"
    echo "[$TIMESTAMP] llama-server was already dead" >> "$LOG_FILE"
fi

# Sync and drop caches
echo "[INFO] Syncing and dropping caches..."
sudo sync && sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'
sleep 2

# RAM status after cache drop
AFTER=$(free -h | awk '/^Mem:/ {print $3 " used of " $2}')
echo "[AFTER]  RAM: $AFTER"
echo "[$TIMESTAMP] RAM after cache drop: $AFTER" >> "$LOG_FILE"

# Check GPU state via rocm-smi before attempting restart
echo ""
echo "[INFO] Checking GPU state..."
if ! rocm-smi --showuse > /dev/null 2>&1; then
    echo "[WARNING] rocm-smi check failed, GPUs may not be fully recovered"
    echo "[WARNING] Waiting 10 seconds and trying again..."
    echo "[$TIMESTAMP] GPU check failed on first attempt, waiting..." >> "$LOG_FILE"
    sleep 10
    if ! rocm-smi --showuse > /dev/null 2>&1; then
        echo "[ERROR] GPUs still not responding. Aborting restart."
        echo "[ERROR] Manual intervention may be required."
        echo "[$TIMESTAMP] GPU check failed twice, restart aborted" >> "$LOG_FILE"
        exit 1
    fi
fi
echo "[INFO] GPUs appear healthy"
echo "[$TIMESTAMP] GPU check passed" >> "$LOG_FILE"

# Brief stabilization wait
echo "[INFO] Waiting for full GPU stabilization..."
sleep 5

# Restart llama.cpp via startup script
echo ""
echo "[INFO] Restarting llama.cpp..."
echo "[$TIMESTAMP] Attempting llama.cpp restart" >> "$LOG_FILE"
gnome-terminal --title="llama.cpp" -- bash -c "/media/nate/Friday/Friday/start_llamacpp.sh; exec bash"

# Final status
sleep 3
if pgrep -x "llama-server" > /dev/null 2>&1; then
    echo "[SUCCESS] llama-server is back up"
    echo "[$TIMESTAMP] Recovery successful, llama-server running" >> "$LOG_FILE"
else
    echo "[ERROR] llama-server failed to start, check start_llamacpp.sh manually"
    echo "[$TIMESTAMP] Recovery failed, llama-server not running after restart attempt" >> "$LOG_FILE"
fi

echo ""
echo "=== Recovery Complete ==="
