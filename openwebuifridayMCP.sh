#!/usr/bin/env bash
export MCP_OPENAPI_VERSION="3.0.3"
uvx mcpo --host 0.0.0.0 --port 12345 -- /usr/bin/python3 -u /media/nate/Friday/Friday/friday_memory_mcp_server.py

