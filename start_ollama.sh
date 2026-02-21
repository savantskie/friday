#!/bin/bash
# Ollama Startup Script

echo "Starting Ollama Server..."
echo "Press Ctrl+C to stop the server"
echo "========================================="

# Force Vulkan backend to support both gfx906 and gfx1100
export OLLAMA_VULKAN=1

# Set environment variables for optimal performance
export OLLAMA_HOST=0.0.0.0:11434
export OLLAMA_DEBUG=INFO

# Start Ollama server
/usr/local/bin/ollama serve
