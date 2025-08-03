#!/usr/bin/env python3
"""
Friday Memory System

Core memory system that handles all database operations, embeddings, and memory logic.
Provides persistent memory capabilities for Friday AI assistant across multiple databases.
"""

import asyncio
import sqlite3
import json
import uuid
import logging
import aiohttp
import numpy as np
import hashlib
import os
import re
import time
import socket
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone, timedelta
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Base database manager for common operations"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.ensure_database_exists()
    
    def ensure_database_exists(self):
        """Ensure the database file and directory exist"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection with proper configuration"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        return conn
    
    async def execute_query(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Execute a SELECT query and return results"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
    
    async def execute_update(self, query: str, params: Tuple = ()) -> str:
        """Execute an INSERT/UPDATE/DELETE query and return last row ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return str(cursor.lastrowid)


class ConversationDatabase(DatabaseManager):
    """Manages conversation auto-save database"""
    
    def __init__(self, db_path: str = "conversations.db"):
        super().__init__(db_path)
        self.initialize_tables()
    
    def initialize_tables(self):
        """Create tables if they don't exist"""
        with self.get_connection() as conn:
            # Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    start_timestamp TEXT NOT NULL,
                    end_timestamp TEXT,
                    context TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Conversations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    start_timestamp TEXT NOT NULL,
                    end_timestamp TEXT,
                    topic_summary TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)
            
            # Messages table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
                )
            """)
            
            conn.commit()
    
    async def store_message(self, content: str, role: str, session_id: str = None, 
                          conversation_id: str = None, metadata: Dict = None) -> Dict[str, str]:
        """Store a message and auto-manage sessions/conversations with duplicate detection"""
        
        timestamp = datetime.now(timezone.utc).isoformat()
        message_id = str(uuid.uuid4())
        
        # Check for duplicate messages (same content, role, and session within recent time)
        if session_id:
            # Create a content hash for duplicate detection
            content_hash = hashlib.md5(f"{content}:{role}:{session_id}".encode()).hexdigest()
            
            # Check if we already have this exact message in this session recently
            existing = await self.execute_query(
                """SELECT message_id FROM messages 
                   WHERE conversation_id IN (
                       SELECT conversation_id FROM conversations WHERE session_id = ?
                   ) AND role = ? AND content = ? 
                   AND datetime(timestamp) > datetime('now', '-1 hour')""",
                (session_id, role, content)
            )
            
            if existing:
                logger.debug(f"Skipping duplicate message in session {session_id}")
                return {
                    "message_id": existing[0]["message_id"],
                    "conversation_id": None,  # Don't return conversation_id for duplicates
                    "session_id": session_id,
                    "duplicate": True
                }
        
        # Auto-create session if not provided or doesn't exist
        if not session_id:
            session_id = str(uuid.uuid4())
            await self.execute_update(
                "INSERT INTO sessions (session_id, start_timestamp, context) VALUES (?, ?, ?)",
                (session_id, timestamp, "auto-created")
            )
        else:
            # Check if session exists, create if not
            existing_session = await self.execute_query(
                "SELECT session_id FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            if not existing_session:
                await self.execute_update(
                    "INSERT INTO sessions (session_id, start_timestamp, context) VALUES (?, ?, ?)",
                    (session_id, timestamp, "imported-session")
                )
        
        # Auto-create conversation if not provided
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            await self.execute_update(
                "INSERT INTO conversations (conversation_id, session_id, start_timestamp) VALUES (?, ?, ?)",
                (conversation_id, session_id, timestamp)
            )
        
        # Store the message
        await self.execute_update(
            """INSERT INTO messages 
               (message_id, conversation_id, timestamp, role, content, metadata) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (message_id, conversation_id, timestamp, role, content, 
             json.dumps(metadata) if metadata else None)
        )
        
        return {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "duplicate": False
        }
    
    async def get_recent_messages(self, limit: int = 10, session_id: str = None) -> List[Dict]:
        """Get recent messages, optionally filtered by session"""
        
        if session_id:
            query = """
                SELECT m.*, c.session_id 
                FROM messages m 
                JOIN conversations c ON m.conversation_id = c.conversation_id
                WHERE c.session_id = ?
                ORDER BY m.timestamp DESC 
                LIMIT ?
            """
            params = (session_id, limit)
        else:
            query = """
                SELECT m.*, c.session_id 
                FROM messages m 
                JOIN conversations c ON m.conversation_id = c.conversation_id
                ORDER BY m.timestamp DESC 
                LIMIT ?
            """
            params = (limit,)
        
        rows = await self.execute_query(query, params)
        return [dict(row) for row in rows]


class AIMemoryDatabase(DatabaseManager):
    """Manages AI-curated memories database"""
    
    def __init__(self, db_path: str = "ai_memories.db"):
        super().__init__(db_path)
        self.initialize_tables()
    
    def initialize_tables(self):
        """Create tables if they don't exist"""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curated_memories (
                    memory_id TEXT PRIMARY KEY,
                    timestamp_created TEXT NOT NULL,
                    timestamp_updated TEXT NOT NULL,
                    source_conversation_id TEXT,
                    source_message_ids TEXT,
                    memory_type TEXT,
                    content TEXT NOT NULL,
                    importance_level INTEGER DEFAULT 5,
                    tags TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    async def create_memory(self, content: str, memory_type: str = None, 
                          importance_level: int = 5, tags: List[str] = None,
                          source_conversation_id: str = None) -> str:
        """Create a new curated memory"""
        
        memory_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        await self.execute_update(
            """INSERT INTO curated_memories 
               (memory_id, timestamp_created, timestamp_updated, source_conversation_id, 
                memory_type, content, importance_level, tags) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (memory_id, timestamp, timestamp, source_conversation_id, 
             memory_type, content, importance_level, 
             json.dumps(tags) if tags else None)
        )
        
        return memory_id
    
    async def update_memory(self, memory_id: str, content: str = None, 
                          importance_level: int = None, tags: List[str] = None) -> bool:
        """Update an existing memory"""
        
        timestamp = datetime.now(timezone.utc).isoformat()
        updates = ["timestamp_updated = ?"]
        params = [timestamp]
        
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        
        if importance_level is not None:
            updates.append("importance_level = ?")
            params.append(importance_level)
        
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))
        
        params.append(memory_id)
        
        query = f"UPDATE curated_memories SET {', '.join(updates)} WHERE memory_id = ?"
        await self.execute_update(query, tuple(params))
        
        return True
    
    async def get_memories(self, limit: int = 10, memory_type: str = None) -> List[Dict]:
        """Get memories, optionally filtered by type"""
        
        if memory_type:
            query = """
                SELECT * FROM curated_memories 
                WHERE memory_type = ? 
                ORDER BY importance_level DESC, timestamp_created DESC 
                LIMIT ?
            """
            params = (memory_type, limit)
        else:
            query = """
                SELECT * FROM curated_memories 
                ORDER BY importance_level DESC, timestamp_created DESC 
                LIMIT ?
            """
            params = (limit,)
        
        rows = await self.execute_query(query, params)
        return [dict(row) for row in rows]


class ScheduleDatabase(DatabaseManager):
    """Manages appointments and reminders database"""
    
    def __init__(self, db_path: str = "schedule.db"):
        super().__init__(db_path)
        self.initialize_tables()
    
    def initialize_tables(self):
        """Create tables if they don't exist"""
        with self.get_connection() as conn:
            # Appointments table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    appointment_id TEXT PRIMARY KEY,
                    timestamp_created TEXT NOT NULL,
                    scheduled_datetime TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    location TEXT,
                    source_conversation_id TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Reminders table
            conn.execute("""
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
            
            conn.commit()
    
    async def create_appointment(self, title: str, scheduled_datetime: str, 
                               description: str = None, location: str = None,
                               source_conversation_id: str = None) -> str:
        """Create a new appointment"""
        
        appointment_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        await self.execute_update(
            """INSERT INTO appointments 
               (appointment_id, timestamp_created, scheduled_datetime, title, description, location, source_conversation_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (appointment_id, timestamp, scheduled_datetime, title, description, location, source_conversation_id)
        )
        
        return appointment_id
    
    async def create_reminder(self, content: str, due_datetime: str, 
                            priority_level: int = 5, source_conversation_id: str = None) -> str:
        """Create a new reminder"""
        
        reminder_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        await self.execute_update(
            """INSERT INTO reminders 
               (reminder_id, timestamp_created, due_datetime, content, priority_level, source_conversation_id) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (reminder_id, timestamp, due_datetime, content, priority_level, source_conversation_id)
        )
        
        return reminder_id


class VSCodeProjectDatabase(DatabaseManager):
    """Manages VS Code project development database"""
    
    def __init__(self, db_path: str = "vscode_project.db"):
        super().__init__(db_path)
        self.initialize_tables()
    
    def initialize_tables(self):
        """Create tables if they don't exist"""
        with self.get_connection() as conn:
            # Project sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS project_sessions (
                    session_id TEXT PRIMARY KEY,
                    start_timestamp TEXT NOT NULL,
                    end_timestamp TEXT,
                    workspace_path TEXT NOT NULL,
                    active_files TEXT,
                    git_branch TEXT,
                    git_commit_hash TEXT,
                    session_summary TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Development conversations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS development_conversations (
                    conversation_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    chat_context_id TEXT,
                    conversation_content TEXT NOT NULL,
                    decisions_made TEXT,
                    code_changes TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES project_sessions (session_id)
                )
            """)
            
            # Project insights table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS project_insights (
                    insight_id TEXT PRIMARY KEY,
                    timestamp_created TEXT NOT NULL,
                    timestamp_updated TEXT NOT NULL,
                    insight_type TEXT,
                    content TEXT NOT NULL,
                    related_files TEXT,
                    source_conversation_id TEXT,
                    importance_level INTEGER DEFAULT 5,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Code context table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS code_context (
                    context_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    function_name TEXT,
                    description TEXT NOT NULL,
                    purpose TEXT,
                    related_insights TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    async def save_development_session(self, workspace_path: str, active_files: List[str] = None,
                                     git_branch: str = None, session_summary: str = None) -> str:
        """Save a development session"""
        
        session_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        await self.execute_update(
            """INSERT INTO project_sessions 
               (session_id, start_timestamp, workspace_path, active_files, git_branch, session_summary) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, timestamp, workspace_path, 
             json.dumps(active_files) if active_files else None,
             git_branch, session_summary)
        )
        
        return session_id
    
    async def store_project_insight(self, content: str, insight_type: str = None,
                                  related_files: List[str] = None, importance_level: int = 5,
                                  source_conversation_id: str = None) -> str:
        """Store a project development insight"""
        
        insight_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        await self.execute_update(
            """INSERT INTO project_insights 
               (insight_id, timestamp_created, timestamp_updated, insight_type, content, 
                related_files, source_conversation_id, importance_level) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (insight_id, timestamp, timestamp, insight_type, content,
             json.dumps(related_files) if related_files else None,
             source_conversation_id, importance_level)
        )
        
        return insight_id


class MCPToolCallDatabase(DatabaseManager):
    """Manages MCP tool call logging and AI self-reflection"""
    
    def __init__(self, db_path: str = "mcp_tool_calls.db"):
        super().__init__(db_path)
        self.initialize_tables()
    
    def initialize_tables(self):
        """Create tables if they don't exist"""
        with self.get_connection() as conn:
            # Tool calls table - logs every MCP tool call
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_calls (
                    call_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    parameters TEXT,
                    execution_time_ms REAL,
                    status TEXT NOT NULL,
                    result TEXT,
                    error_message TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tool usage patterns table - AI insights about tool usage
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    timestamp_created TEXT NOT NULL,
                    analysis_period_days INTEGER NOT NULL,
                    pattern_type TEXT NOT NULL,
                    insight TEXT NOT NULL,
                    confidence_score REAL DEFAULT 0.5,
                    supporting_data TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # AI reflections table - AI's self-analysis
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_reflections (
                    reflection_id TEXT PRIMARY KEY,
                    timestamp_created TEXT NOT NULL,
                    reflection_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    insights TEXT,
                    recommendations TEXT,
                    confidence_level REAL DEFAULT 0.5,
                    source_period_days INTEGER,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    async def log_tool_call(self, client_id: str, tool_name: str, parameters: Dict = None,
                          execution_time_ms: float = None, status: str = "success",
                          result: Any = None, error_message: str = None) -> str:
        """Log a tool call for AI self-reflection analysis"""
        
        call_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Serialize complex data
        parameters_json = json.dumps(parameters) if parameters else None
        result_json = json.dumps(result) if result and not isinstance(result, str) else str(result) if result else None
        
        await self.execute_update(
            """INSERT INTO tool_calls 
               (call_id, timestamp, client_id, tool_name, parameters, execution_time_ms, 
                status, result, error_message) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (call_id, timestamp, client_id, tool_name, parameters_json, 
             execution_time_ms, status, result_json, error_message)
        )
        
        return call_id
    
    async def get_tool_usage_stats(self, days: int = 7, client_id: str = None) -> Dict:
        """Get tool usage statistics for AI self-reflection"""
        
        cutoff_date = (datetime.now(timezone.utc) - 
                      timedelta(days=days)).isoformat()
        
        base_query = "SELECT * FROM tool_calls WHERE timestamp >= ?"
        params = [cutoff_date]
        
        if client_id:
            base_query += " AND client_id = ?"
            params.append(client_id)
        
        base_query += " ORDER BY timestamp DESC"
        
        calls = await self.execute_query(base_query, tuple(params))
        
        if not calls:
            return {
                "total_calls": 0,
                "success_rate": 0.0,
                "avg_execution_time": 0.0,
                "tool_frequency": {},
                "error_patterns": [],
                "client_activity": {}
            }
        
        # Analyze the data
        total_calls = len(calls)
        successful_calls = sum(1 for call in calls if call["status"] == "success")
        success_rate = (successful_calls / total_calls) * 100 if total_calls > 0 else 0
        
        # Execution times (only for successful calls with timing data)
        execution_times = [call["execution_time_ms"] for call in calls 
                          if call["execution_time_ms"] is not None and call["status"] == "success"]
        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
        
        # Tool frequency
        tool_frequency = {}
        for call in calls:
            tool = call["tool_name"]
            tool_frequency[tool] = tool_frequency.get(tool, 0) + 1
        
        # Error patterns
        error_patterns = []
        error_calls = [call for call in calls if call["status"] == "error"]
        error_tools = {}
        for call in error_calls:
            tool = call["tool_name"]
            error_tools[tool] = error_tools.get(tool, 0) + 1
        
        for tool, count in error_tools.items():
            error_patterns.append({
                "tool": tool,
                "error_count": count,
                "error_rate": (count / tool_frequency.get(tool, 1)) * 100
            })
        
        # Client activity
        client_activity = {}
        for call in calls:
            client = call["client_id"]
            if client not in client_activity:
                client_activity[client] = {"total": 0, "successful": 0}
            client_activity[client]["total"] += 1
            if call["status"] == "success":
                client_activity[client]["successful"] += 1
        
        return {
            "total_calls": total_calls,
            "success_rate": success_rate,
            "avg_execution_time": avg_execution_time,
            "tool_frequency": tool_frequency,
            "error_patterns": error_patterns,
            "client_activity": client_activity,
            "analysis_period_days": days,
            "raw_calls": [dict(call) for call in calls]
        }
    
    async def store_usage_pattern(self, pattern_type: str, insight: str, 
                                analysis_period_days: int, confidence_score: float = 0.5,
                                supporting_data: Dict = None) -> str:
        """Store AI-discovered usage pattern"""
        
        pattern_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        await self.execute_update(
            """INSERT INTO usage_patterns 
               (pattern_id, timestamp_created, analysis_period_days, pattern_type, 
                insight, confidence_score, supporting_data) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pattern_id, timestamp, analysis_period_days, pattern_type, insight,
             confidence_score, json.dumps(supporting_data) if supporting_data else None)
        )
        
        return pattern_id
    
    async def store_ai_reflection(self, reflection_type: str, content: str,
                                insights: List[str] = None, recommendations: List[str] = None,
                                confidence_level: float = 0.5, source_period_days: int = None) -> str:
        """Store AI self-reflection analysis"""
        
        reflection_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        await self.execute_update(
            """INSERT INTO ai_reflections 
               (reflection_id, timestamp_created, reflection_type, content, insights, 
                recommendations, confidence_level, source_period_days) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (reflection_id, timestamp, reflection_type, content,
             json.dumps(insights) if insights else None,
             json.dumps(recommendations) if recommendations else None,
             confidence_level, source_period_days)
        )
        
        return reflection_id
    
    async def get_recent_reflections(self, limit: int = 5, reflection_type: str = None) -> List[Dict]:
        """Get recent AI reflections"""
        
        if reflection_type:
            query = """
                SELECT * FROM ai_reflections 
                WHERE reflection_type = ? 
                ORDER BY timestamp_created DESC 
                LIMIT ?
            """
            params = (reflection_type, limit)
        else:
            query = """
                SELECT * FROM ai_reflections 
                ORDER BY timestamp_created DESC 
                LIMIT ?
            """
            params = (limit,)
        
        rows = await self.execute_query(query, params)
        return [dict(row) for row in rows]


class ConversationFileMonitor:
    """Monitors conversation files from various chat applications and imports them to memory"""
    
    def __init__(self, memory_system, watch_directories: List[str] = None):
        self.memory_system = memory_system
        self.watch_directories = watch_directories or []
        self.observers = []
        self.processed_files = set()  # Track processed files to avoid duplicates
        self.file_hashes = {}  # Track file content hashes to detect changes
        self.processed_messages = {}  # Track processed messages per file: {file_path: set(message_hashes)}
        self.conversation_contexts = {}  # Track ongoing conversations for tool detection
        self.mcp_server_running = False  # Will be updated periodically
        self.last_mcp_check = 0  # Timestamp of last MCP server check
        
        # Tool detection patterns
        self.tool_patterns = {
            # Memory search triggers
            'search_request': re.compile(
                r'(?:remember|recall|find|search|what did|tell me about|do you know about)'
                r'.*?(?:conversation|memory|previous|earlier|before|history)',
                re.IGNORECASE
            ),
            # Appointment/schedule triggers  
            'schedule_request': re.compile(
                r'(?:schedule|appointment|meeting|remind me|set reminder|calendar)',
                re.IGNORECASE
            ),
            # Memory storage triggers
            'memory_storage': re.compile(
                r'(?:remember this|save this|store this|make a note|keep track)',
                re.IGNORECASE
            )
        }
        
        # Default watch directories for various platforms
        self.default_directories = self._get_default_chat_directories()
    
    def _check_mcp_server(self) -> bool:
        """Check if the MCP server is running by attempting a connection"""
        # Only check every 60 seconds to avoid overhead
        current_time = time.time()
        if current_time - self.last_mcp_check < 60:
            return self.mcp_server_running
            
        try:
            # Try to connect to MCP server port
            with socket.create_connection(("localhost", 1234), timeout=1.0):
                self.mcp_server_running = True
        except (socket.timeout, ConnectionRefusedError):
            self.mcp_server_running = False
        
        self.last_mcp_check = current_time
        return self.mcp_server_running
        
    async def _is_message_in_mcp(self, msg_hash: str) -> bool:
        """Check if a message was manually stored through MCP server.
        
        Args:
            msg_hash: Hash of the message content to check
            
        Returns:
            bool: True if message exists in MCP storage, False otherwise
        """
        try:
            # Use the memory system's database to check for manual storage
            async with self.memory_system.get_db() as db:
                cursor = await db.execute(
                    "SELECT 1 FROM conversations WHERE message_hash = ? AND storage_type = 'manual'",
                    (msg_hash,)
                )
                result = await cursor.fetchone()
                return bool(result)
        except Exception as e:
            logger.debug(f"Failed to check message in MCP: {e}")
            return False  # If check fails, assume message doesn't exist
    
    def _get_default_chat_directories(self) -> List[str]:
        """Get default chat storage directories for different platforms"""
        home = Path.home()
        documents = home / "Documents"
        downloads = home / "Downloads"
        directories = []
        
        # ChatGPT desktop app directories
        chatgpt_paths = [
            home / "AppData" / "Roaming" / "ChatGPT" / "chats",  # Windows
            home / ".config" / "ChatGPT" / "chats",  # Linux
            home / "Library" / "Application Support" / "ChatGPT" / "chats"  # macOS
        ]
        
        # Claude desktop app directories
        claude_paths = [
            home / "AppData" / "Roaming" / "Anthropic" / "Claude" / "conversations",  # Windows
            home / ".config" / "anthropic-claude" / "conversations",  # Linux
            home / "Library" / "Application Support" / "Claude" / "conversations"  # macOS
        ]
        
        # LM Studio conversation directories
        lm_studio_paths = [
            home / ".lmstudio" / "conversations",  # Windows/Linux/macOS (new location)
            home / "AppData" / "Roaming" / "LM Studio" / "conversations",  # Windows (old location)
            home / ".config" / "lm-studio" / "conversations",  # Linux (old location)
            home / "Library" / "Application Support" / "LM Studio" / "conversations"  # macOS (old location)
        ]
        
        # Ollama chat directories
        ollama_paths = [
            home / ".ollama" / "chats",  # Windows/Linux/macOS (main location)
            home / "AppData" / "Roaming" / "Ollama" / "chats",  # Windows (alternative)
            home / ".config" / "ollama" / "chats",  # Linux (alternative)
            home / "Library" / "Application Support" / "Ollama" / "chats"  # macOS (alternative)
        ]
        
        # ChatGPT desktop app
        chatgpt_paths = [
            home / "AppData" / "Roaming" / "ChatGPT" / "chats",  # Windows
            home / ".config" / "ChatGPT" / "chats",  # Linux
            home / "Library" / "Application Support" / "ChatGPT" / "chats"  # macOS
        ]
        
        # Claude desktop paths
        claude_paths = [
            home / "AppData" / "Roaming" / "Anthropic" / "Claude" / "conversations",  # Windows
            home / ".config" / "anthropic-claude" / "conversations",  # Linux
            home / "Library" / "Application Support" / "Claude" / "conversations"  # macOS
        ]
        
        # Microsoft Copilot/Bing Chat
        copilot_paths = [
            home / "AppData" / "Roaming" / "Microsoft" / "Windows" / "INetCache" / "Copilot",  # Windows
            home / ".config" / "microsoft-copilot" / "Cache",  # Linux
            home / "Library" / "Caches" / "com.microsoft.copilot"  # macOS
        ]
        
        # Character.ai desktop
        character_ai_paths = [
            home / "AppData" / "Roaming" / "Character.ai" / "conversations",  # Windows
            home / ".config" / "character-ai" / "conversations",  # Linux
            home / "Library" / "Application Support" / "Character.ai" / "conversations"  # macOS
        ]
        
        # Local.ai paths
        local_ai_paths = [
            home / ".local.ai" / "conversations",  # Windows/Linux/macOS
            home / "AppData" / "Roaming" / "local.ai" / "conversations",  # Windows alternative
            home / ".config" / "local.ai" / "conversations"  # Linux alternative
        ]
        
        # text-generation-webui paths
        text_gen_paths = [
            home / "text-generation-webui" / "logs",  # Default install location
            documents / "text-generation-webui" / "logs",  # Common custom location
            home / ".cache" / "text-generation-webui" / "logs"  # Alternative location
        ]
        
        # OpenAI API Playground exports
        openai_paths = [
            downloads / "openai-playground-exports",  # Common export location
            documents / "OpenAI" / "playground-exports"  # Alternative location
        ]
        
        # VS Code workspace storage directories
        vscode_base_paths = [
            home / "AppData" / "Roaming" / "Code" / "User" / "workspaceStorage",  # Windows
            home / ".config" / "Code" / "User" / "workspaceStorage",  # Linux
            home / "Library" / "Application Support" / "Code" / "User" / "workspaceStorage"  # macOS
        ]
        
        # Helper function to add paths with logging
        def add_paths_if_exist(paths: List[Path], app_name: str):
            for path in paths:
                if path.exists():
                    directories.append(str(path))
                    logger.info(f"Found {app_name} conversations: {path}")
        
        # Add paths for each application
        add_paths_if_exist(lm_studio_paths, "LM Studio")
        add_paths_if_exist(ollama_paths, "Ollama")
        add_paths_if_exist(chatgpt_paths, "ChatGPT")
        add_paths_if_exist(claude_paths, "Claude")
        add_paths_if_exist(copilot_paths, "Microsoft Copilot/Bing")
        add_paths_if_exist(character_ai_paths, "Character.ai")
        add_paths_if_exist(local_ai_paths, "Local.ai")
        add_paths_if_exist(text_gen_paths, "text-generation-webui")
        add_paths_if_exist(openai_paths, "OpenAI Playground")
        
        # Add VS Code workspace storage paths - find specific workspace hashes
        for vscode_base in vscode_base_paths:
            if vscode_base.exists():
                try:
                    # Look for workspace hashes (directories with chatSessions folders)
                    for workspace_hash in vscode_base.iterdir():
                        if workspace_hash.is_dir():
                            chat_sessions_dir = workspace_hash / "chatSessions"
                            if chat_sessions_dir.exists():
                                directories.append(str(chat_sessions_dir))
                                logger.info(f"Found VS Code chat sessions: {chat_sessions_dir}")
                except Exception as e:
                    logger.error(f"Error scanning VS Code workspace storage: {e}")
        
        return directories
    
    def _detect_conversation_source(self, file_path: str) -> str:
        """Detect the source application of a conversation file"""
        file_lower = file_path.lower()
        
        if 'chatgpt' in file_lower:
            return 'ChatGPT'
        elif 'claude' in file_lower:
            return 'Claude'
        elif 'copilot' in file_lower or 'bing' in file_lower:
            return 'Microsoft Copilot'
        elif 'character.ai' in file_lower:
            return 'Character.ai'
        elif 'lmstudio' in file_lower:
            return 'LM Studio'
        elif 'ollama' in file_lower:
            return 'Ollama'
        elif 'local.ai' in file_lower:
            return 'Local.ai'
        elif 'text-generation-webui' in file_lower:
            return 'Text Generation WebUI'
        elif 'openai' in file_lower and 'playground' in file_lower:
            return 'OpenAI Playground'
        elif 'vscode' in file_lower or 'chatsessions' in file_lower:
            return 'VS Code'
        else:
            return 'Unknown'
            
    def _parse_conversation_data(self, data: Union[Dict, List], file_path: str) -> List[Dict]:
        """Parse conversation data based on known formats"""
        if isinstance(data, dict):
            if 'mapping' in data:  # ChatGPT web/desktop format
                return self._parse_chatgpt_format(data)
            elif 'messages' in data:  # Claude/Anthropic format
                return self._parse_claude_format(data)
            elif 'conversation' in data:  # Character.ai format
                return self._parse_character_ai_format(data)
            elif 'history' in data:  # text-generation-webui format
                return self._parse_text_gen_format(data)
        elif isinstance(data, list):
            # Determine format from file path and content structure
            if any('role' in msg for msg in data if isinstance(msg, dict)):
                return self._parse_simple_array(data)  # OpenAI-like format
            elif any('character' in msg for msg in data if isinstance(msg, dict)):
                return self._parse_character_ai_format({'conversation': data})
        return []
    
    def _parse_markdown_format(self, content: str) -> List[Dict]:
        """Parse markdown conversation formats commonly used by AI apps"""
        conversations = []
        current_role = None
        current_content = []
        current_timestamp = None
        
        # Common markdown patterns
        role_patterns = {
            'user': [
                r'^#+ *User:',
                r'^#+ *Human:',
                r'^\*\*User:\*\*',
                r'^\*\*Human:\*\*',
                r'^> *User:',
                r'^> *Human:'
            ],
            'assistant': [
                r'^#+ *Assistant:',
                r'^#+ *AI:',
                r'^\*\*Assistant:\*\*',
                r'^\*\*AI:\*\*',
                r'^> *Assistant:',
                r'^> *AI:'
            ]
        }
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Try to extract timestamp from markdown metadata
            if line.startswith('<!--') and 'timestamp:' in line:
                try:
                    ts = re.search(r'timestamp: *(.*?) *-->', line)
                    if ts:
                        current_timestamp = datetime.fromisoformat(ts.group(1))
                    continue
                except (ValueError, AttributeError):
                    pass
            
            # Check for role changes
            new_role = None
            for role, patterns in role_patterns.items():
                if any(re.match(pattern, line) for pattern in patterns):
                    # Save previous message if exists
                    if current_role and current_content:
                        conversations.append({
                            'role': current_role,
                            'content': '\n'.join(current_content),
                            'timestamp': current_timestamp.isoformat() if current_timestamp else None
                        })
                        current_content = []
                    new_role = role
                    # Remove the role marker from the line
                    line = re.sub(r'^[#>*]+.*?:', '', line).strip()
                    break
            
            if new_role:
                current_role = new_role
            
            if current_role and line:
                current_content.append(line)
        
        # Add the last message
        if current_role and current_content:
            conversations.append({
                'role': current_role,
                'content': '\n'.join(current_content),
                'timestamp': current_timestamp.isoformat() if current_timestamp else None
            })
        
        return conversations
    
    def add_watch_directory(self, directory: str):
        """Add a directory to monitor for conversation files"""
        if directory not in self.watch_directories:
            self.watch_directories.append(directory)
            logger.info(f"Added watch directory: {directory}")
    
    async def start_monitoring(self):
        """Start monitoring all configured directories"""
        try:
            # Store reference to the current event loop
            self.loop = asyncio.get_running_loop()
            
            # Import watchdog here to make it optional
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            class ConversationFileHandler(FileSystemEventHandler):
                def __init__(self, monitor):
                    self.monitor = monitor
                
                def on_modified(self, event):
                    if not event.is_directory:
                        try:
                            # Get the event loop from the main thread
                            loop = self.monitor.loop
                            if loop and loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    self.monitor._process_file_change(event.src_path), 
                                    loop
                                )
                        except Exception as e:
                            print(f"Error scheduling file change processing: {e}")
                
                def on_created(self, event):
                    if not event.is_directory:
                        try:
                            # Get the event loop from the main thread
                            loop = self.monitor.loop
                            if loop and loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    self.monitor._process_file_change(event.src_path), 
                                    loop
                                )
                        except Exception as e:
                            print(f"Error scheduling file change processing: {e}")
            
            # Combine configured and default directories
            all_directories = self.watch_directories + self.default_directories
            
            for directory in all_directories:
                if os.path.exists(directory):
                    observer = Observer()
                    handler = ConversationFileHandler(self)
                    observer.schedule(handler, directory, recursive=True)
                    observer.start()
                    self.observers.append(observer)
                    logger.info(f"Started monitoring: {directory}")
            
            # Initial scan of all directories
            await self._initial_scan()
            
        except ImportError:
            logger.warning("Watchdog library not installed. File monitoring disabled. Install with: pip install watchdog")
        except Exception as e:
            logger.error(f"Error starting file monitoring: {e}")
    
    async def stop_monitoring(self):
        """Stop all file monitoring"""
        for observer in self.observers:
            observer.stop()
            observer.join()
        self.observers.clear()
        logger.info("Stopped file monitoring")
    
    async def _initial_scan(self):
        """Perform initial scan of all watch directories"""
        logger.info("Performing initial scan of conversation files...")
        
        for directory in self.watch_directories + self.default_directories:
            if os.path.exists(directory):
                for root, _, files in os.walk(directory):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if self._is_conversation_file(file_path):
                            await self._process_file_change(file_path)
    
    def _is_conversation_file(self, file_path: str) -> bool:
        """Determine if a file is likely a conversation file"""
        file_path_lower = file_path.lower()
        file_name = os.path.basename(file_path_lower)
        
        # VS Code chat session files (UUID.json in chatSessions folder)
        if 'chatsessions' in file_path_lower and file_name.endswith('.json'):
            # Check if filename looks like a UUID
            name_without_ext = file_name[:-5]  # Remove .json
            if len(name_without_ext) == 36 and name_without_ext.count('-') == 4:
                return True
        
        # LM Studio conversation files
        if file_path_lower.endswith('.json') and ('conversation' in file_path_lower or 'lm' in file_path_lower):
            return True
        
        # Other potential conversation formats
        if file_path_lower.endswith(('.jsonl', '.chat', '.conversation')):
            return True
        
        # Generic chat files
        if 'chat' in file_path_lower and file_path_lower.endswith(('.json', '.jsonl', '.txt')):
            return True
        
        return False
    
    async def _process_file_change(self, file_path: str):
        """Process a changed conversation file"""
        try:
            if not self._is_conversation_file(file_path) or not os.path.exists(file_path):
                return
            
            # Calculate file hash to detect actual content changes
            with open(file_path, 'rb') as f:
                file_content = f.read()
                file_hash = hashlib.md5(file_content).hexdigest()
            
            # Skip if we've already processed this exact content
            if file_path in self.file_hashes and self.file_hashes[file_path] == file_hash:
                return
            
            self.file_hashes[file_path] = file_hash
            
            # Parse and import the conversation
            await self._import_conversation_file(file_path, file_content.decode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
    
    async def _import_conversation_file(self, file_path: str, content: str):
        """Import a conversation file into the memory system"""
        try:
            # If MCP server is running, only process messages older than server start
            mcp_running = self._check_mcp_server()
            
            # Check if this is a VS Code chat session file
            if 'chatsessions' in file_path.lower() and file_path.endswith('.json'):
                await self._import_vscode_chat_session(file_path, content, mcp_running)
            # Detect other file formats and parse accordingly
            elif file_path.endswith('.json'):
                await self._import_json_conversation(file_path, content, mcp_running)
            elif file_path.endswith('.jsonl'):
                await self._import_jsonl_conversation(file_path, content, mcp_running)
            else:
                await self._import_text_conversation(file_path, content)
                
        except Exception as e:
            logger.error(f"Error importing conversation from {file_path}: {e}")
    
    async def _import_vscode_chat_session(self, file_path: str, content: str):
        """Import a VS Code chat session file (Copilot format) with duplicate prevention"""
        try:
            data = json.loads(content)
            
            # Create a consistent session ID based on the file path and initial metadata
            file_session_id = hashlib.md5(f"vscode:{file_path}".encode()).hexdigest()
            
            # Extract metadata from VS Code chat session
            metadata = {
                "source_file": file_path,
                "import_timestamp": datetime.now(timezone.utc).isoformat(),
                "file_type": "vscode_chat_session",
                "application": "vscode_copilot",
                "session_version": data.get("version"),
                "requester": data.get("requesterUsername"),
                "responder": data.get("responderUsername"),
                "initial_location": data.get("initialLocation")
            }
            
            # Process each request-response pair
            requests = data.get("requests", [])
            new_message_count = 0
            skipped_duplicates = 0
            
            for request in requests:
                # Skip if this exact message was manually stored through MCP
                msg_hash = None
                if "message" in request:
                    msg_hash = hashlib.md5(
                        f"user:{request['message'].get('text', '')}".encode()
                    ).hexdigest()
                    if await self._is_message_in_mcp(msg_hash):
                        skipped_duplicates += 1
                        continue
                
                # Import user message
                if "message" in request:
                    user_content = request["message"].get("text", "")
                    if user_content.strip():
                        # Use consistent session ID for duplicate detection
                        result = await self.memory_system.store_conversation(
                            content=user_content,
                            role="user",
                            session_id=file_session_id,
                            metadata={**metadata, "request_id": request.get("requestId")}
                        )
                        
                        if result.get("duplicate"):
                            skipped_duplicates += 1
                        else:
                            new_message_count += 1
                        
                        # Use the consistent session for the assistant response
                        session_id = result["session_id"]
                        conversation_id = result.get("conversation_id")
                
                # Import assistant response if present
                if "response" in request and "message" in request:
                    response_data = request["response"]
                    
                    # VS Code responses can have multiple parts
                    if "result" in response_data:
                        result_data = response_data["result"]
                        if isinstance(result_data, dict) and "markdown" in result_data:
                            assistant_content = result_data["markdown"]
                        elif isinstance(result_data, str):
                            assistant_content = result_data
                        else:
                            assistant_content = json.dumps(result_data)
                        
                        if assistant_content.strip():
                            result = await self.memory_system.store_conversation(
                                content=assistant_content,
                                role="assistant",
                                session_id=session_id,
                                conversation_id=conversation_id,
                                metadata={**metadata, "request_id": request.get("requestId")}
                            )
                            
                            if result.get("duplicate"):
                                skipped_duplicates += 1
                            else:
                                new_message_count += 1
            
            logger.info(f"Imported {new_message_count} new messages from VS Code chat session {file_path} (skipped {skipped_duplicates} duplicates)")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in VS Code chat session {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error importing VS Code chat session {file_path}: {e}")
    
    async def _import_json_conversation(self, file_path: str, content: str):
        """Import a JSON conversation file (LM Studio format)"""
        try:
            data = json.loads(content)
            
            # Extract metadata
            metadata = {
                "source_file": file_path,
                "import_timestamp": datetime.now(timezone.utc).isoformat(),
                "file_type": "json_conversation",
                "application": "lm_studio" if "lm" in file_path.lower() else "unknown"
            }
            
            # Handle different JSON conversation formats
            messages = []
            
            if isinstance(data, dict):
                # LM Studio format with metadata
                if "messages" in data:
                    messages = data["messages"]
                elif "conversation" in data:
                    messages = data["conversation"]
                else:
                    # Treat the whole object as a single message
                    messages = [data]
            elif isinstance(data, list):
                messages = data
            
            # Let store_message auto-create session/conversation for the first message
            session_id = None
            conversation_id = None
            
            # Import each message
            for msg in messages:
                if isinstance(msg, dict):
                    role = msg.get("role", "unknown")
                    content_data = msg.get("content", "")
                    
                    # Handle different content formats
                    if isinstance(content_data, str):
                        content = content_data
                    elif isinstance(content_data, dict):
                        content = json.dumps(content_data)
                    else:
                        content = str(content_data)
                    
                    if content.strip():  # Only import non-empty messages
                        result = await self.conversations_db.store_message(
                            content=content,
                            role=role,
                            session_id=session_id,
                            conversation_id=conversation_id,
                            metadata=metadata
                        )
                        
                        # Use same session/conversation for subsequent messages
                        if session_id is None:
                            session_id = result["session_id"]
                            conversation_id = result["conversation_id"]
            
            logger.info(f"Imported {len(messages)} messages from {file_path}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error importing JSON conversation {file_path}: {e}")
    
    async def _import_jsonl_conversation(self, file_path: str, content: str):
        """Import a JSONL conversation file (one JSON object per line)"""
        try:
            metadata = {
                "source_file": file_path,
                "import_timestamp": datetime.now(timezone.utc).isoformat(),
                "file_type": "jsonl_conversation"
            }
            
            lines = content.strip().split('\n')
            message_count = 0
            session_id = None
            conversation_id = None
            
            for line in lines:
                if line.strip():
                    try:
                        msg = json.loads(line)
                        role = msg.get("role", "unknown")
                        content_data = msg.get("content", "")
                        
                        if isinstance(content_data, str):
                            msg_content = content_data
                        else:
                            msg_content = json.dumps(content_data)
                        
                        if msg_content.strip():
                            result = await self.conversations_db.store_message(
                                content=msg_content,
                                role=role,
                                session_id=session_id,
                                conversation_id=conversation_id,
                                metadata=metadata
                            )
                            
                            # Use same session/conversation for subsequent messages
                            if session_id is None:
                                session_id = result["session_id"]
                                conversation_id = result["conversation_id"]
                            
                            message_count += 1
                    
                    except json.JSONDecodeError:
                        continue  # Skip invalid JSON lines
            
            logger.info(f"Imported {message_count} messages from {file_path}")
            
        except Exception as e:
            logger.error(f"Error importing JSONL conversation {file_path}: {e}")
    
    def _parse_claude_format(self, data: Dict) -> List[Dict]:
        """Parse Claude/Anthropic conversation format"""
        conversations = []
        
        try:
            # Handle both array and object formats
            messages = data.get('messages', [])
            if isinstance(messages, dict):
                messages = messages.values()
            
            for msg in messages:
                if isinstance(msg, dict) and 'content' in msg:
                    # Try to extract timestamp
                    timestamp = None
                    if 'timestamp' in msg:
                        try:
                            timestamp = datetime.fromisoformat(msg['timestamp'])
                        except (ValueError, TypeError):
                            pass
                    
                    conversations.append({
                        'role': msg.get('role', 'unknown'),
                        'content': msg['content'],
                        'timestamp': timestamp.isoformat() if timestamp else None,
                        'metadata': {
                            'source': 'Claude',
                            'model': data.get('model', 'claude'),
                            'conversation_id': data.get('conversation_id'),
                            'message_id': msg.get('id'),
                            'parent_id': msg.get('parent')
                        }
                    })
        except Exception as e:
            logger.error(f"Error parsing Claude format: {e}")
        
        return conversations
    
    async def _import_text_conversation(self, file_path: str, content: str):
        """Import a plain text conversation file"""
        try:
            metadata = {
                "source_file": file_path,
                "import_timestamp": datetime.now(timezone.utc).isoformat(),
                "file_type": "text_conversation"
            }
            
            # Try to parse common text conversation formats
            lines = content.strip().split('\n')
            current_message = []
            current_role = "unknown"
            message_count = 0
            session_id = None
            conversation_id = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Detect role changes (common patterns)
                if line.startswith(('User:', 'Human:', 'You:')):
                    if current_message:
                        # Save previous message
                        result = await self._save_text_message(current_message, current_role, session_id, conversation_id, metadata)
                        if session_id is None:
                            session_id = result["session_id"]
                            conversation_id = result["conversation_id"]
                        message_count += 1
                    current_message = [line[line.find(':')+1:].strip()]
                    current_role = "user"
                elif line.startswith(('Assistant:', 'AI:', 'Bot:', 'Friday:')):
                    if current_message:
                        # Save previous message
                        result = await self._save_text_message(current_message, current_role, session_id, conversation_id, metadata)
                        if session_id is None:
                            session_id = result["session_id"]
                            conversation_id = result["conversation_id"]
                        message_count += 1
                    current_message = [line[line.find(':')+1:].strip()]
                    current_role = "assistant"
                else:
                    # Continuation of current message
                    current_message.append(line)
            
            # Save the last message
            if current_message:
                await self._save_text_message(current_message, current_role, session_id, conversation_id, metadata)
                message_count += 1
            
            logger.info(f"Imported {message_count} messages from {file_path}")
            
        except Exception as e:
            logger.error(f"Error importing text conversation {file_path}: {e}")
    
    async def _save_text_message(self, message_lines: List[str], role: str, session_id: str, conversation_id: str, metadata: Dict):
        """Save a text message to the memory system"""
        content = '\n'.join(message_lines).strip()
        if content:
            return await self.conversations_db.store_message(
                content=content,
                role=role,
                session_id=session_id,
                conversation_id=conversation_id,
                metadata=metadata
            )


class EmbeddingService:
    """Handles embedding generation via LM Studio"""
    
    def __init__(self, base_url: str = "http://192.168.1.50:1234"):
        self.base_url = base_url
        self.embeddings_endpoint = f"{base_url}/v1/embeddings"
    
    async def generate_embedding(self, text: str, model: str = "text-embedding-nomic-embed-text-v1.5") -> List[float]:
        """Generate embedding for text using LM Studio"""
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": model,
                    "input": text
                }
                
                headers = {
                    "Content-Type": "application/json"
                }
                
                async with session.post(self.embeddings_endpoint, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and "data" in data and len(data["data"]) > 0:
                            return data["data"][0].get("embedding")
                        else:
                            logger.error(f"Invalid response format: {data}")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"Embedding API error {response.status}: {error_text}")
                        return None
                        error_text = await response.text()
                        logger.error(f"Embedding API error {response.status}: {error_text}")
                        return None
        
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    async def batch_generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        
        embeddings = []
        for text in texts:
            embedding = await self.generate_embedding(text)
            embeddings.append(embedding)
        
        return embeddings


class FridayMemorySystem:
    """Main memory system that coordinates all databases and operations"""
    
    def __init__(self, data_dir: str = "memory_data", enable_file_monitoring: bool = True, 
                 watch_directories: List[str] = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize databases
        self.conversations_db = ConversationDatabase(str(self.data_dir / "conversations.db"))
        self.ai_memory_db = AIMemoryDatabase(str(self.data_dir / "ai_memories.db"))
        self.schedule_db = ScheduleDatabase(str(self.data_dir / "schedule.db"))
        self.vscode_db = VSCodeProjectDatabase(str(self.data_dir / "vscode_project.db"))
        self.mcp_db = MCPToolCallDatabase(str(self.data_dir / "mcp_tool_calls.db"))
        
        # Initialize embedding service
        self.embedding_service = EmbeddingService()
        
        # Initialize and start file monitoring
        self.file_monitor = None
        if enable_file_monitoring:
            self.file_monitor = ConversationFileMonitor(self, watch_directories)
            # Create task to start monitoring (will run when event loop is available)
            asyncio.create_task(self._start_monitoring())
    
    async def _start_monitoring(self):
        """Internal method to start the file monitor"""
        if self.file_monitor:
            try:
                await self.file_monitor.start_monitoring()
                logger.info("File monitoring started")
            except Exception as e:
                logger.error(f"Error starting file monitoring: {e}")
    
    async def start_file_monitoring(self):
        """Start monitoring conversation files (manual start if needed)"""
        await self._start_monitoring()
    
    async def stop_file_monitoring(self):
        """Stop monitoring conversation files"""
        if self.file_monitor:
            await self.file_monitor.stop_monitoring()
            logger.info("File monitoring stopped")
    
    def add_watch_directory(self, directory: str):
        """Add a directory to monitor for conversation files"""
        if self.file_monitor:
            self.file_monitor.add_watch_directory(directory)
    
    async def get_system_health(self) -> Dict:
        """Get comprehensive system health and statistics"""
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "databases": {},
            "file_monitoring": {},
            "embedding_service": {}
        }
        
        try:
            # Check conversations database
            conversations_count = await self.conversations_db.execute_query(
                "SELECT COUNT(*) as count FROM messages"
            )
            sessions_count = await self.conversations_db.execute_query(
                "SELECT COUNT(*) as count FROM sessions"
            )
            health_data["databases"]["conversations"] = {
                "status": "healthy",
                "message_count": conversations_count[0]["count"] if conversations_count else 0,
                "session_count": sessions_count[0]["count"] if sessions_count else 0,
                "database_path": self.conversations_db.db_path
            }
            
            # Check AI memories database
            memories_count = await self.ai_memory_db.execute_query(
                "SELECT COUNT(*) as count FROM curated_memories"
            )
            high_importance_count = await self.ai_memory_db.execute_query(
                "SELECT COUNT(*) as count FROM curated_memories WHERE importance_level >= 7"
            )
            health_data["databases"]["ai_memories"] = {
                "status": "healthy",
                "memory_count": memories_count[0]["count"] if memories_count else 0,
                "high_importance_count": high_importance_count[0]["count"] if high_importance_count else 0,
                "database_path": self.ai_memory_db.db_path
            }
            
            # Check schedule database
            appointments_count = await self.schedule_db.execute_query(
                "SELECT COUNT(*) as count FROM appointments"
            )
            reminders_count = await self.schedule_db.execute_query(
                "SELECT COUNT(*) as count FROM reminders"
            )
            active_reminders_count = await self.schedule_db.execute_query(
                "SELECT COUNT(*) as count FROM reminders WHERE completed = 0"
            )
            health_data["databases"]["schedule"] = {
                "status": "healthy",
                "appointment_count": appointments_count[0]["count"] if appointments_count else 0,
                "reminder_count": reminders_count[0]["count"] if reminders_count else 0,
                "active_reminder_count": active_reminders_count[0]["count"] if active_reminders_count else 0,
                "database_path": self.schedule_db.db_path
            }
            
            # Check VS Code project database
            project_sessions_count = await self.vscode_db.execute_query(
                "SELECT COUNT(*) as count FROM project_sessions"
            )
            insights_count = await self.vscode_db.execute_query(
                "SELECT COUNT(*) as count FROM project_insights"
            )
            code_context_count = await self.vscode_db.execute_query(
                "SELECT COUNT(*) as count FROM code_context"
            )
            health_data["databases"]["vscode_project"] = {
                "status": "healthy",
                "session_count": project_sessions_count[0]["count"] if project_sessions_count else 0,
                "insight_count": insights_count[0]["count"] if insights_count else 0,
                "code_context_count": code_context_count[0]["count"] if code_context_count else 0,
                "database_path": self.vscode_db.db_path
            }
            
            # Check MCP tool calls database
            tool_calls_count = await self.mcp_db.execute_query(
                "SELECT COUNT(*) as count FROM tool_calls"
            )
            successful_calls_count = await self.mcp_db.execute_query(
                "SELECT COUNT(*) as count FROM tool_calls WHERE status = 'success'"
            )
            reflections_count = await self.mcp_db.execute_query(
                "SELECT COUNT(*) as count FROM ai_reflections"
            )
            patterns_count = await self.mcp_db.execute_query(
                "SELECT COUNT(*) as count FROM usage_patterns"
            )
            
            total_calls = tool_calls_count[0]["count"] if tool_calls_count else 0
            successful_calls = successful_calls_count[0]["count"] if successful_calls_count else 0
            success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0
            
            health_data["databases"]["mcp_tool_calls"] = {
                "status": "healthy",
                "total_tool_calls": total_calls,
                "successful_calls": successful_calls,
                "success_rate_percent": round(success_rate, 1),
                "ai_reflections": reflections_count[0]["count"] if reflections_count else 0,
                "usage_patterns": patterns_count[0]["count"] if patterns_count else 0,
                "database_path": self.mcp_db.db_path
            }
            
            # Check file monitoring status
            if self.file_monitor:
                health_data["file_monitoring"] = {
                    "status": "enabled",
                    "active_observers": len(self.file_monitor.observers),
                    "watched_directories": len(self.file_monitor.watch_directories + self.file_monitor.default_directories),
                    "processed_files": len(self.file_monitor.processed_files),
                    "monitored_paths": self.file_monitor.watch_directories + self.file_monitor.default_directories
                }
            else:
                health_data["file_monitoring"] = {
                    "status": "disabled",
                    "message": "File monitoring is not enabled"
                }
            
            # Check embedding service
            try:
                # Try a simple ping to the embedding service
                test_embedding = await self.embedding_service.generate_embedding("test")
                if test_embedding:
                    health_data["embedding_service"] = {
                        "status": "healthy",
                        "endpoint": self.embedding_service.embeddings_endpoint,
                        "embedding_dimensions": len(test_embedding)
                    }
                else:
                    health_data["embedding_service"] = {
                        "status": "unhealthy",
                        "endpoint": self.embedding_service.embeddings_endpoint,
                        "error": "Failed to generate test embedding"
                    }
            except Exception as e:
                health_data["embedding_service"] = {
                    "status": "unhealthy",
                    "endpoint": self.embedding_service.embeddings_endpoint,
                    "error": str(e)
                }
            
            # Overall system status
            unhealthy_components = []
            if health_data["embedding_service"]["status"] == "unhealthy":
                unhealthy_components.append("embedding_service")
            
            if unhealthy_components:
                health_data["status"] = "degraded"
                health_data["issues"] = unhealthy_components
            
        except Exception as e:
            health_data["status"] = "error"
            health_data["error"] = str(e)
            logger.error(f"Error getting system health: {e}")
        
        return health_data
    
    # Conversation operations
    async def store_conversation(self, content: str, role: str, session_id: str = None,
                               conversation_id: str = None, metadata: Dict = None) -> Dict:
        """Store a conversation message"""
        
        result = await self.conversations_db.store_message(
            content, role, session_id, conversation_id, metadata
        )
        
        # Generate and store embedding asynchronously
        asyncio.create_task(self._add_embedding_to_message(result["message_id"], content))
        
        return {
            "status": "success",
            "message_id": result["message_id"],
            "conversation_id": result["conversation_id"],
            "session_id": result["session_id"]
        }
    
    async def get_recent_context(self, limit: int = 5, session_id: str = None) -> Dict:
        """Get recent conversation context"""
        
        messages = await self.conversations_db.get_recent_messages(limit, session_id)
        
        return {
            "status": "success",
            "messages": messages,
            "count": len(messages)
        }
    
    # AI Memory operations
    async def create_memory(self, content: str, memory_type: str = None,
                          importance_level: int = 5, tags: List[str] = None,
                          source_conversation_id: str = None) -> Dict:
        """Create a curated memory"""
        
        memory_id = await self.ai_memory_db.create_memory(
            content, memory_type, importance_level, tags, source_conversation_id
        )
        
        # Generate and store embedding asynchronously
        asyncio.create_task(self._add_embedding_to_memory(memory_id, content))
        
        return {
            "status": "success",
            "memory_id": memory_id
        }
    
    async def update_memory(self, memory_id: str, content: str = None,
                          importance_level: int = None, tags: List[str] = None) -> Dict:
        """Update an existing memory"""
        
        success = await self.ai_memory_db.update_memory(memory_id, content, importance_level, tags)
        
        # If content was updated, regenerate embedding
        if content is not None:
            asyncio.create_task(self._add_embedding_to_memory(memory_id, content))
        
        return {
            "status": "success" if success else "error",
            "memory_id": memory_id
        }
    
    # Schedule operations
    async def create_appointment(self, title: str, scheduled_datetime: str,
                               description: str = None, location: str = None,
                               source_conversation_id: str = None) -> Dict:
        """Create an appointment"""
        
        appointment_id = await self.schedule_db.create_appointment(
            title, scheduled_datetime, description, location, source_conversation_id
        )
        
        # Generate embedding for search (combine title and description)
        content_for_embedding = f"{title}"
        if description:
            content_for_embedding += f" {description}"
        
        asyncio.create_task(self._add_embedding_to_appointment(appointment_id, content_for_embedding))
        
        return {
            "status": "success",
            "appointment_id": appointment_id
        }
    
    async def create_reminder(self, content: str, due_datetime: str,
                            priority_level: int = 5, source_conversation_id: str = None) -> Dict:
        """Create a reminder"""
        
        reminder_id = await self.schedule_db.create_reminder(
            content, due_datetime, priority_level, source_conversation_id
        )
        
        # Generate and store embedding for the reminder content
        asyncio.create_task(self._add_embedding_to_reminder(reminder_id, content))
        
        return {
            "status": "success",
            "reminder_id": reminder_id
        }
    
    # VS Code project operations
    async def save_development_session(self, workspace_path: str, active_files: List[str] = None,
                                     git_branch: str = None, session_summary: str = None) -> Dict:
        """Save development session"""
        
        session_id = await self.vscode_db.save_development_session(
            workspace_path, active_files, git_branch, session_summary
        )
        
        return {
            "status": "success",
            "session_id": session_id
        }
    
    async def store_project_insight(self, content: str, insight_type: str = None,
                                  related_files: List[str] = None, importance_level: int = 5,
                                  source_conversation_id: str = None) -> Dict:
        """Store project insight"""
        
        insight_id = await self.vscode_db.store_project_insight(
            content, insight_type, related_files, importance_level, source_conversation_id
        )
        
        # Generate and store embedding for the insight content
        asyncio.create_task(self._add_embedding_to_project_insight(insight_id, content))
        
        return {
            "status": "success",
            "insight_id": insight_id
        }
    
    async def search_project_history(self, query: str, limit: int = 10) -> Dict:
        """Search VS Code project history using semantic similarity"""
        
        # Generate embedding for the search query
        query_embedding = await self.embedding_service.generate_embedding(query)
        if not query_embedding:
            return await self._text_based_project_search(query, limit)
        
        all_results = []
        
        # Search development conversations
        conversation_results = await self._search_development_conversations(query_embedding, limit)
        all_results.extend(conversation_results)
        
        # Search project insights
        insight_results = await self._search_project_insights(query_embedding, limit)
        all_results.extend(insight_results)
        
        # Search code context
        context_results = await self._search_code_context(query_embedding, limit)
        all_results.extend(context_results)
        
        # Sort by similarity score and return top results
        all_results.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        return {
            "status": "success",
            "query": query,
            "results": all_results[:limit],
            "count": len(all_results[:limit])
        }
    
    async def _search_development_conversations(self, query_embedding: List[float], limit: int) -> List[Dict]:
        """Search development conversations using semantic similarity"""
        
        query = """
            SELECT conversation_id, session_id, timestamp, chat_context_id, 
                   conversation_content, decisions_made, code_changes, embedding
            FROM development_conversations 
            WHERE embedding IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 500
        """
        
        rows = await self.vscode_db.execute_query(query)
        results = []
        
        for row in rows:
            if row["embedding"]:
                stored_embedding = np.frombuffer(row["embedding"], dtype=np.float32).tolist()
                similarity = self._calculate_cosine_similarity(query_embedding, stored_embedding)
                
                if similarity > 0.3:
                    result = {
                        "type": "development_conversation",
                        "similarity_score": similarity,
                        "data": {
                            "conversation_id": row["conversation_id"],
                            "session_id": row["session_id"],
                            "timestamp": row["timestamp"],
                            "chat_context_id": row["chat_context_id"],
                            "conversation_content": row["conversation_content"],
                            "decisions_made": json.loads(row["decisions_made"]) if row["decisions_made"] else None,
                            "code_changes": json.loads(row["code_changes"]) if row["code_changes"] else None
                        }
                    }
                    results.append(result)
        
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]
    
    async def _search_project_insights(self, query_embedding: List[float], limit: int) -> List[Dict]:
        """Search project insights using semantic similarity"""
        
        query = """
            SELECT insight_id, timestamp_created, timestamp_updated, insight_type,
                   content, related_files, source_conversation_id, importance_level, embedding
            FROM project_insights 
            WHERE embedding IS NOT NULL
        """
        
        rows = await self.vscode_db.execute_query(query)
        results = []
        
        for row in rows:
            if row["embedding"]:
                stored_embedding = np.frombuffer(row["embedding"], dtype=np.float32).tolist()
                similarity = self._calculate_cosine_similarity(query_embedding, stored_embedding)
                
                if similarity > 0.3:
                    result = {
                        "type": "project_insight",
                        "similarity_score": similarity,
                        "data": {
                            "insight_id": row["insight_id"],
                            "timestamp_created": row["timestamp_created"],
                            "timestamp_updated": row["timestamp_updated"],
                            "insight_type": row["insight_type"],
                            "content": row["content"],
                            "related_files": json.loads(row["related_files"]) if row["related_files"] else None,
                            "source_conversation_id": row["source_conversation_id"],
                            "importance_level": row["importance_level"]
                        }
                    }
                    results.append(result)
        
        # Boost results based on importance level
        for result in results:
            importance_boost = result["data"]["importance_level"] / 10.0 * 0.15
            result["similarity_score"] += importance_boost
        
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]
    
    async def _search_code_context(self, query_embedding: List[float], limit: int) -> List[Dict]:
        """Search code context using semantic similarity"""
        
        query = """
            SELECT context_id, timestamp, file_path, function_name, 
                   description, purpose, related_insights, embedding
            FROM code_context 
            WHERE embedding IS NOT NULL
        """
        
        rows = await self.vscode_db.execute_query(query)
        results = []
        
        for row in rows:
            if row["embedding"]:
                stored_embedding = np.frombuffer(row["embedding"], dtype=np.float32).tolist()
                similarity = self._calculate_cosine_similarity(query_embedding, stored_embedding)
                
                if similarity > 0.3:
                    result = {
                        "type": "code_context",
                        "similarity_score": similarity,
                        "data": {
                            "context_id": row["context_id"],
                            "timestamp": row["timestamp"],
                            "file_path": row["file_path"],
                            "function_name": row["function_name"],
                            "description": row["description"],
                            "purpose": row["purpose"],
                            "related_insights": json.loads(row["related_insights"]) if row["related_insights"] else None
                        }
                    }
                    results.append(result)
        
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]
    
    async def _text_based_project_search(self, query: str, limit: int) -> Dict:
        """Fallback text-based search for project data"""
        
        query_words = query.lower().split()
        results = []
        
        # Search project insights
        for word in query_words:
            rows = await self.vscode_db.execute_query(
                "SELECT * FROM project_insights WHERE LOWER(content) LIKE ? ORDER BY importance_level DESC LIMIT ?",
                (f"%{word}%", limit)
            )
            for row in rows:
                results.append({
                    "type": "project_insight",
                    "similarity_score": 0.5,
                    "data": dict(row)
                })
        
        # Search code context
        for word in query_words:
            rows = await self.vscode_db.execute_query(
                "SELECT * FROM code_context WHERE LOWER(description) LIKE ? OR LOWER(purpose) LIKE ? ORDER BY timestamp DESC LIMIT ?",
                (f"%{word}%", f"%{word}%", limit)
            )
            for row in rows:
                results.append({
                    "type": "code_context",
                    "similarity_score": 0.5,
                    "data": dict(row)
                })
        
        # Remove duplicates
        seen = set()
        unique_results = []
        for result in results:
            key = f"{result['type']}_{result['data'].get('insight_id', result['data'].get('context_id', ''))}"
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
        
        return {
            "status": "success",
            "query": query,
            "results": unique_results[:limit],
            "count": len(unique_results[:limit]),
            "note": "Used text-based search (embeddings unavailable)"
        }
    
    async def link_code_context(self, file_path: str, description: str,
                              function_name: str = None, conversation_id: str = None) -> Dict:
        """Link conversation to code context"""
        
        context_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Store the code context
        await self.vscode_db.execute_update(
            """INSERT INTO code_context 
               (context_id, timestamp, file_path, function_name, description) 
               VALUES (?, ?, ?, ?, ?)""",
            (context_id, timestamp, file_path, function_name, description)
        )
        
        # Generate and store embedding for the description
        asyncio.create_task(self._add_embedding_to_code_context(context_id, description))
        
        return {
            "status": "success",
            "context_id": context_id,
            "message": "Code context linked successfully"
        }
    
    async def get_project_continuity(self, workspace_path: str = None, limit: int = 5) -> Dict:
        """Get project continuity context"""
        
        continuity_data = {}
        
        # Get recent project sessions
        if workspace_path:
            session_query = """
                SELECT * FROM project_sessions 
                WHERE workspace_path = ? 
                ORDER BY start_timestamp DESC 
                LIMIT ?
            """
            params = (workspace_path, limit)
        else:
            session_query = """
                SELECT * FROM project_sessions 
                ORDER BY start_timestamp DESC 
                LIMIT ?
            """
            params = (limit,)
        
        sessions = await self.vscode_db.execute_query(session_query, params)
        continuity_data["recent_sessions"] = [dict(row) for row in sessions]
        
        # Get recent development conversations
        recent_conversations = await self.vscode_db.execute_query(
            """SELECT * FROM development_conversations 
               ORDER BY timestamp DESC 
               LIMIT ?""",
            (limit,)
        )
        continuity_data["recent_conversations"] = [dict(row) for row in recent_conversations]
        
        # Get high-importance insights
        important_insights = await self.vscode_db.execute_query(
            """SELECT * FROM project_insights 
               WHERE importance_level >= 7 
               ORDER BY timestamp_updated DESC 
               LIMIT ?""",
            (limit,)
        )
        continuity_data["important_insights"] = [dict(row) for row in important_insights]
        
        # Get recent code context
        recent_context = await self.vscode_db.execute_query(
            """SELECT * FROM code_context 
               ORDER BY timestamp DESC 
               LIMIT ?""",
            (limit,)
        )
        continuity_data["recent_code_context"] = [dict(row) for row in recent_context]
        
        return {
            "status": "success",
            "workspace_path": workspace_path,
            "continuity_data": continuity_data
        }
    
    # Search operations
    async def search_memories(self, query: str, limit: int = 10, database_filter: str = "all",
                            min_importance: int = None, max_importance: int = None,
                            memory_type: str = None) -> Dict:
        """Search memories across databases using semantic similarity with importance filtering"""
        
        # Generate embedding for the search query
        query_embedding = await self.embedding_service.generate_embedding(query)
        if not query_embedding:
            # Fallback to text-based search if embedding fails
            return await self._text_based_search(query, limit, database_filter, min_importance, max_importance, memory_type)
        
        all_results = []
        
        # Search conversations
        if database_filter in ["all", "conversations"]:
            conversation_results = await self._search_conversations(query_embedding, limit * 2)
            all_results.extend(conversation_results)
        
        # Search AI memories with importance filtering
        if database_filter in ["all", "ai_memories"]:
            memory_results = await self._search_ai_memories(query_embedding, limit * 2, min_importance, max_importance, memory_type)
            all_results.extend(memory_results)
        
        # Search schedule items
        if database_filter in ["all", "schedule"]:
            schedule_results = await self._search_schedule(query_embedding, limit)
            all_results.extend(schedule_results)
        
        # Sort all results by similarity score and return top results
        all_results.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        return {
            "status": "success",
            "query": query,
            "results": all_results[:limit],
            "count": len(all_results[:limit]),
            "filters": {
                "min_importance": min_importance,
                "max_importance": max_importance,
                "memory_type": memory_type,
                "database_filter": database_filter
            }
        }
    
    async def _search_conversations(self, query_embedding: List[float], limit: int) -> List[Dict]:
        """Search conversation messages using semantic similarity"""
        
        # Get all messages with embeddings
        query = """
            SELECT message_id, conversation_id, timestamp, role, content, metadata, embedding
            FROM messages 
            WHERE embedding IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 1000
        """
        
        rows = await self.conversations_db.execute_query(query)
        results = []
        
        for row in rows:
            if row["embedding"]:
                # Convert binary embedding back to float array
                stored_embedding = np.frombuffer(row["embedding"], dtype=np.float32).tolist()
                similarity = self._calculate_cosine_similarity(query_embedding, stored_embedding)
                
                if similarity > 0.3:  # Threshold for relevance
                    result = {
                        "type": "conversation",
                        "similarity_score": similarity,
                        "data": {
                            "message_id": row["message_id"],
                            "conversation_id": row["conversation_id"],
                            "timestamp": row["timestamp"],
                            "role": row["role"],
                            "content": row["content"],
                            "metadata": json.loads(row["metadata"]) if row["metadata"] else None
                        }
                    }
                    results.append(result)
        
        # Sort by similarity and return top results
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]
    
    async def _search_ai_memories(self, query_embedding: List[float], limit: int,
                                min_importance: int = None, max_importance: int = None,
                                memory_type: str = None) -> List[Dict]:
        """Search AI curated memories using semantic similarity with importance filtering"""
        
        # Build SQL query with optional filters
        sql = "SELECT memory_id, timestamp_created, timestamp_updated, source_conversation_id, memory_type, content, importance_level, tags, embedding FROM curated_memories WHERE embedding IS NOT NULL"
        params = []
        
        if min_importance is not None:
            sql += " AND importance_level >= ?"
            params.append(min_importance)
            
        if max_importance is not None:
            sql += " AND importance_level <= ?"
            params.append(max_importance)
            
        if memory_type is not None:
            sql += " AND memory_type = ?"
            params.append(memory_type)
        
        rows = await self.ai_memory_db.execute_query(sql, params)
        results = []
        
        for row in rows:
            if row["embedding"]:
                stored_embedding = np.frombuffer(row["embedding"], dtype=np.float32).tolist()
                similarity = self._calculate_cosine_similarity(query_embedding, stored_embedding)
                
                if similarity > 0.3:  # Threshold for relevance
                    result = {
                        "type": "ai_memory",
                        "similarity_score": similarity,
                        "data": {
                            "memory_id": row["memory_id"],
                            "timestamp_created": row["timestamp_created"],
                            "timestamp_updated": row["timestamp_updated"],
                            "source_conversation_id": row["source_conversation_id"],
                            "memory_type": row["memory_type"],
                            "content": row["content"],
                            "importance_level": row["importance_level"],
                            "tags": json.loads(row["tags"]) if row["tags"] else None
                        }
                    }
                    results.append(result)
        
        # Boost results based on importance level
        for result in results:
            importance_boost = result["data"]["importance_level"] / 10.0 * 0.1
            result["similarity_score"] += importance_boost
        
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]
    
    async def _search_schedule(self, query_embedding: List[float], limit: int) -> List[Dict]:
        """Search appointments and reminders using semantic similarity"""
        
        results = []
        
        # Search appointments
        appointment_query = """
            SELECT appointment_id, timestamp_created, scheduled_datetime, title, 
                   description, location, source_conversation_id, embedding
            FROM appointments 
            WHERE embedding IS NOT NULL
        """
        
        rows = await self.schedule_db.execute_query(appointment_query)
        
        for row in rows:
            if row["embedding"]:
                stored_embedding = np.frombuffer(row["embedding"], dtype=np.float32).tolist()
                similarity = self._calculate_cosine_similarity(query_embedding, stored_embedding)
                
                if similarity > 0.3:
                    result = {
                        "type": "appointment",
                        "similarity_score": similarity,
                        "data": {
                            "appointment_id": row["appointment_id"],
                            "timestamp_created": row["timestamp_created"],
                            "scheduled_datetime": row["scheduled_datetime"],
                            "title": row["title"],
                            "description": row["description"],
                            "location": row["location"],
                            "source_conversation_id": row["source_conversation_id"]
                        }
                    }
                    results.append(result)
        
        # Search reminders
        reminder_query = """
            SELECT reminder_id, timestamp_created, due_datetime, content, 
                   priority_level, completed, source_conversation_id, embedding
            FROM reminders 
            WHERE embedding IS NOT NULL
        """
        
        rows = await self.schedule_db.execute_query(reminder_query)
        
        for row in rows:
            if row["embedding"]:
                stored_embedding = np.frombuffer(row["embedding"], dtype=np.float32).tolist()
                similarity = self._calculate_cosine_similarity(query_embedding, stored_embedding)
                
                if similarity > 0.3:
                    result = {
                        "type": "reminder",
                        "similarity_score": similarity,
                        "data": {
                            "reminder_id": row["reminder_id"],
                            "timestamp_created": row["timestamp_created"],
                            "due_datetime": row["due_datetime"],
                            "content": row["content"],
                            "priority_level": row["priority_level"],
                            "completed": bool(row["completed"]),
                            "source_conversation_id": row["source_conversation_id"]
                        }
                    }
                    results.append(result)
        
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]
    
    def _calculate_cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1, dtype=np.float32)
            vec2 = np.array(embedding2, dtype=np.float32)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    async def _text_based_search(self, query: str, limit: int, database_filter: str,
                               min_importance: int = None, max_importance: int = None,
                               memory_type: str = None) -> Dict:
        """Fallback text-based search when embeddings are unavailable with importance filtering"""
        
        query_words = query.lower().split()
        results = []
        
        if database_filter in ["all", "conversations"]:
            # Search conversations with text matching
            for word in query_words:
                rows = await self.conversations_db.execute_query(
                    "SELECT * FROM messages WHERE LOWER(content) LIKE ? ORDER BY timestamp DESC LIMIT ?",
                    (f"%{word}%", limit)
                )
                for row in rows:
                    results.append({
                        "type": "conversation",
                        "similarity_score": 0.5,  # Default score for text match
                        "data": dict(row)
                    })
        
        if database_filter in ["all", "ai_memories"]:
            # Search AI memories with text matching and filters
            sql = "SELECT * FROM curated_memories WHERE 1=1"
            params = []
            
            # Add content search
            content_conditions = []
            for word in query_words:
                content_conditions.append("LOWER(content) LIKE ?")
                params.append(f"%{word}%")
            
            if content_conditions:
                sql += f" AND ({' OR '.join(content_conditions)})"
            
            # Add importance filters
            if min_importance is not None:
                sql += " AND importance_level >= ?"
                params.append(min_importance)
                
            if max_importance is not None:
                sql += " AND importance_level <= ?"
                params.append(max_importance)
                
            if memory_type is not None:
                sql += " AND memory_type = ?"
                params.append(memory_type)
            
            sql += " ORDER BY importance_level DESC LIMIT ?"
            params.append(limit)
            
            rows = await self.ai_memory_db.execute_query(sql, params)
            for row in rows:
                results.append({
                    "type": "ai_memory",
                    "similarity_score": 0.5,
                    "data": dict(row)
                })
        
        # Remove duplicates and limit results
        seen = set()
        unique_results = []
        for result in results:
            key = f"{result['type']}_{result['data'].get('message_id', result['data'].get('memory_id', ''))}"
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
        
        return {
            "status": "success",
            "query": query,
            "results": unique_results[:limit],
            "count": len(unique_results[:limit]),
            "filters": {
                "min_importance": min_importance,
                "max_importance": max_importance,
                "memory_type": memory_type,
                "database_filter": database_filter
            },
            "search_type": "text_based",
            "note": "Used text-based search (embeddings unavailable)"
        }
    
    # Helper methods for embedding management
    async def _add_embedding_to_message(self, message_id: str, content: str):
        """Add embedding to a message (background task)"""
        try:
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                # Convert to binary format for storage
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.conversations_db.execute_update(
                    "UPDATE messages SET embedding = ? WHERE message_id = ?",
                    (embedding_blob, message_id)
                )
        except Exception as e:
            logger.error(f"Error adding embedding to message {message_id}: {e}")
    
    async def _add_embedding_to_memory(self, memory_id: str, content: str):
        """Add embedding to a memory (background task)"""
        try:
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                # Convert to binary format for storage
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.ai_memory_db.execute_update(
                    "UPDATE curated_memories SET embedding = ? WHERE memory_id = ?",
                    (embedding_blob, memory_id)
                )
        except Exception as e:
            logger.error(f"Error adding embedding to memory {memory_id}: {e}")
    
    async def _add_embedding_to_appointment(self, appointment_id: str, content: str):
        """Add embedding to an appointment (background task)"""
        try:
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.schedule_db.execute_update(
                    "UPDATE appointments SET embedding = ? WHERE appointment_id = ?",
                    (embedding_blob, appointment_id)
                )
        except Exception as e:
            logger.error(f"Error adding embedding to appointment {appointment_id}: {e}")
    
    async def _add_embedding_to_reminder(self, reminder_id: str, content: str):
        """Add embedding to a reminder (background task)"""
        try:
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.schedule_db.execute_update(
                    "UPDATE reminders SET embedding = ? WHERE reminder_id = ?",
                    (embedding_blob, reminder_id)
                )
        except Exception as e:
            logger.error(f"Error adding embedding to reminder {reminder_id}: {e}")
    
    async def _add_embedding_to_project_insight(self, insight_id: str, content: str):
        """Add embedding to a project insight (background task)"""
        try:
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.vscode_db.execute_update(
                    "UPDATE project_insights SET embedding = ? WHERE insight_id = ?",
                    (embedding_blob, insight_id)
                )
        except Exception as e:
            logger.error(f"Error adding embedding to project insight {insight_id}: {e}")
    
    async def _add_embedding_to_code_context(self, context_id: str, content: str):
        """Add embedding to code context (background task)"""
        try:
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.vscode_db.execute_update(
                    "UPDATE code_context SET embedding = ? WHERE context_id = ?",
                    (embedding_blob, context_id)
                )
        except Exception as e:
            logger.error(f"Error adding embedding to code context {context_id}: {e}")
    
    async def _add_embedding_to_development_conversation(self, conversation_id: str, content: str):
        """Add embedding to development conversation (background task)"""
        try:
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.vscode_db.execute_update(
                    "UPDATE development_conversations SET embedding = ? WHERE conversation_id = ?",
                    (embedding_blob, conversation_id)
                )
        except Exception as e:
            logger.error(f"Error adding embedding to development conversation {conversation_id}: {e}")
    
    # MCP Tool Call Logging and AI Self-Reflection Operations
    async def log_tool_call(self, client_id: str, tool_name: str, parameters: Dict = None,
                          execution_time_ms: float = None, status: str = "success",
                          result: Any = None, error_message: str = None) -> str:
        """Log an MCP tool call for AI self-reflection"""
        
        return await self.mcp_db.log_tool_call(
            client_id, tool_name, parameters, execution_time_ms, 
            status, result, error_message
        )
    
    async def get_tool_usage_summary(self, days: int = 7, client_id: str = None) -> Dict:
        """Get comprehensive tool usage summary for AI analysis"""
        
        stats = await self.mcp_db.get_tool_usage_stats(days, client_id)
        
        # Generate AI insights from the stats
        insights = await self._generate_tool_usage_insights(stats)
        
        return {
            "status": "success",
            "period_days": days,
            "stats": stats,
            "insights": insights
        }
    
    async def reflect_on_tool_usage(self, days: int = 7, client_id: str = None) -> Dict:
        """AI self-reflection on tool usage patterns"""
        
        stats = await self.mcp_db.get_tool_usage_stats(days, client_id)
        
        if stats["total_calls"] == 0:
            reflection_content = f"No tool calls recorded in the past {days} days. This suggests either low activity or potential logging issues."
            insights = ["Consider checking if tool call logging is properly configured"]
            recommendations = ["Verify MCP server integration", "Test basic tool functionality"]
        else:
            # Generate detailed AI reflection
            reflection_content = await self._generate_ai_reflection_content(stats, days)
            insights = await self._extract_usage_insights(stats)
            recommendations = await self._generate_usage_recommendations(stats)
        
        # Store the reflection for future reference
        reflection_id = await self.mcp_db.store_ai_reflection(
            reflection_type="tool_usage_analysis",
            content=reflection_content,
            insights=insights,
            recommendations=recommendations,
            confidence_level=0.8,
            source_period_days=days
        )
        
        return {
            "status": "success",
            "reflection_id": reflection_id,
            "period_days": days,
            "reflection": {
                "content": reflection_content,
                "insights": insights,
                "recommendations": recommendations,
                "patterns": await self._identify_usage_patterns(stats)
            }
        }
    
    async def get_ai_insights(self, limit: int = 5, insight_type: str = None) -> Dict:
        """Get recent AI self-reflection insights"""
        
        reflections = await self.mcp_db.get_recent_reflections(limit, insight_type)
        
        return {
            "status": "success",
            "reflections": reflections,
            "count": len(reflections)
        }
    
    async def _generate_tool_usage_insights(self, stats: Dict) -> Dict:
        """Generate AI insights from tool usage statistics"""
        
        total_calls = stats["total_calls"]
        success_rate = stats["success_rate"]
        tool_frequency = stats["tool_frequency"]
        
        # Generate summary insights
        most_used_tool = max(tool_frequency.items(), key=lambda x: x[1])[0] if tool_frequency else None
        least_reliable_tools = [
            pattern["tool"] for pattern in stats["error_patterns"] 
            if pattern["error_rate"] > 20
        ]
        
        insights = {
            "total_tool_calls": total_calls,
            "success_rate_percent": round(success_rate, 1),
            "most_used_tool": most_used_tool,
            "tools_with_issues": least_reliable_tools,
            "avg_execution_time_ms": round(stats["avg_execution_time"], 2),
            "reflection": await self._generate_summary_reflection(stats)
        }
        
        return insights
    
    async def _generate_ai_reflection_content(self, stats: Dict, days: int) -> str:
        """Generate AI reflection content about tool usage"""
        
        total_calls = stats["total_calls"]
        success_rate = stats["success_rate"]
        most_used = max(stats["tool_frequency"].items(), key=lambda x: x[1]) if stats["tool_frequency"] else ("unknown", 0)
        
        reflection = f"""Tool Usage Analysis for Past {days} Days:
        
I processed {total_calls} tool calls with a {success_rate:.1f}% success rate. 
My most frequently used tool was '{most_used[0]}' ({most_used[1]} calls), which suggests this is a core capability I rely on heavily.

Performance Assessment:"""
        
        if success_rate >= 95:
            reflection += "\nMy tool execution is highly reliable with minimal errors."
        elif success_rate >= 80:
            reflection += "\nMy tool execution is generally reliable but there's room for improvement."
        else:
            reflection += "\nMy tool execution has significant reliability issues that need attention."
        
        if stats["error_patterns"]:
            reflection += f"\n\nError Analysis:\nI encountered issues with {len(stats['error_patterns'])} different tools. "
            high_error_tools = [p for p in stats["error_patterns"] if p["error_rate"] > 10]
            if high_error_tools:
                reflection += f"Tools with high error rates: {', '.join([p['tool'] for p in high_error_tools])}"
        
        return reflection
    
    async def _extract_usage_insights(self, stats: Dict) -> List[str]:
        """Extract specific insights from usage patterns"""
        
        insights = []
        
        # Tool frequency insights
        if stats["tool_frequency"]:
            most_used = max(stats["tool_frequency"].items(), key=lambda x: x[1])
            insights.append(f"I rely heavily on '{most_used[0]}' tool ({most_used[1]} uses)")
            
            if len(stats["tool_frequency"]) > 1:
                least_used = min(stats["tool_frequency"].items(), key=lambda x: x[1])
                insights.append(f"'{least_used[0]}' is underutilized ({least_used[1]} uses)")
        
        # Performance insights
        if stats["success_rate"] < 90:
            insights.append(f"Success rate of {stats['success_rate']:.1f}% indicates reliability issues")
        
        if stats["avg_execution_time"] > 1000:  # More than 1 second
            insights.append(f"Average execution time of {stats['avg_execution_time']:.0f}ms suggests performance bottlenecks")
        
        # Error pattern insights
        for pattern in stats["error_patterns"]:
            if pattern["error_rate"] > 15:
                insights.append(f"'{pattern['tool']}' has high error rate of {pattern['error_rate']:.1f}%")
        
        return insights
    
    async def _generate_usage_recommendations(self, stats: Dict) -> List[str]:
        """Generate recommendations based on usage patterns"""
        
        recommendations = []
        
        # Success rate recommendations
        if stats["success_rate"] < 80:
            recommendations.append("Investigate and fix tools with high failure rates")
            recommendations.append("Implement better error handling and retry logic")
        
        # Performance recommendations
        if stats["avg_execution_time"] > 500:
            recommendations.append("Optimize slow-performing tools for better responsiveness")
        
        # Tool usage recommendations
        if stats["tool_frequency"]:
            tool_counts = list(stats["tool_frequency"].values())
            if len(tool_counts) > 1 and max(tool_counts) > sum(tool_counts) * 0.7:
                recommendations.append("Consider diversifying tool usage to reduce over-reliance on single tools")
        
        # Error-specific recommendations
        for pattern in stats["error_patterns"]:
            if pattern["error_rate"] > 20:
                recommendations.append(f"Prioritize fixing issues with '{pattern['tool']}' tool")
        
        if not recommendations:
            recommendations.append("Tool usage patterns look healthy - continue current practices")
        
        return recommendations
    
    async def _identify_usage_patterns(self, stats: Dict) -> Dict:
        """Identify interesting patterns in tool usage"""
        
        patterns = {
            "peak_usage_tools": [],
            "problematic_tools": [],
            "efficiency_metrics": {},
            "usage_distribution": {}
        }
        
        # Peak usage tools
        if stats["tool_frequency"]:
            sorted_tools = sorted(stats["tool_frequency"].items(), key=lambda x: x[1], reverse=True)
            for tool, count in sorted_tools[:3]:
                patterns["peak_usage_tools"].append({
                    "tool": tool,
                    "count": count,
                    "percentage": (count / stats["total_calls"]) * 100,
                    "insight": f"'{tool}' represents {(count / stats['total_calls']) * 100:.1f}% of all tool usage"
                })
        
        # Problematic tools
        for error_pattern in stats["error_patterns"]:
            if error_pattern["error_rate"] > 10:
                patterns["problematic_tools"].append({
                    "tool": error_pattern["tool"],
                    "error_rate": error_pattern["error_rate"],
                    "insight": f"'{error_pattern['tool']}' fails {error_pattern['error_rate']:.1f}% of the time"
                })
        
        # Efficiency metrics
        patterns["efficiency_metrics"] = {
            "overall_success_rate": stats["success_rate"],
            "avg_execution_time": stats["avg_execution_time"],
            "tools_count": len(stats["tool_frequency"]),
            "insight": f"Using {len(stats['tool_frequency'])} different tools with {stats['success_rate']:.1f}% reliability"
        }
        
        return patterns
    
    async def _generate_summary_reflection(self, stats: Dict) -> str:
        """Generate a brief AI reflection summary"""
        
        if stats["total_calls"] == 0:
            return "I haven't made any tool calls recently, which might indicate low activity or configuration issues."
        
        success_rate = stats["success_rate"]
        most_used = max(stats["tool_frequency"].items(), key=lambda x: x[1])[0] if stats["tool_frequency"] else "unknown"
        
        if success_rate >= 95:
            tone = "performing excellently"
        elif success_rate >= 80:
            tone = "performing well"
        elif success_rate >= 60:
            tone = "experiencing some issues"
        else:
            tone = "struggling with reliability"
        
        return f"I'm {tone} with a {success_rate:.1f}% success rate across {stats['total_calls']} tool calls. My primary tool usage focuses on '{most_used}', suggesting consistent workflow patterns."

    async def run_database_maintenance(self, force: bool = False) -> Dict:
        """Run database maintenance including cleanup and optimization"""
        try:
            from database_maintenance import DatabaseMaintenance
            
            maintenance = DatabaseMaintenance(self)
            return await maintenance.run_maintenance(force)
            
        except ImportError:
            logger.warning("Database maintenance module not available")
            return {"error": "Maintenance module not found", "manual_cleanup_recommended": True}
        except Exception as e:
            logger.error(f"Database maintenance failed: {e}")
            return {"error": str(e), "status": "failed"}


# Example usage and testing
async def main():
    """Test the memory system with file monitoring and semantic search"""
    
    memory = FridayMemorySystem(enable_file_monitoring=True)
    
    print("=== Testing Friday Memory System with File Monitoring ===\n")
    
    # First test basic database operations
    print("1. Testing basic storage operations...")
    
    # Test storing conversations manually
    print("\n2. Storing initial conversations...")
    conv1 = await memory.store_conversation(
        content="I prefer detailed technical explanations when discussing programming concepts",
        role="user"
    )
    print(f"Stored conversation: {conv1['message_id']}")
    
    conv2 = await memory.store_conversation(
        content="Could you explain how semantic search works with embeddings?",
        role="user"
    )
    print(f"Stored conversation: {conv2['message_id']}")
    
    # Test creating memories
    print("\n3. Creating curated memories...")
    memory1 = await memory.create_memory(
        content="User enjoys deep technical discussions about AI and machine learning",
        memory_type="preference",
        importance_level=8,
        tags=["user_preference", "technical", "ai"],
        source_conversation_id=conv1["conversation_id"]
    )
    print(f"Created memory: {memory1['memory_id']}")
    
    memory2 = await memory.create_memory(
        content="User is building a persistent memory system for AI assistant with file monitoring",
        memory_type="project",
        importance_level=9,
        tags=["project", "memory_system", "ai_assistant", "file_monitoring"]
    )
    print(f"Created memory: {memory2['memory_id']}")
    
    # Test appointments and reminders
    print("\n4. Creating schedule items...")
    appointment = await memory.create_appointment(
        title="Review AI memory system implementation",
        scheduled_datetime="2025-08-03T10:00:00Z",
        description="Go through the semantic search functionality and test file monitoring"
    )
    print(f"Created appointment: {appointment['appointment_id']}")
    
    reminder = await memory.create_reminder(
        content="Test the MCP server integration with LM Studio and file monitoring",
        due_datetime="2025-08-03T14:00:00Z",
        priority_level=8
    )
    print(f"Created reminder: {reminder['reminder_id']}")
    
    # Test VS Code project tracking
    print("\n5. Testing VS Code project features...")
    session = await memory.save_development_session(
        workspace_path="/path/to/friday/project",
        active_files=["friday_memory_system.py", "friday_memory_mcp_server.py"],
        git_branch="main",
        session_summary="Implementing file monitoring and semantic search for memory system"
    )
    print(f"Saved development session: {session['session_id']}")
    
    insight = await memory.store_project_insight(
        content="Added file monitoring system to automatically capture conversations from LM Studio and VS Code chat files",
        insight_type="architecture_decision",
        related_files=["friday_memory_system.py", "friday_memory_mcp_server.py"],
        importance_level=9
    )
    print(f"Stored project insight: {insight['insight_id']}")
    
    # Wait a moment for embeddings to be generated (in real use, this happens in background)
    print("\n6. Waiting for embeddings to be generated...")
    await asyncio.sleep(2)
    
    # Test semantic search
    print("\n7. Testing semantic search...")
    
    # Search for user preferences
    search1 = await memory.search_memories("user likes technical details", limit=3)
    print(f"Search 'user likes technical details': Found {search1['count']} results")
    for result in search1['results']:
        print(f"  - {result['type']}: {result.get('similarity_score', 'N/A'):.3f} similarity")
    
    # Search for project-related content
    search2 = await memory.search_memories("memory system project file monitoring", limit=3)
    print(f"\nSearch 'memory system project file monitoring': Found {search2['count']} results")
    for result in search2['results']:
        print(f"  - {result['type']}: {result.get('similarity_score', 'N/A'):.3f} similarity")
    
    # Search project history
    project_search = await memory.search_project_history("file monitoring architecture decisions")
    print(f"\nProject search 'file monitoring architecture': Found {project_search['count']} results")
    for result in project_search['results']:
        print(f"  - {result['type']}: {result.get('similarity_score', 'N/A'):.3f} similarity")
    
    # Test project continuity
    continuity = await memory.get_project_continuity("/path/to/friday/project")
    print(f"\nProject continuity data: {len(continuity['continuity_data']['recent_sessions'])} sessions, "
          f"{len(continuity['continuity_data']['important_insights'])} important insights")
    
    print("\n8. Starting file monitoring...")
    # Now that all other systems are initialized and tested, start file monitoring
    await memory.start_file_monitoring()
    
    print("   File monitoring is now starting...")
    print("   The system will automatically detect and import conversations from:")
    print("   - VS Code chat sessions")
    print("   - LM Studio conversations")
    
    print("\n=== Memory System Test Complete ===")
    print("Note: System is fully initialized and file monitoring is now active. Press Ctrl+C to stop.")
    
    try:
        # Keep the program running to demonstrate file monitoring
        while True:
            await asyncio.sleep(10)
            # You could add periodic status updates here
    except KeyboardInterrupt:
        print("\nStopping file monitoring...")
        await memory.stop_file_monitoring()
        print("File monitoring stopped. Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())


async def test_friday_memory_system():
    """Test the Friday Memory System with file monitoring"""
    
    # Initialize the memory system with file monitoring enabled
    memory_system = FridayMemorySystem(enable_file_monitoring=True)
    
    print("🧠 Friday Memory System - Test with File Monitoring")
    print("=" * 60)
    
    # Start file monitoring
    print("\n📁 Starting file monitoring...")
    await memory_system.start_file_monitoring()
    
    print("\n📂 Monitoring these directories:")
    if memory_system.file_monitor:
        all_dirs = memory_system.file_monitor.watch_directories + memory_system.file_monitor.default_directories
        for directory in all_dirs:
            print(f"  • {directory}")
    
    # Test basic memory operations
    print("\n💭 Testing basic memory operations...")
    
    # Store a conversation
    result = await memory_system.store_conversation(
        content="Hello, we are testing the Friday memory system with file monitoring!",
        role="user"
    )
    print(f"✅ Stored conversation: {result['message_id']}")
    
    # Create an AI memory
    memory_result = await memory_system.create_memory(
        content="User is testing the file monitoring system for automatic conversation capture",
        memory_type="system_test",
        importance_level=7,
        tags=["test", "file_monitoring", "conversation_capture"]
    )
    print(f"✅ Created AI memory: {memory_result['memory_id']}")
    
    # Create a reminder
    reminder_result = await memory_system.create_reminder(
        content="Remember to check if VS Code conversations are being automatically captured",
        due_datetime="2025-08-03T12:00:00Z",
        priority_level=8
    )
    print(f"✅ Created reminder: {reminder_result['reminder_id']}")
    
    # Get recent context
    context = await memory_system.get_recent_context(limit=3)
    print(f"\n📜 Recent context ({context['count']} messages):")
    for msg in context['messages']:
        print(f"  • [{msg['role']}] {msg['content'][:50]}...")
    
    print(f"\n🔍 File monitoring status:")
    print(f"  • Monitoring enabled: {memory_system.file_monitor is not None}")
    if memory_system.file_monitor:
        print(f"  • Active observers: {len(memory_system.file_monitor.observers)}")
        print(f"  • Processed files: {len(memory_system.file_monitor.processed_files)}")
    
    print(f"\n💡 To test file monitoring:")
    print(f"  1. Have a conversation in VS Code Copilot Chat")
    print(f"  2. The conversation should be automatically captured")
    print(f"  3. Check the logs for import messages")
    
    # Keep monitoring for a bit to catch any existing files
    print(f"\n⏳ Monitoring for 10 seconds to catch any existing conversations...")
    await asyncio.sleep(10)
    
    # Stop file monitoring
    print(f"\n🛑 Stopping file monitoring...")
    await memory_system.stop_file_monitoring()
    
    print(f"\n✅ Test completed!")
