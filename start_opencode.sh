#!/bin/bash
export PATH="$PATH:/home/nate/.opencode/bin"
echo "Starting OpenCode..."
echo "Press Ctrl+C to stop"
echo "========================================="

cd /media/nate/Friday
#export OPENCODE_HOSTNAME=192.168.1.50
#export OPENCODE_SERVER_USERNAME=savantskie
export OPENCODE_SERVER_PASSWORD=Fuckery103008!@!
OPENCODE_ENABLE_EXA=1 OPENCODE_EXPERIMENTAL_PLAN_MODE=1 opencode #web --port 47291 
