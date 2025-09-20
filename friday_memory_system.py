
#!/usr/bin/env python3    


"""
Friday Memory System

Core memory system that handles all database operations, embeddings, and memory logic.
Provides persistent memory capabilities for Friday AI assistant across multiple databases.

All timestamps are stored in the local timezone (Minnesota) using ISO format. This ensures
that timestamps are correctly displayed and interpreted in the local time context where
the system is being used.
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
from datetime import datetime, timezone, timedelta, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo

# Get local timezone
def get_local_timezone() -> ZoneInfo:
    """Get local timezone based on system settings"""
    try:
        import time
        return ZoneInfo(time.tzname[0])
    except:
        # Fallback to a common timezone if detection fails
        return ZoneInfo("America/Chicago")  # Minnesota is in Central Time



def get_current_timestamp() -> str:
    """Get current timestamp in local timezone ISO format"""
    return datetime.now(get_local_timezone()).isoformat()
    
def datetime_to_local_isoformat(dt: datetime) -> str:
    """Convert any datetime to local timezone ISO format"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_local_timezone())
    return dt.astimezone(get_local_timezone()).isoformat()
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import hashlib
from utils import parse_timestamp

# Configure logging with minimal output
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
# Only show important messages and errors
logger.setLevel(logging.WARNING)


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
    
    def __init__(self, db_path: str = "memory_data/conversations.db"):
        super().__init__(db_path)
        self.initialize_tables()
        # Debug: log the absolute path to a file in memory_data
        import os
        debug_path = os.path.abspath(db_path)
        log_file = os.path.join(os.path.dirname(debug_path), "db_debug_log.txt")
        with open(log_file, "a") as f:
            f.write(f"ConversationDatabase using: {debug_path}\n")
    
    def initialize_tables(self):
        """Create tables if they don't exist, and migrate schema if columns are missing"""
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

            # --- MIGRATION LOGIC FOR MESSAGES TABLE ---
            # Define expected columns
            expected_columns = [
                'message_id', 'conversation_id', 'timestamp', 'role', 'content', 'source_type',
                'source_id', 'source_url', 'source_metadata', 'sync_status', 'last_sync',
                'metadata', 'embedding', 'created_at'
            ]
            # Get current columns
            cur = conn.execute("PRAGMA table_info(messages)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in expected_columns:
                    if col not in current_columns:
                        needs_migration = True
                        break
            # If migration needed, backup data, drop, recreate, restore
            if needs_migration:
                logger.warning("Migrating messages table to new schema!")
                # Backup old data
                old_rows = conn.execute("SELECT * FROM messages").fetchall()
                # Drop old table
                conn.execute("DROP TABLE IF EXISTS messages")
                # Recreate with new schema
                conn.execute("""
                    CREATE TABLE messages (
                        message_id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        source_id TEXT,
                        source_url TEXT,
                        source_metadata TEXT,
                        sync_status TEXT,
                        last_sync TEXT,
                        metadata TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
                    )
                """)
                # Restore old data
                for row in old_rows:
                    # Build new row dict with defaults for missing columns
                    row_dict = dict(row)
                    for col in expected_columns:
                        if col not in row_dict:
                            if col == 'source_type':
                                row_dict[col] = 'unknown'
                            elif col == 'created_at':
                                row_dict[col] = datetime.now().isoformat()
                            else:
                                row_dict[col] = None
                    # Insert
                    conn.execute(
                        f"INSERT INTO messages ({', '.join(expected_columns)}) VALUES ({', '.join(['?' for _ in expected_columns])})",
                        tuple(row_dict[col] for col in expected_columns)
                    )
                logger.warning(f"Restored {len(old_rows)} messages after migration.")

            else:
                # Create table if not exists (normal path)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        message_id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        source_id TEXT,
                        source_url TEXT,
                        source_metadata TEXT,
                        sync_status TEXT,
                        last_sync TEXT,
                        metadata TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
                    )
                """)

            # Source metadata table for tracking chat sources
            conn.execute("""
                CREATE TABLE IF NOT EXISTS source_tracking (
                    source_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_path TEXT,
                    last_check TEXT NOT NULL,
                    last_sync TEXT,
                    status TEXT NOT NULL,
                    error_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Cross-source relationships table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_relationships (
                    relationship_id TEXT PRIMARY KEY,
                    source_conversation_id TEXT NOT NULL,
                    related_conversation_id TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_conversation_id) REFERENCES conversations (conversation_id),
                    FOREIGN KEY (related_conversation_id) REFERENCES conversations (conversation_id)
                )
            """)

            conn.commit()
    
    async def store_message(self, content: str, role: str, session_id: str = None, 
                          conversation_id: str = None, metadata: Dict = None) -> Dict[str, str]:
        """Store a message and auto-manage sessions/conversations with duplicate detection"""
        
        timestamp = datetime.now(get_local_timezone()).isoformat()
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
        
        # Extract source type from metadata
        source_type = "unknown"
        if metadata:
            source_type = metadata.get("application", metadata.get("file_type", "unknown"))
        
        # Store the message
        await self.execute_update(
            """INSERT INTO messages 
               (message_id, conversation_id, timestamp, role, content, source_type, metadata) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (message_id, conversation_id, timestamp, role, content, source_type,
             json.dumps(metadata) if metadata else None)
        )
        
        return {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "duplicate": False
        }
    
    async def get_recent_messages(self, limit: int = 10, session_id: str = None, days_back: int = 7) -> List[Dict]:
        """Get recent messages, optionally filtered by session and within specified days"""
        
        # Calculate cutoff date
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days_back)
        cutoff_timestamp = cutoff_date.isoformat()
        
        if session_id:
            query = """
                SELECT m.*, c.session_id 
                FROM messages m 
                JOIN conversations c ON m.conversation_id = c.conversation_id
                WHERE c.session_id = ? AND m.timestamp >= ?
                ORDER BY m.timestamp DESC 
                LIMIT ?
            """
            params = (session_id, cutoff_timestamp, limit)
        else:
            query = """
                SELECT m.*, c.session_id 
                FROM messages m 
                JOIN conversations c ON m.conversation_id = c.conversation_id
                WHERE m.timestamp >= ?
                ORDER BY m.timestamp DESC 
                LIMIT ?
            """
            params = (cutoff_timestamp, limit)
        
        rows = await self.execute_query(query, params)
        return [dict(row) for row in rows]


class AIMemoryDatabase(DatabaseManager):
    """Manages AI-curated memories database"""
    
    def __init__(self, db_path: str = "memory_data/ai_memories.db"):
        super().__init__(db_path)
        self.initialize_tables()
    
    def initialize_tables(self):
        """Create tables if they don't exist, and migrate schema if columns are missing"""
        with self.get_connection() as conn:
            # --- MIGRATION LOGIC FOR CURATED_MEMORIES TABLE ---
            expected_columns = [
                'memory_id', 'timestamp_created', 'timestamp_updated', 'source_conversation_id',
                'source_message_ids', 'memory_type', 'content', 'importance_level', 'tags',
                'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(curated_memories)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in expected_columns:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                logger.warning("Migrating curated_memories table to new schema!")
                old_rows = conn.execute("SELECT * FROM curated_memories").fetchall()
                conn.execute("DROP TABLE IF EXISTS curated_memories")
                conn.execute("""
                    CREATE TABLE curated_memories (
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
                for row in old_rows:
                    row_dict = dict(row)
                    for col in expected_columns:
                        if col not in row_dict:
                            if col == 'timestamp_created' or col == 'timestamp_updated' or col == 'created_at':
                                row_dict[col] = datetime.now().isoformat()
                            elif col == 'importance_level':
                                row_dict[col] = 5
                            else:
                                row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO curated_memories ({', '.join(expected_columns)}) VALUES ({', '.join(['?' for _ in expected_columns])})",
                        tuple(row_dict[col] for col in expected_columns)
                    )
                logger.warning(f"Restored {len(old_rows)} curated memories after migration.")
            else:
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
        timestamp = datetime.now(get_local_timezone()).isoformat()
        
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
        
        timestamp = get_current_timestamp()
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
    async def get_appointments(self, limit: int = 5, days_ahead: int = 30) -> Dict:
        """Get upcoming appointments (today onward), normalizing mixed datetime types to epoch seconds."""
        now = datetime.now(get_local_timezone())
        future = now + timedelta(days=days_ahead)
        now_epoch = int(now.timestamp())
        future_epoch = int(future.timestamp())
        
        try:
            query = """
                SELECT *
                FROM appointments
                WHERE
                    CASE
                        WHEN typeof(scheduled_datetime) = 'integer' THEN scheduled_datetime
                        ELSE CAST(strftime('%s', scheduled_datetime) AS INTEGER)
                    END >= ?
                AND
                    CASE
                        WHEN typeof(scheduled_datetime) = 'integer' THEN scheduled_datetime
                        ELSE CAST(strftime('%s', scheduled_datetime) AS INTEGER)
                    END <= ?
                ORDER BY
                    CASE
                        WHEN typeof(scheduled_datetime) = 'integer' THEN scheduled_datetime
                        ELSE CAST(strftime('%s', scheduled_datetime) AS INTEGER)
                    END ASC
                LIMIT ?
            """
            rows = await self.execute_query(query, (now_epoch, future_epoch, limit))
            
            if not rows:
                return {
                    "status": "no_appointments",
                    "message": f"No upcoming appointments in the next {days_ahead} days."
                }
            
            return {
                "status": "success",
                "count": len(rows),
                "appointments": [dict(row) for row in rows]
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to retrieve appointments. Please try again later. Error: {str(e)}"
            }
    
    def __init__(self, db_path: str = "memory_data/schedule.db"):
        super().__init__(db_path)
        self.initialize_tables()
    
    def initialize_tables(self):
        """Create tables if they don't exist, and migrate schema if columns are missing"""
        with self.get_connection() as conn:
            # --- MIGRATION LOGIC FOR APPOINTMENTS TABLE ---
            appointments_expected = [
                'appointment_id', 'timestamp_created', 'scheduled_datetime', 'title', 'description',
                'location', 'source_conversation_id', 'embedding', 'created_at', "status"
            ]
            cur = conn.execute("PRAGMA table_info(appointments)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in appointments_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                logger.warning("Migrating appointments table to new schema!")
                old_rows = conn.execute("SELECT * FROM appointments").fetchall()
                conn.execute("DROP TABLE IF EXISTS appointments")
                conn.execute("""
                    CREATE TABLE appointments (
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
                for row in old_rows:
                    row_dict = dict(row)
                    for col in appointments_expected:
                        if col not in row_dict:
                            if col == 'timestamp_created' or col == 'scheduled_datetime' or col == 'created_at':
                                row_dict[col] = datetime.now().isoformat()
                            else:
                                row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO appointments ({', '.join(appointments_expected)}) VALUES ({', '.join(['?' for _ in appointments_expected])})",
                        tuple(row_dict[col] for col in appointments_expected)
                    )
                logger.warning(f"Restored {len(old_rows)} appointments after migration.")
            else:
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

            # --- MIGRATION LOGIC FOR REMINDERS TABLE ---
            reminders_expected = [
                'reminder_id', 'timestamp_created', 'due_datetime', 'content', 'priority_level',
                'completed', 'source_conversation_id', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(reminders)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in reminders_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                logger.warning("Migrating reminders table to new schema!")
                old_rows = conn.execute("SELECT * FROM reminders").fetchall()
                conn.execute("DROP TABLE IF EXISTS reminders")
                conn.execute("""
                    CREATE TABLE reminders (
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
                for row in old_rows:
                    row_dict = dict(row)
                    for col in reminders_expected:
                        if col not in row_dict:
                            if col == 'timestamp_created' or col == 'due_datetime' or col == 'created_at':
                                row_dict[col] = datetime.now().isoformat()
                            elif col == 'priority_level':
                                row_dict[col] = 5
                            elif col == 'completed':
                                row_dict[col] = 0
                            else:
                                row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO reminders ({', '.join(reminders_expected)}) VALUES ({', '.join(['?' for _ in reminders_expected])})",
                        tuple(row_dict[col] for col in reminders_expected)
                    )
                logger.warning(f"Restored {len(old_rows)} reminders after migration.")
            else:
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
        timestamp = get_current_timestamp()
        
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
        timestamp = get_current_timestamp()
        
        await self.execute_update(
            """INSERT INTO reminders 
               (reminder_id, timestamp_created, due_datetime, content, priority_level, source_conversation_id) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (reminder_id, timestamp, due_datetime, content, priority_level, source_conversation_id)
        )
        
        return reminder_id


class VSCodeProjectDatabase(DatabaseManager):
    """Manages VS Code project development database"""
    
    def __init__(self, db_path: str = "memory_data/vscode_project.db"):
        super().__init__(db_path)
        self.initialize_tables()
    
    def initialize_tables(self):
        """Create tables if they don't exist, and migrate schema if columns are missing"""
        with self.get_connection() as conn:
            # --- MIGRATION LOGIC FOR PROJECT_SESSIONS TABLE ---
            sessions_expected = [
                'session_id', 'start_timestamp', 'end_timestamp', 'workspace_path', 'active_files',
                'git_branch', 'git_commit_hash', 'session_summary', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(project_sessions)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in sessions_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                logger.warning("Migrating project_sessions table to new schema!")
                old_rows = conn.execute("SELECT * FROM project_sessions").fetchall()
                conn.execute("DROP TABLE IF EXISTS project_sessions")
                conn.execute("""
                    CREATE TABLE project_sessions (
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
                for row in old_rows:
                    row_dict = dict(row)
                    for col in sessions_expected:
                        if col not in row_dict:
                            if col == 'start_timestamp' or col == 'end_timestamp' or col == 'created_at':
                                row_dict[col] = datetime.now().isoformat()
                            else:
                                row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO project_sessions ({', '.join(sessions_expected)}) VALUES ({', '.join(['?' for _ in sessions_expected])})",
                        tuple(row_dict[col] for col in sessions_expected)
                    )
                logger.warning(f"Restored {len(old_rows)} project sessions after migration.")
            else:
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

            # --- MIGRATION LOGIC FOR DEVELOPMENT_CONVERSATIONS TABLE ---
            devcon_expected = [
                'conversation_id', 'session_id', 'timestamp', 'chat_context_id', 'conversation_content',
                'decisions_made', 'code_changes', 'source_metadata', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(development_conversations)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in devcon_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                logger.warning("Migrating development_conversations table to new schema!")
                old_rows = conn.execute("SELECT * FROM development_conversations").fetchall()
                conn.execute("DROP TABLE IF EXISTS development_conversations")
                conn.execute("""
                    CREATE TABLE development_conversations (
                        conversation_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        chat_context_id TEXT,
                        conversation_content TEXT NOT NULL,
                        decisions_made TEXT,
                        code_changes TEXT,
                        source_metadata TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES project_sessions (session_id)
                    )
                """)
                for row in old_rows:
                    row_dict = dict(row)
                    for col in devcon_expected:
                        if col not in row_dict:
                            if col == 'timestamp' or col == 'created_at':
                                row_dict[col] = datetime.now().isoformat()
                            else:
                                row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO development_conversations ({', '.join(devcon_expected)}) VALUES ({', '.join(['?' for _ in devcon_expected])})",
                        tuple(row_dict[col] for col in devcon_expected)
                    )
                logger.warning(f"Restored {len(old_rows)} development conversations after migration.")
            else:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS development_conversations (
                        conversation_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        chat_context_id TEXT,
                        conversation_content TEXT NOT NULL,
                        decisions_made TEXT,
                        code_changes TEXT,
                        source_metadata TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES project_sessions (session_id)
                    )
                """)

            # --- MIGRATION LOGIC FOR PROJECT_INSIGHTS TABLE ---
            insights_expected = [
                'insight_id', 'timestamp_created', 'timestamp_updated', 'insight_type', 'content',
                'related_files', 'source_conversation_id', 'importance_level', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(project_insights)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in insights_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                logger.warning("Migrating project_insights table to new schema!")
                old_rows = conn.execute("SELECT * FROM project_insights").fetchall()
                conn.execute("DROP TABLE IF EXISTS project_insights")
                conn.execute("""
                    CREATE TABLE project_insights (
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
                for row in old_rows:
                    row_dict = dict(row)
                    for col in insights_expected:
                        if col not in row_dict:
                            if col == 'timestamp_created' or col == 'timestamp_updated' or col == 'created_at':
                                row_dict[col] = datetime.now().isoformat()
                            elif col == 'importance_level':
                                row_dict[col] = 5
                            else:
                                row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO project_insights ({', '.join(insights_expected)}) VALUES ({', '.join(['?' for _ in insights_expected])})",
                        tuple(row_dict[col] for col in insights_expected)
                    )
                logger.warning(f"Restored {len(old_rows)} project insights after migration.")
            else:
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

            # --- MIGRATION LOGIC FOR CODE_CONTEXT TABLE ---
            codectx_expected = [
                'context_id', 'timestamp', 'file_path', 'function_name', 'description', 'purpose',
                'related_insights', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(code_context)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in codectx_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                logger.warning("Migrating code_context table to new schema!")
                old_rows = conn.execute("SELECT * FROM code_context").fetchall()
                conn.execute("DROP TABLE IF EXISTS code_context")
                conn.execute("""
                    CREATE TABLE code_context (
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
                for row in old_rows:
                    row_dict = dict(row)
                    for col in codectx_expected:
                        if col not in row_dict:
                            if col == 'timestamp' or col == 'created_at':
                                row_dict[col] = datetime.now().isoformat()
                            else:
                                row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO code_context ({', '.join(codectx_expected)}) VALUES ({', '.join(['?' for _ in codectx_expected])})",
                        tuple(row_dict[col] for col in codectx_expected)
                    )
                logger.warning(f"Restored {len(old_rows)} code contexts after migration.")
            else:
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
        timestamp = get_current_timestamp()
        
        await self.execute_update(
            """INSERT INTO project_sessions 
               (session_id, start_timestamp, workspace_path, active_files, git_branch, session_summary) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, timestamp, workspace_path, 
             json.dumps(active_files) if active_files else None,
             git_branch, session_summary)
        )
        
        return session_id
    
    async def store_development_conversation(self, content: str, session_id: str = None,
                                          chat_context_id: str = None, decisions_made: str = None,
                                          code_changes: Dict = None) -> str:
        """Store a development conversation from VS Code
        
        Args:
            content: The conversation content
            session_id: Optional project session ID (will create new if none)
            chat_context_id: Optional VS Code chat context ID
            decisions_made: Summary of decisions made in conversation
            code_changes: Dictionary of files changed and their changes
        """
        conversation_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()
        
        # Create session if none provided
        if not session_id:
            session_id = await self.save_development_session(
                workspace_path=os.getcwd(),  # Current workspace
                session_summary="Auto-created session for development conversation"
            )
        
        # Store conversation
        await self.execute_update(
            """INSERT INTO development_conversations 
               (conversation_id, session_id, timestamp, chat_context_id,
                conversation_content, decisions_made, code_changes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (conversation_id, session_id, timestamp, chat_context_id,
             content, decisions_made, json.dumps(code_changes) if code_changes else None)
        )
        
        return conversation_id

    async def store_project_insight(self, content: str, insight_type: str = None,
                                  related_files: List[str] = None, importance_level: int = 5,
                                  source_conversation_id: str = None) -> str:
        """Store a project development insight"""
        
        insight_id = str(uuid.uuid4())
        timestamp = get_current_timestamp()
        
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
    
    def __init__(self, db_path: str = "memory_data/mcp_tool_calls.db"):
        super().__init__(db_path)
        self.initialize_tables()
    
    def initialize_tables(self):
        """Create tables if they don't exist, and migrate schema if columns are missing"""
        with self.get_connection() as conn:
            # --- MIGRATION LOGIC FOR TOOL_CALLS TABLE ---
            toolcalls_expected = [
                'call_id', 'timestamp', 'client_id', 'tool_name', 'parameters', 'execution_time_ms',
                'status', 'result', 'error_message', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(tool_calls)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in toolcalls_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                logger.warning("Migrating tool_calls table to new schema!")
                old_rows = conn.execute("SELECT * FROM tool_calls").fetchall()
                conn.execute("DROP TABLE IF EXISTS tool_calls")
                conn.execute("""
                    CREATE TABLE tool_calls (
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
                for row in old_rows:
                    row_dict = dict(row)
                    for col in toolcalls_expected:
                        if col not in row_dict:
                            if col == 'timestamp' or col == 'created_at':
                                row_dict[col] = datetime.now().isoformat()
                            else:
                                row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO tool_calls ({', '.join(toolcalls_expected)}) VALUES ({', '.join(['?' for _ in toolcalls_expected])})",
                        tuple(row_dict[col] for col in toolcalls_expected)
                    )
                logger.warning(f"Restored {len(old_rows)} tool calls after migration.")
            else:
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

            # --- MIGRATION LOGIC FOR USAGE_PATTERNS TABLE ---
            usage_expected = [
                'pattern_id', 'timestamp_created', 'analysis_period_days', 'pattern_type', 'insight',
                'confidence_score', 'supporting_data', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(usage_patterns)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in usage_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                logger.warning("Migrating usage_patterns table to new schema!")
                old_rows = conn.execute("SELECT * FROM usage_patterns").fetchall()
                conn.execute("DROP TABLE IF EXISTS usage_patterns")
                conn.execute("""
                    CREATE TABLE usage_patterns (
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
                for row in old_rows:
                    row_dict = dict(row)
                    for col in usage_expected:
                        if col not in row_dict:
                            if col == 'timestamp_created' or col == 'created_at':
                                row_dict[col] = datetime.now().isoformat()
                            elif col == 'confidence_score':
                                row_dict[col] = 0.5
                            else:
                                row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO usage_patterns ({', '.join(usage_expected)}) VALUES ({', '.join(['?' for _ in usage_expected])})",
                        tuple(row_dict[col] for col in usage_expected)
                    )
                logger.warning(f"Restored {len(old_rows)} usage patterns after migration.")
            else:
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

            # --- MIGRATION LOGIC FOR AI_REFLECTIONS TABLE ---
            reflections_expected = [
                'reflection_id', 'timestamp_created', 'reflection_type', 'content', 'insights',
                'recommendations', 'confidence_level', 'source_period_days', 'embedding', 'created_at'
            ]
            cur = conn.execute("PRAGMA table_info(ai_reflections)")
            current_columns = [row[1] for row in cur.fetchall()]
            needs_migration = False
            if current_columns:
                for col in reflections_expected:
                    if col not in current_columns:
                        needs_migration = True
                        break
            if needs_migration:
                logger.warning("Migrating ai_reflections table to new schema!")
                old_rows = conn.execute("SELECT * FROM ai_reflections").fetchall()
                conn.execute("DROP TABLE IF EXISTS ai_reflections")
                conn.execute("""
                    CREATE TABLE ai_reflections (
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
                for row in old_rows:
                    row_dict = dict(row)
                    for col in reflections_expected:
                        if col not in row_dict:
                            if col == 'timestamp_created' or col == 'created_at':
                                row_dict[col] = datetime.now().isoformat()
                            elif col == 'confidence_level':
                                row_dict[col] = 0.5
                            else:
                                row_dict[col] = None
                    conn.execute(
                        f"INSERT INTO ai_reflections ({', '.join(reflections_expected)}) VALUES ({', '.join(['?' for _ in reflections_expected])})",
                        tuple(row_dict[col] for col in reflections_expected)
                    )
                logger.warning(f"Restored {len(old_rows)} ai reflections after migration.")
            else:
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
        timestamp = get_current_timestamp()
        
        # Serialize complex data
        parameters_json = json.dumps(parameters) if parameters else None
        
        # Sanitize result to be JSON serializable
        def sanitize_for_json(obj):
            if isinstance(obj, (int, float, str, bool, type(None))):
                return obj
            elif isinstance(obj, (list, tuple)):
                return [sanitize_for_json(item) for item in obj]
            elif isinstance(obj, dict):
                return {str(k): sanitize_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, bytes):
                return f"<binary data {len(obj)} bytes>"
            else:
                return str(obj)
        
        result_json = json.dumps(sanitize_for_json(result)) if result and not isinstance(result, str) else str(result) if result else None
        
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
        
        cutoff_date = (datetime.now(get_local_timezone()) - 
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
        timestamp = get_current_timestamp()
        
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
        timestamp = get_current_timestamp()
        
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
    def __init__(self, memory_system, watch_directories):
        self.memory_system = memory_system
        self.watch_directories = watch_directories
        # Access all databases through memory_system for consistency
        self.conversations_db = memory_system.conversations_db
        self.curated_db = memory_system.curated_db
        
    async def _import_characterai_conversation(self, file_path: str, content: str):
        """Import a Character.ai conversation file with deduplication."""
        try:
            data = json.loads(content)
            metadata = {
                "source_file": file_path,
                "import_timestamp": datetime.now(get_local_timezone()).isoformat(),
                "file_type": "characterai_conversation",
                "application": "character.ai"
            }
            messages = self._parse_conversation_data(data, file_path)
            session_id = None
            conversation_id = None
            imported_count = 0
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role", "unknown")
                content_data = msg.get("content", msg.get("text", ""))
                if isinstance(content_data, str):
                    msg_content = content_data
                elif isinstance(content_data, dict):
                    msg_content = json.dumps(content_data)
                else:
                    msg_content = str(content_data)
                msg_id = msg.get("id") or msg.get("message_id")
                timestamp = parse_timestamp(msg.get("timestamp"))
                content_hash = hashlib.md5(msg_content.encode()).hexdigest()
                duplicate = False
                if msg_id:
                    existing = await self.conversations_db.execute_query(
                        "SELECT message_id FROM messages WHERE message_id = ?", (msg_id,)
                    )
                    if existing:
                        duplicate = True
                if not duplicate:
                    existing = await self.conversations_db.execute_query(
                        "SELECT message_id FROM messages WHERE timestamp = ? AND content = ?", (timestamp, msg_content)
                    )
                    if existing:
                        duplicate = True
                if not duplicate:
                    result = await self.conversations_db.store_message(
                        content=msg_content,
                        role=role,
                        session_id=session_id,
                        conversation_id=conversation_id,
                        metadata={**metadata, "imported_id": msg_id, "imported_timestamp": timestamp, "content_hash": content_hash}
                    )
                    if session_id is None:
                        session_id = result["session_id"]
                        conversation_id = result["conversation_id"]
                    imported_count += 1
            logger.info(f"Imported {imported_count} Character.ai messages from {file_path}")
        except Exception as e:
            logger.error(f"Error importing Character.ai conversation {file_path}: {e}")

    async def _import_localai_conversation(self, file_path: str, content: str):
        """Import a Local.ai conversation file with deduplication."""
        try:
            data = json.loads(content)
            metadata = {
                "source_file": file_path,
                "import_timestamp": get_current_timestamp(),
                "file_type": "localai_conversation",
                "application": "local.ai"
            }
            messages = self._parse_conversation_data(data, file_path)
            session_id = None
            conversation_id = None
            imported_count = 0
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role", "unknown")
                content_data = msg.get("content", msg.get("text", ""))
                if isinstance(content_data, str):
                    msg_content = content_data
                elif isinstance(content_data, dict):
                    msg_content = json.dumps(content_data)
                else:
                    msg_content = str(content_data)
                msg_id = msg.get("id") or msg.get("message_id")
                timestamp = parse_timestamp(msg.get("timestamp"))
                content_hash = hashlib.md5(msg_content.encode()).hexdigest()
                duplicate = False
                if msg_id:
                    existing = await self.conversations_db.execute_query(
                        "SELECT message_id FROM messages WHERE message_id = ?", (msg_id,)
                    )
                    if existing:
                        duplicate = True
                if not duplicate:
                    existing = await self.conversations_db.execute_query(
                        "SELECT message_id FROM messages WHERE timestamp = ? AND content = ?", (timestamp, msg_content)
                    )
                    if existing:
                        duplicate = True
                if not duplicate:
                    result = await self.conversations_db.store_message(
                        content=msg_content,
                        role=role,
                        session_id=session_id,
                        conversation_id=conversation_id,
                        metadata={**metadata, "imported_id": msg_id, "imported_timestamp": timestamp, "content_hash": content_hash}
                    )
                    if session_id is None:
                        session_id = result["session_id"]
                        conversation_id = result["conversation_id"]
                    imported_count += 1
            logger.info(f"Imported {imported_count} Local.ai messages from {file_path}")
        except Exception as e:
            logger.error(f"Error importing Local.ai conversation {file_path}: {e}")

    async def _import_textgenwebui_conversation(self, file_path: str, content: str):
        """Import a text-generation-webui conversation file with deduplication."""
        try:
            # Assume log format: one message per line, JSON or plain text
            lines = content.strip().split('\n')
            metadata = {
                "source_file": file_path,
                "import_timestamp": get_current_timestamp(),
                "file_type": "textgenwebui_conversation",
                "application": "text-generation-webui"
            }
            session_id = None
            conversation_id = None
            imported_count = 0
            for line in lines:
                msg_content = line.strip()
                if not msg_content:
                    continue
                content_hash = hashlib.md5(msg_content.encode()).hexdigest()
                duplicate = False
                existing = await self.conversations_db.execute_query(
                    "SELECT content FROM messages WHERE content = ?", (msg_content,)
                )
                if existing:
                    duplicate = True
                if not duplicate:
                    result = await self.conversations_db.store_message(
                        content=msg_content,
                        role="unknown",
                        session_id=session_id,
                        conversation_id=conversation_id,
                        metadata={**metadata, "content_hash": content_hash}
                    )
                    if session_id is None:
                        session_id = result["session_id"]
                        conversation_id = result["conversation_id"]
                    imported_count += 1
            logger.info(f"Imported {imported_count} text-generation-webui messages from {file_path}")
        except Exception as e:
            logger.error(f"Error importing text-generation-webui conversation {file_path}: {e}")
    async def _import_lmstudio_conversation(self, file_path: str, content: str):
        """Import an LM Studio conversation file with deduplication."""
        try:
            # Debug: Check content length and first few chars
            logger.debug(f"LM Studio import - file: {file_path}, content length: {len(content)}")
            if not content.strip():
                logger.warning(f"Empty content in LM Studio file: {file_path}")
                return
                
            data = json.loads(content)
            logger.debug(f"Successfully parsed JSON with keys: {list(data.keys())}")
            
            metadata = {
                "source_file": file_path,
                "import_timestamp": get_current_timestamp(),
                "file_type": "lmstudio_conversation",
                "application": "lm_studio"
            }
            messages = self._parse_conversation_data(data, file_path)
            logger.info(f"Parsed {len(messages)} messages from LM Studio file")
            
            session_id = None
            conversation_id = None
            imported_count = 0
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role", "unknown")
                content_data = msg.get("content", msg.get("text", ""))
                if isinstance(content_data, str):
                    msg_content = content_data
                elif isinstance(content_data, dict):
                    msg_content = json.dumps(content_data)
                else:
                    msg_content = str(content_data)
                msg_id = msg.get("id") or msg.get("message_id")
                timestamp = parse_timestamp(msg.get("timestamp"))
                content_hash = hashlib.md5(msg_content.encode()).hexdigest()
                duplicate = False
                if msg_id:
                    existing = await self.memory_system.conversations_db.execute_query(
                        "SELECT message_id FROM messages WHERE message_id = ?", (msg_id,)
                    )
                    if existing:
                        duplicate = True
                if not duplicate:
                    existing = await self.memory_system.conversations_db.execute_query(
                        "SELECT message_id FROM messages WHERE timestamp = ? AND content = ?", (timestamp, msg_content)
                    )
                    if existing:
                        duplicate = True
                if not duplicate:
                    result = await self.memory_system.conversations_db.store_message(
                        content=msg_content,
                        role=role,
                        session_id=session_id,
                        conversation_id=conversation_id,
                        metadata={**metadata, "imported_id": msg_id, "imported_timestamp": timestamp, "content_hash": content_hash}
                    )
                    if session_id is None:
                        session_id = result["session_id"]
                        conversation_id = result["conversation_id"]
                    imported_count += 1
            logger.info(f"Imported {imported_count} new messages from LM Studio conversation {file_path} (skipped {len(messages) - imported_count} duplicates)")
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in LM Studio file {file_path}: {e}")
            logger.error(f"Content preview: {content[:200]}...")
        except Exception as e:
            logger.error(f"Error importing LM Studio conversation {file_path}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    async def _import_ollama_conversation(self, file_path: str, content: str = None):
        """Import Ollama conversations from SQLite database."""
        try:
            # Ollama stores conversations in SQLite database, not JSON files
            if file_path.lower().endswith('db.sqlite') and 'ollama' in file_path.lower():
                await self._import_ollama_database(file_path)
            else:
                # Handle legacy JSON format if it exists
                if content:
                    data = json.loads(content)
                    metadata = {
                        "source_file": file_path,
                        "import_timestamp": get_current_timestamp(),
                        "file_type": "ollama_conversation",
                        "application": "ollama"
                    }
                    messages = self._parse_conversation_data(data, file_path)
                    await self._import_parsed_messages(messages, metadata, file_path)
        except Exception as e:
            logger.error(f"Error importing Ollama conversation {file_path}: {e}")
    
    async def _import_ollama_database(self, db_path: str):
        """Import conversations from Ollama SQLite database."""
        try:
            import sqlite3
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get all chats with their messages
            cursor.execute("""
                SELECT c.id, c.title, c.created_at,
                       m.role, m.content, m.model_name, m.created_at as message_created_at
                FROM chats c
                LEFT JOIN messages m ON c.id = m.chat_id
                ORDER BY c.created_at, m.created_at
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                logger.debug(f"No conversations found in Ollama database: {db_path}")
                return
            
            # Group messages by chat
            chats = {}
            for row in rows:
                chat_id, title, chat_created_at, role, content, model_name, msg_created_at = row
                
                if chat_id not in chats:
                    chats[chat_id] = {
                        'title': title,
                        'created_at': chat_created_at,
                        'messages': []
                    }
                
                if role and content:  # Only add if message exists
                    chats[chat_id]['messages'].append({
                        'role': role,
                        'content': content,
                        'model_name': model_name,
                        'created_at': msg_created_at
                    })
            
            # Import each chat
            total_imported = 0
            for chat_id, chat_data in chats.items():
                if not chat_data['messages']:
                    continue
                    
                metadata = {
                    "source_file": db_path,
                    "import_timestamp": get_current_timestamp(),
                    "file_type": "ollama_database",
                    "application": "ollama",
                    "chat_id": chat_id,
                    "chat_title": chat_data['title']
                }
                
                imported_count = await self._import_parsed_messages(chat_data['messages'], metadata, db_path)
                total_imported += imported_count
            
            logger.info(f"Imported {total_imported} messages from {len(chats)} Ollama chats in {db_path}")
            
        except Exception as e:
            logger.error(f"Error importing Ollama database {db_path}: {e}")
    
    async def _import_parsed_messages(self, messages: List[Dict], metadata: Dict, file_path: str) -> int:
        """Helper method to import a list of parsed messages."""
        session_id = None
        conversation_id = None
        imported_count = 0
        
        for msg in messages:
            if not isinstance(msg, dict):
                continue
                
            role = msg.get("role", "unknown")
            content_data = msg.get("content", msg.get("text", ""))
            if isinstance(content_data, str):
                msg_content = content_data
            elif isinstance(content_data, dict):
                msg_content = json.dumps(content_data)
            else:
                msg_content = str(content_data)
            
            if not msg_content.strip():
                continue
                
            msg_id = msg.get("id") or msg.get("message_id")
            timestamp = parse_timestamp(msg.get("timestamp") or msg.get("created_at"))
            content_hash = hashlib.md5(msg_content.encode()).hexdigest()
            
            # Check for duplicates
            duplicate = False
            if msg_id:
                existing = await self.memory_system.conversations_db.execute_query(
                    "SELECT message_id FROM messages WHERE message_id = ?", (msg_id,)
                )
                if existing:
                    duplicate = True
            
            if not duplicate:
                existing = await self.memory_system.conversations_db.execute_query(
                    "SELECT message_id FROM messages WHERE timestamp = ? AND content = ?", 
                    (timestamp, msg_content)
                )
                if existing:
                    duplicate = True
            
            if not duplicate:
                result = await self.memory_system.conversations_db.store_message(
                    content=msg_content,
                    role=role,
                    session_id=session_id,
                    conversation_id=conversation_id,
                    metadata={
                        **metadata, 
                        "imported_id": msg_id, 
                        "imported_timestamp": timestamp, 
                        "content_hash": content_hash,
                        "model_name": msg.get("model_name")
                    }
                )
                if session_id is None:
                    session_id = result["session_id"]
                    conversation_id = result["conversation_id"]
                imported_count += 1
        
        return imported_count
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
        self.last_processed_times = {}  # Track when files were last processed
        self.min_process_interval = 5.0  # Minimum seconds between processing the same file to reduce CPU usage
        
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
        try:
            # Check in both conversations and messages tables using the conversations_db
            # First check messages table
            result = await self.conversations_db.execute_query(
                "SELECT COUNT(*) FROM messages WHERE message_hash = ?",
                (msg_hash,)
            )
            if result and result[0][0] > 0:
                return True
                
            # Then check conversations table
            result = await self.conversations_db.execute_query(
                "SELECT COUNT(*) FROM conversations WHERE message_hash = ?",
                (msg_hash,)
            )
            return result and result[0][0] > 0
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
        
        # Ollama database paths (SQLite database instead of files)
        ollama_db_paths = [
            home / "AppData" / "Local" / "Ollama" / "db.sqlite",  # Windows
            home / ".local" / "share" / "ollama" / "db.sqlite",  # Linux
            home / "Library" / "Application Support" / "Ollama" / "db.sqlite"  # macOS
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
        add_paths_if_exist(chatgpt_paths, "ChatGPT")
        add_paths_if_exist(claude_paths, "Claude")
        add_paths_if_exist(copilot_paths, "Microsoft Copilot/Bing")
        add_paths_if_exist(character_ai_paths, "Character.ai")
        add_paths_if_exist(local_ai_paths, "Local.ai")
        add_paths_if_exist(text_gen_paths, "text-generation-webui")
        add_paths_if_exist(openai_paths, "OpenAI Playground")
        
        # Special handling for Ollama database
        for db_path in ollama_db_paths:
            if db_path.exists():
                directories.append(str(db_path))
                logger.info(f"Found Ollama database: {db_path}")
        
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
        """Parse conversation data using a registry of format handlers for future-proofing."""
        # Registry of format handlers: (predicate, handler)
        format_handlers = [
            (lambda d: isinstance(d, dict) and 'mapping' in d, self._parse_chatgpt_format),
            # LM Studio format: has 'messages' with 'versions' structure
            (lambda d: isinstance(d, dict) and 'messages' in d and self._is_lmstudio_format(d), self._parse_lmstudio_format),
            (lambda d: isinstance(d, dict) and 'messages' in d, self._parse_claude_format),
            (lambda d: isinstance(d, dict) and 'conversation' in d, self._parse_character_ai_format),
            (lambda d: isinstance(d, dict) and 'history' in d, self._parse_text_gen_format),
            (lambda d: isinstance(d, list) and any('role' in msg for msg in d if isinstance(msg, dict)), self._parse_simple_array),
            (lambda d: isinstance(d, list) and any('character' in msg for msg in d if isinstance(msg, dict)), lambda d: self._parse_character_ai_format({'conversation': d})),
        ]
        for predicate, handler in format_handlers:
            if predicate(data):
                return handler(data)
        # Fallback: treat as a list of dicts with 'content' and 'role', or empty
        if isinstance(data, list):
            return [msg for msg in data if isinstance(msg, dict) and 'content' in msg]
        return []

    def _is_lmstudio_format(self, data: Dict) -> bool:
        """Check if data is in LM Studio format (has messages with versions structure)"""
        try:
            messages = data.get('messages', [])
            if not messages:
                return False
            # Check if first message has the LM Studio structure
            first_msg = messages[0] if isinstance(messages, list) else None
            return (isinstance(first_msg, dict) and 
                    'versions' in first_msg and 
                    'currentlySelected' in first_msg)
        except:
            return False

    def _parse_lmstudio_format(self, data: Dict) -> List[Dict]:
        """Parse LM Studio conversation format with versions and complex content structure"""
        conversations = []
        try:
            messages = data.get('messages', [])
            conversation_timestamp = data.get('createdAt')
            base_timestamp = None
            
            if conversation_timestamp:
                try:
                    # LM Studio uses millisecond timestamps
                    base_timestamp = datetime.fromtimestamp(conversation_timestamp / 1000)
                except (ValueError, TypeError):
                    pass
            
            for i, msg in enumerate(messages):
                if not isinstance(msg, dict) or 'versions' not in msg:
                    continue
                
                versions = msg.get('versions', [])
                current_version = msg.get('currentlySelected', 0)
                
                if 0 <= current_version < len(versions):
                    version = versions[current_version]
                    
                    role = version.get('role', 'unknown')
                    content_parts = version.get('content', [])
                    
                    # Extract text content from LM Studio's complex content structure
                    text_content = []
                    for part in content_parts:
                        if isinstance(part, dict):
                            if part.get('type') == 'text':
                                text_content.append(part.get('text', ''))
                            elif part.get('type') == 'file':
                                # Handle file attachments
                                file_info = f"[File: {part.get('fileIdentifier', 'unknown')}]"
                                text_content.append(file_info)
                        elif isinstance(part, str):
                            text_content.append(part)
                    
                    # For assistant messages, handle multi-step responses
                    if version.get('type') == 'multiStep' and 'steps' in version:
                        for step in version.get('steps', []):
                            if step.get('type') == 'contentBlock':
                                step_content = step.get('content', [])
                                for step_part in step_content:
                                    if isinstance(step_part, dict) and step_part.get('type') == 'text':
                                        text_content.append(step_part.get('text', ''))
                    
                    final_content = ' '.join(text_content).strip()
                    if final_content:
                        # Calculate approximate timestamp for each message
                        timestamp = None
                        if base_timestamp:
                            # Spread messages over time based on their position
                            timestamp = datetime_to_local_isoformat(
                                base_timestamp + timedelta(minutes=i * 2)
                            )
                        
                        conversations.append({
                            'role': role,
                            'content': final_content,
                            'timestamp': timestamp,
                            'metadata': {
                                'source': 'LM_Studio',
                                'model': version.get('senderInfo', {}).get('senderName', 'unknown'),
                                'conversation_name': data.get('name', 'Untitled'),
                                'version_index': current_version,
                                'step_type': version.get('type'),
                                'token_count': data.get('tokenCount')
                            }
                        })
        
        except Exception as e:
            logger.error(f"Error parsing LM Studio format: {e}")
        
        return conversations

    def _parse_chatgpt_format(self, data: Dict) -> List[Dict]:
        """Parse ChatGPT export format with timestamps"""
        conversations = []
        try:
            if 'mapping' in data:
                for node_id, node in data['mapping'].items():
                    if node.get('message') and node['message'].get('content'):
                        content_parts = node['message']['content'].get('parts', [])
                        if content_parts:
                            timestamp = None
                            if 'create_time' in node['message']:
                                try:
                                    timestamp = datetime_to_local_isoformat(
                                        datetime.fromtimestamp(
                                            int(node['message']['create_time'])
                                        )
                                    )
                                except (ValueError, TypeError):
                                    pass
                            conversations.append({
                                'role': node['message'].get('author', {}).get('role', 'unknown'),
                                'content': ' '.join(str(part) for part in content_parts if part),
                                'timestamp': timestamp
                            })
        except Exception as e:
            logger.error(f"Error parsing ChatGPT format: {e}")
        return conversations

    def _parse_simple_array(self, data: List) -> List[Dict]:
        """Parse simple conversation array format with timestamps"""
        conversations = []
        for item in data:
            if isinstance(item, dict) and 'content' in item:
                timestamp = None
                for key in ['timestamp', 'time', 'created_at', 'date']:
                    if key in item:
                        try:
                            if isinstance(item[key], (int, float)):
                                timestamp = datetime_to_local_isoformat(datetime.fromtimestamp(item[key]))
                            else:
                                timestamp = datetime_to_local_isoformat(datetime.fromisoformat(str(item[key])))
                            break
                        except (ValueError, TypeError):
                            continue
                conversations.append({
                    'role': item.get('role', 'user'),
                    'content': str(item['content']),
                    'timestamp': timestamp
                })
        return conversations

    def _parse_character_ai_format(self, data: Dict) -> List[Dict]:
        """Parse Character.ai conversation format (list of messages under 'conversation')"""
        conversations = []
        try:
            messages = data.get('conversation', [])
            for msg in messages:
                if isinstance(msg, dict) and 'content' in msg:
                    conversations.append({
                        'role': msg.get('character', msg.get('role', 'unknown')),
                        'content': msg['content'],
                        'timestamp': msg.get('timestamp')
                    })
        except Exception as e:
            logger.error(f"Error parsing Character.ai format: {e}")
        return conversations

    def _parse_text_gen_format(self, data: Dict) -> List[Dict]:
        """Parse text-generation-webui format (list of messages under 'history')"""
        conversations = []
        try:
            history = data.get('history', [])
            for msg in history:
                if isinstance(msg, dict) and 'content' in msg:
                    conversations.append({
                        'role': msg.get('role', 'unknown'),
                        'content': msg['content'],
                        'timestamp': msg.get('timestamp')
                    })
        except Exception as e:
            logger.error(f"Error parsing text-generation-webui format: {e}")
        return conversations
    
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
                            logger.info(f"Detected file modification: {event.src_path}")
                            # Get the event loop from the main thread
                            loop = self.monitor.loop
                            if loop and loop.is_running():
                                logger.debug("Processing file change in event loop")
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
        
        # Ollama database files
        if file_name == 'db.sqlite' and 'ollama' in file_path_lower:
            return True
        
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
            # Skip if not a conversation file or doesn't exist
            if not self._is_conversation_file(file_path) or not os.path.exists(file_path):
                return
                
            # Check if we've processed this file recently
            current_time = time.time()
            last_processed = self.last_processed_times.get(file_path, 0)
            if current_time - last_processed < self.min_process_interval:
                return
            
            # Update last processed time before we start processing
            self.last_processed_times[file_path] = current_time
            
            # Calculate file hash and read content with better error handling
            try:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                    if not file_content:
                        logger.warning(f"Empty file detected: {file_path}")
                        return
                    file_hash = hashlib.md5(file_content).hexdigest()
                
                # Skip if we've already processed this exact content
                if file_path in self.file_hashes and self.file_hashes[file_path] == file_hash:
                    return
                
                self.file_hashes[file_path] = file_hash
                
                # Handle SQLite databases (binary files)
                if file_path.lower().endswith('db.sqlite') and 'ollama' in file_path.lower():
                    await self._import_conversation_file(file_path, None)  # Pass None for binary files
                else:
                    # Try to decode text content
                    try:
                        decoded_content = file_content.decode('utf-8')
                        if not decoded_content.strip():
                            logger.warning(f"File contains only whitespace: {file_path}")
                            return
                        logger.debug(f"File content preview: {decoded_content[:100]}...")
                        
                        # Parse and import the conversation
                        await self._import_conversation_file(file_path, decoded_content)
                    except UnicodeDecodeError as e:
                        logger.error(f"Failed to decode file content for {file_path}: {e}")
            except PermissionError:
                logger.error(f"Permission denied reading file: {file_path}")
            except FileNotFoundError:
                logger.error(f"File not found (may have been deleted): {file_path}")
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
    
    async def _import_conversation_file(self, file_path: str, content: str):
        """Import a conversation file into the memory system"""
        try:
            # If MCP server is running, only process messages older than server start
            mcp_running = self._check_mcp_server()
            
            # Special handling for Ollama SQLite database
            if file_path.lower().endswith('db.sqlite') and 'ollama' in file_path.lower():
                await self._import_ollama_conversation(file_path)
                return
            
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
    
    async def _import_vscode_chat_session(self, file_path: str, content: str, mcp_running: bool = False):
        """Import a VS Code chat session file (Copilot format) with duplicate prevention"""
        try:
            # Handle empty or whitespace-only content
            if not content or not content.strip():
                logger.warning(f"Empty or whitespace-only VS Code chat session file: {file_path}")
                return
            
            try:
                data = json.loads(content)
                logger.debug(f"Successfully parsed JSON data: {json.dumps(data, indent=2)[:500]}...")
            except json.JSONDecodeError as e:
                # Log the problematic content for debugging
                logger.error(f"Invalid JSON in VS Code chat session {file_path}. Content preview: {content[:100]}...")
                logger.debug(f"Full content that caused JSON error: {content}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error parsing VS Code chat session: {str(e)}")
                logger.debug(f"Content that caused error: {content[:500]}...")
                raise
            
            # Create a consistent session ID based on the file path and initial metadata
            file_session_id = hashlib.md5(f"vscode:{file_path}".encode()).hexdigest()
            
            # Initialize conversation tracking variables
            conversation_id = None
            session_id = None
            
            # Instead of checking whole session, we'll check individual messages as we process them
            last_import_result = await self.memory_system.vscode_db.execute_query(
                """SELECT conversation_content, timestamp FROM development_conversations 
                   WHERE chat_context_id = ? ORDER BY timestamp DESC LIMIT 1""",
                (file_session_id,)
            )
            last_imported_content = last_import_result[0][0] if last_import_result else ""
            last_timestamp = last_import_result[0][1] if last_import_result else "1970-01-01T00:00:00+00:00"
            
            # We'll compare timestamps and content as we process messages to find new ones
            
            # Create a development session for this VS Code chat
            dev_session_id = await self.memory_system.vscode_db.save_development_session(
                workspace_path=os.path.dirname(file_path),
                session_summary=f"Imported VS Code chat session from {os.path.basename(file_path)}"
            )
            
            # Extract metadata from VS Code chat session
            metadata = {
                "source_file": file_path,
                "import_timestamp": get_current_timestamp(),
                "file_type": "vscode_chat_session",
                "application": "vscode_copilot",
                "session_version": data.get("version"),
                "requester": data.get("requesterUsername"),
                "responder": data.get("responderUsername"),
                "initial_location": data.get("initialLocation")
            }
            
            # Build full conversation content for development tracking
            full_conversation = []
            
            # Process each request-response pair
            requests = data.get("requests", [])
            logger.debug(f"Found {len(requests)} requests in chat session")
            logger.debug(f"Sample request structure: {json.dumps(requests[0] if requests else {}, indent=2)}")
            
            # Log raw structure of each request for debugging
            for idx, req in enumerate(requests):
                logger.debug(f"\nRequest {idx} structure:")
                logger.debug(f"Keys present: {list(req.keys())}")
                if "message" in req:
                    logger.debug(f"Message present with keys: {list(req['message'].keys())}")
                if "response" in req:
                    logger.debug(f"Response present with type: {type(req['response'])}")
                    if isinstance(req['response'], dict):
                        logger.debug(f"Response keys: {list(req['response'].keys())}")
            
            new_message_count = 0
            skipped_duplicates = 0
            
            # Initialize tracking variables for message counting
            current_session_id = file_session_id
            current_conversation_id = None
            messages_to_process = []
            already_imported = set()

            # Get all previously imported message hashes
            try:
                imported_messages = await self.memory_system.vscode_db.execute_query(
                    """SELECT source_metadata FROM development_conversations 
                       WHERE chat_context_id = ?""",
                    (file_session_id,)
                )
                for row in imported_messages:
                    if row[0]:  # source_metadata exists
                        metadata = json.loads(row[0])
                        if "content_hash" in metadata:
                            already_imported.add(metadata["content_hash"])
                logger.debug(f"Found {len(already_imported)} previously imported message hashes")
            except Exception as e:
                logger.warning(f"Error getting imported messages: {e}, starting fresh")
                already_imported = set()
            
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
                    # Ensure we have a valid ISO format timestamp
                try:
                    msg_timestamp = request.get("timestamp")
                    if not msg_timestamp:
                        logger.debug("No timestamp found, using current time")
                        msg_timestamp = get_current_timestamp()
                    elif isinstance(msg_timestamp, (int, float)):
                        logger.debug(f"Converting numeric timestamp: {msg_timestamp}")
                        try:
                            msg_timestamp = datetime_to_local_isoformat(datetime.fromtimestamp(msg_timestamp / 1000))
                        except (ValueError, OSError):
                            try:
                                msg_timestamp = datetime_to_local_isoformat(datetime.fromtimestamp(msg_timestamp))
                            except (ValueError, OSError):
                                logger.warning(f"Could not convert numeric timestamp: {msg_timestamp}")
                                msg_timestamp = get_current_timestamp()
                    elif isinstance(msg_timestamp, str):
                        logger.debug(f"Processing string timestamp: {msg_timestamp}")
                        try:
                            # Try parsing different formats
                            if msg_timestamp.endswith('Z'):
                                msg_timestamp = msg_timestamp.replace('Z', '+00:00')
                            if 'T' not in msg_timestamp and ' ' in msg_timestamp:
                                msg_timestamp = msg_timestamp.replace(' ', 'T')
                            parsed = datetime.fromisoformat(msg_timestamp)
                            msg_timestamp = datetime_to_local_isoformat(parsed)
                        except ValueError as e:
                            logger.warning(f"Invalid timestamp string format: {msg_timestamp}, error: {e}")
                            msg_timestamp = get_current_timestamp()
                    else:
                        logger.warning(f"Unexpected timestamp type: {type(msg_timestamp)}")
                        msg_timestamp = get_current_timestamp()
                except Exception as e:
                    logger.warning(f"Error processing timestamp: {e}, using current time")
                    msg_timestamp = get_current_timestamp()
                    
                # Process message if it's valid
                if user_content.strip():
                    content_hash = hashlib.md5(f"{user_content}:{msg_timestamp}".encode()).hexdigest()
                    if content_hash not in already_imported:
                        logger.debug("Found new user message to store")
                        result = await self.memory_system.store_conversation(
                            content=user_content,
                            role="user",
                            session_id=current_session_id,
                            conversation_id=current_conversation_id,
                            metadata={
                                **metadata, 
                                "request_id": request.get("requestId"), 
                                "timestamp": msg_timestamp,
                                "content_hash": content_hash
                            }
                        )
                        logger.info(f"Stored new user message: first 100 chars: {user_content[:100]}...")
                        
                        if result.get("duplicate"):
                            skipped_duplicates += 1
                        else:
                            new_message_count += 1
                            full_conversation.append(f"User: {user_content}")
                            # Update tracking IDs from result
                            if result.get("session_id"):
                                current_session_id = result["session_id"]
                            if result.get("conversation_id"):
                                current_conversation_id = result["conversation_id"]
                            # Add to already imported set to prevent duplicates in same session
                            already_imported.add(content_hash)
                    else:
                        skipped_duplicates += 1
                        logger.debug(f"Skipped duplicate message (hash: {content_hash})")
                    
                # Check for debug logging control commands
                if "disable debug logs" in user_content.lower() or "stop debug logging" in user_content.lower():
                    logger.info("===================================")
                    logger.info("Debug logging disabled by user request")
                    logger.info("Only important messages will be shown")
                    logger.info("Restart the system to re-enable debug logging")
                    logger.info("===================================")
                    logger.setLevel(logging.INFO)
                        
                # Process message with timestamp logging
                logger.debug(f"Processing message with timestamp: {msg_timestamp}")
                if user_content.strip():
                    content_hash = hashlib.md5(f"{user_content}:{msg_timestamp}".encode()).hexdigest()
                    logger.debug("Found user message to process")

                # Only process if this is a new message (after our last processed timestamp)
                if user_content.strip() and str(msg_timestamp) > str(last_timestamp):
                    logger.debug(f"Found new message to process")
                    # Use current tracking IDs
                    logger.debug(f"Storing new user message, timestamp: {msg_timestamp}")
                    result = await self.memory_system.store_conversation(
                        content=user_content,
                        role="user",
                        session_id=current_session_id,
                        conversation_id=current_conversation_id,
                        metadata={**metadata, "request_id": request.get("requestId"), "timestamp": msg_timestamp}
                    )
                    logger.info(f"Stored new user message: first 100 chars: {user_content[:100]}...")
                    
                    if result.get("duplicate"):
                        skipped_duplicates += 1
                    else:
                        new_message_count += 1
                        full_conversation.append(f"User: {user_content}")
                        # Update tracking IDs from result
                        if result.get("session_id"):
                            current_session_id = result["session_id"]
                        if result.get("conversation_id"):
                            current_conversation_id = result["conversation_id"]
                    full_conversation.append(f"User: {user_content}")
                    logger.debug(f"Stored user message with session_id: {current_session_id}, conversation_id: {current_conversation_id}")
                
                # Import assistant response if present
                if "response" in request:
                    response_data = request["response"]
                    assistant_content = None
                    logger.debug("Found assistant response to process")
                    logger.debug(f"Processing response type: {type(response_data).__name__}")
                    logger.debug(f"Session: {current_session_id[:8]}..., Conv: {current_conversation_id[:8] if current_conversation_id else 'None'}")
                    
                    # VS Code responses can have multiple parts
                    if isinstance(response_data, str):
                        logger.debug("Response is string type")
                        assistant_content = response_data
                    elif isinstance(response_data, dict):
                        logger.debug(f"Response is dict type with keys: {list(response_data.keys())}")
                        if "result" in response_data:
                            result_data = response_data["result"]
                            logger.debug(f"Found result data of type {type(result_data)}")
                            if isinstance(result_data, dict):
                                logger.debug(f"Result data keys: {list(result_data.keys())}")
                                # Try to use content or markdown from result
                                if "content" in result_data:
                                    assistant_content = result_data["content"]
                                    logger.debug("Using content from result")
                                elif "markdown" in result_data:
                                    assistant_content = result_data["markdown"]
                                    logger.debug("Using markdown content from result")
                                elif "value" in result_data:
                                    assistant_content = result_data["value"]
                                    logger.debug("Using value content from result")
                            elif isinstance(result_data, str):
                                assistant_content = result_data
                                logger.debug("Using string result data directly")
                            else:
                                assistant_content = json.dumps(result_data)
                                logger.debug("Converted result data to JSON string")
                        elif "content" in response_data:
                            assistant_content = response_data["content"]
                            logger.debug("Using content from response_data directly")
                        elif "value" in response_data:
                            assistant_content = response_data["value"]
                            logger.debug("Using value from response_data directly")
                        elif "markdown" in response_data:
                            assistant_content = response_data["markdown"]
                            logger.debug("Using markdown from response_data directly")
                        else:
                            assistant_content = json.dumps(response_data)
                            logger.debug("No recognized format found, using full response as JSON")
                    
                    if assistant_content:
                        logger.debug(f"Found assistant content (first 100 chars): {assistant_content[:100]}...")
                        # Get timestamp from user message or current time
                        msg_timestamp = None

                        logger.debug(f"Processing assistant message with timestamp: {msg_timestamp}")
                        if assistant_content.strip():
                            content_hash = hashlib.md5(f"{assistant_content}:{msg_timestamp}".encode()).hexdigest()
                            logger.debug("Found assistant message to process")
                        
                        # Try to get timestamp from the user's message first
                        if "message" in request and request["message"].get("timestamp"):
                            try:
                                user_ts = request["message"].get("timestamp")
                                if isinstance(user_ts, (int, float)):
                                    if user_ts > 10**12:  # milliseconds
                                        user_ts = datetime.fromtimestamp(user_ts / 1000)
                                    else:  # seconds
                                        user_ts = datetime.fromtimestamp(user_ts)
                                else:  # string
                                    user_ts = datetime.fromisoformat(str(user_ts).replace('Z', '+00:00'))
                                # Set assistant timestamp 1 second after user's message
                                msg_timestamp = datetime_to_local_isoformat(user_ts + timedelta(seconds=1))
                                logger.debug(f"Using timestamp based on user message: {msg_timestamp}")
                            except (ValueError, TypeError, AttributeError) as e:
                                logger.debug(f"Error parsing user timestamp: {e}")
                                msg_timestamp = None
                        
                        # If no user timestamp, try request timestamp
                        if not msg_timestamp:
                            msg_timestamp = request.get("timestamp")
                            if isinstance(msg_timestamp, (int, float)):
                                try:
                                    if msg_timestamp > 10**12:  # milliseconds
                                        msg_timestamp = datetime_to_local_isoformat(datetime.fromtimestamp(msg_timestamp / 1000))
                                    else:  # seconds
                                        msg_timestamp = datetime_to_local_isoformat(datetime.fromtimestamp(msg_timestamp))
                                except (ValueError, OSError):
                                    msg_timestamp = None
                            elif isinstance(msg_timestamp, str):
                                try:
                                    msg_timestamp = datetime.fromisoformat(msg_timestamp.replace('Z', '+00:00')).isoformat()
                                except ValueError:
                                    msg_timestamp = None
                        
                        # If still no timestamp, use current time
                        if not msg_timestamp:
                            msg_timestamp = get_current_timestamp()
                            logger.debug("Using current system time for timestamp")
                        
                        logger.debug(f"Final message timestamp: {msg_timestamp}, last processed: {last_timestamp}")

                        # Process message with timestamp logging
                        logger.debug(f"Processing message with timestamp: {msg_timestamp}")
                        if assistant_content.strip():
                            content_hash = hashlib.md5(f"{assistant_content}:{msg_timestamp}".encode()).hexdigest()
                            logger.debug("Found assistant message to process")
                        
                        # Store the message if it's new
                        if assistant_content.strip() and str(msg_timestamp) > str(last_timestamp):
                            logger.debug("Storing new assistant message")
                            result = await self.memory_system.store_conversation(
                                content=assistant_content,
                                role="assistant",
                                session_id=current_session_id,
                                conversation_id=current_conversation_id,
                                metadata={
                                    **metadata, 
                                    "request_id": request.get("requestId"), 
                                    "timestamp": msg_timestamp,
                                    "source_type": "vscode_chat"
                                }
                            )
                            logger.info(f"Stored new assistant message: first 100 chars: {assistant_content[:100]}...")
                            
                            if result.get("duplicate"):
                                skipped_duplicates += 1
                                logger.debug("Assistant message was duplicate")
                            else:
                                new_message_count += 1
                                full_conversation.append(f"Assistant: {assistant_content}")
                                logger.info(f"Added new assistant message to conversation: first 100 chars: {assistant_content[:100]}...")
                                # Update tracking IDs from result if needed
                                if result.get("session_id"):
                                    current_session_id = result["session_id"]
                                if result.get("conversation_id"):
                                    current_conversation_id = result["conversation_id"]
            
            # Only store development conversation if we have new messages
            if new_message_count > 0:
                # Store the complete development conversation
                await self.memory_system.vscode_db.store_development_conversation(
                    content="\n\n".join(full_conversation),
                    session_id=dev_session_id,
                    chat_context_id=file_session_id,
                    code_changes=data.get("codeActions", {})  # Store any code actions if present
                )
            
            logger.info(f"Imported {new_message_count} new messages from VS Code chat session {file_path} (skipped {skipped_duplicates} duplicates)")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in VS Code chat session {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error importing VS Code chat session {file_path}: {e}")
    
    async def _import_json_conversation(self, file_path: str, content: str, mcp_running: bool = False):
        """Import a JSON conversation file (future-proof, extensible format support)"""
        try:
            data = json.loads(content)
            metadata = {
                "source_file": file_path,
                "import_timestamp": datetime.now(get_local_timezone()).isoformat(),
                "file_type": "json_conversation",
                "mcp_enabled": mcp_running,
                "application": "lm_studio" if "lm" in file_path.lower() else "unknown",
                "source_type": "lm_studio" if "lm" in file_path.lower() else "external_json"
            }
            # Use extensible parser
            messages = self._parse_conversation_data(data, file_path)
            session_id = None
            conversation_id = None
            imported_count = 0
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role", "unknown")
                content_data = msg.get("content", msg.get("text", ""))
                # Handle different content formats
                if isinstance(content_data, str):
                    msg_content = content_data
                elif isinstance(content_data, dict):
                    msg_content = json.dumps(content_data)
                else:
                    msg_content = str(content_data)
                # Deduplication: use id, timestamp, and content hash
                msg_id = msg.get("id") or msg.get("message_id")
                timestamp = parse_timestamp(msg.get("timestamp"))
                content_hash = hashlib.md5(msg_content.encode()).hexdigest()
                # Check for duplicate by id or content hash
                duplicate = False
                if msg_id:
                    existing = await self.conversations_db.execute_query(
                        "SELECT message_id FROM messages WHERE message_id = ?", (msg_id,)
                    )
                    if existing:
                        duplicate = True
                if not duplicate:
                    existing = await self.conversations_db.execute_query(
                        "SELECT message_id FROM messages WHERE timestamp = ? AND content = ?", (timestamp, msg_content)
                    )
                    if existing:
                        duplicate = True
                if not duplicate:
                    result = await self.conversations_db.store_message(
                        content=msg_content,
                        role=role,
                        session_id=session_id,
                        conversation_id=conversation_id,
                        metadata={**metadata, "imported_id": msg_id, "imported_timestamp": timestamp, "content_hash": content_hash}
                    )
                    if session_id is None:
                        session_id = result["session_id"]
                        conversation_id = result["conversation_id"]
                    imported_count += 1
            logger.info(f"Imported {imported_count} messages from {file_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error importing JSON conversation {file_path}: {e}")
    
    async def _import_jsonl_conversation(self, file_path: str, content: str):
        """Import a JSONL conversation file (one JSON object per line), with deduplication."""
        try:
            metadata = {
                "source_file": file_path,
                "import_timestamp": datetime.now(get_local_timezone()).isoformat(),
                "file_type": "jsonl_conversation",
                "source_type": "external_jsonl"
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
                        # Deduplication: use id, timestamp, and content hash
                        msg_id = msg.get("id") or msg.get("message_id")
                        timestamp = parse_timestamp(msg.get("timestamp"))
                        content_hash = hashlib.md5(msg_content.encode()).hexdigest()
                        duplicate = False
                        if msg_id:
                            existing = await self.conversations_db.execute_query(
                                "SELECT message_id FROM messages WHERE message_id = ?", (msg_id,)
                            )
                            if existing:
                                duplicate = True
                        if not duplicate:
                            existing = await self.conversations_db.execute_query(
                                "SELECT message_id FROM messages WHERE timestamp = ? AND content = ?", (timestamp, msg_content)
                            )
                            if existing:
                                duplicate = True
                        if not duplicate and msg_content.strip():
                            result = await self.conversations_db.store_message(
                                content=msg_content,
                                role=role,
                                session_id=session_id,
                                conversation_id=conversation_id,
                                metadata={**metadata, "imported_id": msg_id, "imported_timestamp": timestamp, "content_hash": content_hash}
                            )
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
    
    async def _import_conversation_file(self, file_path: str, content: str):
        """Import a conversation file into the memory system, only importing new messages after the first scan."""
        try:
            mcp_running = self._check_mcp_server() if hasattr(self, '_check_mcp_server') else False
            file_lower = file_path.lower()
            # VS Code chat session files
            if 'chatsessions' in file_lower and file_path.endswith('.json'):
                await self._import_vscode_chat_session(file_path, content, mcp_running)
            # LM Studio conversation files
            elif 'lmstudio' in file_lower or ('lm studio' in file_lower) or ('lm_studio' in file_lower):
                await self._import_lmstudio_conversation(file_path, content)
            # Ollama conversation files
            elif 'ollama' in file_lower:
                await self._import_ollama_conversation(file_path, content)
            # Character.ai conversation files
            elif 'character.ai' in file_lower or 'character-ai' in file_lower:
                await self._import_characterai_conversation(file_path, content)
            # Local.ai conversation files
            elif 'local.ai' in file_lower or 'localai' in file_lower:
                await self._import_localai_conversation(file_path, content)
            # text-generation-webui conversation files
            elif 'text-generation-webui' in file_lower or 'textgenwebui' in file_lower:
                await self._import_textgenwebui_conversation(file_path, content)
            # Other JSON conversation files
            elif file_path.endswith('.json'):
                await self._import_json_conversation(file_path, content, mcp_running)
            elif file_path.endswith('.jsonl'):
                await self._import_jsonl_conversation(file_path, content, mcp_running)
            else:
                await self._import_text_conversation(file_path, content)
        except Exception as e:
            logger.error(f"Error importing conversation from {file_path}: {e}")

    # The following block had indentation and variable errors. Fixing only those, not refactoring.
    async def _import_text_conversation(self, file_path, lines, session_id=None, conversation_id=None, metadata=None):
        current_role = "user"
        current_message = []
        message_count = 0
        try:
            for line in lines:
                if line.startswith(("User:", "Human:", "You:")):
                    if current_message:
                        msg_content = '\n'.join(current_message).strip()
                        duplicate = False
                        existing = await self.conversations_db.execute_query(
                            "SELECT content FROM messages WHERE content = ?", (msg_content,)
                        )
                        if existing:
                            duplicate = True
                        if not duplicate:
                            result = await self._save_text_message(current_message, current_role, session_id, conversation_id, metadata)
                            if session_id is None:
                                session_id = result["session_id"]
                                conversation_id = result["conversation_id"]
                            message_count += 1
                    current_message = [line[line.find(":")+1:].strip()]
                    current_role = "user"
                elif line.startswith(("Assistant:", "AI:", "Bot:", "Friday:")):
                    if current_message:
                        msg_content = '\n'.join(current_message).strip()
                        duplicate = False
                        existing = await self.conversations_db.execute_query(
                            "SELECT content FROM messages WHERE content = ?", (msg_content,)
                        )
                        if existing:
                            duplicate = True
                        if not duplicate:
                            result = await self._save_text_message(current_message, current_role, session_id, conversation_id, metadata)
                            if session_id is None:
                                session_id = result["session_id"]
                                conversation_id = result["conversation_id"]
                            message_count += 1
                    current_message = [line[line.find(":")+1:].strip()]
                    current_role = "assistant"
                else:
                    # Continuation of current message
                    current_message.append(line)
            # Save the last message
            if current_message:
                msg_content = '\n'.join(current_message).strip()
                existing = await self.conversations_db.execute_query(
                    "SELECT content FROM messages WHERE content = ?", (msg_content,)
                )
                if not existing:
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
    """Intelligent embedding service that preserves existing embeddings while optimizing for quality"""
    
    def __init__(self, config_path: str = "embedding_config.json"):
        self.config_path = config_path
        self.full_config = self._load_full_config()
        self.primary_config = self.full_config.get("primary", {})
        self.fallback_config = self.full_config.get("fallback", {})
        self.initialized = False
        self.provider_availability = {
            "lm_studio": None,  # Will be tested on first use
            "ollama": None,
            "openai": None
        }
        
        print("🔧 Intelligent Embedding Service Configuration")
        primary_provider = self.primary_config.get('provider', 'lm_studio')
        primary_model = self.primary_config.get('model', 'text-embedding-nomic-embed-text-v1.5')
        fallback_provider = self.fallback_config.get('provider', 'ollama')
        fallback_model = self.fallback_config.get('model', 'nomic-embed-text')
        
        print(f"✅ Primary: {primary_provider} ({primary_model})")
        print(f"⚡ Fallback: {fallback_provider} ({fallback_model})")
        print(f"💾 Preserving existing 768D embeddings, using best available for new ones")
        print("To customize, edit embedding_config.json in the Friday directory")
    
    def _load_full_config(self) -> dict:
        """Load complete embedding configuration from JSON file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)
                    return config_data.get("embedding_configuration", {})
            else:
                # Create default config file if it doesn't exist
                self._create_default_config()
                return self._get_default_full_config()
        except Exception as e:
            logger.warning(f"Failed to load embedding config: {e}, using defaults")
            return self._get_default_full_config()
    
    def _get_default_full_config(self) -> dict:
        """Get default full configuration for Friday system"""
        return {
            "primary": {
                "provider": "lm_studio",
                "model": "text-embedding-nomic-embed-text-v1.5",
                "base_url": "http://192.168.1.50:1234",
                "description": "High-quality LM Studio embeddings for semantic search"
            },
            "fallback": {
                "provider": "ollama",
                "model": "nomic-embed-text",
                "base_url": "http://localhost:11434",
                "description": "Fast local Ollama embeddings"
            }
        }
    
    def _create_default_config(self):
        """Create default embedding configuration file"""
        default_config = {
            "embedding_configuration": {
                "primary": {
                    "provider": "lm_studio",
                    "model": "text-embedding-nomic-embed-text-v1.5", 
                    "base_url": "http://192.168.1.50:1234",
                    "description": "High-quality LM Studio embeddings for semantic search"
                },
                "fallback": {
                    "provider": "ollama",
                    "model": "nomic-embed-text",
                    "base_url": "http://localhost:11434",
                    "description": "Fast local Ollama embeddings"
                },
                "options": {
                    "openai": {
                        "provider": "openai",
                        "model": "text-embedding-3-small",
                        "base_url": "https://api.openai.com/v1",
                        "api_key": "your-openai-api-key-here",
                        "description": "OpenAI embeddings (requires API key)"
                    }
                }
            },
            "instructions": {
                "setup": [
                    "1. Edit this file to configure your preferred embedding providers",
                    "2. Configure 'primary' for your main embedding service",
                    "3. Configure 'fallback' for backup when primary fails",
                    "4. For Ollama: Make sure model is pulled (ollama pull nomic-embed-text)",
                    "5. For LM Studio: Load an embedding model and update base_url if needed",
                    "6. For OpenAI: Add your API key",
                    "7. Restart Friday to apply changes"
                ],
                "providers": {
                    "lm_studio": "High quality embeddings, best for semantic search",
                    "ollama": "Fast local embeddings, good for development",
                    "openai": "Premium quality but requires internet and API costs"
                },
                "preservation_note": "Existing embeddings are preserved automatically - new embeddings use your configured providers"
            }
        }
        
        try:
            with open(self.config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            logger.info(f"Created default embedding config at {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to create default config: {e}")
    
    @property
    def config(self) -> dict:
        """Backward compatibility property - returns primary config"""
        return self.primary_config
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using intelligent provider selection with preservation strategy"""
        
        # Try primary provider first
        primary_provider = self.primary_config.get("provider", "lm_studio")
        
        try:
            if primary_provider == "lm_studio":
                result = await self._generate_lm_studio_embedding(text)
                if result:
                    self.provider_availability["lm_studio"] = True
                    self.initialized = True
                    return result
                else:
                    self.provider_availability["lm_studio"] = False
                    logger.warning("LM Studio unavailable, trying fallback")
                    
            elif primary_provider == "ollama":
                result = await self._generate_ollama_embedding(text)
                if result:
                    self.provider_availability["ollama"] = True
                    self.initialized = True
                    return result
                else:
                    self.provider_availability["ollama"] = False
                    logger.warning("Ollama unavailable, trying fallback")
                    
            elif primary_provider == "openai":
                result = await self._generate_openai_embedding(text)
                if result:
                    self.provider_availability["openai"] = True
                    self.initialized = True
                    return result
                else:
                    self.provider_availability["openai"] = False
                    logger.warning("OpenAI unavailable, trying fallback")
                    
        except Exception as e:
            logger.warning(f"Primary provider {primary_provider} failed: {e}")
        
        # Try fallback provider
        fallback_provider = self.fallback_config.get("provider")
        if fallback_provider and fallback_provider != primary_provider:
            try:
                if fallback_provider == "lm_studio":
                    result = await self._generate_lm_studio_embedding(text, fallback=True)
                    if result:
                        self.provider_availability["lm_studio"] = True
                        self.initialized = True
                        logger.info("Using LM Studio fallback for embedding")
                        return result
                        
                elif fallback_provider == "ollama":
                    result = await self._generate_ollama_embedding(text, fallback=True)
                    if result:
                        self.provider_availability["ollama"] = True
                        self.initialized = True
                        logger.info("Using Ollama fallback for embedding")
                        return result
                        
                elif fallback_provider == "openai":
                    result = await self._generate_openai_embedding(text, fallback=True)
                    if result:
                        self.provider_availability["openai"] = True
                        self.initialized = True
                        logger.info("Using OpenAI fallback for embedding")
                        return result
                        
            except Exception as e:
                logger.error(f"Fallback provider {fallback_provider} also failed: {e}")
        
        # If both primary and fallback fail, log the issue
        logger.error("All embedding providers failed - semantic search will be unavailable")
        return []
    
    async def _generate_ollama_embedding(self, text: str, fallback: bool = False) -> List[float]:
        """Generate embedding using Ollama"""
        if fallback:
            config = self.fallback_config
        else:
            config = self.primary_config if self.primary_config.get("provider") == "ollama" else self.fallback_config
            
        base_url = config.get("base_url", "http://localhost:11434")
        model = config.get("model", "nomic-embed-text")
        
        async with aiohttp.ClientSession() as session:
            payload = {"model": model, "prompt": text}
            async with session.post(f"{base_url}/api/embeddings", json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("embedding")
                else:
                    error_text = await response.text()
                    logger.error(f"Ollama API error {response.status}: {error_text}")
                    return None
    
    async def _generate_lm_studio_embedding(self, text: str, fallback: bool = False) -> List[float]:
        """Generate embedding using LM Studio"""
        if fallback:
            config = self.fallback_config
        else:
            config = self.primary_config if self.primary_config.get("provider") == "lm_studio" else self.fallback_config
            
        base_url = config.get("base_url", "http://192.168.1.50:1234")
        model = config.get("model", "text-embedding-nomic-embed-text-v1.5")
        
        max_retries = 3 if self.initialized else 5
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    payload = {"model": model, "input": text}
                    async with session.post(f"{base_url}/v1/embeddings", json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data and "data" in data and len(data["data"]) > 0:
                                embedding = data["data"][0].get("embedding")
                                if embedding:
                                    return embedding
                            logger.error(f"Invalid LM Studio response format: {data}")
                            return None
                        else:
                            error_text = await response.text()
                            logger.error(f"LM Studio API error {response.status}: {error_text}")
                            
                            # Retry if model not found (JIT race)
                            if (
                                (response.status == 404 or response.status == 400) and
                                ("model does not exist" in error_text.lower() or 
                                 "failed to load model" in error_text.lower() or
                                 "cannot read properties of null" in error_text.lower())
                                and attempt < max_retries - 1
                            ):
                                delay = (attempt + 1) * 5
                                logger.info(f"Retrying LM Studio in {delay} seconds (attempt {attempt+2}/{max_retries})...")
                                await asyncio.sleep(delay)
                                continue
                            return None
            except Exception as e:
                logger.error(f"LM Studio embedding error: {e}")
                return None
        return None
    
    async def _generate_openai_embedding(self, text: str, fallback: bool = False) -> List[float]:
        """Generate embedding using OpenAI"""
        if fallback:
            config = self.fallback_config
        else:
            config = self.primary_config if self.primary_config.get("provider") == "openai" else self.fallback_config
            
        api_key = config.get("api_key")
        if not api_key or api_key == "your-openai-api-key-here":
            logger.error("OpenAI API key not configured")
            return None
            
        base_url = self.config.get("base_url", "https://api.openai.com/v1")
        model = self.config.get("model", "text-embedding-3-small")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            payload = {"model": model, "input": text}
            async with session.post(f"{base_url}/embeddings", json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and "data" in data and len(data["data"]) > 0:
                        return data["data"][0]["embedding"]
                else:
                    error_text = await response.text()
                    logger.error(f"OpenAI API error {response.status}: {error_text}")
                    return None
    
    async def _generate_custom_embedding(self, text: str) -> List[float]:
        """Generate embedding using custom endpoint"""
        base_url = self.config.get("base_url", "http://localhost:8000")
        model = self.config.get("model", "custom-model")
        
        async with aiohttp.ClientSession() as session:
            payload = {"model": model, "input": text}
            async with session.post(f"{base_url}/embeddings", json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("embedding") or data.get("data", [{}])[0].get("embedding")
                else:
                    error_text = await response.text()
                    logger.error(f"Custom API error {response.status}: {error_text}")
                    return None
    
    async def batch_generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        
        embeddings = []
        for text in texts:
            embedding = await self.generate_embedding(text)
            embeddings.append(embedding)
        
        return embeddings


class FridayMemorySystem:
    async def background_main(self):
        # Start maintenance loop, file monitoring, etc.
        await self.run_database_maintenance()
        await self.start_file_monitoring()
        # ...other background tasks as needed...
    async def get_appointments(self, limit: int = 5, days_ahead: int = 30) -> Dict:
        """Get recent appointments from the schedule database"""
        appointments = await self.schedule_db.get_appointments(limit, days_ahead)
        
        if not appointments:
            return {
                "status": "no_appointments",
                "message": "No appointments in the next {} days.".format(days_ahead),
                "appointments": []
            }
        
        return {
            "status": "success",
            "count": len(appointments),
            "appointments": appointments
        }
    """Main memory system that coordinates all databases and operations"""
    def __init__(self, data_dir: str = "memory_data", enable_file_monitoring: bool = True, 
                 watch_directories: List[str] = None, workspace_path: str = r"F:\Friday"):
        self.workspace_path = workspace_path
        # Hardcoded database paths for reliability
        self.conversations_db = ConversationDatabase("F:/Friday/memory_data/conversations.db")
        self.ai_memory_db = AIMemoryDatabase("F:/Friday/memory_data/ai_memories.db")
        self.schedule_db = ScheduleDatabase("F:/Friday/memory_data/schedule.db")
        self.vscode_db = VSCodeProjectDatabase("F:/Friday/memory_data/vscode_project.db")
        self.mcp_db = MCPToolCallDatabase("F:/Friday/memory_data/mcp_tool_calls.db")
        self.workspace_path = Path(self.workspace_path) if isinstance(self.workspace_path, str) else self.workspace_path
        self.data_dir = Path(self.workspace_path) / "memory_data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Initialize embedding service
        self.embedding_service = EmbeddingService()
        
        # Initialize file monitoring (but do NOT start yet)
        self.file_monitor = None
        if enable_file_monitoring:
            try:
                # Make sure vscode_db is initialized before creating monitor
                if not hasattr(self, 'vscode_db') or self.vscode_db is None:
                    logger.warning("VS Code database not initialized, creating it now")
                    self.vscode_db = VSCodeProjectDatabase(str(self.data_dir / "vscode_project.db"))
                self.file_monitor = ConversationFileMonitor(self, watch_directories)
                # Do NOT start monitoring here; will be started after LM Studio initialization
            except Exception as e:
                logger.error(f"Error initializing file monitor: {e}")
                raise
    
    # === Reminder Management Tools ===
    async def complete_reminder(self, reminder_id: str, selection_id: str | None = None) -> Dict:
        """Mark a reminder as completed (single multi-step tool, DB pinned to F:\\Friday\\memory_data\\schedule.db)"""
        import sqlite3
        import asyncio

        DB_PATH = r"F:\Friday\memory_data\schedule.db"

        # ---- sync helpers (run via to_thread to avoid blocking the event loop) ----
        def _update_by_id(rid: str) -> int:
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.execute(
                    "UPDATE reminders SET completed = 1, completed_at = ? WHERE reminder_id = ?",
                    (get_current_timestamp(), rid)
                )
                conn.commit()
                return cur.rowcount or 0

        def _select_by_due(due: str):
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.execute(
                    "SELECT reminder_id, title, due_datetime "
                    "FROM reminders "
                    "WHERE due_datetime = ? AND (completed IS NULL OR completed = 0)",
                    (due,)
                )
                return cur.fetchall()

        # If a selection_id is provided, skip discovery and complete that specific ID.
        if selection_id:
            affected = await asyncio.to_thread(_update_by_id, selection_id)
            if affected > 0:
                return {
                    "status": "success",
                    "message": f"Reminder {selection_id} marked as completed",
                    "reminder_id": selection_id,
                    "source_db": DB_PATH
                }
            return {
                "status": "error",
                "message": f"Reminder {selection_id} not found (follow-up)",
                "source_db": DB_PATH
            }

        # No selection yet — try exact reminder_id first.
        affected = await asyncio.to_thread(_update_by_id, reminder_id)
        if affected > 0:
            return {
                "status": "success",
                "message": f"Reminder {reminder_id} marked as completed",
                "reminder_id": reminder_id,
                "source_db": DB_PATH
            }

        # Treat 'reminder_id' as a due_datetime and discover matches.
        matches = await asyncio.to_thread(_select_by_due, reminder_id)

        if not matches:
            return {
                "status": "error",
                "message": "Reminder not found by id or due date",
                "source_db": DB_PATH
            }

        if len(matches) == 1:
            only_id = matches[0][0]
            affected = await asyncio.to_thread(_update_by_id, only_id)
            if affected > 0:
                return {
                    "status": "success",
                    "message": f"Reminder with due date {reminder_id} (id {only_id}) marked as completed",
                    "reminder_id": only_id,
                    "source_db": DB_PATH
                }
            return {
                "status": "error",
                "message": "Failed to mark reminder as completed after single-match resolution",
                "source_db": DB_PATH
            }

        # Multiple matches — return options and instruct caller to pass selection_id on the next call.
        options = [
            {"reminder_id": row[0], "title": row[1], "due_datetime": row[2]}
            for row in matches
        ]
        return {
            "status": "needs_selection",
            "message": f"Multiple reminders share due date {reminder_id}. Call this tool again with selection_id set to the chosen reminder_id.",
            "options": options,
            "source_db": DB_PATH
        }



    async def get_active_reminders(self, limit: int = 10, days_ahead: int = 30) -> Dict:
        """Get active (not completed) reminders within the next X days"""
        now = datetime.now(get_local_timezone()).isoformat()
        cutoff = (datetime.now(get_local_timezone()) + timedelta(days=days_ahead)).isoformat()
        rows = await self.schedule_db.execute_query(
            "SELECT * FROM reminders WHERE completed = 0 AND due_datetime >= ? AND due_datetime <= ? ORDER BY due_datetime LIMIT ?",
            (now, cutoff, limit)
        )
        
        if not rows:
            return {
                "status": "no_reminders",
                "message": "No active reminders scheduled."
            }
        
        return {
            "status": "success",
            "count": len(rows),
            "reminders": [
                {
                    "reminder_id": r["reminder_id"],
                    "content": r["content"],
                    "due_datetime": r["due_datetime"],
                    "priority_level": r["priority_level"],
                    "created_at": r["created_at"]
                }
                for r in rows
            ]
        }

    async def get_completed_reminders(self, days: int = 7) -> Dict:
        """Get recently completed reminders"""
        cutoff = (datetime.now(get_local_timezone()) - timedelta(days=days)).isoformat()
        rows = await self.schedule_db.execute_query(
            "SELECT * FROM reminders WHERE completed = 1 AND completed_at >= ? ORDER BY completed_at DESC",
            (cutoff,)
        )
        
        if not rows:
            return {
                "status": "no_completed_reminders",
                "message": "All reminders are completed in the last {} days.".format(days)
            }
        
        return {
            "status": "success",
            "count": len(rows),
            "reminders": [
                {
                    "reminder_id": r["reminder_id"],
                    "content": r["content"],
                    "due_datetime": r["due_datetime"],
                    "completed_at": r["completed_at"]
                }
                for r in rows
            ]
        }

    async def reschedule_reminder_post(self, body: Dict) -> Dict:
        if "reminder_id" not in body or "new_due_datetime" not in body:
            return {
                "error": "HTTP error! Status: 422. Message: Missing required fields. Please provide 'reminder_id' and 'new_due_datetime'."
            }
        
        reminder_id = body["reminder_id"]
        new_due_datetime = body["new_due_datetime"]
        
        result = await self.schedule_db.execute_update(
            "UPDATE reminders SET due_datetime = ? WHERE reminder_id = ?",
            (new_due_datetime, reminder_id)
        )
        if result > 0:
            return {"status": "success", "message": f"Reminder {reminder_id} rescheduled to {new_due_datetime}"}
        else:
            return {"status": "error", "message": "Reminder not found"}

    async def delete_reminder(self, reminder_id: str) -> Dict:
        result = await self.schedule_db.execute_update(
            "DELETE FROM reminders WHERE reminder_id = ?",
            (reminder_id,)
        )
        if result and result != "0":
            return {"status": "success", "message": f"Reminder {reminder_id} deleted"}
        else:
            return {"status": "error", "message": "Reminder not found"}

    # === Appointment Management Tools ===
    async def cancel_appointment(self, appointment_id: str) -> Dict:
        """Cancel an appointment"""
        result = await self.schedule_db.execute_update(
            "UPDATE appointments SET status = 'cancelled', cancelled_at = ? WHERE appointment_id = ?",
            (get_current_timestamp(), appointment_id)
        )
        if result > 0:
            return {"status": "success", "message": f"Appointment {appointment_id} cancelled"}
        else:
            return {"status": "error", "message": "Appointment not found"}

    async def get_upcoming_appointments(self, limit: int = 5, days_ahead: int = 30) -> Dict:
        """Get upcoming appointments (not cancelled), today onward. Handles ISO-text and integer-epoch datetimes."""
        now_local = datetime.now(get_local_timezone())
        cutoff_local = now_local + timedelta(days=days_ahead)
        now_epoch = int(now_local.timestamp())
        cutoff_epoch = int(cutoff_local.timestamp())
        query = """
            SELECT *
            FROM appointments
            WHERE status != 'cancelled'
            AND (
                    CASE
                        WHEN typeof(scheduled_datetime) = 'integer' THEN scheduled_datetime
                        ELSE CAST(strftime('%s', scheduled_datetime) AS INTEGER)
                    END
            ) BETWEEN ? AND ?
            ORDER BY
                CASE
                    WHEN typeof(scheduled_datetime) = 'integer' THEN scheduled_datetime
                    ELSE CAST(strftime('%s', scheduled_datetime) AS INTEGER)
                END ASC
            LIMIT ?
        """
        rows = await self.schedule_db.execute_query(query, (now_epoch, cutoff_epoch, limit))
        
        if not rows:
            return {
                "status": "no_appointments",
                "message": "No upcoming appointments in the next {} days.".format(days_ahead)
            }
        
        return {
            "status": "success",
            "count": len(rows),
            "appointments": [
                {
                    "appointment_id": r["appointment_id"],
                    "title": r["title"],
                    "scheduled_datetime": r["scheduled_datetime"],
                    "duration_minutes": r["duration_minutes"],
                    "description": r["description"]
                }
                for r in rows
            ]
        }
    
    def ensure_all_memory_databases_ready(self):
        base_dir = Path("F:/Friday")  # ← YOUR ROOT
        db_dir = base_dir / "F:/Friday/memory_data"
        db_dir.mkdir(exist_ok=True)
        """
        Ensure all expected memory database files exist with required tables.
        Safe to run repeatedly. Creates empty tables if missing.
        """
        logger.info("Ensuring memory databases are initialized...")

        for db_path, schema in [
            ("memory_data/conversations.db", """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    sender TEXT,
                    content TEXT,
                    timestamp TEXT
                );
            """),
            (str(self.data_dir / "ai_memories.db"), """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT,
                    timestamp TEXT,
                    importance TEXT
                );
            """),
            (str(self.data_dir / "schedule.db"), """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT,
                    datetime TEXT,
                    is_active INTEGER
                );
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    datetime TEXT,
                    notes TEXT
                    status TEXT DEFAULT 'scheduled' CHECK("status" IN ('scheduled', 'cancelled', 'completed'))
                );
            """),
            (str(self.data_dir / "vscode_project.db"), """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    file_path TEXT,
                    timestamp TEXT
                );
                CREATE TABLE IF NOT EXISTS insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    type TEXT,
                    detail TEXT
                );
            """),
            (str(self.data_dir / "mcp_tool_calls.db"), """
                CREATE TABLE IF NOT EXISTS tool_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT,
                    timestamp TEXT,
                    success INTEGER
                );
            """),
        ]:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.executescript(schema)
                conn.commit()
                conn.close()
                logger.info(f"✔️  Verified: {db_path}")
            except Exception as e:
                logger.error(f"❌ Failed to verify {db_path}: {e}")

    async def import_openwebui_chat_history(self, db_path=r'F:\\OpenWebUI\\data\\webui.db'):
        """Import OpenWebUI chat/messages into Friday memory system with deduplication."""
        import sqlite3
        from datetime import datetime
        if not os.path.exists(db_path):
            print(f"OpenWebUI database not found at {db_path}")
            return
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM chat')
        chats = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.execute('SELECT id, chat_id, role, content, created_at FROM message ORDER BY chat_id, created_at')
        messages = cursor.fetchall()
        conn.close()
        imported_count = 0
        for msg_id, chat_id, role, content, created_at in messages:
            chat_name = chats.get(chat_id, f'Chat {chat_id}')
            # Use chat_id as session_id for deduplication
            session_id = str(chat_id)
            metadata = {
                'source': 'openwebui',
                'chat_id': chat_id,
                'chat_name': chat_name,
                'role': role,
                'created_at': created_at
            }
            # Deduplication: check for existing message in session with same content/role in last 24h
            recent = await self.conversations_db.execute_query(
                """SELECT message_id FROM messages WHERE conversation_id IN (
                        SELECT conversation_id FROM conversations WHERE session_id = ?
                    ) AND role = ? AND content = ? AND datetime(timestamp) > datetime('now', '-24 hour')""",
                (session_id, role, content)
            )
            if recent:
                continue  # Skip duplicate
            # Store message
            await self.conversations_db.execute_update(
                """INSERT INTO messages (message_id, conversation_id, timestamp, role, content, source_type, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (str(msg_id), str(chat_id), created_at, role, content, 'openwebui', json.dumps(metadata))
            )
            imported_count += 1
        print(f"Imported {imported_count} OpenWebUI messages (deduplicated)")

    async def _start_monitoring(self):
        """Internal method to start the file monitor"""
        if self.file_monitor:
            try:
                await self.file_monitor.start_monitoring()
                logger.info("File monitoring started")
            except Exception as e:
                logger.error(f"Error starting file monitoring: {e}")
        self.ensure_all_memory_databases_ready()
        
    async def start_file_monitoring(self):
        """Start monitoring conversation files (manual start if needed)"""
        # Only clear the file processing cache to allow reprocessing while maintaining timestamps
        if self.file_monitor:
            self.file_monitor.processed_files.clear()
            logger.info("Cleared processed files cache for fresh start")
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
            "timestamp": datetime.now(get_local_timezone()).isoformat(),
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
    
    async def get_recent_context(self, limit: int = 5, session_id: str = None, days_back: int = 7) -> Dict:
        """Get recent conversation context from the last N days"""
        
        messages = await self.conversations_db.get_recent_messages(limit, session_id, days_back)
        
        return {
            "status": "success",
            "messages": messages,
            "count": len(messages),
            "days_back": days_back
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
        timestamp = get_current_timestamp()
        
        # Store the code context
        await self.vscode_db.execute_update(
            """INSERT INTO code_context 
               (context_id, timestamp, file_path, function_name, description) 
               VALUES (?, ?, ?, ?, ?)""",
            (context_id, datetime.now(get_local_timezone()).isoformat(), file_path, function_name, description)
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
        """Add embedding to a message (background task) - skip if already exists"""
        try:
            # Check if embedding already exists
            existing = await self.conversations_db.execute_query(
                "SELECT embedding FROM messages WHERE message_id = ? AND embedding IS NOT NULL",
                (message_id,)
            )
            if existing:
                logger.debug(f"Embedding already exists for message {message_id}, skipping")
                return
                
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                # Convert to binary format for storage
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.conversations_db.execute_update(
                    "UPDATE messages SET embedding = ? WHERE message_id = ?",
                    (embedding_blob, message_id)
                )
                logger.debug(f"Generated embedding for message {message_id}")
        except Exception as e:
            logger.error(f"Error adding embedding to message {message_id}: {e}")
    
    async def _add_embedding_to_memory(self, memory_id: str, content: str):
        """Add embedding to a memory (background task) - skip if already exists"""
        try:
            # Check if embedding already exists
            existing = await self.ai_memory_db.execute_query(
                "SELECT embedding FROM curated_memories WHERE memory_id = ? AND embedding IS NOT NULL",
                (memory_id,)
            )
            if existing:
                logger.debug(f"Embedding already exists for memory {memory_id}, skipping")
                return
                
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                # Convert to binary format for storage
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.ai_memory_db.execute_update(
                    "UPDATE curated_memories SET embedding = ? WHERE memory_id = ?",
                    (embedding_blob, memory_id)
                )
                logger.debug(f"Generated embedding for memory {memory_id}")
        except Exception as e:
            logger.error(f"Error adding embedding to memory {memory_id}: {e}")
    
    async def _add_embedding_to_appointment(self, appointment_id: str, content: str):
        """Add embedding to an appointment (background task) - skip if already exists"""
        try:
            # Check if embedding already exists
            existing = await self.schedule_db.execute_query(
                "SELECT embedding FROM appointments WHERE appointment_id = ? AND embedding IS NOT NULL",
                (appointment_id,)
            )
            if existing:
                logger.debug(f"Embedding already exists for appointment {appointment_id}, skipping")
                return
                
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.schedule_db.execute_update(
                    "UPDATE appointments SET embedding = ? WHERE appointment_id = ?",
                    (embedding_blob, appointment_id)
                )
                logger.debug(f"Generated embedding for appointment {appointment_id}")
        except Exception as e:
            logger.error(f"Error adding embedding to appointment {appointment_id}: {e}")
    
    async def _add_embedding_to_reminder(self, reminder_id: str, content: str):
        """Add embedding to a reminder (background task) - skip if already exists"""
        try:
            # Check if embedding already exists
            existing = await self.schedule_db.execute_query(
                "SELECT embedding FROM reminders WHERE reminder_id = ? AND embedding IS NOT NULL",
                (reminder_id,)
            )
            if existing:
                logger.debug(f"Embedding already exists for reminder {reminder_id}, skipping")
                return
                
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.schedule_db.execute_update(
                    "UPDATE reminders SET embedding = ? WHERE reminder_id = ?",
                    (embedding_blob, reminder_id)
                )
                logger.debug(f"Generated embedding for reminder {reminder_id}")
        except Exception as e:
            logger.error(f"Error adding embedding to reminder {reminder_id}: {e}")
    
    async def _add_embedding_to_project_insight(self, insight_id: str, content: str):
        """Add embedding to a project insight (background task) - skip if already exists"""
        try:
            # Check if embedding already exists
            existing = await self.vscode_db.execute_query(
                "SELECT embedding FROM project_insights WHERE insight_id = ? AND embedding IS NOT NULL",
                (insight_id,)
            )
            if existing:
                logger.debug(f"Embedding already exists for insight {insight_id}, skipping")
                return
                
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.vscode_db.execute_update(
                    "UPDATE project_insights SET embedding = ? WHERE insight_id = ?",
                    (embedding_blob, insight_id)
                )
                logger.debug(f"Generated embedding for insight {insight_id}")
        except Exception as e:
            logger.error(f"Error adding embedding to project insight {insight_id}: {e}")
    
    async def _add_embedding_to_code_context(self, context_id: str, content: str):
        """Add embedding to code context (background task) - skip if already exists"""
        try:
            # Check if embedding already exists
            existing = await self.vscode_db.execute_query(
                "SELECT embedding FROM code_context WHERE context_id = ? AND embedding IS NOT NULL",
                (context_id,)
            )
            if existing:
                logger.debug(f"Embedding already exists for code context {context_id}, skipping")
                return
                
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.vscode_db.execute_update(
                    "UPDATE code_context SET embedding = ? WHERE context_id = ?",
                    (embedding_blob, context_id)
                )
                logger.debug(f"Generated embedding for code context {context_id}")
        except Exception as e:
            logger.error(f"Error adding embedding to code context {context_id}: {e}")
    
    async def _add_embedding_to_development_conversation(self, conversation_id: str, content: str):
        """Add embedding to development conversation (background task) - skip if already exists"""
        try:
            # Check if embedding already exists
            existing = await self.vscode_db.execute_query(
                "SELECT embedding FROM development_conversations WHERE conversation_id = ? AND embedding IS NOT NULL",
                (conversation_id,)
            )
            if existing:
                logger.debug(f"Embedding already exists for dev conversation {conversation_id}, skipping")
                return
                
            embedding = await self.embedding_service.generate_embedding(content)
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
                await self.vscode_db.execute_update(
                    "UPDATE development_conversations SET embedding = ? WHERE conversation_id = ?",
                    (embedding_blob, conversation_id)
                )
                logger.debug(f"Generated embedding for dev conversation {conversation_id}")
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

    # === SillyTavern-specific methods ===
    
    async def get_character_context(self, character_name: str, context_type: str = None, limit: int = 5) -> Dict:
        """Get relevant context about characters from memory for SillyTavern roleplay"""
        try:
            # Search memories for character-related content
            search_query = f"character {character_name}"
            if context_type:
                search_query += f" {context_type}"
            
            # Search across all memory types for character information
            results = await self.search_memories(
                query=search_query,
                limit=limit,
                database_filter="all"
            )
            
            # Filter and categorize results specifically for character context
            character_context = {
                "character_name": character_name,
                "context_type": context_type,
                "personality_traits": [],
                "relationships": [],
                "history": [],
                "preferences": [],
                "memories": results.get("results", [])
            }
            
            # Categorize memories by type
            for memory in results.get("results", []):
                content = memory.get("content", "").lower()
                tags = memory.get("tags", [])
                
                if any(tag in ["personality", "traits", "character"] for tag in tags):
                    character_context["personality_traits"].append(memory)
                elif any(tag in ["relationship", "social"] for tag in tags):
                    character_context["relationships"].append(memory)
                elif any(tag in ["history", "background", "past"] for tag in tags):
                    character_context["history"].append(memory)
                elif any(tag in ["preference", "likes", "dislikes"] for tag in tags):
                    character_context["preferences"].append(memory)
            
            return {
                "status": "success",
                "character_context": character_context,
                "total_memories": len(results.get("results", [])),
                "query_used": search_query
            }
            
        except Exception as e:
            logger.error(f"Error getting character context: {e}")
            return {
                "status": "error",
                "error": str(e),
                "character_context": {"character_name": character_name, "memories": []}
            }
    
    async def store_roleplay_memory(self, character_name: str, event_description: str, 
                                  importance_level: int = 5, tags: List[str] = None) -> Dict:
        """Store important roleplay moments or character developments for SillyTavern"""
        try:
            # Create content that includes character context
            content = f"Roleplay event with {character_name}: {event_description}"
            
            # Default tags for roleplay memories
            if tags is None:
                tags = []
            
            roleplay_tags = ["roleplay", "character", character_name.lower()] + tags
            
            # Store as a curated memory with roleplay type
            result = await self.create_memory(
                content=content,
                memory_type="roleplay",
                importance_level=importance_level,
                tags=roleplay_tags
            )
            
            # Also store as a conversation to maintain chat context
            await self.store_conversation(
                content=f"[Roleplay Memory] {event_description}",
                role="system",
                metadata={
                    "character_name": character_name,
                    "event_type": "roleplay_memory",
                    "importance": importance_level
                }
            )
            
            return {
                "status": "success",
                "memory_id": result["memory_id"],
                "character_name": character_name,
                "content": content,
                "tags": roleplay_tags
            }
            
        except Exception as e:
            logger.error(f"Error storing roleplay memory: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def search_roleplay_history(self, query: str, character_name: str = None, limit: int = 10) -> Dict:
        """Search past roleplay interactions and character development for SillyTavern"""
        try:
            # Enhance query with roleplay context
            search_query = f"roleplay {query}"
            if character_name:
                search_query += f" {character_name}"
            
            # Search specifically for roleplay memories and conversations
            results = await self.search_memories(
                query=search_query,
                limit=limit,
                database_filter="all",
                memory_type="roleplay"
            )
            
            # Also search general conversations for roleplay content
            all_results = await self.search_memories(
                query=search_query,
                limit=limit * 2,
                database_filter="conversations"
            )
            
            # Combine and deduplicate results
            combined_results = results.get("results", [])
            for result in all_results.get("results", []):
                if result not in combined_results:
                    combined_results.append(result)
            
            # Sort by relevance/similarity score
            combined_results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
            combined_results = combined_results[:limit]
            
            # Categorize results for better SillyTavern integration
            categorized_results = {
                "character_development": [],
                "interactions": [],  
                "plot_events": [],
                "general": []
            }
            
            for result in combined_results:
                content = result.get("content", "").lower()
                tags = result.get("tags", [])
                
                if any(word in content for word in ["development", "growth", "change", "personality"]):
                    categorized_results["character_development"].append(result)
                elif any(word in content for word in ["interaction", "conversation", "dialogue"]):
                    categorized_results["interactions"].append(result)
                elif any(word in content for word in ["event", "plot", "story", "scene"]):
                    categorized_results["plot_events"].append(result)
                else:
                    categorized_results["general"].append(result)
            
            return {
                "status": "success",
                "query": query,
                "character_name": character_name,
                "total_results": len(combined_results),
                "results": combined_results,
                "categorized_results": categorized_results,
                "search_context": "roleplay_history"
            }
            
        except Exception as e:
            logger.error(f"Error searching roleplay history: {e}")
            return {
                "status": "error",
                "error": str(e),
                "results": [],
                "categorized_results": {}
            }

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
        workspace_path= r"F:\Friday",
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
    continuity = await memory.get_project_continuity(r"F:\Friday")
    print(f"\nProject continuity data: {len(continuity['continuity_data']['recent_sessions'])} sessions, "
          f"{len(continuity['continuity_data']['important_insights'])} important insights")
    
    print("\n8. Starting file monitoring...")
    # Now that all other systems are initialized and tested, start file monitoring
    await memory.start_file_monitoring()
    
    print("   File monitoring is now starting...")
    print("   The system will automatically detect and import conversations from:")
    print("   - VS Code chat sessions")
    print("   - LM Studio conversations")
    print("   - Ollama conversations")
    print("   - OpenWebUI Conversations")
    
    print("\n9. Cleaning up test data...")
    
    # Delete the test reminder we created
    try:
        cleanup_result = await memory.delete_reminder(reminder['reminder_id'])
        print(f"   Deleted test reminder: {cleanup_result['message']}")
    except Exception as e:
        print(f"   Failed to delete test reminder: {e}")
    
    # Cancel the test appointment we created  
    try:
        cleanup_result = await memory.cancel_appointment(appointment['appointment_id'])
        print(f"   Cancelled test appointment: {cleanup_result['message']}")
    except Exception as e:
        print(f"   Failed to cancel test appointment: {e}")
    
    # Delete the test memories we created
    try:
        # Delete memory1 and memory2 using their IDs
        cleanup_result = await memory.ai_memory_db.execute_update(
            "DELETE FROM curated_memories WHERE memory_id = ?", 
            (memory1['memory_id'],)
        )
        cleanup_result = await memory.ai_memory_db.execute_update(
            "DELETE FROM curated_memories WHERE memory_id = ?", 
            (memory2['memory_id'],)
        )
        print(f"   Deleted test memories")
    except Exception as e:
        print(f"   Failed to delete test memories: {e}")
    
    print("   Test data cleanup complete!")
    
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
