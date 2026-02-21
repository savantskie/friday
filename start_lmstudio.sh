#!/bin/bash
# LM Studio Startup Script
# This script starts LM Studio with CPU affinity and shows output

echo "Starting LM Studio..."
echo "Press Ctrl+C to stop LM Studio"
echo "========================================="

Get gpus recocgnized
export HSA_OVERRIDE_GFX_VERSION=9.0.6:11.0.0

# Start LM Studio
/media/nate/Friday/lmstudio/squashfs-root/lm-studio
