#!/bin/bash
echo -ne "\033]0;OpenWebUI Logs\007"
echo "Starting openwebui logs..."
echo "Press Ctrl+C to stop"
echo "========================================="

sudo journalctl -u open-webui -f

