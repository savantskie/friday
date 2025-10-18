#!/usr/bin/env python3
"""
Friday Memory MCP Server - Streamable HTTP version for OpenWebUI
"""

import asyncio
import sys
from pathlib import Path

# Add the current directory to the path so we can import the MCP server
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP
from friday_memory_system import FridayMemorySystem
import os

# Get the base directory dynamically
def get_base_path():
    return Path(__file__).resolve().parent

BASE_PATH = get_base_path()
memory_system = FridayMemorySystem(data_dir=str(BASE_PATH / "memory_data"))

# Create FastMCP server instance
mcp = FastMCP(
    name="friday-memory",
    host="0.0.0.0",  # Listen on all interfaces
    port=8000,       # Port for the HTTP server
    debug=True
)

# Tool functions
@mcp.tool()
async def get_current_time() -> dict:
    """Return the current server time in readable format"""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    try:
        central_tz = ZoneInfo("America/Chicago")
        now_central = datetime.now(central_tz)
        formatted_time = now_central.strftime("%Y-%m-%d %I:%M:%S %p %Z")
        iso_time = now_central.isoformat()
        
        return {
            "success": True,
            "current_time": formatted_time,
            "iso_time": iso_time,
            "timezone": "America/Chicago"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def search_memories(
    query: str, 
    limit: int = 10,
    min_importance: int = None,
    max_importance: int = None,
    memory_type: str = None,
    database_filter: str = "all"
) -> dict:
    """Search memories using semantic similarity"""
    try:
        result = await memory_system.search_memories(
            query=query,
            limit=limit,
            min_importance=min_importance,
            max_importance=max_importance,
            memory_type=memory_type,
            database_filter=database_filter
        )
        return {"success": True, "memories": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def create_reminder(
    content: str,
    due_datetime: str,
    priority_level: int = 5
) -> dict:
    """Create a reminder"""
    try:
        result = await memory_system.create_reminder(
            content=content,
            due_datetime=due_datetime,
            priority_level=priority_level
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_reminders(
    days_ahead: int = 30,
    include_completed: bool = False,
    limit: int = 5
) -> dict:
    """Get reminders"""
    try:
        result = await memory_system.get_reminders(
            days_ahead=days_ahead,
            include_completed=include_completed,
            limit=limit
        )
        return {"success": True, "reminders": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def brave_web_search(query: str, count: int = 20) -> dict:
    """Execute web search using Brave Search API"""
    # Import Brave search function from main server
    try:
        from friday_memory_mcp_server import brave_web_search as brave_search
        result = await brave_search(query, count)
        return {"success": True, "results": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
async def brave_local_search(query: str, count: int = 20) -> dict:
    """Search for local businesses and places"""
    try:
        from friday_memory_mcp_server import brave_local_search as brave_local
        result = await brave_local(query, count)
        return {"success": True, "results": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    print("Starting Friday Memory MCP Server (Streamable HTTP mode)...")
    print(f"Server will be available at: http://localhost:8000/mcp")
    print("For OpenWebUI, use: http://localhost:8000/mcp")
    
    # Run the server in streamable HTTP mode
    mcp.run(transport="streamable-http")