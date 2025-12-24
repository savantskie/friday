#!/bin/bash
# LM Studio Startup Script
# This script starts LM Studio with CPU affinity and shows output

echo "Starting LM Studio..."
echo "Press Ctrl+C to stop LM Studio"
echo "========================================="

# Start LM Studio pinned to cores 2-7
/media/nate/Friday/lmstudio/squashfs-root/lm-studio
