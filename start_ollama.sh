#!/bin/bash
# Ollama Startup Script
# This script starts Ollama server directly (not as a service)

echo "Starting Ollama Server..."
echo "Press Ctrl+C to stop the server"
echo "========================================="

# Set environment variables for optimal performance
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_DEBUG=INFO

# Start Ollama server
/usr/local/bin/ollama serve