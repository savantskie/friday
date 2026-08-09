#!/usr/bin/env python3
"""
Friday Memory MCP Server

Acts as an interface layer between MCP clients (VS Code, LM Studio, Ollama UIs)
and the Friday Memory System. Provides standardized tools for memory operations
while maintaining client-specific access controls.
"""

import asyncio
import logging

# Configure logging first so we can use it immediately
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Friday Memory MCP Server starting...")
import json
import logging
import sqlite3
import threading
import requests
import aiohttp
from zoneinfo import ZoneInfo
import os
import importlib
import numpy as np
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
import time
import warnings
import traceback
from pathlib import Path

# Get the base directory dynamically - works on both Windows and Linux
def get_base_path():
    """Get the base Friday path, works on both Windows and Linux"""
    current_file = Path(__file__).resolve()
    # This should return /media/nate/Friday/Friday on Linux or F:\Friday on Windows
    return current_file.parent
# MCP imports
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    TextContent,
    Tool,
)

# Local imports (will be implemented)
from friday_memory_system import FridayMemorySystem
from port_manager import PortManager, CallerProgram

# Initialize with dynamic path
BASE_PATH = get_base_path()
memory_system = FridayMemorySystem(data_dir=str(BASE_PATH / "memory_data"))
memory_system.set_llm_config(
    llm_endpoint=os.getenv("LLM_API_ENDPOINT", "http://192.168.1.50:8080/v1/chat/completions"),
    llm_model=os.getenv("LLM_MODEL", "Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced"),
    llm_provider=os.getenv("LLM_PROVIDER", "openai_compatible"),
    llm_api_key=os.getenv("LLM_API_KEY")
)

# Initialize port manager
port_manager = PortManager(memory_data_path=str(BASE_PATH / "memory_data"))

# Custom exception for clean server restart signaling
# Using a regular Exception (not BaseException like SystemExit) allows it to
# propagate cleanly through asyncio tasks without corrupting the event loop.
# The sys.exit(0) is deferred to the outermost level where it is safe to call.
class ServerRestartSignal(Exception):
    """Raised to signal a clean server restart without calling sys.exit() mid-task."""

# ---------- Friday Weather (Open-Meteo) with same-day cache ----------
# Defaults for Motley, MN (no API key; Open-Meteo requires lat/lon)
HOME_LAT = 46.33301
HOME_LON = -94.64384
NATE_HOME = (HOME_LAT,HOME_LON)
HOME_TZ  = "America/Chicago"
ENFORCE_HOME_COORDS = True
# Cache directory (uses weather if set)
import os, json
weather_directory = os.getenv("weather_directory", str(BASE_PATH / "weather_directory"))
WEATHER_CACHE_DIR = os.path.join(weather_directory, "weather")
os.makedirs(WEATHER_CACHE_DIR, exist_ok=True)

def _wx_today_str(tz: str) -> str:
        return datetime.now(ZoneInfo(tz)).date().isoformat()

def _wx_cache_path(tz: str, lat: float, lon: float) -> str:
    day = _wx_today_str(tz)
    key_lat = f"{lat:.3f}"
    key_lon = f"{lon:.3f}"
    return os.path.join(WEATHER_CACHE_DIR, f"openmeteo_{day}{lat}{lon}.json")

def _wx_load(path: str):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None

def _wx_save(path: str, payload: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        pass  # cache failures should never break the tool

_wx_load_cache = _wx_load
_wx_save_cache = _wx_save


from glob import glob
from datetime import datetime, timedelta

def _wx_today_mdy(tz: str) -> str:
    # e.g., "08-27-2025"
    return datetime.now(ZoneInfo(tz)).strftime("%m-%d-%Y")

def _wx_time_HHMM(now: datetime) -> str:
    # e.g., "0900"
    return now.strftime("%H%M")

def _wx_today_glob_mdy(tz: str) -> str:
    # matches openmeteo_MM-DD-YYYY.json and openmeteo_MM-DD-YYYY_*.json
    day = _wx_today_mdy(tz)
    return os.path.join(WEATHER_CACHE_DIR, f"openmeteo_{day}*.json")

def _wx_find_today_latest_file(tz: str) -> str | None:
    paths = glob(_wx_today_glob_mdy(tz))
    if not paths:
        return None
    paths.sort(key=lambda p: os.path.getmtime(p))
    return paths[-1]

def _wx_base_file_today(tz: str) -> str:
    # openmeteo_MM-DD-YYYY.json
    day = _wx_today_mdy(tz)
    return os.path.join(WEATHER_CACHE_DIR, f"openmeteo_{day}.json")

def _wx_timestamped_file_today(tz: str, now_local: datetime) -> str:
    # openmeteo_MM-DD-YYYY_HHMM.json
    day = _wx_today_mdy(tz)
    hhmm = _wx_time_HHMM(now_local)
    return os.path.join(WEATHER_CACHE_DIR, f"openmeteo_{day}_{hhmm}.json")

def _wx_last_updated_iso(payload: dict | None) -> datetime | None:
    if not payload:
        return None
    ts = payload.get("last_updated_at") or payload.get("first_saved_at")
    if not ts:
        return None
    try:
        # supports both "2025-08-27T10:05:00" and "2025-08-27 10:05:00"
        ts = ts.replace("T", " ")
        return datetime.fromisoformat(ts)
    except Exception:
        return None

# --- REQUIRED HELPERS (paste above your class) ---
import os, json
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

# If you already defined these elsewhere, keep your existing ones and skip duplicates.
# --- update windows ---
DEFAULT_UPDATE_WINDOW_MIN = 240   # 4 hours
SEVERE_UPDATE_WINDOW_MIN  = 30    # 30 minutes

def _wx_today_str(tz: str) -> str:
    return datetime.now(ZoneInfo(tz)).date().isoformat()


def _wx_fetch_openmeteo(lat: float, lon: float, tz: str) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation_probability",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": tz,
        "temperature_unit": "fahrenheit",
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    # Build compact hourly (next 48h)
    hourly = []
    hh = data.get("hourly") or {}
    for t, tf, pop in zip(hh.get("time") or [],
                          hh.get("temperature_2m") or [],
                          hh.get("precipitation_probability") or []):
        hourly.append({"time": t, "temp_f": tf, "pop": int(pop) if pop is not None else None})
    hourly = hourly[:48]

    # Build daily
    daily = []
    dd = data.get("daily") or {}
    for d, mx, mn, p in zip(dd.get("time") or [],
                            dd.get("temperature_2m_max") or [],
                            dd.get("temperature_2m_min") or [],
                            dd.get("precipitation_probability_max") or []):
        daily.append({"date": d, "tmax_f": mx, "tmin_f": mn, "pop_max": int(p) if p is not None else None})

    return {
        "source": "open-meteo",
        "tz": tz,
        "latitude": lat,
        "longitude": lon,
        "cached_for_day": _wx_today_str(tz),
        "hourly": hourly,
        "daily": daily
    }


# --- change detection for weather payloads (add-only) ---
from datetime import datetime

def _wx_index_by(items: list[dict], key: str) -> dict:
    out = {}
    for it in items or []:
        k = it.get(key)
        if k is not None:
            out[k] = it
    return out

def _wx_diff_summ(old: dict, new: dict) -> dict:
    """Return only what changed in 'daily' (by date) and 'hourly' (by time)."""
    changes = {"daily_changed": [], "hourly_changed": []}

    # --- daily (by date) ---
    old_d = _wx_index_by((old or {}).get("daily", []), "date")
    new_d = _wx_index_by((new or {}).get("daily", []), "date")
    for date_key, new_row in new_d.items():
        o = old_d.get(date_key)
        if not o:
            changes["daily_changed"].append({"date": date_key, "old": None, "new": new_row})
            continue
        # compare keys we actually set
        fields = ("tmax_c", "tmin_c", "pop_max")
        if any(o.get(f) != new_row.get(f) for f in fields):
            changes["daily_changed"].append({"date": date_key, "old": o, "new": new_row})

    # --- hourly (by time) -> just first 48 like we return
    old_h = _wx_index_by((old or {}).get("hourly", []), "time")
    new_h = _wx_index_by((new or {}).get("hourly", []), "time")
    # to keep this concise, check only overlapping times
    for t_key, new_row in list(new_h.items())[:48]:
        o = old_h.get(t_key)
        if not o:
            changes["hourly_changed"].append({"time": t_key, "old": None, "new": new_row})
            continue
        if (o.get("temp_c") != new_row.get("temp_c")) or (o.get("pop") != new_row.get("pop")):
            changes["hourly_changed"].append({"time": t_key, "old": o, "new": new_row})

    # prune empties
    if not changes["daily_changed"] and not changes["hourly_changed"]:
        return {}
    return changes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FridayMemoryMCPServer:
    def start_memory_system_background(self):
        def run_background():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.memory_system.background_main())
        t = threading.Thread(target=run_background, daemon=True)
        t.start()

    async def get_current_time_tool(self, source: str = "direct") -> Dict:
        """Return the current server time in ISO format (system local time only)"""
        try:
            now_local = datetime.now().isoformat()
            return {
                "success": True,
                "current_time": now_local
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    """MCP Server for Friday's Memory System"""

    async def handle_initialization(self, *args, **kwargs):
        # Call this after LM Studio/OpenWebUI tool registration
        # Start file monitoring and maintenance after 1 minute
        async def delayed_start():
            await asyncio.sleep(60)  # 1 minute
            logger.info("⏳ Starting file monitoring and maintenance after 1 minute...")
            
            # Start file monitoring for auto-reload
            try:
                self._reload_task = asyncio.create_task(self._check_and_reload_modules())
                logger.info("✅ Module file monitoring started (watches for changes to memory system files).")
            except Exception as e:
                logger.error(f"❌ Error starting module file monitoring: {e}")
            
            try:
                await self.memory_system._start_monitoring()
                logger.info("✅ File monitoring started.")
            except Exception as e:
                logger.error(f"❌ Error starting file monitoring: {e}")
            try:
                self._start_automatic_maintenance()
                logger.info("✅ Maintenance scheduled.")
            except Exception as e:
                logger.error(f"❌ Error starting maintenance: {e}")

            # Start OpenWebUI chat import loop
            async def openwebui_import_loop():
                while True:
                    try:
                        logger.info("⏳ Importing OpenWebUI chat history...")
                        await self.memory_system.import_openwebui_chat_history()
                        logger.info("✅ OpenWebUI chat import complete.")
                    except Exception as e:
                        logger.error(f"❌ Error importing OpenWebUI chat: {e}")
                    await asyncio.sleep(3 * 60 * 60)  # 3 hours
            asyncio.create_task(openwebui_import_loop())
        asyncio.create_task(delayed_start())    


    async def _execute_list_available_tags(self, memory_bank: str = None, user_id: str = None, model_id: str = None, source: str = "direct") -> Dict:
        """
        Load tag registry and return available tags with their metadata.
        
        Args:
            memory_bank: Optional filter for specific memory bank
            user_id: User ID for logging
            model_id: Model ID for model isolation
            
        Returns:
            Dict with available tags, canonical forms, variations, and usage counts
        """
        try:
            from tag_manager import TagManager
            from pathlib import Path
            
            tag_manager = TagManager()
            
            # Load the tag registry
            registry_path = Path("/media/nate/Friday/Friday/tag_registry.json")
            registry = tag_manager.load_registry(str(registry_path))
            
            if not registry:
                logger.info("Tag registry is empty or not found")
                return {
                    "status": "success",
                    "tags": {},
                    "summary": {
                        "total_tags": 0,
                        "total_variations": 0
                    }
                }
            
            # Organize results
            result_tags = {}
            
            for canonical, tag_data in registry.items():
                # Add to results
                result_tags[canonical] = tag_data
            
            summary = tag_manager.get_registry_summary()
            
            return {
                "status": "success",
                "tags": result_tags,
                "summary": summary,
                "memory_bank_filter": memory_bank,
                "model_id": model_id,
                "user_id": user_id
            }
            
        except Exception as e:
            logger.error(f"Error listing available tags: {e}")
            return {
                "status": "error",
                "error": f"Failed to retrieve tags: {str(e)}",
                "tags": {}
            }

    async def _execute_list_available_memory_banks(self, user_id: str = None, model_id: str = None, source: str = "direct") -> Dict:
        """
        Load memory_bank registry and return available banks with memory counts.
        
        Args:
            user_id: User ID for logging
            model_id: Model ID for model isolation
            
        Returns:
            Dict with available memory banks and their memory counts
        """
        try:
            from pathlib import Path
            import json
            
            # Load the memory_bank registry
            registry_path = Path("/media/nate/Friday/Friday/memory_bank_registry.json")
            
            if registry_path.exists():
                with open(registry_path, 'r') as f:
                    registry = json.load(f)
            else:
                logger.warning(f"Memory bank registry not found at {registry_path}")
                registry = {}
            
            if not registry:
                logger.info("Memory bank registry is empty or not found")
                return {
                    "status": "success",
                    "banks": {},
                    "total_memories": 0
                }
            
            # Calculate totals
            total_memories = sum(bank.get("memory_count", 0) for bank in registry.values())
            
            return {
                "status": "success",
                "banks": registry,
                "total_memories": total_memories,
                "bank_count": len(registry),
                "model_id": model_id,
                "user_id": user_id
            }
            
        except Exception as e:
            logger.error(f"Error listing available memory banks: {e}")
            return {
                "status": "error",
                "error": f"Failed to retrieve memory banks: {str(e)}",
                "banks": {}
            }

    async def get_reminders(self, limit=5, include_completed=False, days_ahead=30, user_id=None, model_id=None, source=None) -> Dict:
        try:
            # Set defaults for mandatory user/model tracking
            if not user_id:
                user_id = "Nate"
            
            if include_completed:
                # For completed reminders, use memory system's method
                result = await self.memory_system.get_completed_reminders(days=days_ahead, user_id=user_id, model_id=model_id)
                if result["status"] == "success":
                    return {
                        "success": True,
                        "reminders": [
                            {
                                "id": r["reminder_id"],
                                "content": r["content"],
                                "due": r["due_datetime"],
                                "completed": True,
                                "priority": r.get("priority_level", 5)
                            } for r in result["reminders"][:limit]
                        ]
                    }
            else:
                # For active reminders, use memory system's method
                result = await self.memory_system.get_active_reminders(limit=limit, days_ahead=days_ahead, user_id=user_id, model_id=model_id)
                if result["status"] == "success":
                    return {
                        "success": True,
                        "reminders": [
                            {
                                "id": r["reminder_id"],
                                "content": r["content"],
                                "due": r["due_datetime"],
                                "completed": False,
                                "priority": r["priority_level"]
                            } for r in result["reminders"]
                        ]
                    }
            
            return {"success": True, "reminders": []}
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    
    def __init__(self):
        self.memory_data_dir = BASE_PATH / "memory_data"
        self.memory_system = FridayMemorySystem(data_dir=str(self.memory_data_dir))
        self.memory_system.set_llm_config(
            llm_endpoint=os.getenv("LLM_API_ENDPOINT", "http://192.168.1.50:8080/v1/chat/completions"),
            llm_model=os.getenv("LLM_MODEL", "Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced"),
            llm_provider=os.getenv("LLM_PROVIDER", "openai_compatible"),
            llm_api_key=os.getenv("LLM_API_KEY")
        )
        self.server = Server("friday-memory")
        self.client_context = {}  # Track client-specific context
        self._maintenance_task = None  # Background maintenance task
        self._http_server_task = None  # HTTP API server task (for graceful shutdown)
        # Semaphore to limit concurrent database/embedding access (prevents system freeze)
        # Allows up to 3 simultaneous operations, queues the rest
        self.db_semaphore = asyncio.Semaphore(3)
        if not isinstance(self.memory_data_dir, Path):
            self.memory_data_dir = Path(self.memory_data_dir)       
        self.schedule_db_path = str(self.memory_data_dir / "schedule.db")
        # Enable debug logging for MCP server
        logging.getLogger("mcp.server").setLevel(logging.DEBUG)
        # File monitoring for auto-reload
        self._module_watch_times = {}
        self._reload_task = None
        self._is_reloading = False
        # File monitoring runs on the main event loop via asyncio.gather in main()
        
        self._register_handlers()
        # Do NOT start maintenance or file monitoring here
        logger.info("FridayMemoryMCPServer initialized successfully (Semaphore: 3 concurrent DB ops max)")
    
    def _initialize_reminders_database(self):
        """Initialize the dedicated reminders database"""
        try:
            # Make sure the directory exists
            self.memory_data_dir.mkdir(exist_ok=True)
            
            with sqlite3.connect(self.schedule_db_path) as conn:
                cursor = conn.cursor()
                
                # Create reminders table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS reminders (
                        reminder_id TEXT PRIMARY KEY,
                        timestamp_created TEXT NOT NULL,
                        due_datetime TEXT NOT NULL,
                        content TEXT NOT NULL,
                        priority_level INTEGER DEFAULT 5,
                        completed INTEGER DEFAULT 0,
                        source_conversation_id TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for faster queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_reminders_due_datetime 
                    ON reminders(due_datetime)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_reminders_completed 
                    ON reminders(completed)
                """)
                
                conn.commit()
                print(f"✅ Reminders database initialized at: {self.schedule_db_path}")
                
        except Exception as e:
            print(f"❌ Error initializing reminders database: {e}")
            raise
    

    async def _check_and_reload_modules(self):
        """Monitor source files and reload modules if they change"""
        files_to_watch = [
            BASE_PATH / "friday_memory_system.py",
            BASE_PATH / "friday_memory_mcp_server.py"
        ]
        
        while True:
            try:
                await asyncio.sleep(2)  # Check every 2 seconds
                
                any_changed = False
                for filepath in files_to_watch:
                    if not filepath.exists():
                        continue
                    
                    try:
                        current_mtime = filepath.stat().st_mtime
                        last_mtime = self._module_watch_times.get(str(filepath))
                        
                        if last_mtime is None:
                            # First time seeing this file
                            self._module_watch_times[str(filepath)] = current_mtime
                        elif current_mtime > last_mtime:
                            # File has changed!
                            any_changed = True
                            logger.info(f"📝 Detected change in {filepath.name}")
                            self._module_watch_times[str(filepath)] = current_mtime
                    except Exception as e:
                        logger.debug(f"Error checking {filepath.name}: {e}")
                        continue
                
                if any_changed and not self._is_reloading:
                    await self._reload_memory_modules()
                    
            except asyncio.CancelledError:
                logger.info("📁 File monitoring task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in file monitoring: {e}")
                await asyncio.sleep(5)  # Back off on error
    
    async def _reload_memory_modules(self):
        """Reload the memory system modules by restarting the entire server"""
        if self._is_reloading:
            return
        
        self._is_reloading = True
        try:
            logger.info("Detected file changes - restarting MCP server to load latest code...")
            await asyncio.sleep(0.5)  # Brief delay to ensure logs are written
            
            # Cancel HTTP server task if running
            if self._http_server_task and not self._http_server_task.done():
                logger.info("🌐 Cancelling HTTP API server...")
                self._http_server_task.cancel()
                try:
                    await asyncio.wait_for(self._http_server_task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            
            # Cancel maintenance task if running
            if self._maintenance_task and not self._maintenance_task.done():
                logger.info("🔧 Cancelling maintenance task...")
                self._maintenance_task.cancel()
                try:
                    await asyncio.wait_for(self._maintenance_task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            
            # Perform cleanup with timeout
            try:
                logger.info("🧹 Running cleanup...")
                await asyncio.wait_for(self.cleanup(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.error("Cleanup timeout - forcing exit")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
            
            logger.info("Gracefully shutting down to restart with latest code...")
            await asyncio.sleep(0.5)  # Allow shutdown logs to flush

            # Signal restart at the outermost level instead of calling sys.exit() in-task
            # ServerRestartSignal propagates up through asyncio cleanly (it is a regular
            # Exception) and is caught by the main block's except handler, which calls
            # sys.exit(0) at the outermost level where it is safe.
            raise ServerRestartSignal()
            
        except Exception as e:
            logger.error(f"Error during restart sequence: {e}")
            self._is_reloading = False


    def _register_handlers(self):
        """Register MCP server handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available tools based on client context"""
            return await self._get_client_tools()
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            """Execute tool based on client and parameters"""
            return await self._execute_tool(name, arguments or {})
    
    async def _get_client_tools(self) -> List[Tool]:
        """Return tools available to the current client"""
        logger.debug("Getting client tools")
        
        # Detect client type based on user agent or connection context
        client_type = self._detect_client_type()
        logger.info(f"Detected client type: {client_type}")
        
        try:
            # Common tools available to all clients (SillyTavern, VS Code, LM Studio, etc.)
            common_tools = [
            
            Tool(
                name="complete_reminder",
                description="Mark a reminder as completed",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "reminder_id": {"type": "string", "description": "ID of the reminder to complete"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["reminder_id", "user_id", "model_id"]
                }
            ),
            Tool(
                name="get_active_reminders",
                description="Get active (not completed) reminders",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of reminders to return", "default": 10},
                        "days_ahead": {"type": "integer", "description": "Only show reminders due within X days", "default": 30},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"]
                }
            ),
            Tool(
                name="get_completed_reminders",
                description="Get recently completed reminders",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Look back X days", "default": 7},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"]
                }
            ),
            Tool(
                name="reschedule_reminder",
                description="Update the due date of a reminder",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "reminder_id": {"type": "string", "description": "ID of the reminder"},
                        "new_due_datetime": {"type": "string", "description": "New ISO datetime (e.g., 2025-08-03T14:00:00Z)"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["reminder_id", "new_due_datetime", "user_id", "model_id"]
                }
            ),
            Tool(
                name="delete_reminder",
                description="Permanently delete a reminder",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "reminder_id": {"type": "string", "description": "ID of the reminder to delete"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["reminder_id", "user_id", "model_id"]
                }
            ),
            Tool(
                name="cancel_appointment",
                description="Cancel a scheduled appointment",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "appointment_id": {"type": "string", "description": "ID of the appointment to cancel"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["appointment_id", "user_id", "model_id"]
                }
            ),
            Tool(
                name="complete_appointment",
                description="Mark an appointment as completed",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "appointment_id": {"type": "string", "description": "ID of the appointment to complete"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["appointment_id", "user_id", "model_id"]
                }
            ),
            Tool(
                name="get_upcoming_appointments",
                description="Get upcoming appointments (not cancelled)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number to return", "default": 5},
                        "days_ahead": {"type": "integer", "description": "Only show within X days", "default": 30},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"]
                }
            ),
            
            Tool(
                name="search_memories",
                description="Search memories using semantic similarity with importance and type filtering, or direct ID lookup. Searches across long-term curated memories, short-term memories, conversations, and schedule. Each result includes a 'source' field (short_term, long_term, conversation, or schedule) for transparency. Either 'query' or 'memory_id' must be provided.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query (required if memory_id not provided)"},
                        "limit": {"type": "integer", "description": "Max results", "default": 10},
                        "database_filter": {"type": "string", "description": "Filter by database type — ai_memories includes both long-term curated and short-term memories", "enum": ["conversations", "ai_memories", "schedule", "all"], "default": "all"},
                        "min_importance": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Minimum importance level to include (1-10)"},
                        "max_importance": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Maximum importance level to include (1-10)"},
                        "memory_type": {"type": "string", "description": "Filter by memory type (e.g., 'safety', 'preference', 'skill', 'general')"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags (OR logic - returns memories matching ANY tag)"},
                        "memory_bank": {"type": "string", "description": "Filter by memory bank (e.g., General, Personal, Work, Context, Tasks)"},
                        "memory_id": {"type": "string", "description": "Direct lookup by memory ID (bypasses semantic search, required if query not provided)"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"]
                }
            ),
            Tool(
                name="search_memories_by_date",
                description="Search all memories and conversations chronologically within a date range. If a query is provided, results are filtered by semantic relevance first then sorted by date. If no query, returns everything in the date range oldest-first. Searches short-term memories, long-term curated memories, and conversation history.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "Start of date range in ISO format e.g. '2024-10-01'"},
                        "end_date": {"type": "string", "description": "End of date range in ISO format e.g. '2024-12-31'"},
                        "query": {"type": "string", "description": "Optional semantic search query to filter results by relevance within the date range"},
                        "limit": {"type": "integer", "description": "Max results to return", "default": 20},
                        "database_filter": {"type": "string", "description": "Filter by database type", "enum": ["all", "ai_memories", "conversations"], "default": "all"},
                        "memory_bank": {"type": "string", "description": "Optional filter by memory bank"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional filter by tags"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"]
                }
            ),
            Tool(
                name="store_conversation",
                description="Store conversation automatically",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Conversation content"},
                        "role": {"type": "string", "description": "Role (user/assistant)"},
                        "session_id": {"type": "string", "description": "Session identifier"},
                        "metadata": {"type": "object", "description": "Additional metadata"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["content", "role", "user_id", "model_id"]
                }
            ),
            Tool(
                name="create_memory",
                description="Create a curated memory entry",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Memory content"},
                        "memory_type": {"type": "string", "description": "Type of memory"},
                        "importance_level": {"type": "integer", "description": "Importance (1-10)", "default": 5},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Memory tags"},
                        "source_conversation_id": {"type": "string", "description": "Source conversation ID"},
                        "memory_bank": {"type": "string", "description": "Memory category (General, Personal, Work, Context, Tasks)", "default": "General"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["content", "user_id", "model_id"]
                }
            ),
            Tool(
                name="update_memory",
                description="Update an existing curated memory",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string", "description": "Memory ID to update"},
                        "content": {"type": "string", "description": "Updated content"},
                        "importance_level": {"type": "integer", "description": "Updated importance"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Updated tags"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["memory_id", "user_id", "model_id"]
                }
            ),
            Tool(
                name="get_conversation_context",
                description="Retrieve conversation context linked to a memory in three modes: snippet (4 msgs before/after), summary (count, date range, first/last msgs), or full (all messages)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string", "description": "ID of the memory to get linked conversation for"},
                        "mode": {"type": "string", "enum": ["snippet", "summary", "full"], "description": "Mode: snippet (default, 4 msgs before/after), summary (overview), or full (all messages)", "default": "snippet"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["memory_id", "user_id", "model_id"]
                }
            ),
            Tool(
                name="create_appointment",
                description="Create an appointment, optionally recurring (e.g., weekly mental health appointments)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Appointment title"},
                        "description": {"type": "string", "description": "Appointment description"},
                        "scheduled_datetime": {"type": "string", "description": "ISO format datetime for first appointment"},
                        "location": {"type": "string", "description": "Location"},
                        "recurrence_pattern": {"type": "string", "description": "Recurrence pattern: 'daily', 'weekly', 'monthly', 'yearly'", "enum": ["daily", "weekly", "monthly", "yearly"]},
                        "recurrence_count": {"type": "integer", "description": "Number of appointments to create (including first), e.g., 12 for 12 weeks", "minimum": 1},
                        "recurrence_end_date": {"type": "string", "description": "End date for recurrences (ISO format), alternative to recurrence_count"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["title", "scheduled_datetime", "user_id", "model_id"]
                }
            ),
            Tool(
                name="create_reminder",
                description="Create a reminder or multiple recurring reminders",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Reminder content"},
                        "due_datetime": {"type": "string", "description": "ISO format datetime"},
                        "priority_level": {"type": "integer", "description": "Priority (1-10)", "default": 5},
                        "recurrence_pattern": {
                            "type": "string", 
                            "enum": ["daily", "weekly", "monthly", "yearly"],
                            "description": "Optional: Pattern for recurring reminders"
                        },
                        "recurrence_count": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 365,
                            "description": "Optional: Number of recurring reminders to create"
                        },
                        "recurrence_end_date": {
                            "type": "string",
                            "description": "Optional: ISO format datetime to stop recurring reminders"
                        },
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["content", "due_datetime", "user_id", "model_id"]
                }
            ),
            Tool(
                name="get_reminders",
                description="Get recent reminders, optionally filtered by date range",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of reminders to return", "default": 5},
                        "include_completed": {"type": "boolean", "description": "Include completed reminders", "default": False},
                        "days_ahead": {"type": "integer", "description": "Only show reminders due within X days", "default": 30},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"]
                }
            ),
            Tool(
                name="get_recent_context",
                description="Get recent conversation context from the last N days",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of recent items", "default": 5},
                        "session_id": {"type": "string", "description": "Specific session ID"},
                        "days_back": {"type": "integer", "description": "Only show messages from the last N days", "default": 7},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"]
                }
            ),
            Tool(
                name="get_system_health",
                description="Get comprehensive system health, statistics, and database status",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"],
                    "additionalProperties": False
                }
            ),
            Tool(
                name="get_error_summary",
                description="Get recent error summary from the short-term memory system — failed operations, LLM errors, embedding failures, and JSON parse issues",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"],
                    "additionalProperties": False
                }
            ),
            Tool(
                name="get_tool_information",
                description="Get tool usage statistics OR tool documentation. Pass mode='documentation' to get descriptions of available tools. Optionally specify tool_name to get docs for a specific tool.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "mode": {"type": "string", "description": "Mode: 'usage' (default) for statistics or 'documentation' for tool descriptions", "default": "usage"},
                        "tool_name": {"type": "string", "description": "Optional: specific tool name to document (only with mode='documentation')"},
                        "days": {"type": "integer", "description": "For usage mode: Days to analyze", "default": 7},
                        "client_id": {"type": "string", "description": "For usage mode: Specific client ID to analyze"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"]
                }
            ),
            Tool(
                name="reflect_on_tool_usage",
                description="AI self-reflection on tool usage patterns and effectiveness",
                inputSchema={
                    "type": "object", 
                    "properties": {
                        "days": {"type": "integer", "description": "Days to analyze", "default": 7},
                        "client_id": {"type": "string", "description": "Specific client ID to analyze"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"]
                }
            ),
            Tool(
                name="get_ai_insights",
                description="Get recent AI self-reflection insights and patterns",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of insights", "default": 5},
                        "insight_type": {"type": "string", "description": "Type of insight to filter"},
                        "query": {"type": "string", "description": "Search query for keywords or phrases in insights"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"]
                }
            )
            ,
            Tool(
                name="store_ai_reflection",
                description="Store an AI self-reflection/insight record (manual write)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "reflection_type": {
                            "type": "string",
                            "description": "Category (e.g., tool_usage_analysis, memory, general)",
                            "default": "general"
                        },
                        "content": {
                            "type": "string",
                            "description": "Freeform write-up of the reflection"
                        },
                        "insights": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Bullet insights derived from the analysis"
                        },
                        "recommendations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Recommended next actions"
                        },
                        "confidence_level": {
                            "type": "number",
                            "description": "Confidence 0.0–1.0",
                            "default": 0.7
                        },
                        "source_period_days": {
                            "type": "integer",
                            "description": "Days of data this reflection summarizes"
                        },
                        "user_id": {
                            "type": "string",
                            "description": "User ID for user separation"
                        },
                        "model_id": {
                            "type": "string",
                            "description": "Model ID for model separation"
                        }
                    },
                    "required": ["content", "user_id", "model_id"],
                    "additionalProperties": False
                }
            )
            ,
            Tool(
                name="write_ai_insights",
                description="Alias of store_ai_reflection — write an AI self-reflection/insight record",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "reflection_type": {
                            "type": "string",
                            "description": "Category (e.g., tool_usage_analysis, memory, general)",
                            "default": "general"
                        },
                        "content": {
                            "type": "string",
                            "description": "Freeform write-up of the reflection"
                        },
                        "insights": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Bullet insights derived from the analysis"
                        },
                        "recommendations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Recommended next actions"
                        },
                        "confidence_level": {
                            "type": "number",
                            "description": "Confidence 0.0–1.0",
                            "default": 0.7
                        },
                        "source_period_days": {
                            "type": "integer",
                            "description": "Days of data this reflection summarizes"
                        },
                        "user_id": {
                            "type": "string",
                            "description": "User ID for user separation"
                        },
                        "model_id": {
                            "type": "string",
                            "description": "Model ID for model separation"
                        }
                    },
                    "required": ["content", "user_id", "model_id"],
                    "additionalProperties": False
                }
            )
            ,
            Tool(
                name="get_current_time",
                description="Get the current server time in ISO format (UTC and local)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"],
                    "additionalProperties": False
                }
            )
            ,
            Tool(
                name="trigger_database_maintenance",
                description="Manually trigger database maintenance (archival, repairs, optimization) outside of the regular 6-hour schedule",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "force": {"type": "boolean", "description": "Force maintenance to run immediately, bypassing any running checks", "default": True},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for user separation"}
                    },
                    "required": ["user_id", "model_id"],
                    "additionalProperties": False
                }
            )
            ,
            Tool(
                name="export_all_tool_calls",
                description="Export all tool calls from current and archived databases for LORA training dataset generation (web-only, not for models)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "output_filename": {"type": "string", "description": "Optional custom filename for export (defaults to timestamp-based name)"},
                        "user_id": {"type": "string", "description": "User ID for logging (required)"},
                        "model_id": {"type": "string", "description": "Model ID for logging (required)"}
                    },
                    "required": ["user_id", "model_id"],
                    "additionalProperties": False
                }
            )
            ,
            Tool(
                name="list_available_tags",
                description="Get list of available tags from registry with their canonical forms, variations, and usage counts",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "memory_bank": {"type": "string", "description": "Filter tags by specific memory bank (optional)"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"]
                }
            )
            ,
            Tool(
                name="list_available_memory_banks",
                description="Get list of available memory banks with memory counts per bank",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"]
                }
            )
            ,
            Tool(
                name="get_appointments",
                description="Get recent appointments, optionally filtered by date range",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of appointments to return", "default": 5},
                        "days_ahead": {"type": "integer", "description": "Only show appointments scheduled within X days", "default": 30},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["user_id", "model_id"]
                }
            )
        ]
        except Exception as e:
            logger.error(f"Error creating common tools: {e}")
            common_tools = []
        
        # VS Code specific tools
        vscode_tools = [
            Tool(
                name="save_development_session",
                description="Save VS Code development session context",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workspace_path": {"type": "string", "description": "Workspace path"},
                        "active_files": {"type": "array", "items": {"type": "string"}, "description": "Active files"},
                        "git_branch": {"type": "string", "description": "Current git branch"},
                        "session_summary": {"type": "string", "description": "Session summary"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["workspace_path", "user_id", "model_id"]
                }
            ),
            Tool(
                name="store_project_insight",
                description="Store development insight or decision",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "insight_type": {"type": "string", "description": "Type of insight"},
                        "content": {"type": "string", "description": "Insight content"},
                        "related_files": {"type": "array", "items": {"type": "string"}, "description": "Related files"},
                        "importance_level": {"type": "integer", "description": "Importance (1-10)", "default": 5},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["content", "user_id", "model_id"]
                }
            ),
            Tool(
                name="search_project_history",
                description="Search VS Code project development history",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results", "default": 10},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["query", "user_id", "model_id"]
                }
            ),
            Tool(
                name="link_code_context",
                description="Link conversation to specific code context",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path"},
                        "function_name": {"type": "string", "description": "Function name"},
                        "description": {"type": "string", "description": "Context description"},
                        "conversation_id": {"type": "string", "description": "Related conversation ID"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["file_path", "description", "user_id", "model_id"]
                }
            ),
            Tool(
                name="get_project_continuity",
                description="Get context to continue development work",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workspace_path": {"type": "string", "description": "Workspace path"},
                        "limit": {"type": "integer", "description": "Context items", "default": 5},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
                    },
                    "required": ["workspace_path", "user_id", "model_id"]
                }
            )
        ]
        
        try:
            # Return appropriate tools based on client type
            if client_type == "sillytavern":
                # SillyTavern gets memory tools + character/roleplay specific tools
                sillytavern_tools = [
                    Tool(
                        name="get_character_context",
                        description="Get relevant context about characters from memory",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "character_name": {"type": "string", "description": "Character name to search for"},
                                "context_type": {"type": "string", "description": "Type of context (personality, relationships, history)"},
                                "limit": {"type": "integer", "description": "Max results", "default": 5},
                                "user_id": {"type": "string", "description": "User ID for user separation"},
                                "model_id": {"type": "string", "description": "Model ID for model separation"}
                            },
                            "required": ["character_name", "user_id", "model_id"]
                        }
                    ),
                    Tool(
                        name="store_roleplay_memory",
                        description="Store important roleplay moments or character developments",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "character_name": {"type": "string", "description": "Character involved"},
                                "event_description": {"type": "string", "description": "What happened"},
                                "importance_level": {"type": "integer", "description": "Importance (1-10)", "default": 5},
                                "tags": {"type": "array", "items": {"type": "string"}, "description": "Relevant tags"},
                                "user_id": {"type": "string", "description": "User ID for user separation"},
                                "model_id": {"type": "string", "description": "Model ID for model separation"}
                            },
                            "required": ["character_name", "event_description", "user_id", "model_id"]
                        }
                    ),
                    Tool(
                        name="search_roleplay_history",
                        description="Search past roleplay interactions and character development",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"},
                                "character_name": {"type": "string", "description": "Focus on specific character"},
                                "limit": {"type": "integer", "description": "Max results", "default": 10},
                                "user_id": {"type": "string", "description": "User ID for user separation"},
                                "model_id": {"type": "string", "description": "Model ID for model separation"}
                            },
                            "required": ["query", "user_id", "model_id"]
                        }
                    )
                ]
                return common_tools + sillytavern_tools
            
            elif client_type == "vscode":
                # VS Code gets development-specific tools
                return common_tools + vscode_tools
            
            else:
                # Default: LM Studio, Ollama UIs, etc. get core memory tools only
                return common_tools
                
        except Exception as e:
            logger.error(f"Error combining tool lists: {e}")
            return []

    def _detect_client_type(self) -> str:
        """Detect the type of MCP client connecting using multiple detection methods
        
        Detection priority:
        1. Port-based detection: OpenWebUI always uses port 12345
        2. Process-based detection: Parent process name (VS Code, LM Studio, Ollama)
        3. Command-line detection: Process arguments
        
        Maps to tool set names:
        - vscode -> VS Code development tools
        - lm_studio -> LM Studio integration
        - openwebui -> OpenWebUI/MCPO integration (port 12345)
        - ollama -> Ollama integration
        - unknown -> Default core memory tools only
        
        NOTE: If caller_program hasn't been detected yet (e.g., during module import),
        this will trigger detection now rather than waiting for HTTP server startup.
        """
        try:
            # Ensure caller program has been detected
            # (It's normally called during start_http_server, but may be called earlier via module import)
            if port_manager.caller_program == CallerProgram.UNKNOWN and not getattr(port_manager, '_detection_attempted', False):
                logger.debug("Caller program not yet detected - running detection now")
                port_manager.detect_caller_program()
                port_manager._detection_attempted = True
            
            # Priority 1: Check if we're running on OpenWebUI's dedicated port (12345)
            # (Only check if port has been set - it won't be during module import)
            if port_manager.active_port and port_manager.active_port == 12345:
                logger.info("🌐 OpenWebUI (MCPO) detected via port 12345 - providing core memory tools")
                return "unknown"  # OpenWebUI gets core tools via port detection
            
            # Priority 2: Use process-based caller detection
            caller = port_manager.caller_program.value
            
            # Map caller program to client type for tool selection
            if caller == "vscode":
                logger.info("📝 VS Code detected (parent: code/electron) - providing development tools")
                return "vscode"
            elif caller == "lm_studio":
                logger.info("🤖 LM Studio detected - providing core memory tools")
                return "unknown"  # LM Studio gets core tools, not platform-specific
            elif caller == "openwebui":
                logger.info("🌐 OpenWebUI detected (process name) - providing core memory tools")
                return "unknown"  # OpenWebUI gets core tools, not platform-specific
            elif caller == "ollama":
                logger.info("🐫 Ollama detected - providing core memory tools")
                return "unknown"  # Ollama gets core tools, not platform-specific
            else:
                logger.info(f"❓ Unknown caller program: {caller} - providing core memory tools")
                return "unknown"
                
        except Exception as e:
            logger.warning(f"Error detecting client type: {e}. Defaulting to core tools.")
            return "unknown"
    
    async def create_reminder_direct(self, content: str, due_datetime: str, 
                                   priority_level: int = 5, source_conversation_id: str = None) -> Dict:
        """Create a reminder directly in schedule database"""
        try:
            created_at = datetime.now().isoformat()
            try:
                datetime.fromisoformat(due_datetime.replace('Z', '+00:00'))
            except ValueError:
                return {
                    "status": "error",
                    "error": "Invalid due_datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
                }
            priority_level = max(1, min(10, priority_level))
            with sqlite3.connect(self.schedule_db_path) as conn:
                cursor = conn.cursor()
                import uuid
                reminder_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO reminders (reminder_id, timestamp_created, due_datetime, content, priority_level, completed, source_conversation_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (reminder_id, created_at, due_datetime, content, priority_level, 0, source_conversation_id, created_at))
                conn.commit()
                print(f"✅ Reminder created with ID: {reminder_id}")
                asyncio.create_task(self._add_embedding_to_reminder(reminder_id, content))
                return {
                    "status": "success",
                    "reminder_id": reminder_id,
                    "message": f"Reminder created successfully",
                    "due_datetime": due_datetime,
                    "priority_level": priority_level
                }
        except Exception as e:
            print(f"❌ Error creating reminder: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
        
    def _get_total_reminders_count(self, include_completed: bool = False) -> int:
        """Get total count of reminders in database"""
        try:
            with sqlite3.connect(self.reminders_db_path) as conn:
                cursor = conn.cursor()
                
                if include_completed:
                    cursor.execute("SELECT COUNT(*) FROM reminders")
                else:
                    cursor.execute("SELECT COUNT(*) FROM reminders WHERE completed = 0")
                
                return cursor.fetchone()[0]
        except:
            return 0
    
    async def _add_embedding_to_reminder(self, reminder_id: int, content: str):
        """Add embedding to a reminder (background task)"""
        try:
            embedding = await self.memory_system.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                with sqlite3.connect(self.schedule_db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE reminders SET embedding = ? WHERE id = ?",
                        (embedding_blob, reminder_id)
                    )
                    conn.commit()
        except Exception as e:
            print(f"⚠️ Could not add embedding to reminder {reminder_id}: {e}")
    
    async def _protected_tool_call(self, coro):
        """Wrap a memory system coroutine with semaphore protection to limit concurrent access"""
        async with self.db_semaphore:
            return await coro
           
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Execute the requested tool with logging for AI self-reflection"""
        import time

        # ---------------------------------------------------------------------
        # MANDATORY PARAMETER VALIDATION: user_id and model_id REQUIRED
        # (Exception: export_all_tool_calls defaults model_id to 'system')
        # ---------------------------------------------------------------------
        # ALL tools must have both user_id and model_id for tracking and debugging
        user_id = arguments.get("user_id")
        model_id = arguments.get("model_id")
        
        # ALL tools require user_id and model_id for logging and tracking
        if not user_id:
            error_msg = (
                "❌ MISSING REQUIRED PARAMETER: user_id\n\n"
                "ALL Friday tools REQUIRE both user_id and model_id for:\n"
                "  • Memory system separation (different users = different memory spaces)\n"
                "  • Model tracking (knowing which model made which changes)\n"
                "  • Failure debugging (tracing issues to specific model/user combinations)\n\n"
                "Please provide user_id in your tool call.\n"
                "Example: { \"user_id\": \"Nate\", \"model_id\": \"Eddie\", ... }"
            )
            logger.error(error_msg)
            return {
                "content": [{"type": "text", "text": error_msg}],
                "success": False,
                "isError": True,
            }
        
        if not model_id:
            error_msg = (
                "❌ MISSING REQUIRED PARAMETER: model_id\n\n"
                "ALL Friday tools REQUIRE both user_id and model_id for:\n"
                "  • Memory system separation (different users = different memory spaces)\n"
                "  • Model tracking (knowing which model made which changes)\n"
                "  • Failure debugging (tracing issues to specific model/user combinations)\n\n"
                "Please provide model_id in your tool call.\n"
                "Example: { \"user_id\": \"Nate\", \"model_id\": \"Eddie\", ... }"
            )
            logger.error(error_msg)
            return {
                "content": [{"type": "text", "text": error_msg}],
                "success": False,
                "isError": True,
            }

        # Log the incoming call with user/model info
        logger.info(f"🔧 Tool called: {tool_name} | user_id={user_id} | model_id={model_id}")

        # ---------------------------------------------------------------------
        # LOG ALL INCOMING TOOL CALLS (for debugging)
        # ---------------------------------------------------------------------
        try:
            log_dir = BASE_PATH / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "tool_calls.log", "a", encoding="utf-8") as _lf:
                import json
                _lf.write(f"{datetime.now().isoformat()} - Tool called: {tool_name}\n")
                _lf.write(f"  user_id: {user_id} | model_id: {model_id}\n")
                _lf.write(f"  Arguments: {json.dumps(arguments, indent=2)}\n")
                _lf.write("-" * 80 + "\n")
        except Exception:
            pass  # best-effort logging

        # Store context for client tracking
        client_id = self.client_context.get("current_client", f"{user_id}_{model_id}")
        
        # Determine source from MCP caller detection
        def get_source_from_caller() -> str:
            """Map MCP caller to source tracking value"""
            try:
                from port_manager import port_manager, CallerProgram
                # Check OpenWebUI port first
                if port_manager.active_port and port_manager.active_port == 12345:
                    return "mcp_openwebui"
                # Check caller program
                caller = port_manager.caller_program.value if port_manager.caller_program else "unknown"
                if caller == "lm_studio":
                    return "mcp_lm_studio"
                elif caller == "vscode":
                    return "mcp_vscode"
                elif caller == "openwebui":
                    return "mcp_openwebui"
                elif caller == "ollama":
                    return "mcp_ollama"
                else:
                    return "mcp_external"  # Default for unknown callers
            except Exception:
                return "mcp_external"  # Fallback
        
        source = get_source_from_caller()

        # Store context for logging but don't modify arguments yet
        def _ensure_user_id(args: Dict[str, Any]) -> None:
            # Only add user_id if it was explicitly provided
            if user_id:
                args["user_id"] = args.get("user_id") or user_id

        def _clean_appointment(appt: Dict[str, Any]) -> Dict[str, Any]:
            """Return only essential appointment fields, no embeddings"""
            return {
                "appointment_id": appt.get("appointment_id"),
                "title": appt.get("title"),
                "scheduled_datetime": appt.get("scheduled_datetime"),
                "duration_minutes": appt.get("duration_minutes"),
                "description": appt.get("description")
            }

        def _apply_model_filter(args: Dict[str, Any], allow_blank_all_models: bool = False) -> None:
            has_model_arg = "model_id" in arguments
            explicit_model = arguments.get("model_id")

            if has_model_arg:
                if explicit_model:
                    args["model_id"] = explicit_model
                elif allow_blank_all_models:
                    args.pop("model_id", None)
                else:
                    args["model_id"] = model_id
                return

            if allow_blank_all_models:
                args.pop("model_id", None)
            else:
                args.setdefault("model_id", model_id)

        start_time = time.perf_counter()

        try:
            # -----------------------------------------------------------------
            # Memory & Context Tools
            # -----------------------------------------------------------------
            if tool_name in ("search_memories", "tool_search_memories_post"):
                # search_memories accepts: query, limit, database_filter, min_importance, max_importance, memory_type, memory_id, tags, memory_bank, user_id, model_id
                allowed_args = {"query", "limit", "database_filter", "min_importance", "max_importance", "memory_type", "memory_id", "tags", "memory_bank", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                result = await self._protected_tool_call(self.memory_system.search_memories(**filtered_args))
                
                # Add source attribution to each result for transparency
                if result.get("status") == "success" and result.get("results"):
                    for search_result in result["results"]:
                        result_type = search_result.get("type", "").lower()
                        if "ai_memory" in result_type or result_type == "memory":
                            # Try to determine if this is short-term or long-term based on other indicators
                            # If it has importance_level field, it's likely long-term curated
                            if search_result.get("data", {}).get("importance_level"):
                                search_result["source"] = "long_term"
                            else:
                                search_result["source"] = "short_term"
                        elif "conversation" in result_type:
                            search_result["source"] = "conversation"
                        elif result_type in ("appointment", "reminder"):
                            search_result["source"] = "schedule"
                        else:
                            search_result["source"] = "unknown"

            elif tool_name in ("create_memory", "tool_create_memory_post"):
                # create_memory accepts: content, memory_type, importance_level, tags, source_conversation_id, memory_bank, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"content", "memory_type", "importance_level", "tags", "source_conversation_id", "memory_bank", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                
                result = await self._protected_tool_call(self.memory_system.create_memory(**filtered_args))

            elif tool_name in ("update_memory", "tool_update_memory_post"):
                # update_memory accepts: memory_id, content, importance_level, tags, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"memory_id", "content", "importance_level", "tags", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.update_memory(**filtered_args))

            elif tool_name in ("get_conversation_context", "tool_get_conversation_context_post"):
                # get_conversation_context accepts: memory_id, mode, user_id, model_id
                allowed_args = {"memory_id", "mode", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                
                # Get mode parameter (default: snippet)
                mode = filtered_args.get("mode", "snippet")
                memory_id = filtered_args.get("memory_id")
                
                if not memory_id:
                    result = {
                        "error": "memory_id is required",
                        "success": False
                    }
                else:
                    try:
                        from friday_memory_system import ConversationDatabase, get_base_path
                        from pathlib import Path
                        conv_db = ConversationDatabase(
                            str(Path(get_base_path()) / "memory_data" / "conversations.db")
                        )
                        
                        # Look up memory in memory_conversation_links
                        links = await conv_db.execute_query(
                            "SELECT conversation_id, metadata FROM memory_conversation_links WHERE memory_id = ? LIMIT 1",
                            (memory_id,)
                        )
                        
                        if not links:
                            result = {
                                "error": "no linked conversation found for this memory",
                                "memory_id": memory_id,
                                "success": False
                            }
                        else:
                            link_record = links[0]
                            conversation_id = link_record.get("conversation_id")
                            link_metadata = link_record.get("metadata", {})
                            if isinstance(link_metadata, str):
                                import json
                                try:
                                    link_metadata = json.loads(link_metadata)
                                except:
                                    link_metadata = {}
                            memory_timestamp = link_metadata.get("timestamp", None)
                            
                            # Query messages from this conversation
                            messages = await conv_db.execute_query(
                                "SELECT id, role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp",
                                (conversation_id,)
                            )
                            
                            if mode == "snippet":
                                # 4 messages before and 4 after the memory's timestamp
                                snippet_messages = []
                                if memory_timestamp:
                                    found_idx = None
                                    for idx, msg in enumerate(messages):
                                        if msg.get("timestamp") == memory_timestamp:
                                            found_idx = idx
                                            break
                                    if found_idx is not None:
                                        start_idx = max(0, found_idx - 4)
                                        end_idx = min(len(messages), found_idx + 5)
                                        snippet_messages = messages[start_idx:end_idx]
                                    else:
                                        # If exact match not found, take last 8
                                        snippet_messages = messages[-8:] if len(messages) >= 8 else messages
                                else:
                                    snippet_messages = messages[-8:] if len(messages) >= 8 else messages
                                
                                result = {
                                    "mode": "snippet",
                                    "conversation_id": conversation_id,
                                    "memory_id": memory_id,
                                    "message_count": len(snippet_messages),
                                    "messages": [{"role": m.get("role"), "content": m.get("content"), "timestamp": m.get("timestamp")} for m in snippet_messages],
                                    "success": True
                                }
                            
                            elif mode == "summary":
                                # Count, date range, first and last messages
                                first_msg = messages[0] if messages else None
                                last_msg = messages[-1] if messages else None
                                date_range = None
                                if first_msg and last_msg:
                                    date_range = f"{first_msg.get('timestamp', 'unknown')} to {last_msg.get('timestamp', 'unknown')}"
                                
                                result = {
                                    "mode": "summary",
                                    "conversation_id": conversation_id,
                                    "memory_id": memory_id,
                                    "total_messages": len(messages),
                                    "date_range": date_range,
                                    "first_message": {"role": first_msg.get("role"), "content": first_msg.get("content")[:200]} if first_msg else None,
                                    "last_message": {"role": last_msg.get("role"), "content": last_msg.get("content")[:200]} if last_msg else None,
                                    "success": True
                                }
                            
                            elif mode == "full":
                                # All messages chronologically
                                result = {
                                    "mode": "full",
                                    "conversation_id": conversation_id,
                                    "memory_id": memory_id,
                                    "message_count": len(messages),
                                    "messages": [{"role": m.get("role"), "content": m.get("content"), "timestamp": m.get("timestamp")} for m in messages],
                                    "success": True
                                }
                            else:
                                result = {
                                    "error": f"unknown mode: {mode}",
                                    "success": False
                                }
                    except Exception as e:
                        logger.error(f"Error retrieving conversation context: {e}\n{traceback.format_exc()}")
                        result = {
                            "error": str(e),
                            "memory_id": memory_id,
                            "success": False
                        }
            elif tool_name in ("search_memories_by_date", "tool_search_memories_by_date_post"):
                allowed_args = {"start_date", "end_date", "query", "limit", "database_filter", "memory_bank", "tags", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                result = await self._protected_tool_call(self.memory_system.search_memories_by_date(**filtered_args))
                
            elif tool_name in ("get_recent_context", "tool_get_recent_context_post"):
                # get_recent_context accepts: limit, session_id, days_back, user_id, model_id
                allowed_args = {"limit", "session_id", "days_back", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                _ensure_user_id(filtered_args)
                _apply_model_filter(filtered_args, allow_blank_all_models=True)
                result = await self._protected_tool_call(self.memory_system.get_recent_context(**filtered_args))

            elif tool_name == "store_conversation":
                # store_conversation accepts: content, role, session_id, metadata, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"content", "role", "session_id", "metadata", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.store_conversation(**filtered_args))

            elif tool_name == "store_ai_reflection" or tool_name == "write_ai_insights":
                try:
                    # store_ai_reflection accepts: reflection_type, content, insights, recommendations, confidence_level, source_period_days, user_id, model_id, source
                    # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                    allowed_args = {"reflection_type", "content", "insights", "recommendations", "confidence_level", "source_period_days", "user_id", "model_id"}
                    filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                    # Ensure user_id and model_id are provided
                    if user_id:
                        filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                    if model_id:
                        filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                    # Auto-inject source based on where the call originated (completely transparent to model)
                    filtered_args["source"] = source
                    reflection_id = await self._protected_tool_call(self.memory_system.mcp_db.store_ai_reflection(**filtered_args))
                    result = {"status": "success", "reflection_id": reflection_id}
                except Exception as e:
                    logger.error(f"Error storing AI reflection: {e}")
                    result = {"status": "error", "message": f"Failed to store AI reflection: {str(e)}"}

            elif tool_name == "get_ai_insights":
                try:
                    # get_ai_insights accepts: limit, insight_type, query, user_id, model_id
                    allowed_args = {"limit", "insight_type", "query", "user_id", "model_id"}
                    filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                    # Ensure user_id and model_id are provided
                    if user_id:
                        filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                    if model_id:
                        filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                    query = arguments.get("query", "").lower()
                    result = await self._protected_tool_call(self.memory_system.get_ai_insights(**{k: v for k, v in filtered_args.items() if k != "query"}))
                    
                    # Filter results if query is provided
                    if query and "reflections" in result:
                        filtered_reflections = []
                        for reflection in result["reflections"]:
                            content = reflection.get("content", "").lower()
                            insights = reflection.get("insights", [])
                            if query in content or any(query in insight.lower() for insight in insights):
                                filtered_reflections.append(reflection)
                        result["reflections"] = filtered_reflections
                        result["count"] = len(filtered_reflections)
                        
                except Exception as e:
                    logger.error(f"Error getting AI insights: {e}")
                    result = {"status": "error", "message": f"Failed to get AI insights: {str(e)}", "reflections": [], "count": 0}

            elif tool_name == "get_character_context":
                # get_character_context accepts: character_name, context_type, limit, user_id, model_id
                allowed_args = {"character_name", "context_type", "limit", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                result = await self._protected_tool_call(self.memory_system.get_character_context(**filtered_args))

            # -----------------------------------------------------------------
            # Reminder & Appointment Tools
            # -----------------------------------------------------------------
            elif tool_name == "create_appointment":
                # create_appointment accepts: title, description, scheduled_datetime, location, recurrence_pattern, recurrence_count, recurrence_end_date, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"title", "description", "scheduled_datetime", "location", "recurrence_pattern", "recurrence_count", "recurrence_end_date", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.create_appointment(**filtered_args))
            elif tool_name == "cancel_appointment":
                # cancel_appointment accepts: appointment_id, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"appointment_id", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.cancel_appointment(**filtered_args))
            elif tool_name == "complete_appointment":
                # complete_appointment accepts: appointment_id, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"appointment_id", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.complete_appointment(**filtered_args))
            elif tool_name == "list_available_tags":
                # list_available_tags accepts: memory_bank (optional), user_id, model_id
                allowed_args = {"memory_bank", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                _ensure_user_id(filtered_args)
                _apply_model_filter(filtered_args, allow_blank_all_models=True)
                result = await self._protected_tool_call(self._execute_list_available_tags(**filtered_args))
            elif tool_name == "list_available_memory_banks":
                # list_available_memory_banks accepts: user_id, model_id
                allowed_args = {"user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                _ensure_user_id(filtered_args)
                _apply_model_filter(filtered_args, allow_blank_all_models=True)
                result = await self._protected_tool_call(self._execute_list_available_memory_banks(**filtered_args))
            elif tool_name == "get_appointments":
                # get_appointments accepts: limit, days_ahead, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"limit", "days_ahead", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                _ensure_user_id(filtered_args)
                _apply_model_filter(filtered_args, allow_blank_all_models=True)
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.get_appointments(**filtered_args))
                # Clean appointment data - remove embeddings and internal fields
                if result.get("status") == "success" and "appointments" in result:
                    result["appointments"] = [_clean_appointment(appt) for appt in result["appointments"]]
            elif tool_name == "get_upcoming_appointments":
                # get_upcoming_appointments accepts: limit, days_ahead, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"limit", "days_ahead", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                _ensure_user_id(filtered_args)
                _apply_model_filter(filtered_args, allow_blank_all_models=True)
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.get_upcoming_appointments(**filtered_args))
                # Clean appointment data - remove embeddings and internal fields
                if result.get("status") == "success" and "appointments" in result:
                    result["appointments"] = [_clean_appointment(appt) for appt in result["appointments"]]
            elif tool_name == "create_reminder":
                # create_reminder accepts: content, due_datetime, priority_level, recurrence_pattern, recurrence_count, recurrence_end_date, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"content", "due_datetime", "priority_level", "recurrence_pattern", "recurrence_count", "recurrence_end_date", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.create_reminder(**filtered_args))
            elif tool_name == "reschedule_reminder":
                # reschedule_reminder accepts: reminder_id, new_due_datetime, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"reminder_id", "new_due_datetime", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.reschedule_reminder(**filtered_args))
            elif tool_name == "complete_reminder":
                # complete_reminder accepts: reminder_id, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"reminder_id", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.complete_reminder(**filtered_args))
            elif tool_name == "get_active_reminders":
                # get_active_reminders accepts: limit, days_ahead, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"limit", "days_ahead", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                _ensure_user_id(filtered_args)
                _apply_model_filter(filtered_args, allow_blank_all_models=True)
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.get_active_reminders(**filtered_args))
            elif tool_name == "get_completed_reminders":
                # get_completed_reminders accepts: days, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"days", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                _ensure_user_id(filtered_args)
                _apply_model_filter(filtered_args, allow_blank_all_models=True)
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.get_completed_reminders(**filtered_args))
            elif tool_name == "delete_reminder":
                # delete_reminder accepts: reminder_id, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"reminder_id", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.delete_reminder(**filtered_args))
            elif tool_name == "get_reminders":
                # get_reminders accepts: limit, include_completed, days_ahead, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"limit", "include_completed", "days_ahead", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                _ensure_user_id(filtered_args)
                _apply_model_filter(filtered_args, allow_blank_all_models=True)
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self.get_reminders(**filtered_args)

            # -----------------------------------------------------------------
            # Project / System Tools
            # -----------------------------------------------------------------
            elif tool_name == "get_system_health":
                result = await self._protected_tool_call(self.memory_system.get_system_health(source=source))
            elif tool_name == "get_error_summary":
                result = await self._protected_tool_call(self.memory_system.get_error_summary(source=source))
            elif tool_name == "save_development_session":
                # save_development_session accepts: workspace_path, active_files, git_branch, session_summary, user_id, model_id
                allowed_args = {"workspace_path", "active_files", "git_branch", "session_summary", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                result = await self._protected_tool_call(self.memory_system.save_development_session(**filtered_args))
            elif tool_name == "store_project_insight":
                # store_project_insight accepts: insight_type, content, related_files, importance_level, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"insight_type", "content", "related_files", "importance_level", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.store_project_insight(**filtered_args))
            elif tool_name == "search_project_history":
                # search_project_history accepts: query, limit, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"query", "limit", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.search_project_history(**filtered_args))
            elif tool_name == "link_code_context":
                # link_code_context accepts: file_path, function_name, description, conversation_id, user_id, model_id
                allowed_args = {"file_path", "function_name", "description", "conversation_id", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                result = await self._protected_tool_call(self.memory_system.link_code_context(**filtered_args))
            elif tool_name == "get_project_continuity":
                # get_project_continuity accepts: workspace_path, limit, include_archives, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"workspace_path", "limit", "include_archives", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.get_project_continuity(**filtered_args))
            elif tool_name == "get_tool_information":
                # get_tool_information accepts: mode, tool_name, days, client_id, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"mode", "tool_name", "days", "client_id", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                # Add detected client type
                client_type = self._detect_client_type()
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.get_tool_information(client_type=client_type, **filtered_args))
            elif tool_name == "reflect_on_tool_usage":
                # reflect_on_tool_usage accepts: days, client_id, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"days", "client_id", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.reflect_on_tool_usage(**filtered_args))
            elif tool_name == "store_roleplay_memory":
                # store_roleplay_memory accepts: character_name, event_description, importance_level, tags, user_id, model_id
                allowed_args = {"character_name", "event_description", "importance_level", "tags", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                result = await self._protected_tool_call(self.memory_system.store_roleplay_memory(**filtered_args))
            elif tool_name == "search_roleplay_history":
                # search_roleplay_history accepts: query, character_name, limit, user_id, model_id, source
                # Note: 'source' is NOT in allowed_args - it's auto-injected by MCP server based on caller detection
                allowed_args = {"query", "character_name", "limit", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                if user_id:
                    filtered_args["user_id"] = filtered_args.get("user_id") or user_id
                if model_id:
                    filtered_args["model_id"] = filtered_args.get("model_id") or model_id
                # Auto-inject source based on where the call originated (completely transparent to model)
                filtered_args["source"] = source
                result = await self._protected_tool_call(self.memory_system.search_roleplay_history(**filtered_args))

            # -----------------------------------------------------------------
            # Utility Tools
            # -----------------------------------------------------------------
            elif tool_name == "get_current_time":
                result = await self.get_current_time_tool()

            elif tool_name == "export_all_tool_calls":
                # export_all_tool_calls accepts: output_filename (optional), model_id defaults to 'system'
                output_filename = arguments.get("output_filename")
                logger.info(f"Exporting all tool calls for LORA training dataset")
                
                # Force model_id to 'system' for this tool (unless explicitly overridden)
                export_model_id = arguments.get("model_id", "system")
                
                result = await self._protected_tool_call(
                    self.memory_system.export_all_tool_calls(
                        output_filename=output_filename,
                        user_id=user_id,
                        model_id=export_model_id
                    )
                )

            elif tool_name == "trigger_database_maintenance":
                force = arguments.get("force", True)
                logger.info(f"Database maintenance triggered manually (force={force})")
                
                try:
                    await self.memory_system.db_maintenance.run_maintenance(force=force)
                    result = {
                        "status": "success",
                        "message": "Database maintenance completed successfully",
                        "details": {
                            "archival": "Completed (session-based grouping applied)",
                            "repairs": "Completed (archive links checked and repaired)",
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                except Exception as e:
                    logger.error(f"Error running database maintenance: {e}\n{traceback.format_exc()}")
                    result = {
                        "status": "error",
                        "message": f"Database maintenance failed: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }

            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            # -----------------------------------------------------------------
            # Logging & Response Formatting
            # -----------------------------------------------------------------
            end_time = time.perf_counter()
            execution_time_ms = (end_time - start_time) * 1000

            try:
                asyncio.create_task(
                    self.memory_system.log_tool_call(
                        client_id=client_id,
                        tool_name=tool_name,
                        parameters=arguments,
                        execution_time_ms=execution_time_ms,
                        status="success",
                        result=result,
                        source=source,
                    )
                )
            except Exception as log_error:
                logger.warning(f"Could not log tool call: {log_error}")

            # Normalize result to text
            result_text = json.dumps(result, indent=2, default=str) if isinstance(result, (dict, list)) else str(result)

            return {
                "content": [{"type": "text", "text": result_text}],
                "success": True,
                "isError": False,
            }

        # ---------------------------------------------------------------------
        # Error Handling
        # ---------------------------------------------------------------------
        except Exception as e:
            end_time = time.perf_counter()
            execution_time_ms = (end_time - start_time) * 1000
            try:
                asyncio.create_task(
                    self.memory_system.log_tool_call(
                        client_id=client_id,
                        tool_name=tool_name,
                        parameters=arguments,
                        execution_time_ms=execution_time_ms,
                        status="error",
                        error_message=str(e),
                        source=source,
                    )
                )
            except Exception as log_error:
                logger.warning(f"Could not log tool call failure: {log_error}")

            logger.error(f"Error executing tool {tool_name}: {e}")
            return {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "success": False,
                "isError": True,
            }
    
    def _start_automatic_maintenance(self):
        """Start automatic database maintenance background task"""
        try:
            loop = asyncio.get_running_loop()
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            self._maintenance_task = loop.create_task(self._maintenance_loop())

        except RuntimeError:
            logger.warning("Event loop not running. Call `_start_automatic_maintenance()` after loop starts.")
        logger.info("🔧 Automatic database maintenance started")
    
    async def _maintenance_loop(self):
        """Background loop for automatic database maintenance with detailed error reporting"""
        import traceback
        # Initial delay is now handled by delayed_start in handle_initialization
        while True:
            try:
                logger.info("🧹 Running automatic database maintenance...")
                result = await self.memory_system.run_database_maintenance()
                # Log maintenance results
                if result.get("success"):
                    logger.info(f"✅ Automatic maintenance completed - optimized {len(result.get('optimization_results', {}))} databases")
                else:
                    logger.warning(f"⚠️ Automatic maintenance had issues: {result.get('error', 'Unknown error')}")
                    # If error exists, log full result and traceback if present
                    if 'error' in result:
                        logger.error(f"Maintenance error details: {result['error']}")
                        if 'traceback' in result:
                            logger.error(f"Maintenance traceback:\n{result['traceback']}")
            except Exception as e:
                tb = traceback.format_exc()
                logger.error(f"❌ Automatic maintenance failed: {e}\nTraceback:\n{tb}")
                # Optionally, write error details to a file for persistent debugging
                try:
                    with open("maintenance_error.log", "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.now().isoformat()}] Maintenance error: {e}\n{tb}\n\n")
                except Exception as file_err:
                    logger.error(f"Could not write maintenance error log: {file_err}")
            await asyncio.sleep(6 * 60 * 60)
    
    async def cleanup(self):
        """Cleanup resources when server stops with timeout protection"""
        try:
            # Release maintenance claim
            if hasattr(self, '_maintenance_coordinator'):
                self._maintenance_coordinator.release_claim()
            
            # Cancel HTTP server task if still running
            if self._http_server_task and not self._http_server_task.done():
                self._http_server_task.cancel()
                try:
                    await asyncio.wait_for(self._http_server_task, timeout=1.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            
            # Cancel maintenance task if still running
            if self._maintenance_task and not self._maintenance_task.done():
                self._maintenance_task.cancel()
                try:
                    await asyncio.wait_for(self._maintenance_task, timeout=1.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            
            logger.info("🔧 Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


async def start_http_server(mcp_server: FridayMemoryMCPServer, host: str = "127.0.0.1", port: Optional[int] = None):
    """Start the HTTP API server with intelligent port binding
    
    Uses port_manager to:
    - Find an available port (tries primary, then backups)
    - Detect calling program (VS Code, LM Studio, etc.)
    - Save port info for client discovery
    
    Args:
        mcp_server: The MCP server instance
        host: Host to bind to (default 127.0.0.1)
        port: Optional port override. If None, uses port_manager to find one.
    """
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn
        
        # Use port manager to find an available port if not specified
        if port is None:
            try:
                # Detect caller program first
                port_manager.detect_caller_program()
                
                # Find available port
                port = port_manager.find_available_port()
                logger.warning(f"🔍 Using port {port} (caller: {port_manager.caller_program.value})")
                
                # Save port info for clients to discover
                port_manager.save_port_info()
                
            except RuntimeError as e:
                logger.error(f"❌ {e}")
                raise
        
        app = FastAPI(title="Friday Memory API")

        from fastapi import Request, HTTPException

        # Load API key from mcpo_api_key.txt file
        API_KEY = None
        try:
            key_file = BASE_PATH / "keys" / "mcpo_api_key.txt"
            if key_file.exists():
                with open(key_file, 'r') as f:
                    content = f.read().strip()
                    API_KEY = content
                logger.info("✅ Loaded API key from keys/mcpo_api_key.txt")
        except Exception as e:
            logger.error(f"❌ Failed to load API key from file: {e}")
        
        if not API_KEY:
            raise RuntimeError("API Key could not be loaded from keys/mcpo_api_key.txt")

        async def verify_api_key(request: Request):
            client_key = request.headers.get("X-API-Key")
            if client_key != API_KEY:
                raise HTTPException(status_code=403, detail="Forbidden: Invalid or missing API key")

        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        @app.get("/api/health")
        async def health_check():
            """Health check endpoint with server info"""
            process_info = await port_manager.get_process_info()
            
            return {
                "status": "healthy",
                "server": "friday-memory",
                "port": port_manager.active_port,
                "primary_port": port_manager.PRIMARY_PORT,
                "caller_program": port_manager.caller_program.value,
                "process_id": port_manager.process_id,
                "http_url": f"http://127.0.0.1:{port_manager.active_port}",
                "process_name": process_info.get("process_name"),
                "memory_usage_mb": process_info.get("memory_usage_mb")
            }
        
        @app.get("/api/diagnostics")
        async def diagnostics():
            """Diagnostics endpoint showing port and caller info"""
            process_info = await port_manager.get_process_info()
            
            return {
                "server_info": {
                    "active_port": port_manager.active_port,
                    "primary_port": port_manager.PRIMARY_PORT,
                    "backup_ports": port_manager.BACKUP_PORTS,
                    "http_url": f"http://127.0.0.1:{port_manager.active_port}",
                    "caller_program": port_manager.caller_program.value
                },
                "process_info": process_info,
                "message": "MCP server successfully detected caller program and bound to available port"
            }
        
        @app.post("/api/memories/promote")
        async def promote_memory(request: Request):
            """
            Promote a memory from short-term (OpenWebUI) to long-term (Friday Memory System).
            
            Request body:
            {
                "content": "Memory content (required)",
                "user_id": "User identifier (optional, defaults to 'nate')",
                "memory_type": "Optional: memory type",
                "tags": ["optional", "tags"],
                "memory_bank": "Optional: category (General, Personal, Work, Context, Tasks) - default: General",
                "conversation_id": "Optional: source conversation ID for linking",
                "source_conversation_id": "Optional: source conversation ID (deprecated, use conversation_id)",
                "model_id": "Optional: model card name (persona) - extracted from [Model: ...] tag if not provided"
            }
            
            Response:
            {
                "status": "success",
                "memory_id": "new_memory_id",
                "importance_level": 8,
                "memory_bank": "Personal",
                "link_id": "optional_link_id_if_conversation_linked",
                "message": "Memory promoted to long-term storage"
            }
            """
            try:
                # Verify API key
                await verify_api_key(request)
                
                # Parse request body
                body = await request.json()
                content = body.get("content")
                
                if not content or not content.strip():
                    raise HTTPException(status_code=400, detail="Memory content is required")
                
                # Extract required and optional fields
                user_id = body.get("user_id", "nate")  # Default to "nate" if not provided
                
                memory_type = body.get("memory_type")
                tags = body.get("tags", [])
                memory_bank = body.get("memory_bank", "General")
                conversation_id = body.get("conversation_id") or body.get("source_conversation_id")
                model_id = body.get("model_id")
                short_term_memory_id = body.get("memory_id")  # Optional: for link provenance
                
                # Extract model_id from [Model: ...] tag if not provided
                if not model_id:
                    import re
                    model_match = re.search(r'\[Model:\s*([^\]]+)\]', content)
                    if model_match:
                        model_id = model_match.group(1).strip()
                        logger.debug(f"Extracted model_id from content: {model_id}")
                
                if not model_id:
                    model_id = "friday"  # Default to "friday" if not provided
                
                # Strip [Model: ...] tag from content before storing in long-term system
                import re
                cleaned_content = re.sub(r'\s*\[Model:\s*[^\]]+\]', '', content).strip()
                if cleaned_content != content:
                    logger.debug(f"Stripped model tag from promoted memory content")
                
                # Add "promoted" tag to indicate origin
                if isinstance(tags, list):
                    if "promoted" not in tags:
                        tags.append("promoted")
                else:
                    tags = ["promoted"]
                
                # Look up existing links for link provenance (if short-term memory_id provided)
                provenance_metadata = {}
                if short_term_memory_id and mcp_server.memory_system.conversations_db:
                    try:
                        old_links = await mcp_server.memory_system.conversations_db.get_memory_conversation_links(
                            memory_id=short_term_memory_id
                        )
                        if old_links:
                            provenance_metadata = {
                                "previous_link_count": len(old_links),
                                "previous_link_ids": [l["link_id"] for l in old_links],
                                "previous_conversation_ids": list(set(
                                    l["conversation_id"] for l in old_links if l.get("conversation_id")
                                )),
                                "previous_link_types": list(set(
                                    l["link_type"] for l in old_links if l.get("link_type")
                                )),
                            }
                            logger.debug(
                                f"Found {len(old_links)} previous link(s) for memory {short_term_memory_id}, "
                                f"carrying forward provenance metadata"
                            )
                    except Exception as prov_err:
                        logger.debug(f"Link provenance lookup note (non-blocking): {prov_err}")
                
                # Call create_memory with promoted importance level (8-9)
                # Use 8 as default for promoted memories (high but not critical)
                # Store memory with memory_bank category for future enrichment
                # Use cleaned_content (model tag stripped) and model_id from tag or request
                memory_id = await mcp_server.memory_system.create_memory(
                    content=cleaned_content,
                    memory_type=memory_type,
                    importance_level=8,
                    tags=tags,
                    memory_bank=memory_bank,
                    source_conversation_id=conversation_id,
                    user_id=user_id,
                    model_id=model_id,
                    source="openwebui_promotion",  # CHANGE 4B: Mark as promoted from OpenWebUI
                    wait_for_embedding=True  # Ensure embedding completes for promoted memories
                )
                
                # Link memory to conversation if provided (with FK stub support for OpenWebUI chat_id UUIDs)
                link_id = None
                if conversation_id and memory_id:
                    try:
                        link_id = await mcp_server.memory_system.link_memory_to_conversation(
                            memory_id=memory_id,
                            conversation_id=conversation_id,
                            link_type="promoted_from_short_term",
                            link_strength=1.0,
                            source_system="openwebui_promotion",
                            stub_user_id=user_id,
                            stub_model_id=model_id,
                            metadata={
                                "memory_bank": memory_bank,
                                "promoted_at": datetime.now(timezone.utc).isoformat(),
                                "tags": tags,
                                "original_importance": 5,
                                "promotion_importance": 8,
                                "short_term_memory_id": short_term_memory_id,
                                **({"link_provenance": provenance_metadata} if provenance_metadata else {}),
                            }
                        )
                        logger.debug(f"✅ Linked promoted memory {memory_id} to conversation {conversation_id}")
                    except Exception as link_error:
                        logger.warning(f"Could not link promoted memory to conversation (non-blocking): {link_error}")
                        # Don't fail the promotion if linking fails - it's a nice-to-have
                
                # Build response with full context
                result = {
                    "status": "success",
                    "memory_id": memory_id,
                    "importance_level": 8,
                    "memory_bank": memory_bank,
                    "message": "Memory promoted to long-term storage"
                }
                
                if link_id:
                    result["link_id"] = link_id
                    result["message"] += " and linked to conversation"
                
                logger.info(f"✅ Memory promoted: {memory_id} (bank: {memory_bank})")
                return result
                
            except HTTPException:
                raise
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")
            except Exception as e:
                logger.error(f"❌ Error promoting memory: {e}")
                raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
        
        @app.delete("/api/memories/cleanup")
        async def cleanup_test_memories(request: Request):
            """
            Delete test/temporary memories marked with 'test' or 'temporary' tags.
            
            Query parameters:
                tag: "test" or "temporary" (default: "test")
                dry_run: true/false - if true, return count without deleting (default: false)
            
            Response:
            {
                "status": "success",
                "deleted_count": 5,
                "deleted_ids": ["id1", "id2", ...],
                "message": "5 test memories cleaned up"
            }
            """
            try:
                # Verify API key
                await verify_api_key(request)
                
                # Get query parameters
                tag = request.query_params.get("tag", "test")
                dry_run = request.query_params.get("dry_run", "false").lower() == "true"
                
                # Valid cleanup tags
                valid_tags = ["test", "temporary", "promoted"]  # promoted for testing
                if tag not in valid_tags:
                    raise HTTPException(status_code=400, detail=f"Invalid tag: {tag}. Must be one of: {valid_tags}")
                
                # Search for memories with this tag
                search_results = await mcp_server.memory_system.search_memories(
                    query=f"tag:{tag}",
                    limit=1000  # Get up to 1000 test memories
                )
                
                # Extract memory IDs from results
                deleted_ids = []
                
                if dry_run:
                    # Just count and report
                    deleted_count = len(search_results) if search_results else 0
                    logger.info(f"🧹 DRY RUN: Would delete {deleted_count} memories with tag '{tag}'")
                    return {
                        "status": "success",
                        "deleted_count": deleted_count,
                        "deleted_ids": [],
                        "dry_run": True,
                        "message": f"DRY RUN: Would delete {deleted_count} test memories"
                    }
                else:
                    # Actually delete memories
                    if search_results:
                        for result in search_results:
                            memory_id = result.get("memory_id") or result.get("id")
                            if memory_id:
                                try:
                                    await mcp_server.memory_system.ai_memory_db.delete_memory(memory_id)
                                    deleted_ids.append(memory_id)
                                except Exception as e:
                                    logger.warning(f"Failed to delete memory {memory_id}: {e}")
                    
                    deleted_count = len(deleted_ids)
                    logger.info(f"🧹 Cleaned up {deleted_count} memories with tag '{tag}'")
                    
                    return {
                        "status": "success",
                        "deleted_count": deleted_count,
                        "deleted_ids": deleted_ids,
                        "message": f"{deleted_count} test memories cleaned up"
                    }
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"❌ Error cleaning up memories: {e}")
                raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
            
        # -------- MCP over Streamable HTTP (native, replaces mcpo) --------
        from uuid import uuid4
        from mcp.server.models import InitializationOptions
        from mcp.server import NotificationOptions
        from mcp.server.streamable_http import StreamableHTTPServerTransport
        import anyio

        class MCPStreamableSessionManager:
            """Manages Streamable HTTP sessions for the MCP server."""

            def __init__(self, server, api_key):
                self.server = server
                self.api_key = api_key
                self._transports: dict[str, StreamableHTTPServerTransport] = {}
                self._task_group = None

            async def start(self):
                self._task_group = await anyio.create_task_group().__aenter__()

            async def stop(self):
                if self._task_group:
                    await self._task_group.__aexit__(None, None, None)
                    self._task_group = None

            async def handle_request(self, scope, receive, send):
                request = Request(scope, receive)
                session_id = request.headers.get("Mcp-Session-Id")

                if session_id and session_id in self._transports:
                    await self._transports[session_id].handle_request(scope, receive, send)
                    return

                if session_id is None:
                    new_id = uuid4().hex
                    transport = StreamableHTTPServerTransport(
                        mcp_session_id=new_id,
                    )
                    self._transports[new_id] = transport

                    async def run_server(*, task_status):
                        async with transport.connect() as streams:
                            read_stream, write_stream = streams
                            task_status.started()
                            try:
                                await self.server.run(
                                    read_stream,
                                    write_stream,
                                    InitializationOptions(
                                        server_name="friday-memory",
                                        server_version="1.0.0",
                                        capabilities=self.server.get_capabilities(
                                            notification_options=NotificationOptions(),
                                            experimental_capabilities={}
                                        )
                                    ),
                                    stateless=False,
                                )
                            finally:
                                if transport.mcp_session_id in self._transports and not transport.is_terminated:
                                    del self._transports[transport.mcp_session_id]

                    await self._task_group.start(run_server)
                    await transport.handle_request(scope, receive, send)
                else:
                    from starlette.responses import Response
                    response = Response("Invalid session", status_code=400)
                    await response(scope, receive, send)

        session_manager = MCPStreamableSessionManager(mcp_server.server, API_KEY)

        @app.on_event("startup")
        async def start_mcp_streamable():
            await session_manager.start()

        @app.on_event("shutdown")
        async def stop_mcp_streamable():
            await session_manager.stop()

        class MCPASGIHandler:
            def __init__(self, mgr, key):
                self.mgr = mgr
                self.key = key

            async def __call__(self, scope, receive, send):
                headers = dict(scope.get("headers", []))
                api_key = None
                hdr = headers.get(b"x-api-key")
                if hdr:
                    api_key = hdr.decode()
                if not api_key:
                    auth = headers.get(b"authorization", b"").decode()
                    if auth.startswith("Bearer "):
                        api_key = auth[7:]
                if not api_key:
                    qs = scope.get("query_string", b"").decode()
                    for param in qs.split("&"):
                        if param.startswith("api_key="):
                            api_key = param[8:]
                            break
                if api_key != self.key:
                    from starlette.responses import PlainTextResponse
                    resp = PlainTextResponse("Forbidden", status_code=403)
                    await resp(scope, receive, send)
                    return
                await self.mgr.handle_request(scope, receive, send)

        from starlette.routing import Route
        app.router.routes.append(
            Route(
                "/mcp/sse",
                endpoint=MCPASGIHandler(session_manager, API_KEY),
                methods=["GET", "POST", "DELETE"],
            )
        )

        # Create and start server
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        logger.info(f"🌐 HTTP API server ready on http://{host}:{port}")
        await server.serve()
        
    except ImportError:
        logger.info("FastAPI not installed - HTTP API disabled")
        return None
    except Exception as e:
        logger.warning(f"Failed to start HTTP server: {e}")
        return None

async def main():
    """Main entry point for the MCP server"""
    logger.info("Friday Memory MCP Server starting...")
    
    # Set debug logging for MCP components
    logging.getLogger("mcp").setLevel(logging.DEBUG)
    logging.getLogger("mcp.server").setLevel(logging.DEBUG)
    
    srv = FridayMemoryMCPServer()
    logger.debug("Server initialized, starting stdio interface for LM Studio...")
    
    # Claim maintenance ownership — if we win, start background services
    from task_coordinator import TaskCoordinator
    srv._maintenance_coordinator = TaskCoordinator()
    if srv._maintenance_coordinator.setup_claim(str(srv.memory_data_dir)):
        logger.info("MCP server won maintenance claim — starting background services")
        asyncio.create_task(srv.memory_system.background_main())
    else:
        logger.info("Short-term plugin owns maintenance — MCP server skipping background services")
    
    # Start HTTP API server in background
    # Port will be auto-detected and fallback to backups if needed
    srv._http_server_task = asyncio.create_task(
        start_http_server(srv, host="127.0.0.1", port=None)
    )
    
    try:
        from mcp.server.lowlevel.server import InitializationOptions, NotificationOptions
        async with stdio_server() as (read_stream, write_stream):
            # Run MCP server and file monitor concurrently on the main event loop
            server_task = asyncio.create_task(
                srv.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="friday-memory",
                        server_version="1.0.0",
                        capabilities=srv.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )
            )
            monitor_task = asyncio.create_task(srv._check_and_reload_modules())
            
            # Wait for either the server to stop or a file change to trigger restart
            done, pending = await asyncio.wait(
                [server_task, monitor_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel whatever is still running
            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, SystemExit):
                    pass
            
            # Re-raise SystemExit if the monitor triggered a restart
            # (legacy path only; new ServerRestartSignal passes through to outer handler)
            for task in done:
                try:
                    task.result()
                except SystemExit:
                    raise

    except (SystemExit, ServerRestartSignal):
        logger.info("Server restart triggered by file change")
        await srv.cleanup()
        # Clean up port info on shutdown
        port_manager.cleanup_port_info()
        # Exit cleanly at outermost level for supervisor auto-restart.
        # sys.exit() is safe here because we are not inside an asyncio task --
        # we are at the top-level event loop handler.
        import sys
        sys.exit(0)
    except Exception:
        logger.exception("Server error")
        await srv.cleanup()
        # Clean up port info on shutdown
        port_manager.cleanup_port_info()




# ---- MCP STDIO ENTRYPOINT (run main() in background; start MCP correctly) ----
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())




