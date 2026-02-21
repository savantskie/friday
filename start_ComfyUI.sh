#!/bin/bash
# LM Studio Startup Script
# This script starts LM Studio with CPU affinity and shows output

echo "Starting LM ComfyUI..."
echo "Press Ctrl+C to stop LM Studio"
echo "========================================="

export HIP_VISIBLE_DEVICES=1
export HSA_OVERRIDE_GFX_VERSION=9.0.6
export TMPDIR=/media/nate/friday/tmp
cd /media/nate/Friday/ComfyUI
sudo -E python main.py --cache-none --listen 192.168.1.50
