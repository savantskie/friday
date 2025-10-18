#!/bin/bash
# Ollama Background Startup Script
# This script starts Ollama server in the background

OLLAMA_PID_FILE="/tmp/ollama.pid"

# Function to check if Ollama is running
check_ollama() {
    if [ -f "$OLLAMA_PID_FILE" ] && kill -0 $(cat "$OLLAMA_PID_FILE") 2>/dev/null; then
        echo "Ollama is already running (PID: $(cat $OLLAMA_PID_FILE))"
        return 0
    else
        return 1
    fi
}

# Function to start Ollama
start_ollama() {
    echo "Starting Ollama Server in background..."
    
    # Set environment variables
    export OLLAMA_HOST=127.0.0.1:11434
    export OLLAMA_DEBUG=INFO
    
    # Start Ollama in background and save PID
    nohup /usr/local/bin/ollama serve > /tmp/ollama.log 2>&1 &
    echo $! > "$OLLAMA_PID_FILE"
    
    sleep 2
    
    if check_ollama; then
        echo "Ollama started successfully!"
        echo "Log file: /tmp/ollama.log"
        echo "To stop: ./stop_ollama.sh"
    else
        echo "Failed to start Ollama"
        return 1
    fi
}

# Function to stop Ollama
stop_ollama() {
    if [ -f "$OLLAMA_PID_FILE" ]; then
        PID=$(cat "$OLLAMA_PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping Ollama (PID: $PID)..."
            kill "$PID"
            rm -f "$OLLAMA_PID_FILE"
            echo "Ollama stopped."
        else
            echo "Ollama process not found."
            rm -f "$OLLAMA_PID_FILE"
        fi
    else
        echo "Ollama PID file not found."
    fi
}

# Check command line argument
case "${1:-start}" in
    start)
        if ! check_ollama; then
            start_ollama
        fi
        ;;
    stop)
        stop_ollama
        ;;
    restart)
        stop_ollama
        sleep 2
        start_ollama
        ;;
    status)
        if check_ollama; then
            echo "Ollama is running (PID: $(cat $OLLAMA_PID_FILE))"
        else
            echo "Ollama is not running"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo "  start   - Start Ollama in background (default)"
        echo "  stop    - Stop Ollama"
        echo "  restart - Restart Ollama"
        echo "  status  - Check if Ollama is running"
        ;;
esac