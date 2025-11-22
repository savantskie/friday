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
import numpy as np
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
import time
import warnings
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

# Initialize port manager
port_manager = PortManager(memory_data_path=str(BASE_PATH / "memory_data"))

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
                # If return_changes_only is True, return just the changes summary
                if return_changes_only:
                    return {"success": True, "changes": {}, "updated": False, "via_cache": True}
                return {"success": True, "data": cached, "updated": False}
            
            # outside window and update_today is True -> fetch/rename/update
            if update_today:
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

                # If return_changes_only is True, return just the changes
                if return_changes_only:
                    return {"success": True, "changes": diff, "updated": True, "via_cache": False}
                
                if diff:
                    fresh["_via_cache"] = False
                    fresh["changes"] = diff
                    return {"success": True, "data": fresh, "updated": True}
                else:
                    fresh["_via_cache"] = False
                    fresh["changes"] = {}
                    return {"success": True, "data": fresh, "updated": True}
            else:
                # update_today is False, return cached data
                cached["_via_cache"] = True
                if return_changes_only:
                    return {"success": True, "changes": {}, "updated": False, "via_cache": True}
                return {"success": True, "data": cached, "updated": False}

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
        
        # If return_changes_only is True, return empty changes since this is a new file
        if return_changes_only:
            return {"success": True, "changes": {}, "updated": False, "via_cache": False}
            
        return {"success": True, "data": fresh, "updated": False}


    async def brave_web_search(self, query: str, count: int = 10, country: str = "US", language: str = "en") -> Dict:
        """Perform a general web search using Brave Search API"""
        logger.info(f"Brave web search called with query: {query}")
        # Also write a simple append-only log for quick debugging (separate from python logging)
        try:
            log_dir = BASE_PATH / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "brave_search.log", "a", encoding="utf-8") as _lf:
                _lf.write(f"{datetime.now().isoformat()} - brave_web_search called - query={query!r}, count={count}, country={country}, language={language}\n")
        except Exception:
            # best-effort logging; do not fail the search if logging can't write
            pass
        try:
            # Get Brave API key from environment or file
            api_key = os.getenv("BRAVE_API_KEY")
            if not api_key:
                # Try to load from file
                key_file = BASE_PATH / "keys" / "brave_api_key.txt"
                if key_file.exists():
                    try:
                        with open(key_file, "r") as f:
                            content = f.read().strip()
                            # Parse "Brave_API_Key=\"key\""
                            if content.startswith('Brave_API_Key="') and content.endswith('"'):
                                api_key = content[len('Brave_API_Key="'):-1]
                    except Exception as e:
                        logger.warning(f"Failed to read Brave API key from file: {e}")
            
            logger.info(f"BRAVE_API_KEY present: {bool(api_key)}")
            if not api_key:
                return {
                    "success": False,
                    "error": "Brave API key not configured. Please set BRAVE_API_KEY environment variable or ensure /keys/brave_api_key.txt exists."
                }

            # Limit count to reasonable bounds
            count = min(max(count, 1), 20)

            async with aiohttp.ClientSession() as session:
                url = "https://api.search.brave.com/res/v1/web/search"
                params = {
                    "q": query,
                    "count": count,
                    "country": country,
                    "search_lang": language
                }
                headers = {
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": api_key
                }

                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = []

                        # Process web results
                        if "web" in data and "results" in data["web"]:
                            for result in data["web"]["results"][:count]:
                                results.append({
                                    "title": result.get("title", ""),
                                    "url": result.get("url", ""),
                                    "description": result.get("description", ""),
                                    "type": "web"
                                })

                        return {
                            "success": True,
                            "query": query,
                            "results": results,
                            "count": len(results)
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"Brave API error {response.status}: {error_text}"
                        }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to perform web search: {str(e)}"
            }

    async def brave_local_search(self, query: str, location: str = None, count: int = 10, radius: int = 5000) -> Dict:
        """Search for local businesses and places using Brave Search API"""
        try:
            # Get Brave API key from environment or file
            api_key = os.getenv("BRAVE_API_KEY")
            if not api_key:
                # Try to load from file
                key_file = BASE_PATH / "keys" / "brave_api_key.txt"
                if key_file.exists():
                    try:
                        with open(key_file, "r") as f:
                            content = f.read().strip()
                            # Parse "Brave_API_Key=\"key\""
                            if content.startswith('Brave_API_Key="') and content.endswith('"'):
                                api_key = content[len('Brave_API_Key="'):-1]
                    except Exception as e:
                        logger.warning(f"Failed to read Brave API key from file: {e}")
            
            if not api_key:
                return {
                    "success": False,
                    "error": "Brave API key not configured. Please set BRAVE_API_KEY environment variable or ensure /keys/brave_api_key.txt exists."
                }

            # Limit count to reasonable bounds
            count = min(max(count, 1), 20)

            # Build location-aware query for web search since local search endpoint may not be available
            search_query = query
            if location:
                search_query = f"{query} near {location}"

            async with aiohttp.ClientSession() as session:
                url = "https://api.search.brave.com/res/v1/web/search"
                params = {
                    "q": search_query,
                    "count": count,
                    "country": "US",
                    "search_lang": "en"
                }
                headers = {
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": api_key
                }

                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = []

                        # Process web results that are likely local businesses/places
                        if "web" in data and "results" in data["web"]:
                            for result in data["web"]["results"][:count]:
                                # Try to identify local business results
                                title = result.get("title", "")
                                description = result.get("description", "")
                                url = result.get("url", "")

                                # Extract potential business info from title and description
                                results.append({
                                    "name": title.split(" - ")[0] if " - " in title else title,  # Try to extract business name
                                    "address": "",  # Web search doesn't provide structured address data
                                    "phone": "",    # Web search doesn't provide phone data
                                    "rating": None, # Web search doesn't provide ratings
                                    "price_range": "",
                                    "type": "local_search_result",
                                    "url": url,
                                    "distance": None,
                                    "description": description
                                })

                        return {
                            "success": True,
                            "query": query,
                            "location": location,
                            "results": results,
                            "count": len(results),
                            "note": "Local search results are based on web search with location context"
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"Brave Local API error {response.status}: {error_text}"
                        }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to perform local search: {str(e)}"
            }




    async def get_reminders(self, limit=5, include_completed=False, days_ahead=30) -> Dict:
        try:
            if include_completed:
                # For completed reminders, use memory system's method
                result = await self.memory_system.get_completed_reminders(days=days_ahead)
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
                result = await self.memory_system.get_active_reminders(limit=limit, days_ahead=days_ahead)
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
        self.server = Server("friday-memory")
        self.client_context = {}  # Track client-specific context
        self._maintenance_task = None  # Background maintenance task
        # Semaphore to limit concurrent database/embedding access (prevents system freeze)
        # Allows up to 3 simultaneous operations, queues the rest
        self.db_semaphore = asyncio.Semaphore(3)
        if not isinstance(self.memory_data_dir, Path):
            self.memory_data_dir = Path(self.memory_data_dir)       
        self.schedule_db_path = str(self.memory_data_dir / "schedule.db")
        # Enable debug logging for MCP server
        logging.getLogger("mcp.server").setLevel(logging.DEBUG)
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
                        "latitude":  {"type": ["number","null"], "description": "Ignored unless override=True"},
                        "longitude": {"type": ["number","null"], "description": "Ignored unless override=True"},
                        "timezone_str": {"type": ["string","null"], "description": "Ignored unless override=True"},
                        "override": {"type": "boolean", "description": "Set to true to use custom coordinates", "default": False},
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
                name="brave_web_search",
                description="General web search using the Brave search engine",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "count": {"type": "integer", "description": "Number of results to return", "default": 10, "maximum": 20},
                        "country": {"type": "string", "description": "Country code (e.g., 'US', 'CA')", "default": "US"},
                        "language": {"type": "string", "description": "Language code (e.g., 'en', 'es')", "default": "en"}
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="brave_local_search",
                description="Search for local businesses and places",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query (e.g., 'pizza near me')"},
                        "location": {"type": "string", "description": "Location to search around (e.g., 'New York, NY' or coordinates)"},
                        "count": {"type": "integer", "description": "Number of results to return", "default": 10, "maximum": 20},
                        "radius": {"type": "integer", "description": "Search radius in meters", "default": 5000}
                    },
                    "required": ["query"]
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
                name="complete_appointment",
                description="Mark an appointment as completed",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "appointment_id": {"type": "string", "description": "ID of the appointment to complete"}
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
                description="Search memories using semantic similarity with importance and type filtering, or direct ID lookup",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results", "default": 10},
                        "database_filter": {"type": "string", "description": "Filter by database type", "enum": ["conversations", "ai_memories", "schedule", "all"], "default": "all"},
                        "min_importance": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Minimum importance level to include (1-10)"},
                        "max_importance": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Maximum importance level to include (1-10)"},
                        "memory_type": {"type": "string", "description": "Filter by memory type (e.g., 'safety', 'preference', 'skill', 'general')"},
                        "memory_id": {"type": "string", "description": "Direct lookup by memory ID (bypasses semantic search)"}
                    },
                    "anyOf": [
                        {"required": ["query"]},
                        {"required": ["memory_id"]}
                    ]
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
                        "source_conversation_id": {"type": "string", "description": "Source conversation ID"},
                        "user_id": {"type": "string", "description": "User ID for user separation"},
                        "model_id": {"type": "string", "description": "Model ID for model separation"}
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
                    "required": ["title", "scheduled_datetime"]
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
                description="Get recent conversation context from the last N days",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of recent items", "default": 5},
                        "session_id": {"type": "string", "description": "Specific session ID"},
                        "days_back": {"type": "integer", "description": "Only show messages from the last N days", "default": 7}
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
                name="get_tool_information",
                description="Get tool usage statistics OR tool documentation. Pass mode='documentation' to get descriptions of available tools. Optionally specify tool_name to get docs for a specific tool.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "mode": {"type": "string", "description": "Mode: 'usage' (default) for statistics or 'documentation' for tool descriptions", "default": "usage"},
                        "tool_name": {"type": "string", "description": "Optional: specific tool name to document (only with mode='documentation')"},
                        "days": {"type": "integer", "description": "For usage mode: Days to analyze", "default": 7},
                        "client_id": {"type": "string", "description": "For usage mode: Specific client ID to analyze"}
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
                        "insight_type": {"type": "string", "description": "Type of insight to filter"},
                        "query": {"type": "string", "description": "Search query for keywords or phrases in insights"}
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
        # LOG ALL INCOMING TOOL CALLS (for debugging)
        # ---------------------------------------------------------------------
        try:
            log_dir = BASE_PATH / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "tool_calls.log", "a", encoding="utf-8") as _lf:
                import json
                _lf.write(f"{datetime.now().isoformat()} - Tool called: {tool_name}\n")
                _lf.write(f"  Arguments: {json.dumps(arguments, indent=2)}\n")
                _lf.write("-" * 80 + "\n")
        except Exception:
            pass  # best-effort logging

        # ---------------------------------------------------------------------
        # Context Setup
        # ---------------------------------------------------------------------
        user_id = (
            self.client_context.get("user_id")
            or arguments.get("user_id")
        )
        model_id = (
            self.client_context.get("model_id")
            or arguments.get("model_id")
            or os.getenv("FRIDAY_DEFAULT_MODEL", "Friday")
        )

        # Store context for logging but don't modify arguments yet
        client_id = self.client_context.get("current_client", "unknown")

        start_time = time.perf_counter()

        try:
            # -----------------------------------------------------------------
            # Memory & Context Tools
            # -----------------------------------------------------------------
            if tool_name in ("search_memories", "tool_search_memories_post"):
                # search_memories accepts: query, limit, database_filter, min_importance, max_importance, memory_type, memory_id, user_id, model_id
                allowed_args = {"query", "limit", "database_filter", "min_importance", "max_importance", "memory_type", "memory_id", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self._protected_tool_call(self.memory_system.search_memories(**filtered_args))

            elif tool_name in ("create_memory", "tool_create_memory_post"):
                # create_memory accepts: content, memory_type, importance_level, tags, source_conversation_id, user_id, model_id
                allowed_args = {"content", "memory_type", "importance_level", "tags", "source_conversation_id", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                result = await self._protected_tool_call(self.memory_system.create_memory(**filtered_args))

            elif tool_name in ("update_memory", "tool_update_memory_post"):
                # update_memory accepts: memory_id, content, importance_level, tags, user_id, model_id
                allowed_args = {"memory_id", "content", "importance_level", "tags", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self._protected_tool_call(self.memory_system.update_memory(**filtered_args))

            elif tool_name in ("get_recent_context", "tool_get_recent_context_post"):
                # get_recent_context accepts: limit, session_id, days_back, user_id, model_id
                allowed_args = {"limit", "session_id", "days_back", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self._protected_tool_call(self.memory_system.get_recent_context(**filtered_args))

            elif tool_name == "store_conversation":
                # store_conversation accepts: content, role, session_id, metadata, user_id, model_id
                allowed_args = {"content", "role", "session_id", "metadata", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self._protected_tool_call(self.memory_system.store_conversation(**filtered_args))

            elif tool_name == "store_ai_reflection" or tool_name == "write_ai_insights":
                try:
                    # store_ai_reflection accepts: reflection_type, content, insights, recommendations, confidence_level, source_period_days
                    allowed_args = {"reflection_type", "content", "insights", "recommendations", "confidence_level", "source_period_days"}
                    filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                    reflection_id = await self._protected_tool_call(self.memory_system.mcp_db.store_ai_reflection(**filtered_args))
                    result = {"status": "success", "reflection_id": reflection_id}
                except TypeError as e:
                    if "unexpected keyword argument 'user_id'" in str(e):
                        logger.warning(f"store_ai_reflection tool temporarily disabled due to user/model separation work in progress: {e}")
                        result = {"status": "temporarily_disabled", "message": "AI reflection storage is temporarily disabled while implementing user/model separation. This will be restored tomorrow."}
                    else:
                        raise  # Re-raise other TypeErrors
                except Exception as e:
                    logger.error(f"Error storing AI reflection: {e}")
                    result = {"status": "error", "message": f"Failed to store AI reflection: {str(e)}"}

            elif tool_name == "get_ai_insights":
                try:
                    # get_ai_insights accepts: limit, insight_type, query
                    allowed_args = {"limit", "insight_type", "query"}
                    filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
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
                # get_character_context accepts: character_name, context_type, limit
                allowed_args = {"character_name", "context_type", "limit"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                result = await self._protected_tool_call(self.memory_system.get_character_context(**filtered_args))

            # -----------------------------------------------------------------
            # Reminder & Appointment Tools
            # -----------------------------------------------------------------
            elif tool_name == "create_appointment":
                # create_appointment accepts: title, description, scheduled_datetime, location, recurrence_pattern, recurrence_count, recurrence_end_date, user_id, model_id
                allowed_args = {"title", "description", "scheduled_datetime", "location", "recurrence_pattern", "recurrence_count", "recurrence_end_date", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                result = await self._protected_tool_call(self.memory_system.create_appointment(**filtered_args))
            elif tool_name == "cancel_appointment":
                # cancel_appointment accepts: appointment_id, user_id, model_id
                allowed_args = {"appointment_id", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self._protected_tool_call(self.memory_system.cancel_appointment(**filtered_args))
            elif tool_name == "complete_appointment":
                # complete_appointment accepts: appointment_id, user_id, model_id
                allowed_args = {"appointment_id", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self._protected_tool_call(self.memory_system.complete_appointment(**filtered_args))
            elif tool_name == "get_appointments":
                # get_appointments accepts: limit, days_ahead, user_id, model_id
                allowed_args = {"limit", "days_ahead", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self._protected_tool_call(self.memory_system.get_appointments(**filtered_args))
            elif tool_name == "get_upcoming_appointments":
                # get_upcoming_appointments accepts: limit, days_ahead, user_id, model_id
                allowed_args = {"limit", "days_ahead", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self._protected_tool_call(self.memory_system.get_upcoming_appointments(**filtered_args))
            elif tool_name == "create_reminder":
                # create_reminder accepts: content, due_datetime, priority_level, recurrence_pattern, recurrence_count, recurrence_end_date, user_id, model_id
                allowed_args = {"content", "due_datetime", "priority_level", "recurrence_pattern", "recurrence_count", "recurrence_end_date", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                result = await self._protected_tool_call(self.memory_system.create_reminder(**filtered_args))
            elif tool_name == "reschedule_reminder":
                # reschedule_reminder accepts: reminder_id, new_due_datetime, user_id, model_id
                allowed_args = {"reminder_id", "new_due_datetime", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self._protected_tool_call(self.memory_system.reschedule_reminder(**filtered_args))
            elif tool_name == "complete_reminder":
                # complete_reminder accepts: reminder_id, user_id, model_id
                allowed_args = {"reminder_id", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self._protected_tool_call(self.memory_system.complete_reminder(**filtered_args))
            elif tool_name == "get_active_reminders":
                # get_active_reminders accepts: limit, days_ahead, user_id, model_id
                allowed_args = {"limit", "days_ahead", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self._protected_tool_call(self.memory_system.get_active_reminders(**filtered_args))
            elif tool_name == "get_completed_reminders":
                # get_completed_reminders accepts: days, user_id, model_id
                allowed_args = {"days", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self._protected_tool_call(self.memory_system.get_completed_reminders(**filtered_args))
            elif tool_name == "delete_reminder":
                # delete_reminder accepts: reminder_id, user_id, model_id
                allowed_args = {"reminder_id", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self._protected_tool_call(self.memory_system.delete_reminder(**filtered_args))
            elif tool_name == "get_reminders":
                result = await self.get_reminders(**arguments)

            # -----------------------------------------------------------------
            # Weather Tools (keep the override guard exactly as before)
            # -----------------------------------------------------------------
            elif tool_name == "get_weather_open_meteo":
                override = bool(arguments.get("override", False))
                latitude = arguments.get("latitude") or None
                longitude = arguments.get("longitude") or None
                timezone_str = arguments.get("timezone_str") or None

                # Sanitize empty strings
                if latitude == "": latitude = None
                if longitude == "": longitude = None
                if timezone_str == "": timezone_str = None

                if not override:
                    attempted_lat = latitude
                    attempted_lon = longitude
                    attempted_tz = timezone_str
                    latitude = longitude = timezone_str = None

                    try:
                        log_path = BASE_PATH / "logs" / "friday.log"
                        log_path.parent.mkdir(exist_ok=True)
                        with open(log_path, "a", encoding="utf-8") as _lf:
                            _lf.write(
                                f"[weather] blocked coords (override=False) "
                                f"lat={attempted_lat} lon={attempted_lon} tz={attempted_tz}\n"
                            )
                    except Exception:
                        pass

                result = await self.get_weather_open_meteo(
                    latitude=latitude,
                    longitude=longitude,
                    timezone_str=timezone_str,
                    force_refresh=arguments.get("force_refresh", False),
                    override=override,
                    update_today=arguments.get("update_today", True),
                    return_changes_only=arguments.get("return_changes_only", False),
                    severe_update=arguments.get("severe_update", False),
                )

            # -----------------------------------------------------------------
            # Brave Search Tools
            # -----------------------------------------------------------------
            elif tool_name == "brave_web_search":
                # brave_web_search accepts: query, count, country, language, user_id, model_id
                allowed_args = {"query", "count", "country", "language", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self.brave_web_search(**filtered_args)

            elif tool_name == "brave_local_search":
                # brave_local_search accepts: query, location, count, radius, user_id, model_id
                allowed_args = {"query", "location", "count", "radius", "user_id", "model_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                filtered_args["user_id"] = filtered_args.get("user_id") or user_id or "Nate"
                filtered_args["model_id"] = filtered_args.get("model_id") or model_id or "Friday"
                result = await self.brave_local_search(**filtered_args)

            # -----------------------------------------------------------------
            # Project / System Tools
            # -----------------------------------------------------------------
            elif tool_name == "get_system_health":
                result = await self._protected_tool_call(self.memory_system.get_system_health())
            elif tool_name == "save_development_session":
                # save_development_session accepts: workspace_path, active_files, git_branch, session_summary
                allowed_args = {"workspace_path", "active_files", "git_branch", "session_summary"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                result = await self._protected_tool_call(self.memory_system.save_development_session(**filtered_args))
            elif tool_name == "store_project_insight":
                # store_project_insight accepts: insight_type, content, related_files, importance_level
                allowed_args = {"insight_type", "content", "related_files", "importance_level"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                result = await self._protected_tool_call(self.memory_system.store_project_insight(**filtered_args))
            elif tool_name == "search_project_history":
                # search_project_history accepts: query, limit
                allowed_args = {"query", "limit"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                result = await self._protected_tool_call(self.memory_system.search_project_history(**filtered_args))
            elif tool_name == "link_code_context":
                # link_code_context accepts: file_path, function_name, description, conversation_id
                allowed_args = {"file_path", "function_name", "description", "conversation_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                result = await self._protected_tool_call(self.memory_system.link_code_context(**filtered_args))
            elif tool_name == "get_project_continuity":
                # get_project_continuity accepts: workspace_path, limit
                allowed_args = {"workspace_path", "limit"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                result = await self._protected_tool_call(self.memory_system.get_project_continuity(**filtered_args))
            elif tool_name == "get_tool_information":
                # get_tool_information accepts: mode, tool_name, days, client_id
                # Detects client type automatically
                allowed_args = {"mode", "tool_name", "days", "client_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                # Add detected client type
                client_type = self._detect_client_type()
                result = await self._protected_tool_call(self.memory_system.get_tool_information(client_type=client_type, **filtered_args))
            elif tool_name == "reflect_on_tool_usage":
                # reflect_on_tool_usage accepts: days, client_id
                allowed_args = {"days", "client_id"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                result = await self._protected_tool_call(self.memory_system.reflect_on_tool_usage(**filtered_args))
            elif tool_name == "store_roleplay_memory":
                # store_roleplay_memory accepts: character_name, event_description, importance_level, tags
                allowed_args = {"character_name", "event_description", "importance_level", "tags"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                result = await self._protected_tool_call(self.memory_system.store_roleplay_memory(**filtered_args))
            elif tool_name == "search_roleplay_history":
                # search_roleplay_history accepts: query, character_name, limit
                allowed_args = {"query", "character_name", "limit"}
                filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
                result = await self._protected_tool_call(self.memory_system.search_roleplay_history(**filtered_args))

            # -----------------------------------------------------------------
            # Utility Tools
            # -----------------------------------------------------------------
            elif tool_name == "get_current_time":
                result = await self.get_current_time_tool()

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
                "memory_type": "Optional: memory type",
                "tags": ["optional", "tags"],
                "source_conversation_id": "Optional: source conversation ID"
            }
            
            Response:
            {
                "status": "success",
                "memory_id": "new_memory_id",
                "importance_level": 8,
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
                
                # Extract optional fields
                memory_type = body.get("memory_type")
                tags = body.get("tags", [])
                source_conversation_id = body.get("source_conversation_id")
                
                # Add "promoted" tag to indicate origin
                if isinstance(tags, list):
                    if "promoted" not in tags:
                        tags.append("promoted")
                else:
                    tags = ["promoted"]
                
                # Call create_memory with promoted importance level (8-9)
                # Use 8 as default for promoted memories (high but not critical)
                result = await mcp_server.memory_system.create_memory(
                    content=content,
                    memory_type=memory_type,
                    importance_level=8,
                    tags=tags,
                    source_conversation_id=source_conversation_id
                )
                
                # Add additional metadata to response
                result["importance_level"] = 8
                result["message"] = "Memory promoted to long-term storage"
                
                logger.info(f"✅ Memory promoted: {result.get('memory_id')}")
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
    
    # Start HTTP API server in background
    # Port will be auto-detected and fallback to backups if needed
    http_task = asyncio.create_task(
        start_http_server(srv, host="127.0.0.1", port=None)
    )
    
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
        await srv.cleanup()
        if not http_task.done():
            http_task.cancel()
        # Clean up port info on shutdown
        port_manager.cleanup_port_info()




# ---- MCP STDIO ENTRYPOINT (run main() in background; start MCP correctly) ----
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())




