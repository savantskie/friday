#!/bin/bash
# Linux version of OpenWebUI Friday MCP launcher
# Use system python3 since we already installed dependencies there
export PYTHONPATH="/media/nate/Friday/Friday:$PYTHONPATH"
uvx mcpo --host 0.0.0.0 --port 12345 -- /usr/bin/python3 -u /media/nate/Friday/Friday/friday_memory_mcp_server.py
