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
    async def get_appointments_direct(self, limit: int = 5, days_ahead: int = 30) -> Dict:
        """Get appointments directly from schedule database, with fallback support for schema mismatch"""
        try:
            schedule_db_path = str(Path("memory_data") / "schedule.db")
            with sqlite3.connect(schedule_db_path) as conn:
                cursor = conn.cursor()

                # Check schema for actual column names
                cursor.execute("PRAGMA table_info(appointments)")
                columns = [col[1] for col in cursor.fetchall()]

                # Column fallback mapping
                column_map = {
                    "appointment_id": next((c for c in columns if c.endswith("_id") and "appointment" in c), None),
                    "title": "title" if "title" in columns else None,
                    "scheduled_datetime": "scheduled_datetime" if "scheduled_datetime" in columns else "datetime" if "datetime" in columns else None,
                    "description": "description" if "description" in columns else "notes" if "notes" in columns else None,
                    "location": "location" if "location" in columns else None,
                    "source_conversation_id": "source_conversation_id" if "source_conversation_id" in columns else None,
                }

                for field, actual in column_map.items():
                    if actual != field:
                        print(f"⚠ Warning: column '{field}' mapped to '{actual}' — possible schema drift")

                selected_cols = [col for col in column_map.values() if col is not None]
                query = f"""
                    SELECT {', '.join(selected_cols)}
                    FROM appointments
                    WHERE 1=1
                """
                params = []

                if days_ahead > 0:
                    from datetime import datetime, timedelta
                    future_date = (datetime.now() + timedelta(days=days_ahead)).isoformat()
                    query += " AND scheduled_datetime <= ?"
                    params.append(future_date)

                query += " ORDER BY scheduled_datetime ASC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                appointments = []
                for row in rows:
                    appointment = dict(zip([k for k in column_map.keys() if column_map[k] is not None], row))

                    # Human-friendly time calculation
                    try:
                        sched_dt = datetime.fromisoformat(appointment["scheduled_datetime"].replace('Z', '+00:00'))
                        now = datetime.now()
                        diff = sched_dt - now
                        if diff.total_seconds() < 0:
                            appointment["status"] = "past"
                            appointment["time_until"] = f"Occurred {abs(diff.days)} days ago"
                        elif diff.days == 0:
                            hours = int(diff.total_seconds() / 3600)
                            if hours <= 0:
                                minutes = int(diff.total_seconds() / 60)
                                appointment["time_until"] = f"In {minutes} minutes"
                            else:
                                appointment["time_until"] = f"In {hours} hours"
                            appointment["status"] = "today"
                        else:
                            appointment["status"] = "upcoming"
                            appointment["time_until"] = f"In {diff.days} days"
                    except:
                        appointment["status"] = "unknown"
                        appointment["time_until"] = "Unknown"

                    appointments.append(appointment)

                return {
                    "success": True,
                    "appointments": appointments,
                    "count": len(appointments)
                }

        except Exception as e:
            print(f"❌ Error getting appointments: {e}")
            return {
                "success": False,
                "error": str(e),
                "appointments": []
            }

    async def get_reminders(self, limit=5, include_completed=False, days_ahead=30) -> Dict:
        try:
            with sqlite3.connect(self.schedule_db_path) as conn:
                cursor = conn.cursor()
                query = "SELECT reminder_id, content, due_datetime, completed, priority_level FROM reminders WHERE 1=1"
                params = []
                if not include_completed:
                    query += " AND completed = 0"
                if days_ahead > 0:
                    from datetime import datetime, timedelta
                    future_date = (datetime.now() + timedelta(days=days_ahead)).isoformat()
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
    
    def __init__(self):
        self.memory_system = FridayMemorySystem()
        self.server = Server("friday-memory")
        self.client_context = {}  # Track client-specific context
        self._maintenance_task = None  # Background maintenance task
        self.memory_data_dir = Path("memory_data")
        self.schedule_db_path = self.memory_data_dir / "schedule.db"
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

    async def get_reminders_direct(self, limit: int = 5, include_completed: bool = False, days_ahead: int = 30) -> Dict:
        """Get reminders directly from schedule database"""
        try:
            with sqlite3.connect(self.schedule_db_path) as conn:
                cursor = conn.cursor()
                query = """
                    SELECT reminder_id, content, due_datetime, priority_level, completed, timestamp_created, source_conversation_id, created_at
                    FROM reminders
                    WHERE 1=1
                """
                params = []
                if not include_completed:
                    query += " AND completed = 0"
                if days_ahead > 0:
                    from datetime import datetime, timedelta
                    future_date = (datetime.now() + timedelta(days=days_ahead)).isoformat()
                    query += " AND due_datetime <= ?"
                    params.append(future_date)
                query += " ORDER BY due_datetime ASC LIMIT ?"
                params.append(limit)
                cursor.execute(query, params)
                rows = cursor.fetchall()
                reminders = []
                for row in rows:
                    reminder = {
                        "reminder_id": row[0],
                        "content": row[3],
                        "due_datetime": row[2],
                        "priority_level": row[4],
                        "completed": row[5],
                        "timestamp_created": row[1],
                        "source_conversation_id": row[6],
                        "created_at": row[8]
                    }
                    try:
                        due_dt = datetime.fromisoformat(reminder["due_datetime"].replace('Z', '+00:00'))
                        now = datetime.now()
                        time_diff = due_dt - now
                        if time_diff.total_seconds() < 0:
                            reminder["status"] = "overdue"
                            reminder["time_until_due"] = f"Overdue by {abs(time_diff.days)} days"
                        elif time_diff.days == 0:
                            hours = int(time_diff.total_seconds() / 3600)
                            if hours <= 0:
                                minutes = int(time_diff.total_seconds() / 60)
                                reminder["time_until_due"] = f"Due in {minutes} minutes"
                            else:
                                reminder["time_until_due"] = f"Due in {hours} hours"
                            reminder["status"] = "due_today"
                        else:
                            reminder["status"] = "upcoming"
                            reminder["time_until_due"] = f"Due in {time_diff.days} days"
                    except:
                        reminder["status"] = "unknown"
                        reminder["time_until_due"] = "Unknown"
                    reminders.append(reminder)
                return {
                    "success": True,
                    "reminders": reminders,
                    "count": len(reminders)
                }
        except Exception as e:
            print(f"❌ Error getting reminders: {e}")
            return {
                "success": False,
                "error": str(e),
                "reminders": []
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
    
    logger.debug("Server initialized, starting stdio interface for LM Studio...")
    
    try:
        # Only use stdio for LM Studio - no HTTP server needed
        logger.info("Waiting for stdio connection from LM Studio...")
        async with stdio_server() as (read_stream, write_stream):
            logger.info("LM Studio connected via stdio")
            await mcp_server.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="friday-memory",
                    server_version="1.0.0",
                    capabilities=mcp_server.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        await mcp_server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())