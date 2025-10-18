#!/bin/bash
# Friday MCP Server - HTTP launcher for OpenWebUI

cd /media/nate/Friday/Friday
export PYTHONPATH="/media/nate/Friday/Friday:$PYTHONPATH"

echo "Starting Friday MCP Server in HTTP mode..."
echo "Server will be available at: http://localhost:8000/mcp"
echo "For OpenWebUI, configure URL as: http://localhost:8000/mcp"

python3 friday_mcp_http.py