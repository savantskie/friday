#!/usr/bin/env bash
export MCP_OPENAPI_VERSION="3.0.3"
export OPENWEBUIFRIDAYMCP="true"

# Load API key from file
API_KEY=$(cat /media/nate/Friday/Friday/keys/mcpo_api_key.txt)

# Start mcpo with bearer token authentication
uvx mcpo --host 0.0.0.0 --port 12345 --root-path /mcpo --api-key "$API_KEY" -- /usr/bin/python3 -u /media/nate/Friday/Friday/friday_memory_mcp_server.py
