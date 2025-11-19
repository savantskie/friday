#!/usr/bin/env python3
"""
Friday Memory System - Database Maintenance Module

Provides automated cleanup, optimization, retention policies, and database sharding for the memory system.
"""

import asyncio
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import os

logger = logging.getLogger(__name__)


class DatabaseMaintenance:
    """
    Handles automated database cleanup, optimization, and sharding/rotation management.
    
    Combines maintenance tasks with database lifecycle management:
    - Discovery: Scans memory_data folder to discover all database files
    - Monitoring: Tracks file sizes and health
    - Rotation: Creates new databases when size/time thresholds are exceeded
    - Cleanup: Applies retention policies and removes old data
    - Migration: Retroactively splits large databases into sharded structure
    """
    
    def __init__(self, memory_system, memory_data_path: str = None):
        self.memory_system = memory_system
        
        # Database discovery and management
        if memory_data_path:
            self.memory_data_path = Path(memory_data_path)
        else:
            # Try to infer from memory_system if not provided
            self.memory_data_path = Path(memory_system.conversations_db.db_path).parent
        
        self.db_registry: Dict[str, List[Dict]] = {}  # {db_type: [{"path": str, "date_range": tuple, "size": int}, ...]}
        self.rotation_threshold_bytes = 3 * 1024 * 1024 * 1024  # 3GB
        self.last_discovery = None
        
        # Retention policies for cleanup
        self.retention_policies = {
            "conversations": {
                "max_age_days": None,  # No age limit - keep ALL conversations indefinitely
                "max_count": None,     # No count limit - keep all conversations
                "preserve_important": True  # Keep all conversations (no pruning)
            },
            "curated_memories": {
                "max_age_days": None,  # No age limit - keep all memories indefinitely
                "max_count": None,     # No count limit - keep all memories
                "preserve_important": True  # Keep all memories (no pruning)
            },
            "schedule": {
                "max_age_days": 30,  # Keep old appointments/reminders for 1 month
                "cleanup_completed": True  # Remove completed items
            },
            "mcp_tool_calls": {
                "max_age_days": None,  # No age limit - keep ALL tool calls indefinitely
                "max_count": None      # No count limit - keep all tool calls
            },
            "memory_conversation_links": {
                "max_age_days": None,  # No age limit - keep ALL links indefinitely
                "cleanup_orphaned": True  # Remove links to deleted memories/conversations (only orphaned)
            },
            "memory_processing_queue": {
                "max_age_days": 30,  # Keep processed queue entries for 1 month
                "cleanup_completed": True  # Remove completed processing records
            },
            "memory_processing_log": {
                "max_age_days": 90,  # Keep processing logs for 3 months
                "max_count": 100000  # Keep max 100k log entries
            },
            "image_database": {
                "max_age_days": None,  # No age limit - keep all images (memories reference them)
                "max_count": None,     # No count limit - keep all images
                "preserve_important": True  # Keep all images (linked to memories)
            }
        }
    
    # ===== Database Discovery & Lifecycle Management =====
    
    async def discover_databases(self) -> Dict[str, List[Dict]]:
        """
        Scan memory_data folder and discover all database files.
        
        Returns:
            Dict mapping database types to list of DB file info
        """
        logger.info(f"Discovering databases in {self.memory_data_path}")
        
        if not self.memory_data_path.exists():
            logger.error(f"Memory data path does not exist: {self.memory_data_path}")
            return {}
        
        discovered = {}
        
        # Patterns for different database types
        db_patterns = {
            "conversations": "conversations*.db",
            "ai_memories": "ai_memories*.db",
            "schedule": "schedule*.db",
            "mcp_tool_calls": "mcp_tool_calls*.db",
            "vscode_project": "vscode_project*.db",
            "image_database": "image_database*.db"
        }
        
        for db_type, pattern in db_patterns.items():
            db_files = []
            matching_files = list(self.memory_data_path.glob(pattern))
            
            for db_file in matching_files:
                try:
                    file_size = db_file.stat().st_size
                    date_range = self._extract_date_range_from_db(str(db_file))
                    
                    db_info = {
                        "path": str(db_file),
                        "filename": db_file.name,
                        "date_range": date_range,
                        "size": file_size,
                        "size_mb": round(file_size / 1024 / 1024, 2),
                        "healthy": await self._check_db_health(str(db_file))
                    }
                    db_files.append(db_info)
                    
                except Exception as e:
                    logger.error(f"Error discovering {db_file}: {e}")
            
            if db_files:
                # Sort by date (most recent first)
                db_files.sort(key=lambda x: x["date_range"][1] if x["date_range"][1] else "", reverse=True)
                discovered[db_type] = db_files
                logger.info(f"  Found {len(db_files)} {db_type} database(s)")
        
        self.db_registry = discovered
        self.last_discovery = datetime.now(timezone.utc)
        
        return discovered
    
    def _extract_date_range_from_db(self, db_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract date range from database filename."""
        filename = Path(db_path).name
        
        if "conversations_" in filename:
            parts = filename.replace("conversations_", "").replace(".db", "").split("_")
            if len(parts) >= 1 and "-" in parts[0]:
                year_month = parts[0]
                try:
                    dt = datetime.fromisoformat(f"{year_month}-01")
                    if dt.month == 12:
                        next_month = dt.replace(year=dt.year + 1, month=1, day=1)
                    else:
                        next_month = dt.replace(month=dt.month + 1, day=1)
                    last_day = (next_month - timedelta(days=1)).day
                    
                    start = f"{year_month}-01"
                    end = f"{year_month}-{last_day:02d}"
                    return (start, end)
                except Exception as e:
                    logger.debug(f"Could not parse date from filename {filename}: {e}")
        
        return (None, None)
    
    async def _check_db_health(self, db_path: str) -> bool:
        """Check if a database file is healthy and accessible."""
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            conn.close()
            
            return result == "ok"
                
        except Exception as e:
            logger.error(f"Error checking database health for {db_path}: {e}")
            return False
    
    def get_active_db(self, db_type: str) -> Optional[str]:
        """Get the currently active (most recent) database file for a given type."""
        if db_type not in self.db_registry or not self.db_registry[db_type]:
            return None
        
        return self.db_registry[db_type][0]["path"]
    
    def get_all_dbs_of_type(self, db_type: str) -> List[str]:
        """Get all database files of a given type (sorted by recency)."""
        if db_type not in self.db_registry:
            return []
        
        return [db_info["path"] for db_info in self.db_registry[db_type]]
    
    def get_db_registry(self) -> Dict[str, List[Dict]]:
        """Get the current database registry."""
        return self.db_registry
    
    async def check_rotation_needed(self, db_type: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a database needs rotation (size threshold or month boundary).
        Returns tuple of (rotation_needed, reason)
        """
        active_db = self.get_active_db(db_type)
        if not active_db:
            return (False, None)
        
        try:
            db_size = Path(active_db).stat().st_size
            
            # Check size threshold (all databases)
            if db_size >= self.rotation_threshold_bytes:
                return (True, f"Size threshold exceeded ({db_size / 1024 / 1024 / 1024:.2f}GB >= 3GB)")
            
            # Check month boundary (conversations only)
            if db_type == "conversations":
                filename = Path(active_db).name
                if "conversations_" in filename:
                    try:
                        parts = filename.replace("conversations_", "").replace(".db", "").split("_")
                        if "-" in parts[0]:
                            db_month = parts[0]
                            current_month = datetime.now().strftime("%Y-%m")
                            
                            if db_month != current_month:
                                return (True, f"Month boundary crossed (DB: {db_month}, Current: {current_month})")
                    except Exception as e:
                        logger.debug(f"Could not check month boundary: {e}")
            
            return (False, None)
            
        except Exception as e:
            logger.error(f"Error checking rotation for {db_type}: {e}")
            return (False, None)
    
    async def create_rotated_db(self, db_type: str, current_db_path: str) -> Optional[str]:
        """
        Create a new rotated database file when current one exceeds limits.
        Returns path to the new database file.
        """
        try:
            logger.info(f"Creating rotated database for {db_type}")
            
            now = datetime.now()
            
            # Determine new filename
            if db_type == "conversations":
                new_filename = f"conversations_{now.strftime('%Y-%m')}_{now.strftime('%Y%m%d')}.db"
            else:
                new_filename = f"{db_type}_{now.strftime('%Y%m%d')}.db"
            
            new_db_path = self.memory_data_path / new_filename
            
            # If file exists, add counter
            counter = 1
            base_path = new_db_path
            while new_db_path.exists():
                stem = base_path.stem
                new_filename = f"{stem}_{counter}.db"
                new_db_path = self.memory_data_path / new_filename
                counter += 1
            
            # Create the new database with schema
            await self._create_new_db_with_schema(new_db_path, current_db_path, db_type)
            
            logger.info(f"Successfully created rotated database: {new_db_path}")
            
            # Refresh discovery
            await self.discover_databases()
            
            return str(new_db_path)
            
        except Exception as e:
            logger.error(f"Error creating rotated database: {e}")
            return None
    
    async def _create_new_db_with_schema(self, new_db_path: Path, source_db_path: str, db_type: str):
        """Create a new database file and copy schema from source database."""
        try:
            # Get schema from source DB (exclude sqlite internal tables)
            source_conn = sqlite3.connect(source_db_path)
            source_cursor = source_conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql NOT NULL AND name NOT LIKE 'sqlite_%'"
            )
            tables = source_cursor.fetchall()
            source_conn.close()
            
            # Create new database with same schema
            new_conn = sqlite3.connect(str(new_db_path))
            new_cursor = new_conn.cursor()
            
            for table_name, create_sql in tables:
                logger.debug(f"Creating table {table_name} in new database")
                new_cursor.execute(create_sql)
            
            # Recreate indexes (excluding internal sqlite indexes)
            source_conn = sqlite3.connect(source_db_path)
            source_cursor = source_conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND sql NOT NULL AND name NOT LIKE 'sqlite_%'"
            )
            indexes = source_cursor.fetchall()
            source_conn.close()
            
            for (index_sql,) in indexes:
                try:
                    logger.debug(f"Creating index: {index_sql[:50]}...")
                    new_cursor.execute(index_sql)
                except Exception as e:
                    logger.debug(f"Could not recreate index: {e}")
            
            new_conn.commit()
            new_conn.close()
            
            logger.info(f"Successfully created new database with schema: {new_db_path}")
            
        except Exception as e:
            logger.error(f"Error creating new database with schema: {e}")
            raise
    
    async def _ensure_archive_tables(self, archive_db_path: str, db_type: str):
        """Ensure archive database has all required tables, especially linking tables.
        
        This is a safety check to guarantee that archive databases have the complete schema
        including any linking tables that might not exist if the main DB didn't have them yet.
        """
        try:
            # Import database classes to get their table definitions
            from friday_memory_system import (
                ConversationDatabase, AIMemoryDatabase, ScheduleDatabase,
                MCPToolCallDatabase, VSCodeProjectDatabase
            )
            
            # Map db_type to database class
            db_classes = {
                "conversations": ConversationDatabase,
                "ai_memories": AIMemoryDatabase,
                "schedule": ScheduleDatabase,
                "mcp_tool_calls": MCPToolCallDatabase,
                "vscode_project": VSCodeProjectDatabase
            }
            
            if db_type not in db_classes:
                logger.debug(f"Unknown db_type {db_type}, skipping table ensure check")
                return
            
            # Create a temporary instance to trigger initialize_tables
            # This ensures all tables including linking tables are created
            db_class = db_classes[db_type]
            temp_instance = db_class(archive_db_path)
            
            logger.debug(f"Ensured all required tables exist in archive: {Path(archive_db_path).name}")
            
        except Exception as e:
            logger.debug(f"Note: Could not ensure all archive tables for {db_type}: {e}")
            # Don't raise - this is just a safety check, data is already there
    
    async def check_and_rotate_if_needed(self, db_type: str) -> Dict[str, any]:
        """
        Check if a database needs rotation, and if so, create the new one.
        
        This is the main orchestration method called by FridayMemorySystem.
        
        Args:
            db_type: Type of database (e.g., "conversations", "mcp_tool_calls")
        
        Returns:
            Dict with keys:
            - "rotation_needed": bool - whether rotation was triggered
            - "reason": str - why rotation was needed (if triggered)
            - "new_db_path": str - path to new database (if rotated), None otherwise
            - "old_db_path": str - path to database that was rotated (if rotated)
            - "status": str - "rotated" | "no_action" | "error"
            - "error": str - error message if rotation failed
        """
        result = {
            "rotation_needed": False,
            "reason": None,
            "new_db_path": None,
            "old_db_path": None,
            "status": "no_action",
            "error": None
        }
        
        try:
            # Check if rotation needed
            rotation_needed, reason = await self.check_rotation_needed(db_type)
            result["rotation_needed"] = rotation_needed
            result["reason"] = reason
            
            if not rotation_needed:
                logger.debug(f"No rotation needed for {db_type}")
                return result
            
            # Get current DB before rotation
            current_db = self.get_active_db(db_type)
            if not current_db:
                result["status"] = "error"
                result["error"] = f"No active database found for {db_type}"
                logger.error(result["error"])
                return result
            
            result["old_db_path"] = current_db
            
            # Perform rotation
            logger.info(f"Rotating database {db_type}. Reason: {reason}")
            new_db_path = await self.create_rotated_db(db_type, current_db)
            
            if not new_db_path:
                result["status"] = "error"
                result["error"] = f"Failed to create rotated database for {db_type}"
                logger.error(result["error"])
                return result
            
            result["new_db_path"] = new_db_path
            result["status"] = "rotated"
            
            logger.warning(f"✅ Database {db_type} rotated successfully")
            logger.warning(f"  Old: {current_db}")
            logger.warning(f"  New: {new_db_path}")
            
            return result
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(f"Error during rotation check/create: {e}")
            return result
    
    async def check_and_rotate_all_databases(self) -> Dict[str, Dict]:
        """
        Check ALL databases and rotate any that need it.
        
        This is called by database maintenance as a safety net—if the memory system
        didn't catch a rotation, maintenance will catch it and handle it.
        
        Returns:
            Dict mapping db_type to rotation result:
            {
                "conversations": {"status": "rotated", "new_db_path": "...", ...},
                "mcp_tool_calls": {"status": "no_action", ...},
                "schedule": {"status": "rotated", ...},
                ...
            }
        """
        logger.warning("🔄 Checking all databases for rotation needs...")
        
        # First discover all current databases
        await self.discover_databases()
        
        results = {}
        db_types = list(self.db_registry.keys())
        
        if not db_types:
            logger.warning("No databases discovered during maintenance rotation check")
            return results
        
        for db_type in db_types:
            logger.info(f"Checking {db_type}...")
            result = await self.check_and_rotate_if_needed(db_type)
            results[db_type] = result
            
            if result["status"] == "rotated":
                logger.warning(f"  ✅ Rotated {db_type}")
                logger.warning(f"     Reason: {result['reason']}")
                logger.warning(f"     New DB: {Path(result['new_db_path']).name}")
            elif result["status"] == "error":
                logger.error(f"  ❌ Error rotating {db_type}: {result['error']}")
            else:
                logger.debug(f"  ℹ️  No rotation needed for {db_type}")
        
        return results
    
    # ===== Cleanup & Optimization =====
    
    async def migrate_database_to_sharded_structure(self, db_type: str, source_db_path: str, archive: bool = True) -> Dict[str, any]:
        """
        Migrate an existing large database to sharded structure based on timestamps.
        
        Reads all records from source DB, groups by date/size, creates target DBs, 
        and migrates data. Verifies integrity before archiving.
        
        Args:
            db_type: Type of database ("conversations", "mcp_tool_calls", "ai_memories", etc)
            source_db_path: Path to the existing large database file
            archive: If True, rename original to .archive after successful migration
        
        Returns:
            Dict with migration results:
            {
                "status": "success" | "partial" | "error",
                "db_type": str,
                "source_db": str,
                "records_migrated": int,
                "target_dbs_created": list,
                "verification": {"source_count": int, "migrated_count": int, "match": bool},
                "errors": list,
                "archived": bool
            }
        """
        result = {
            "status": "success",
            "db_type": db_type,
            "source_db": source_db_path,
            "records_migrated": 0,
            "target_dbs_created": [],
            "verification": {"source_count": 0, "migrated_count": 0, "match": False},
            "errors": [],
            "archived": False
        }
        
        try:
            logger.warning(f"🔄 Starting migration of {db_type} from {Path(source_db_path).name}")
            
            # 1. Connect to source DB and get row count
            source_conn = sqlite3.connect(source_db_path)
            source_conn.row_factory = sqlite3.Row  # Get rows as dict-like objects
            source_cursor = source_conn.execute(f"SELECT COUNT(*) FROM {self._get_main_table(db_type)}")
            total_rows = source_cursor.fetchone()[0]
            result["verification"]["source_count"] = total_rows
            logger.info(f"  Found {total_rows} records to migrate")
            
            # 2. Get all records with timestamps (using Row factory for named access)
            timestamp_col = self._get_timestamp_column(db_type)
            source_cursor = source_conn.execute(
                f"SELECT * FROM {self._get_main_table(db_type)} ORDER BY {timestamp_col} ASC"
            )
            records = source_cursor.fetchall()
            source_conn.close()
            
            # 3. Group records by target database
            target_groups = self._group_records_by_target_db(db_type, records, timestamp_col)
            logger.info(f"  Grouped into {len(target_groups)} target databases")
            
            # 4. Create target DBs and migrate data
            for target_db_path, group_records in target_groups.items():
                try:
                    logger.info(f"  Migrating to {Path(target_db_path).name} ({len(group_records)} records)")
                    
                    # Create new DB with schema
                    await self._create_new_db_with_schema(Path(target_db_path), source_db_path, db_type)
                    
                    # Insert records into target DB
                    await self._insert_records_batch(target_db_path, db_type, group_records)
                    
                    result["target_dbs_created"].append(target_db_path)
                    result["records_migrated"] += len(group_records)
                    
                except Exception as e:
                    error_msg = f"Error migrating to {target_db_path}: {e}"
                    logger.error(f"  ❌ {error_msg}")
                    result["errors"].append(error_msg)
                    result["status"] = "partial"
            
            # 5. Verify integrity
            result["verification"]["migrated_count"] = result["records_migrated"]
            result["verification"]["match"] = (result["verification"]["source_count"] == result["records_migrated"])
            
            if result["verification"]["match"]:
                logger.warning(f"  ✅ Verification passed: All {total_rows} records migrated successfully")
            else:
                logger.error(f"  ⚠️  Verification failed: Expected {total_rows}, got {result['records_migrated']}")
                result["status"] = "partial"
            
            # 6. Archive original if verification passed
            # Archives are PERMANENT read-only backups—never deleted, always preserved for Friday's memory
            if archive and result["verification"]["match"]:
                try:
                    import shutil
                    
                    # Create archives folder if it doesn't exist
                    archives_folder = self.memory_data_path / "archives"
                    archives_folder.mkdir(exist_ok=True)
                    
                    # Archive in dedicated folder with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archive_name = f"{Path(source_db_path).stem}_{timestamp}.db.archive"
                    archive_path = archives_folder / archive_name
                    
                    shutil.move(source_db_path, str(archive_path))
                    result["archived"] = True
                    result["archive_path"] = str(archive_path)
                    logger.warning(f"  📦 PERMANENTLY ARCHIVED: {archive_name}")
                    logger.warning(f"     Location: {archives_folder.name}/")
                    logger.warning(f"     ✅ This archive will NEVER be deleted—Friday remembers everything")
                except Exception as e:
                    logger.error(f"  ⚠️  Could not archive original: {e}")
                    result["errors"].append(f"Archive error: {e}")
            
            # Refresh database discovery
            await self.discover_databases()
            
            logger.warning(f"✅ Migration complete for {db_type}")
            
            return result
            
        except Exception as e:
            result["status"] = "error"
            result["errors"].append(str(e))
            logger.error(f"❌ Migration failed for {db_type}: {e}")
            return result
    
    def _get_main_table(self, db_type: str) -> str:
        """Get the main table name for a database type"""
        table_map = {
            "conversations": "messages",
            "ai_memories": "curated_memories",
            "schedule": "reminders",  # or appointments
            "mcp_tool_calls": "tool_calls",
            "vscode_project": "development_conversations"
        }
        return table_map.get(db_type, "data")
    
    def _get_timestamp_column(self, db_type: str) -> str:
        """Get the timestamp column name for a database type"""
        timestamp_map = {
            "conversations": "timestamp",
            "ai_memories": "timestamp_created",
            "schedule": "timestamp_created",
            "mcp_tool_calls": "timestamp",
            "vscode_project": "timestamp"
        }
        return timestamp_map.get(db_type, "timestamp")
    
    def _group_records_by_target_db(self, db_type: str, records: List[Tuple], timestamp_col_idx: int) -> Dict[str, List[Tuple]]:
        """
        Group records into target databases based on timestamps and db_type rules.
        
        For conversations: monthly (2025-11, 2025-12, etc)
        For others: by year-month
        
        Returns:
            Dict mapping target_db_path to list of records
        """
        groups = {}
        
        for record in records:
            try:
                # Records are Row objects (dict-like), so we can access by column name
                try:
                    # Get timestamp by column name (safe access)
                    timestamp_col = self._get_timestamp_column(db_type)
                    timestamp_str = record[timestamp_col]
                    
                    # Handle None/NULL timestamps by using current date
                    if not timestamp_str:
                        from datetime import datetime
                        timestamp_str = datetime.now().isoformat()
                    
                except (KeyError, TypeError):
                    # If timestamp column doesn't exist or record is not dict-like,
                    # fall back to current datetime
                    from datetime import datetime
                    timestamp_str = datetime.now().isoformat()
                    logger.warning(f"Could not extract timestamp for {db_type}, using current date")
                
                # Extract date from ISO format (2025-08-05T01:52:37.366998+00:00)
                date_part = timestamp_str.split("T")[0]  # 2025-08-05
                year_month = date_part[:7]  # 2025-08
                
                if db_type == "conversations":
                    # Monthly files: conversations_YYYY-MM.db
                    target_name = f"conversations_{year_month}.db"
                else:
                    # Date-based: type_YYYYMMDD.db 
                    date_compact = year_month.replace("-", "")  # 202508
                    target_name = f"{db_type}_{date_compact}.db"
                
                target_path = str(self.memory_data_path / target_name)
                
                if target_path not in groups:
                    groups[target_path] = []
                groups[target_path].append(record)
                
            except Exception as e:
                logger.error(f"Error grouping record: {e}")
                continue
        
        return groups
    
    async def _insert_records_batch(self, target_db_path: str, db_type: str, records: List, batch_size: int = 1000):
        """Insert records into target database in batches to avoid memory issues
        
        Records can be Row objects (from source with row_factory) or tuples.
        We convert Row objects to tuples for insertion.
        """
        try:
            conn = sqlite3.connect(target_db_path)
            cursor = conn.cursor()
            
            main_table = self._get_main_table(db_type)
            
            # Convert Row objects to tuples if needed
            record_tuples = []
            for record in records:
                if isinstance(record, sqlite3.Row):
                    # Convert Row to tuple (preserves column order)
                    record_tuples.append(tuple(record))
                else:
                    # Already a tuple
                    record_tuples.append(record)
            
            # Get column count from first record to build INSERT statement
            if not record_tuples:
                logger.warning(f"No records to insert into {target_db_path}")
                conn.close()
                return
            
            num_cols = len(record_tuples[0])
            placeholders = ", ".join(["?" for _ in range(num_cols)])
            
            # Process in batches
            for i in range(0, len(record_tuples), batch_size):
                batch = record_tuples[i:i+batch_size]
                try:
                    cursor.executemany(
                        f"INSERT INTO {main_table} VALUES ({placeholders})",
                        batch
                    )
                    conn.commit()
                except Exception as e:
                    logger.error(f"Error inserting batch: {e}")
                    conn.rollback()
                    raise
            
            conn.close()
            logger.debug(f"Inserted {len(record_tuples)} records into {Path(target_db_path).name}")
            
        except Exception as e:
            logger.error(f"Error inserting records: {e}")
            raise
    
    async def archive_rotate_to_sharded_structure(self) -> Dict[str, Dict]:
        """
        Archive rotation: Move data from main folder to sharded archive structure.
        
        When month changes or file hits 3GB limit:
        1. Read all data from main folder DBs (cache in memory)
        2. Group by date (month) or conversation_id
        3. Create archive files with correct table structure
        4. Migrate data preserving conversation-memory links
        5. Clear/remake original main folder databases with empty schema
        
        For data without timestamps: grouped into pre_timestamp_data file.
        
        Returns:
            Dict mapping db_type to rotation result
        """
        logger.warning("🚀 Starting archive rotation to sharded structure")
        
        results = {}
        archives_folder = self.memory_data_path / "archives"
        archives_folder.mkdir(exist_ok=True)
        
        # Define which databases to rotate and their paths
        db_rotation_map = {
            "conversations": str(self.memory_data_path / "conversations.db"),
            "ai_memories": str(self.memory_data_path / "ai_memories.db"),
            "schedule": str(self.memory_data_path / "schedule.db"),
            "mcp_tool_calls": str(self.memory_data_path / "mcp_tool_calls.db"),
            "vscode_project": str(self.memory_data_path / "vscode_project.db")
        }
        
        for db_type, db_path in db_rotation_map.items():
            if not Path(db_path).exists():
                logger.info(f"  ℹ️  {db_type} database not found, skipping")
                continue
            
            try:
                logger.warning(f"\n📊 Rotating {db_type}...")
                
                # Step 1: Read all data from main folder DB (cache in memory)
                source_conn = sqlite3.connect(db_path)
                source_conn.row_factory = sqlite3.Row
                main_table = self._get_main_table(db_type)
                
                source_cursor = source_conn.execute(f"SELECT * FROM {main_table}")
                all_records = source_cursor.fetchall()
                total_records = len(all_records)
                
                if total_records == 0:
                    logger.info(f"  ℹ️  No records in {db_type}, skipping")
                    source_conn.close()
                    continue
                
                logger.info(f"  Cached {total_records} records from {db_type}")
                
                # Step 2: Group records by date or pre-timestamp
                timestamp_col = self._get_timestamp_column(db_type)
                grouped_records = self._group_records_for_archiving(db_type, all_records, timestamp_col)
                
                logger.info(f"  Grouped into {len(grouped_records)} archive groups")
                
                # Step 3 & 4: Create archive files and migrate data
                migrated_count = 0
                archive_files_created = []
                
                for group_key, group_records in grouped_records.items():
                    try:
                        # Create archive filename based on group key
                        # group_key format: "2025-08" (date) or "pre_timestamp_data" or "conversation_id"
                        archive_filename = f"{db_type}_{group_key}.db"
                        archive_path = archives_folder / archive_filename
                        
                        logger.info(f"    Creating {archive_filename} ({len(group_records)} records)")
                        
                        # Create new archive DB with schema
                        await self._create_new_db_with_schema(archive_path, db_path, db_type)
                        
                        # Insert records, preserving conversation-memory links
                        await self._insert_records_batch(str(archive_path), db_type, group_records)
                        
                        # Safety check: ensure archive has all required tables (especially linking tables)
                        await self._ensure_archive_tables(str(archive_path), db_type)
                        
                        migrated_count += len(group_records)
                        archive_files_created.append(str(archive_path))
                        logger.info(f"    ✓ Migrated to {archive_filename}")
                        
                    except Exception as e:
                        error_msg = f"Error creating archive {group_key}: {e}"
                        logger.error(f"    ❌ {error_msg}")
                        if "errors" not in results[db_type]:
                            results[db_type]["errors"] = []
                        results[db_type]["errors"].append(error_msg)
                
                source_conn.close()
                
                # Step 5: Clear all data from main folder database (keep the file and schema intact)
                logger.info(f"  Clearing main folder database...")
                
                try:
                    # Open the main database and delete all records from all tables
                    main_conn = sqlite3.connect(db_path)
                    main_cursor = main_conn.cursor()
                    
                    # Get all table names (excluding sqlite internal tables)
                    main_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                    tables = main_cursor.fetchall()
                    
                    # Clear all tables
                    for (table_name,) in tables:
                        try:
                            main_cursor.execute(f"DELETE FROM {table_name}")
                            logger.debug(f"    Cleared table: {table_name}")
                        except Exception as e:
                            logger.debug(f"    Could not clear {table_name}: {e}")
                    
                    main_conn.commit()
                    main_conn.close()
                    logger.info(f"    ✓ Cleared all tables in {Path(db_path).name}")
                    
                except Exception as e:
                    error_msg = f"Error clearing main database: {e}"
                    logger.error(f"    ❌ {error_msg}")
                    if "errors" not in results[db_type]:
                        results[db_type]["errors"] = []
                    results[db_type]["errors"].append(error_msg)
                
                # Store results
                results[db_type] = {
                    "status": "success",
                    "db_type": db_type,
                    "records_rotated": migrated_count,
                    "archive_files_created": archive_files_created,
                    "total_records": total_records,
                    "match": migrated_count == total_records,
                    "errors": results.get(db_type, {}).get("errors", [])
                }
                
                if results[db_type]["match"]:
                    logger.warning(f"  ✅ Rotation successful: {migrated_count} records archived")
                else:
                    logger.error(f"  ⚠️  Rotation incomplete: Expected {total_records}, got {migrated_count}")
                    results[db_type]["status"] = "partial"
                
            except Exception as e:
                logger.error(f"❌ Rotation failed for {db_type}: {e}")
                results[db_type] = {
                    "status": "error",
                    "db_type": db_type,
                    "error": str(e),
                    "errors": [str(e)]
                }
        
        logger.warning(f"\n✅ Archive rotation complete")
        return results
    
    def _group_records_for_archiving(self, db_type: str, records: List, timestamp_col: str) -> Dict[str, List]:
        """
        Group records for archiving based on timestamp or conversation_id.
        
        - Records WITH timestamps: grouped by date (YYYY-MM for conversations, YYYYMM for others)
        - Records WITHOUT timestamps: all grouped into "pre_timestamp_data" file
        
        Returns:
            Dict mapping group_key to list of records
        """
        groups = {}
        pre_timestamp_group = []
        
        for record in records:
            try:
                # Try to get timestamp by column name
                timestamp_str = None
                try:
                    timestamp_str = record[timestamp_col]
                except (KeyError, TypeError):
                    pass
                
                # If no timestamp or NULL, put in pre_timestamp_data
                if not timestamp_str:
                    pre_timestamp_group.append(record)
                    continue
                
                # Extract date from ISO format (2025-08-05T01:52:37.366998+00:00)
                try:
                    date_part = timestamp_str.split("T")[0]  # 2025-08-05
                    year_month = date_part[:7]  # 2025-08
                except:
                    pre_timestamp_group.append(record)
                    continue
                
                # Determine group key based on db_type
                if db_type == "conversations":
                    # Monthly files: conversations_YYYY-MM
                    group_key = year_month  # 2025-08
                else:
                    # Date-based: type_YYYYMM
                    group_key = year_month.replace("-", "")  # 202508
                
                if group_key not in groups:
                    groups[group_key] = []
                groups[group_key].append(record)
                
            except Exception as e:
                logger.error(f"Error grouping record for archiving: {e}")
                pre_timestamp_group.append(record)
        
        # Add pre-timestamp data if any exists
        if pre_timestamp_group:
            groups["pre_timestamp_data"] = pre_timestamp_group
            logger.info(f"  Found {len(pre_timestamp_group)} records without timestamps → pre_timestamp_data")
        
        return groups
    
    async def migrate_all_large_databases(self) -> Dict[str, Dict]:
        """
        Migrate ALL large databases to sharded structure.
        
        Returns:
            Dict mapping db_type to migration result
        """
        logger.warning("🚀 Starting full database migration to sharded structure")
        
        results = {}
        
        # Define which databases to migrate and their paths
        db_migration_map = {
            "conversations": str(self.memory_data_path / "conversations.db"),
            "ai_memories": str(self.memory_data_path / "ai_memories.db"),
            "schedule": str(self.memory_data_path / "schedule.db"),
            "mcp_tool_calls": str(self.memory_data_path / "mcp_tool_calls.db"),
            "vscode_project": str(self.memory_data_path / "vscode_project.db")
        }
        
        for db_type, db_path in db_migration_map.items():
            if Path(db_path).exists():
                logger.warning(f"\n📊 Migrating {db_type}...")
                result = await self.migrate_database_to_sharded_structure(db_type, db_path, archive=True)
                results[db_type] = result
            else:
                logger.info(f"  ℹ️  {db_type} database not found, skipping")
        
        return results
    
    async def run_maintenance(self, force: bool = False) -> Dict:
        """Run full database maintenance"""
        logger.info("🧹 Starting database maintenance...")
        
        results = {
            "maintenance_timestamp": datetime.now(timezone.utc).isoformat(),
            "rotation_results": {},
            "cleanup_results": {},
            "optimization_results": {},
            "statistics": {},
            "schema_upgrades": []
        }
        
        try:
            # 0. Check and rotate databases (as a safety net)
            logger.info("🔄 Checking all databases for rotation needs...")
            results["rotation_results"] = await self.check_and_rotate_all_databases()
            
            # 0.5 Archive rotation to sharded structure (month-based grouping)
            logger.info("📦 Performing archive rotation to sharded structure...")
            results["archive_rotation"] = await self.archive_rotate_to_sharded_structure()
            
            # 1. Apply any needed schema upgrades
            logger.info("🔄 Checking and applying schema upgrades...")
            schema_upgrades = await self._upgrade_schemas()
            results["schema_upgrades"] = schema_upgrades
            
            # 2. Clean up old data based on retention policies
            logger.info("📅 Applying retention policies...")
            results["cleanup_results"] = await self._apply_retention_policies(force)
            
            # 3. Remove duplicate entries (shouldn't be many with our new system)
            logger.info("🔍 Removing any remaining duplicates...")
            results["cleanup_results"]["duplicates"] = await self._remove_duplicates()
            
            # 4. Optimize database performance
            logger.info("⚡ Optimizing database performance...")
            results["optimization_results"] = await self._optimize_databases()
            
            # 5. Collect post-cleanup statistics
            logger.info("📊 Collecting statistics...")
            results["statistics"] = await self._collect_statistics()
            
            logger.info("✅ Database maintenance completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Database maintenance failed: {e}")
            results["error"] = str(e)
        
        return results
    
    async def _apply_retention_policies(self, force: bool = False) -> Dict:
        """Apply retention policies to remove old data"""
        cleanup_results = {}
        
        # Clean conversations
        cleanup_results["conversations"] = await self._cleanup_conversations()
        
        # Clean AI memories (more conservative)
        cleanup_results["curated_memories"] = await self._cleanup_ai_memories()
        
        # Clean old schedule items
        cleanup_results["schedule"] = await self._cleanup_schedule()
        
        # Clean old tool call logs
        cleanup_results["mcp_tool_calls"] = await self._cleanup_tool_calls()
        
        # Clean memory-conversation links
        cleanup_results["memory_conversation_links"] = await self._cleanup_memory_links()
        
        # Clean memory processing queue
        cleanup_results["memory_processing_queue"] = await self._cleanup_processing_queue()
        
        # Clean memory processing logs
        cleanup_results["memory_processing_log"] = await self._cleanup_processing_log()
        
        return cleanup_results
    
    async def _cleanup_conversations(self) -> Dict:
        """Clean up old conversation data (disabled - keeping all conversations indefinitely)"""
        policy = self.retention_policies["conversations"]
        
        before_stats = await self._get_conversation_stats()
        
        # All conversations are kept indefinitely - no deletion
        # Only log the count
        
        after_stats = before_stats  # No changes made
        
        return {
            "policy_applied": policy,
            "cutoff_date": "No cutoff (indefinite retention)",
            "conversations_before": before_stats["conversation_count"],
            "conversations_after": after_stats["conversation_count"],
            "conversations_deleted": 0,  # No pruning - keeping all conversations
            "messages_before": before_stats["message_count"],
            "messages_after": after_stats["message_count"],
            "messages_deleted": 0,  # No pruning - keeping all messages
            "note": "All conversations are preserved indefinitely with no pruning"
        }
    
    async def _cleanup_ai_memories(self) -> Dict:
        """Clean up old AI memory data (disabled for long-term storage - no pruning)"""
        policy = self.retention_policies["curated_memories"]
        
        before_count = len(await self.memory_system.ai_memory_db.execute_query(
            "SELECT memory_id FROM curated_memories", ()
        ))
        
        # Long-term storage: No pruning - keep all memories indefinitely
        # Only log the count, don't delete anything
        
        after_count = before_count  # No changes made
        
        return {
            "policy_applied": policy,
            "cutoff_date": "No cutoff (indefinite retention)",
            "memories_before": before_count,
            "memories_after": after_count,
            "memories_deleted": 0,  # No pruning in long-term storage
            "note": "Long-term curated memories are preserved indefinitely with no pruning"
        }
    
    async def _cleanup_schedule(self) -> Dict:
        """Clean up completed and old schedule items"""
        policy = self.retention_policies["schedule"]
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=policy["max_age_days"])
        now = datetime.now(timezone.utc).isoformat()
        
        # Auto-complete overdue reminders (assume they're done) - with 24 hour grace period
        grace_period_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        overdue_completed = await self.memory_system.schedule_db.execute_update(
            "UPDATE reminders SET completed = 1, completed_at = ? WHERE due_datetime < ? AND completed = 0",
            (now, grace_period_cutoff.isoformat())
        )
        
        # Clean old completed appointments
        old_appointments = await self.memory_system.schedule_db.execute_update(
            "DELETE FROM appointments WHERE scheduled_datetime < ?",
            (cutoff_date.isoformat(),)
        )
        
        # Clean old completed reminders
        old_reminders = await self.memory_system.schedule_db.execute_update(
            "DELETE FROM reminders WHERE due_datetime < ? AND completed = 1",
            (cutoff_date.isoformat(),)
        )
        
        return {
            "policy_applied": policy,
            "cutoff_date": cutoff_date.isoformat(),
            "overdue_reminders_auto_completed": overdue_completed,
            "old_appointments_deleted": old_appointments,
            "old_reminders_deleted": old_reminders
        }
    
    async def _cleanup_tool_calls(self) -> Dict:
        """Clean up old tool call logs (disabled - keeping all tool calls indefinitely)"""
        policy = self.retention_policies["mcp_tool_calls"]
        
        before_count = len(await self.memory_system.mcp_db.execute_query(
            "SELECT call_id FROM tool_calls", ()
        ))
        
        # All tool calls are kept indefinitely - no deletion
        # Only log the count
        
        after_count = before_count  # No changes made
        
        return {
            "policy_applied": policy,
            "cutoff_date": "No cutoff (indefinite retention)",
            "tool_calls_before": before_count,
            "tool_calls_after": after_count,
            "tool_calls_deleted": 0,  # No pruning - keeping all tool calls
            "note": "All tool call logs are preserved indefinitely with no pruning"
        }
    
    async def _cleanup_memory_links(self) -> Dict:
        """Clean up memory-conversation links and remove only orphaned entries (disabled time-based deletion)"""
        policy = self.retention_policies["memory_conversation_links"]
        
        before_count = len(await self.memory_system.conversations_db.execute_query(
            "SELECT link_id FROM memory_conversation_links", ()
        ))
        
        # Remove links to non-existent memories or conversations (orphaned links only)
        if policy.get("cleanup_orphaned"):
            orphaned_deleted = await self.memory_system.conversations_db.execute_update(
                """DELETE FROM memory_conversation_links 
                   WHERE memory_id NOT IN (SELECT memory_id FROM curated_memories)
                   OR conversation_id NOT IN (SELECT conversation_id FROM conversations)""",
                ()
            )
        else:
            orphaned_deleted = 0
        
        # No time-based deletion - keep all valid links indefinitely
        old_deleted = 0
        
        after_count = len(await self.memory_system.conversations_db.execute_query(
            "SELECT link_id FROM memory_conversation_links", ()
        ))
        
        return {
            "policy_applied": policy,
            "cutoff_date": "No cutoff (indefinite retention)",
            "links_before": before_count,
            "links_after": after_count,
            "links_deleted": before_count - after_count,
            "orphaned_links_removed": orphaned_deleted,
            "old_links_removed": 0,  # No time-based deletion
            "note": "All valid conversation-memory links are preserved indefinitely"
        }
    
    async def _cleanup_processing_queue(self) -> Dict:
        """Clean up memory processing queue entries"""
        policy = self.retention_policies["memory_processing_queue"]
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=policy["max_age_days"])
        
        before_count = len(await self.memory_system.conversations_db.execute_query(
            "SELECT queue_id FROM memory_processing_queue", ()
        ))
        
        # Remove completed processing records older than cutoff
        if policy.get("cleanup_completed"):
            completed_deleted = await self.memory_system.conversations_db.execute_update(
                """DELETE FROM memory_processing_queue 
                   WHERE processing_status = 'completed' 
                   AND updated_at < ?""",
                (cutoff_date.isoformat(),)
            )
        
        after_count = len(await self.memory_system.conversations_db.execute_query(
            "SELECT queue_id FROM memory_processing_queue", ()
        ))
        
        return {
            "policy_applied": policy,
            "cutoff_date": cutoff_date.isoformat(),
            "queue_entries_before": before_count,
            "queue_entries_after": after_count,
            "queue_entries_deleted": before_count - after_count,
            "completed_entries_removed": completed_deleted if policy.get("cleanup_completed") else 0
        }
    
    async def _cleanup_processing_log(self) -> Dict:
        """Clean up memory processing log entries"""
        policy = self.retention_policies["memory_processing_log"]
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=policy["max_age_days"])
        
        before_count = len(await self.memory_system.conversations_db.execute_query(
            "SELECT log_id FROM memory_processing_log", ()
        ))
        
        # Delete old processing logs
        deleted = await self.memory_system.conversations_db.execute_update(
            "DELETE FROM memory_processing_log WHERE created_at < ?",
            (cutoff_date.isoformat(),)
        )
        
        after_count = len(await self.memory_system.conversations_db.execute_query(
            "SELECT log_id FROM memory_processing_log", ()
        ))
        
        # If we have too many logs, remove the oldest ones
        policy_max_count = policy.get("max_count", 100000)
        if after_count > policy_max_count:
            excess_count = after_count - policy_max_count
            excess_deleted = await self.memory_system.conversations_db.execute_update(
                """DELETE FROM memory_processing_log 
                   WHERE log_id IN (
                       SELECT log_id FROM memory_processing_log 
                       ORDER BY created_at ASC 
                       LIMIT ?
                   )""",
                (excess_count,)
            )
            after_count = policy_max_count
        else:
            excess_deleted = 0
        
        return {
            "policy_applied": policy,
            "cutoff_date": cutoff_date.isoformat(),
            "log_entries_before": before_count,
            "log_entries_after": after_count,
            "old_logs_deleted": deleted,
            "excess_logs_deleted": excess_deleted
        }
    
    async def _remove_duplicates(self) -> Dict:
        """Remove any remaining duplicate entries with strict deduplication"""
        results = {}

        # Deduplicate messages by (content, role, conversation_id), keep entry with earliest timestamp
        dedup_query_messages = '''
            DELETE FROM messages
            WHERE message_id NOT IN (
                SELECT message_id FROM (
                    SELECT message_id
                    FROM messages m1
                    WHERE timestamp = (
                        SELECT MIN(timestamp)
                        FROM messages m2
                        WHERE m2.content = m1.content
                          AND m2.role = m1.role
                          AND m2.conversation_id = m1.conversation_id
                    )
                )
            )
        '''
        duplicate_messages = await self.memory_system.conversations_db.execute_update(dedup_query_messages)
        results["duplicate_messages_removed"] = duplicate_messages

        # Deduplicate curated memories by (content, memory_type, source_conversation_id), keep entry with earliest timestamp_created
        dedup_query_memories = '''
            DELETE FROM curated_memories
            WHERE memory_id NOT IN (
                SELECT memory_id FROM (
                    SELECT memory_id
                    FROM curated_memories m1
                    WHERE timestamp_created = (
                        SELECT MIN(timestamp_created)
                        FROM curated_memories m2
                        WHERE m2.content = m1.content
                          AND m2.memory_type = m1.memory_type
                          AND (m2.source_conversation_id IS m1.source_conversation_id OR (m2.source_conversation_id IS NULL AND m1.source_conversation_id IS NULL))
                    )
                )
            )
        '''
        duplicate_memories = await self.memory_system.ai_memory_db.execute_update(dedup_query_memories)
        results["duplicate_memories_removed"] = duplicate_memories

        # Deduplicate reminders by (content, due_datetime, source_conversation_id), keep entry with earliest timestamp_created
        dedup_query_reminders = '''
            DELETE FROM reminders
            WHERE reminder_id NOT IN (
                SELECT reminder_id FROM (
                    SELECT reminder_id
                    FROM reminders r1
                    WHERE timestamp_created = (
                        SELECT MIN(timestamp_created)
                        FROM reminders r2
                        WHERE r2.content = r1.content
                          AND r2.due_datetime = r1.due_datetime
                          AND (r2.source_conversation_id IS r1.source_conversation_id OR (r2.source_conversation_id IS NULL AND r1.source_conversation_id IS NULL))
                    )
                )
            )
        '''
        duplicate_reminders = await self.memory_system.schedule_db.execute_update(dedup_query_reminders)
        results["duplicate_reminders_removed"] = duplicate_reminders

        # Deduplicate appointments by (title, scheduled_datetime, location, source_conversation_id), keep entry with earliest timestamp_created
        dedup_query_appointments = '''
            DELETE FROM appointments
            WHERE appointment_id NOT IN (
                SELECT appointment_id FROM (
                    SELECT appointment_id
                    FROM appointments a1
                    WHERE timestamp_created = (
                        SELECT MIN(timestamp_created)
                        FROM appointments a2
                        WHERE a2.title = a1.title
                          AND a2.scheduled_datetime = a1.scheduled_datetime
                          AND (a2.location IS a1.location OR (a2.location IS NULL AND a1.location IS NULL))
                          AND (a2.source_conversation_id IS a1.source_conversation_id OR (a2.source_conversation_id IS NULL AND a1.source_conversation_id IS NULL))
                    )
                )
            )
        '''
        duplicate_appointments = await self.memory_system.schedule_db.execute_update(dedup_query_appointments)
        results["duplicate_appointments_removed"] = duplicate_appointments

        return results
    
    async def _upgrade_messages_schema(self) -> List[str]:
        """Upgrade messages table schema if needed"""
        upgrades_applied = []
        
        try:
            # Use raw connection for schema modification
            conn = self.memory_system.conversations_db.get_connection()
            try:
                # First check if we need to modify the source_type column
                cursor = conn.execute("""SELECT sql FROM sqlite_master 
                                      WHERE type='table' AND name='messages'""")
                table_sql = cursor.fetchone()[0]
                
                if 'source_type TEXT NOT NULL' in table_sql:
                    # We need to modify the constraint
                    logger.info("Updating messages table source_type constraint")
                    
                    # Create new table with modified schema
                    conn.execute("""CREATE TABLE messages_new (
                        message_id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        source_type TEXT DEFAULT 'unknown',
                        source_id TEXT,
                        source_url TEXT,
                        source_metadata TEXT,
                        sync_status TEXT,
                        last_sync TEXT,
                        metadata TEXT,
                        embedding BLOB,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
                    )""")
                    
                    # Copy data
                    conn.execute("""INSERT INTO messages_new 
                                  SELECT * FROM messages""")
                    
                    # Drop old table and rename new one
                    conn.execute("DROP TABLE messages")
                    conn.execute("ALTER TABLE messages_new RENAME TO messages")
                    conn.commit()
                    
                    upgrades_applied.append("updated_messages_source_type")
                    logger.info("Successfully updated messages table schema")
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error upgrading messages schema: {e}")
            
        return upgrades_applied

    async def _optimize_databases(self) -> Dict:
        """Optimize database performance"""
        results = {}
        
        # List of database paths to optimize
        db_paths = [
            self.memory_system.conversations_db.db_path,
            self.memory_system.ai_memory_db.db_path,
            self.memory_system.schedule_db.db_path,
            self.memory_system.vscode_db.db_path,
            self.memory_system.mcp_db.db_path
        ]
        
        for db_path in db_paths:
            db_name = Path(db_path).stem
            try:
                # Get database size before optimization
                size_before = Path(db_path).stat().st_size if Path(db_path).exists() else 0
                
                # Optimize database
                conn = sqlite3.connect(db_path)
                conn.execute("VACUUM")  # Reclaim space and defragment
                conn.execute("REINDEX")  # Rebuild indexes for better performance
                conn.execute("ANALYZE")  # Update query planner statistics
                conn.close()
                
                # Get size after optimization
                size_after = Path(db_path).stat().st_size if Path(db_path).exists() else 0
                
                results[db_name] = {
                    "size_before_mb": round(size_before / 1024 / 1024, 2),
                    "size_after_mb": round(size_after / 1024 / 1024, 2),
                    "space_saved_mb": round((size_before - size_after) / 1024 / 1024, 2),
                    "optimized": True
                }
                
            except Exception as e:
                results[db_name] = {"error": str(e), "optimized": False}
        
        return results
    
    async def _upgrade_schemas(self) -> List[str]:
        """Apply any needed schema upgrades"""
        upgrades_applied = []
        
        try:
            # 1. Upgrade development_conversations table
            logger.info("Checking development_conversations schema...")
            conn = self.memory_system.vscode_db.get_connection()
            try:
                # Check if column exists
                cursor = conn.execute("""SELECT COUNT(*) 
                                      FROM pragma_table_info('development_conversations') 
                                      WHERE name='source_metadata'""")
                has_column = cursor.fetchone()[0] > 0
                
                if not has_column:
                    logger.info("Adding source_metadata column to development_conversations table")
                    # Add the column
                    conn.execute("""ALTER TABLE development_conversations 
                                  ADD COLUMN source_metadata TEXT""")
                    conn.commit()
                    upgrades_applied.append("added_source_metadata_column")
                    logger.info("Successfully added source_metadata column")
            finally:
                conn.close()
                
            # 2. Upgrade messages table schema
            logger.info("Checking messages table schema...")
            messages_upgrades = await self._upgrade_messages_schema()
            upgrades_applied.extend(messages_upgrades)
                
        except Exception as e:
            logger.error(f"Error during schema upgrades: {e}")
            
        return upgrades_applied

    async def _get_conversation_stats(self) -> Dict:
        """Get current conversation statistics"""
        conversations = await self.memory_system.conversations_db.execute_query(
            "SELECT COUNT(*) as count FROM conversations", ()
        )
        messages = await self.memory_system.conversations_db.execute_query(
            "SELECT COUNT(*) as count FROM messages", ()
        )
        
        return {
            "conversation_count": conversations[0]["count"],
            "message_count": messages[0]["count"]
        }
    
    async def _collect_statistics(self) -> Dict:
        """Collect database statistics after maintenance"""
        stats = {}
        
        # Get system health for current statistics
        health = await self.memory_system.get_system_health()
        
        for db_name, db_info in health["databases"].items():
            if "count" in str(db_info):
                # Extract counts from the database info
                stats[db_name] = {
                    key: value for key, value in db_info.items() 
                    if "count" in key or "size" in key
                }
        
        return stats


# Integration function to add to PersistentAIMemorySystem
async def run_database_maintenance(memory_system, force: bool = False) -> Dict:
    """Convenience function to run database maintenance"""
    maintenance = DatabaseMaintenance(memory_system)
    return await maintenance.run_maintenance(force)
