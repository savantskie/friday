#!/bin/bash
echo "Starting Signal CLI Daemon..."
echo "Press Ctrl+C to stop"
echo "========================================="

wmctrl -r "Signal CLI Daemon" -e 0,4220,0,-1,-1 &
signal-cli -u +12185398360 daemon --http 127.0.0.1:8090
