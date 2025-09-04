#!/usr/bin/env python3
"""
Friday Memory MCP Server

Acts as an interface layer between MCP clients (VS Code, LM Studio, Ollama UIs)
and the Friday Memory System. Provides standardized tools for memory operations
while maintaining client-specific access controls.
"""

print("Friday Memory MCP Server starting...")  # This will show up in stdout immediately

import asyncio
import json
import logging
import sqlite3
import threading
import requests
from zoneinfo import ZoneInfo
import os
import numpy as np
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
import time
import warnings
from pathlib import Path
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
memory_system = FridayMemorySystem(data_dir="F:/Friday/memory_data")

# ---------- Friday Weather (Open-Meteo) with same-day cache ----------
# Defaults for Motley, MN (no API key; Open-Meteo requires lat/lon)
HOME_LAT = 46.33301
HOME_LON = -94.64384
NATE_HOME = (HOME_LAT,HOME_LON)
HOME_TZ  = "America/Chicago"
ENFORCE_HOME_COORDS = True
# Cache directory (uses weather if set)
import os, json
weather_directory = os.getenv("weather_directory", r"F:\Friday\weather_directory")
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
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    # Build compact hourly (next 48h)
    hourly = []
    hh = data.get("hourly") or {}
    for t, tc, pop in zip(hh.get("time") or [],
                          hh.get("temperature_2m") or [],
                          hh.get("precipitation_probability") or []):
        hourly.append({"time": t, "temp_c": tc, "pop": int(pop) if pop is not None else None})
    hourly = hourly[:48]

    # Build daily
    daily = []
    dd = data.get("daily") or {}
    for d, mx, mn, p in zip(dd.get("time") or [],
                            dd.get("temperature_2m_max") or [],
                            dd.get("temperature_2m_min") or [],
                            dd.get("precipitation_probability_max") or []):
        daily.append({"date": d, "tmax_c": mx, "tmin_c": mn, "pop_max": int(p) if p is not None else None})

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

    async def get_current_time_tool(self) -> Dict:
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
        # Start file monitoring and maintenance after 3 minutes
        async def delayed_start():
            await asyncio.sleep(180)  # 3 minutes
            logger.info("⏳ Starting file monitoring and maintenance after 3 minutes...")
            try:
                await self.memory_system.start_file_monitoring()
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

    async def get_weather_open_meteo(self,
                                    latitude: float | None = None,
                                    longitude: float | None = None,
                                    timezone_str: str | None = None,
                                    force_refresh: bool = False,
                                    override: bool = False,
                                    update_today: bool = True,
                                    return_changes_only: bool = False,
                                    severe_update: bool = False) -> dict:
        # Lock to home unless explicitly overridden
        if ENFORCE_HOME_COORDS and not override:
            lat = float(HOME_LAT)
            lon = float(HOME_LON)
            tz  = HOME_TZ if timezone_str is None else timezone_str
        else:
            lat = float(HOME_LAT if latitude is None else latitude)
            lon = float(HOME_LON if longitude is None else longitude)
            tz  = timezone_str or HOME_TZ

        cpath = _wx_cache_path(tz, lat, lon)
        cached = _wx_load(cpath)

        # -------- single-file-per-day, rename after ≥4h logic --------
        now_local = datetime.now(ZoneInfo(tz))

        latest_path = _wx_find_today_latest_file(tz)   # e.g., ...\openmeteo_08-27-2025.json or ..._0900.json
        cached = _wx_load(latest_path) if latest_path else None

        # If we already have today's file and we're not forcing a refresh
        if cached and not force_refresh:
            last_upd = _wx_last_updated_iso(cached)
            within_4h = bool(last_upd and (now_local - last_upd) < timedelta(hours=4))

        # decide the window (4h normal, 30m for severe)
        window_minutes = SEVERE_UPDATE_WINDOW_MIN if severe_update else DEFAULT_UPDATE_WINDOW_MIN

        last_upd = _wx_last_updated_iso(cached) if cached else None
        within_window = bool(last_upd and (now_local - last_upd) < timedelta(minutes=window_minutes))

        if cached and not force_refresh:
            if within_window:
                cached["_via_cache"] = True
                return {"success": True, "data": cached, "updated": False}
            # outside window -> fetch/rename/update as you already do...

            # ≥4h since last update -> fetch fresh, write to a new timestamped filename and delete the old one
            fresh = _wx_fetch_openmeteo(lat, lon, tz)
            diff = _wx_diff_summ(cached, fresh)

            # stamp metadata
            fresh["first_saved_at"] = cached.get("first_saved_at") or now_local.isoformat(timespec="seconds")
            fresh["last_updated_at"] = now_local.isoformat(timespec="seconds")
            fresh["update_count"] = int(cached.get("update_count", 0)) + 1

            # new filename with HHMM
            new_path = _wx_timestamped_file_today(tz, now_local)
            _wx_save(new_path, fresh)

            # delete any other files for today so exactly one remains
            for p in glob(_wx_today_glob_mdy(tz)):
                if p != new_path:
                    try:
                        os.remove(p)
                    except Exception:
                        pass

            if diff:
                fresh["_via_cache"] = False
                fresh["changes"] = diff
                return {"success": True, "data": fresh, "updated": True}
            else:
                fresh["_via_cache"] = False
                fresh["changes"] = {}
                return {"success": True, "data": fresh, "updated": True}

        # No file for today yet, or force refresh -> create the base MM-DD-YYYY.json
        fresh = _wx_fetch_openmeteo(lat, lon, tz)
        now_iso = now_local.isoformat(timespec="seconds")
        fresh.setdefault("first_saved_at", now_iso)
        fresh["last_updated_at"] = now_iso
        fresh["update_count"] = 1

        base_path = _wx_base_file_today(tz)  # openmeteo_MM-DD-YYYY.json
        _wx_save(base_path, fresh)

        # ensure only this base file exists for today
        for p in glob(_wx_today_glob_mdy(tz)):
            if p != base_path:
                try:
                    os.remove(p)
                except Exception:
                    pass

        fresh["_via_cache"] = False
        return {"success": True, "data": fresh, "updated": False}




    async def get_reminders(self, limit=5, include_completed=False, days_ahead=30) -> Dict:
        try:
            from datetime import datetime, timedelta
            now = datetime.now().isoformat()
            future_date = (datetime.now() + timedelta(days=days_ahead)).isoformat()

            with sqlite3.connect(self.schedule_db_path) as conn:
                cursor = conn.cursor()
                query = """
                    SELECT reminder_id, content, due_datetime, completed, priority_level
                    FROM reminders
                    WHERE 1=1
                """
                params = []

                if not include_completed:
                    query += " AND completed = 0"

                # Only return reminders that are due now or in the future
                query += " AND due_datetime >= ?"
                params.append(now)

                if days_ahead > 0:
                    query += " AND due_datetime <= ?"
                    params.append(future_date)

                query += " ORDER BY due_datetime ASC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return {
                    "success": True,
                    "reminders": [
                        {
                            "id": r[0],
                            "content": r[1],
                            "due": r[2],
                            "completed": bool(r[3]),
                            "priority": r[4]
                        } for r in rows
                    ]
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    
    def __init__(self):
        self.memory_data_dir = ("F:/Friday/memory_data")
        self.memory_system = FridayMemorySystem(data_dir=str(self.memory_data_dir))
        self.server = Server("friday-memory")
        self.client_context = {}  # Track client-specific context
        self._maintenance_task = None  # Background maintenance task 
        if not isinstance(self.memory_data_dir, Path):
            self.memory_data_dir = Path(self.memory_data_dir)       
        self.schedule_db_path = str(self.memory_data_dir / "schedule.db")
        # Enable debug logging for MCP server
        logging.getLogger("mcp.server").setLevel(logging.DEBUG)
        self._register_handlers()
        # Do NOT start maintenance or file monitoring here
        logger.info("FridayMemoryMCPServer initialized successfully")
    
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
                        "reminder_id": {"type": "string", "description": "ID of the reminder to complete"}
                    },
                    "required": ["reminder_id"]
                }
            ),
            Tool(
                name="get_active_reminders",
                description="Get active (not completed) reminders",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of reminders to return", "default": 10},
                        "days_ahead": {"type": "integer", "description": "Only show reminders due within X days", "default": 30}
                    }
                }
            ),
            Tool(
                name="get_weather_open_meteo",
                description="Open-Meteo forecast (no API key). Defaults to Motley, MN and caches once per local day.",
                inputSchema={
                    "type": "object",
                    "properties": {
                                    "latitude":  {"type": ["number","null"], "description": "Ignored unless override=True", "default": None},
                                    "longitude": {"type": ["number","null"], "description": "Ignored unless override=True", "default": None},
                                    "timezone_str": {"type": ["string","null"], "description": "Ignored unless override=True", "default": None},

                                    "update_today": {
                                        "type": "boolean",
                                        "description": "If true (default), fetch and merge changes into today's file before returning.",
                                        "default": True
                                    },
                                    "return_changes_only": {
                                        "type": "boolean",
                                        "description": "If true, return only a summary of changed fields for today.",
                                        "default": False
                                    },
                                    "severe_update": {
                                    "type": "boolean",
                                    "description": "If true, shrink the update window to 30 minutes for severe weather.",
                                    "default": False
                                    },


                        "force_refresh": {"type": "boolean", "description": "Ignore same-day cache", "default": False}
                    }
                }
            ),
            Tool(
                name="get_completed_reminders",
                description="Get recently completed reminders",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Look back X days", "default": 7}
                    }
                }
            ),
            Tool(
                name="reschedule_reminder",
                description="Update the due date of a reminder",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "reminder_id": {"type": "string", "description": "ID of the reminder"},
                        "new_due_datetime": {"type": "string", "description": "New ISO datetime (e.g., 2025-08-03T14:00:00Z)"}
                    },
                    "required": ["reminder_id", "new_due_datetime"]
                }
            ),
            Tool(
                name="delete_reminder",
                description="Permanently delete a reminder",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "reminder_id": {"type": "string", "description": "ID of the reminder to delete"}
                    },
                    "required": ["reminder_id"]
                }
            ),
            Tool(
                name="cancel_appointment",
                description="Cancel a scheduled appointment",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "appointment_id": {"type": "string", "description": "ID of the appointment to cancel"}
                    },
                    "required": ["appointment_id"]
                }
            ),
            Tool(
                name="get_upcoming_appointments",
                description="Get upcoming appointments (not cancelled)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number to return", "default": 5},
                        "days_ahead": {"type": "integer", "description": "Only show within X days", "default": 30}
                    }
                }
            ),
            
            Tool(
                name="search_memories",
                description="Search memories using semantic similarity with importance and type filtering",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results", "default": 10},
                        "database_filter": {"type": "string", "description": "Filter by database type", "enum": ["conversations", "ai_memories", "schedule", "all"], "default": "all"},
                        "min_importance": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Minimum importance level to include (1-10)"},
                        "max_importance": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Maximum importance level to include (1-10)"},
                        "memory_type": {"type": "string", "description": "Filter by memory type (e.g., 'safety', 'preference', 'skill', 'general')"}
                    },
                    "required": ["query"]
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
                        "metadata": {"type": "object", "description": "Additional metadata"}
                    },
                    "required": ["content", "role"]
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
                        "source_conversation_id": {"type": "string", "description": "Source conversation ID"}
                    },
                    "required": ["content"]
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
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Updated tags"}
                    },
                    "required": ["memory_id"]
                }
            ),
            Tool(
                name="create_appointment",
                description="Create an appointment",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Appointment title"},
                        "description": {"type": "string", "description": "Appointment description"},
                        "scheduled_datetime": {"type": "string", "description": "ISO format datetime"},
                        "location": {"type": "string", "description": "Location"}
                    },
                    "required": ["title", "scheduled_datetime"]
                }
            ),
            Tool(
                name="create_reminder",
                description="Create a reminder",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Reminder content"},
                        "due_datetime": {"type": "string", "description": "ISO format datetime"},
                        "priority_level": {"type": "integer", "description": "Priority (1-10)", "default": 5}
                    },
                    "required": ["content", "due_datetime"]
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
                        "days_ahead": {"type": "integer", "description": "Only show reminders due within X days", "default": 30}
                    }
                }
            ),
            Tool(
                name="get_recent_context",
                description="Get recent conversation context",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of recent items", "default": 5},
                        "session_id": {"type": "string", "description": "Specific session ID"}
                    }
                }
            ),
            Tool(
                name="get_system_health",
                description="Get comprehensive system health, statistics, and database status",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            ),
            Tool(
                name="get_tool_usage_summary",
                description="Get AI tool usage summary and insights for self-reflection",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Days to analyze", "default": 7},
                        "client_id": {"type": "string", "description": "Specific client ID to analyze"}
                    }
                }
            ),
            Tool(
                name="reflect_on_tool_usage",
                description="AI self-reflection on tool usage patterns and effectiveness",
                inputSchema={
                    "type": "object", 
                    "properties": {
                        "days": {"type": "integer", "description": "Days to analyze", "default": 7},
                        "client_id": {"type": "string", "description": "Specific client ID to analyze"}
                    }
                }
            ),
            Tool(
                name="get_ai_insights",
                description="Get recent AI self-reflection insights and patterns",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of insights", "default": 5},
                        "insight_type": {"type": "string", "description": "Type of insight to filter"}
                    }
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
                        }
                    },
                    "required": ["content"],
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
                        }
                    },
                    "required": ["content"],
                    "additionalProperties": False
                }
            )
            ,
            Tool(
                name="get_current_time",
                description="Get the current server time in ISO format (UTC and local)",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
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
                        "days_ahead": {"type": "integer", "description": "Only show appointments scheduled within X days", "default": 30}
                    }
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
                        "session_summary": {"type": "string", "description": "Session summary"}
                    },
                    "required": ["workspace_path"]
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
                        "importance_level": {"type": "integer", "description": "Importance (1-10)", "default": 5}
                    },
                    "required": ["content"]
                }
            ),
            Tool(
                name="search_project_history",
                description="Search VS Code project development history",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results", "default": 10}
                    },
                    "required": ["query"]
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
                        "conversation_id": {"type": "string", "description": "Related conversation ID"}
                    },
                    "required": ["file_path", "description"]
                }
            ),
            Tool(
                name="get_project_continuity",
                description="Get context to continue development work",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workspace_path": {"type": "string", "description": "Workspace path"},
                        "limit": {"type": "integer", "description": "Context items", "default": 5}
                    }
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
                                "limit": {"type": "integer", "description": "Max results", "default": 5}
                            },
                            "required": ["character_name"]
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
                                "tags": {"type": "array", "items": {"type": "string"}, "description": "Relevant tags"}
                            },
                            "required": ["character_name", "event_description"]
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
                                "limit": {"type": "integer", "description": "Max results", "default": 10}
                            },
                            "required": ["query"]
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
        """Detect the type of MCP client connecting"""
        # This is a placeholder - in real implementation we might check:
        # - User agent headers
        # - Connection parameters
        # - Client capabilities during handshake
        # For now, assume external clients are SillyTavern if not VS Code
        return "unknown"  # Will be enhanced based on actual client detection
    
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
           
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Execute the requested tool with logging for AI self-reflection"""
            
        import time
        
        # Start timing and get client info
        start_time = time.perf_counter()
        client_id = self.client_context.get("current_client", "unknown")
        
        try:
            # Route to appropriate handler
            if tool_name == "search_memories":
                result = await self.memory_system.search_memories(**arguments)
            elif tool_name == "store_conversation":
                result = await self.memory_system.store_conversation(**arguments)
            if tool_name == "create_appointment":
                result = await self.memory_system.create_appointment(
                    title=arguments.get("title"),
                    scheduled_datetime=arguments.get("scheduled_datetime"),
                    description=arguments.get("description"),
                    location=arguments.get("location"),
                    source_conversation_id=arguments.get("source_conversation_id")
                )
            elif tool_name == "store_ai_reflection" or tool_name == "write_ai_insights":
                reflection_id = await self.memory_system.mcp_db.store_ai_reflection(**arguments)
                result = {"status": "success", "reflection_id": reflection_id}

            elif tool_name == "get_appointments":
                result = await self.memory_system.get_appointments(
                    limit=arguments.get("limit", 5),
                    days_ahead=arguments.get("days_ahead", 30)
                )
            elif tool_name == "create_reminder":
                result = await self.memory_system.create_reminder(
                    content=arguments.get("content"),
                    due_datetime=arguments.get("due_datetime"),
                    priority_level=arguments.get("priority_level", 5),
                    source_conversation_id=arguments.get("source_conversation_id")
                )
            # ...existing code for other tools...
            elif tool_name == "complete_reminder":
                return await self.memory_system.complete_reminder(**arguments)
            elif tool_name == "get_weather_open_meteo":
                # Hard gate: ignore coords unless override=True
                override = bool(arguments.get("override", False))
                if not override:
                    # strip any coordinates or tz Friday tried to send
                    attempted_lat = arguments.pop("latitude", None)
                    attempted_lon = arguments.pop("longitude", None)
                    attempted_tz  = arguments.pop("timezone_str", None)
                    # optional: log the attempt so you can see when she tries
                    try:
                        with open(r"F:\Friday\logs\friday.log", "a", encoding="utf-8") as _lf:
                            _lf.write(f"[weather] blocked coords (override=False) lat={attempted_lat} lon={attempted_lon} tz={attempted_tz}\n")
                    except Exception:
                        pass

                result = await self.get_weather_open_meteo(
                    latitude=arguments.get("latitude"),
                    longitude=arguments.get("longitude"),
                    timezone_str=arguments.get("timezone_str"),
                    force_refresh=arguments.get("force_refresh", False),
                    override=override,
                    update_today=arguments.get("update_today", True),
                    return_changes_only=arguments.get("return_changes_only", False),
                    severe_update=arguments.get("severe_update", False),
                )
            elif tool_name == "reschedule_reminder":
                return await self.memory_system.reschedule_reminder(**arguments)
            elif tool_name == "get_active_reminders":
                return await self.memory_system.get_active_reminders(**arguments)
            elif tool_name == "get_completed_reminders":
                return await self.memory_system.get_completed_reminders(**arguments)
            elif tool_name == "delete_reminder":
                return await self.memory_system.delete_reminder(**arguments)
            elif tool_name == "cancel_appointment":
                return await self.memory_system.cancel_appointment(**arguments)
            elif tool_name == "get_upcoming_appointments":
                return await self.memory_system.get_upcoming_appointments(**arguments)
            elif tool_name == "search_memories":
                result = await self.memory_system.search_memories(**arguments)
            elif tool_name == "get_reminders":
                result = await self.get_reminders(**arguments)
            elif tool_name == "get_current_time":
                result = await self.get_current_time_tool()    
            elif tool_name == "store_conversation":
                result = await self.memory_system.store_conversation(**arguments)
            elif tool_name == "create_memory":
                result = await self.memory_system.create_memory(**arguments)
            elif tool_name == "update_memory":
                result = await self.memory_system.update_memory(**arguments)
            elif tool_name == "get_recent_context":
                result = await self.memory_system.get_recent_context(**arguments)
            elif tool_name == "get_system_health":
                result = await self.memory_system.get_system_health()
            elif tool_name == "save_development_session":
                result = await self.memory_system.save_development_session(**arguments)
            elif tool_name == "store_project_insight":
                result = await self.memory_system.store_project_insight(**arguments)
            elif tool_name == "search_project_history":
                result = await self.memory_system.search_project_history(**arguments)
            elif tool_name == "link_code_context":
                result = await self.memory_system.link_code_context(**arguments)
            elif tool_name == "get_project_continuity":
                result = await self.memory_system.get_project_continuity(**arguments)
            elif tool_name == "get_tool_usage_summary":
                result = await self.memory_system.get_tool_usage_summary(**arguments)
            elif tool_name == "reflect_on_tool_usage":
                result = await self.memory_system.reflect_on_tool_usage(**arguments)
            elif tool_name == "get_ai_insights":
                result = await self.memory_system.get_ai_insights(**arguments)
            elif tool_name == "get_character_context":
                result = await self.memory_system.get_character_context(**arguments)
            elif tool_name == "store_roleplay_memory":
                result = await self.memory_system.store_roleplay_memory(**arguments)
            elif tool_name == "search_roleplay_history":
                result = await self.memory_system.search_roleplay_history(**arguments)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            # Calculate execution time and log successful call
            end_time = time.perf_counter()
            execution_time_ms = (end_time - start_time) * 1000
            
            # Log tool call for AI self-reflection (async, don't wait)
            try:
                asyncio.create_task(self.memory_system.log_tool_call(
                    client_id=client_id,
                    tool_name=tool_name,
                    parameters=arguments,
                    execution_time_ms=execution_time_ms,
                    status="success",
                    result=result
                ))
            except Exception as log_error:
                logger.warning(f"Could not log tool call: {log_error}")
            
            # Format the result as a proper TextContent object
            if isinstance(result, (dict, list)):
                result_text = json.dumps(result, indent=2, default=str)
            else:
                result_text = str(result)
            
            text_content = {
                "type": "text",
                "text": result_text,
                "highlights": None,
                "meta": None
            }
            
            return {
                "content": [text_content],
                "success": True,
                "structuredContent": None,
                "isError": False,
                "meta": None
            }
            
        except Exception as e:
            # Calculate execution time and log failed call
            end_time = time.perf_counter()
            execution_time_ms = (end_time - start_time) * 1000
            
            # Log tool call failure for AI self-reflection (async, don't wait)
            try:
                asyncio.create_task(self.memory_system.log_tool_call(
                    client_id=client_id,
                    tool_name=tool_name,
                    parameters=arguments,
                    execution_time_ms=execution_time_ms,
                    status="error",
                    error_message=str(e)
                ))
            except Exception as log_error:
                logger.warning(f"Could not log tool call failure: {log_error}")
            
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {
                "content": [{
                    "type": "text",
                    "text": f"Error: {str(e)}",
                    "highlights": None,
                    "meta": None
                }],
                "success": False,
                "structuredContent": None,
                "isError": True,
                "meta": None
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
            await asyncio.sleep(3 * 60 * 60)
    
    async def cleanup(self):
        """Cleanup resources when server stops"""
        if self._maintenance_task and not self._maintenance_task.done():
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
            logger.info("🔧 Automatic maintenance stopped")


async def start_http_server(mcp_server: FridayMemoryMCPServer, host: str = "127.0.0.1", port: int = 11434):
    """Start the HTTP API server if needed"""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn
        
        app = FastAPI(title="Friday Memory API")

        from fastapi import Request, HTTPException

        API_KEY = "0d4b94f58f5a401ea88b149a17f09fc9"  # Change this later or load from env

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
            return {"status": "healthy", "server": "friday-memory"}
            
        # Start server without blocking
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        return await server.serve()
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
    
    mcp_server = FridayMemoryMCPServer()
    srv = FridayMemoryMCPServer()
    logger.debug("Server initialized, starting stdio interface for LM Studio...")
    import friday_memory_system as fms
    asyncio.create_task(fms.main())
    logger.info("Memory system started in background.")
    
    try:
        from mcp.server.lowlevel.server import InitializationOptions, NotificationOptions
        async with stdio_server() as (read_stream, write_stream):
            await srv.server.run(
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

    except Exception:
        logger.exception("Server error")
        await mcp_server.cleanup()
        await srv.cleanup()




# ---- MCP STDIO ENTRYPOINT (run main() in background; start MCP correctly) ----
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())




