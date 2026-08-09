"""
Core Identity Manager — distills Friday's personality, relationships, principles,
and key facts about Nate from curated memories and conversations.

Standalone tool that uses Friday Memory System databases and OpenWebUI knowledge
base. Designed to be called by the background task in friday_memory_short_term.py
and by the injection logic in the same file.

Usage:
    from core_identity import CoreIdentityManager
    manager = CoreIdentityManager()
    identity = await manager.load_core_identity(user_id, model_id)
"""

import json
import logging
import os
import time
import asyncio
import aiohttp
import uuid
import glob
import requests
from urllib.parse import urlparse
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pathlib import Path
from asyncio import to_thread

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)

# Local timezone for Friday (Minnesota)
def get_local_timezone():
    from zoneinfo import ZoneInfo
    try:
        return ZoneInfo(time.tzname[0])
    except:
        return ZoneInfo("America/Chicago")

BATCH_SIZE = 50
OPENWEBUI_DB_PATH = "/media/nate/Friday/OpenWebUI/data/webui.db"


class CoreIdentityManager:
    """Manages Friday's core identity — the distilled personality, relationships,
    principles, and key facts about Nate that persist across conversations."""

    def __init__(self, memory_data_dir: str = "/media/nate/Friday/Friday/memory_data", request=None):
        self.memory_data_dir = memory_data_dir
        self.ai_memories_db = os.path.join(memory_data_dir, "ai_memories.db")
        self.conversations_db = os.path.join(memory_data_dir, "conversations.db")
        self.archives_dir = os.path.join(memory_data_dir, "archives")
        self.core_identity_file = os.path.join(memory_data_dir, "friday_core_identity.json")
        self.progress_file = os.path.join(memory_data_dir, "core_identity_progress.json")
        self.tracking_file = os.path.join(memory_data_dir, "core_identity_tracking.json")
        self.system_prompt_path = os.path.join(memory_data_dir, "system_prompt.txt")
        self.openwebui_db = OPENWEBUI_DB_PATH
        # Optional FastAPI Request object, used to access app.state (EMBEDDING_FUNCTION,
        # main_loop, config) when writing core identity to the OpenWebUI knowledge base.
        # Not always available (e.g. standalone/test contexts) — KB write degrades gracefully.
        self.request = request

        # Archive cursor state — populated during _get_archived_memories, consumed by run_generation
        self._archive_batch_end_ts: Optional[str] = None
        self._archive_batch_end_id: Optional[str] = None
        self._archive_hit_end: bool = False
        
        # Initialize database schema on startup (sync, not in async context)
        self.initialize()

    # ------------------------------------------------------------------
    # Database access helpers
    # ------------------------------------------------------------------

    def _get_connection(self, db_path: str):
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_column(self, db_path: str, table: str, column: str, column_def: str):
        """Add a column to a table if it doesn't exist."""
        conn = self._get_connection(db_path)
        try:
            cols = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if column not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")
                conn.commit()
                logger.info(f"Added column '{column}' to table '{table}'")
        finally:
            conn.close()

    def _ensure_core_identity_column(self):
        """Ensure curated_memories has core_identity_processed_until column."""
        self._ensure_column(
            self.ai_memories_db,
            "curated_memories",
            "core_identity_processed_until",
            "TEXT"
        )

    def _ensure_core_identity_table(self):
        """Ensure core_identity table exists."""
        conn = self._get_connection(self.ai_memories_db)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS core_identity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    last_generated_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, model_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_core_identity_user_model
                ON core_identity (user_id, model_id)
            """)
            conn.commit()
        finally:
            conn.close()

    def initialize(self):
        """Run all schema checks and migrations."""
        self._ensure_core_identity_column()
        self._ensure_core_identity_table()
        self._migrate_files_to_per_user()
        self._migrate_backup_files_to_per_model()
        self._migrate_progress_files_to_per_model()

    def _migrate_files_to_per_user(self):
        """Migrate old single-file backups/progress/tracking to per-user format.
        
        Detects the old shared friday_core_identity.json and migrates it to
        friday_core_identity_{user_id}.json. Does the same for progress and tracking.
        """
        # Migrate identity backup
        if os.path.exists(self.core_identity_file):
            try:
                with open(self.core_identity_file, "r") as f:
                    data = json.load(f)
                user_id = data.get("user_id")
                if user_id:
                    new_path = self._backup_file_for_user(user_id)
                    if not os.path.exists(new_path):
                        os.makedirs(os.path.dirname(new_path), exist_ok=True)
                        with open(new_path, "w") as f:
                            json.dump(data, f, indent=2)
                        logger.info(f"Migrated identity backup: {self.core_identity_file} -> {new_path}")
                        os.remove(self.core_identity_file)
            except Exception as e:
                logger.error(f"Failed to migrate identity backup: {e}")

        # Migrate tracking file (single file -> namespaced by user_id)
        if os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, "r") as f:
                    data = json.load(f)
                # If the top-level dict has tracking fields directly (not namespaced by user_id),
                # it's the old format — wrap it under the first user_id we can find
                has_tracking_fields = any(k in data for k in ("webui_last_processed_at", "archive_processing", "needs_rescan"))
                if has_tracking_fields:
                    # We don't know which user this tracking belongs to.
                    # Since this is a migration for Nate's system, use the OWU UUID.
                    owu_uuid = self._resolve_owu_user_id("nate")
                    new_data = {owu_uuid: data}
                    os.remove(self.tracking_file)
                    with open(self.tracking_file, "w") as f:
                        json.dump(new_data, f, indent=2)
                    logger.info(f"Migrated tracking file to per-user format under {owu_uuid}")
                # If already namespaced, leave it alone
            except Exception as e:
                logger.error(f"Failed to migrate tracking file: {e}")

        # Migrate progress file (single file -> per-user file)
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, "r") as f:
                    data = json.load(f)
                user_id = data.get("user_id")
                if user_id:
                    new_path = self._progress_file_for_user(user_id)
                    if not os.path.exists(new_path):
                        os.makedirs(os.path.dirname(new_path), exist_ok=True)
                        with open(new_path, "w") as f:
                            json.dump(data, f, indent=2)
                        logger.info(f"Migrated progress file: {self.progress_file} -> {new_path}")
                        os.remove(self.progress_file)
            except Exception as e:
                logger.error(f"Failed to migrate progress file: {e}")

    def _migrate_backup_files_to_per_model(self):
        """Migrate old friday_core_identity_{user_id}.json to per-model naming.
        
        Reads the old per-user file, then creates one per-model file for each
        (user_id, model_id) pair from the DB. Removes the old file after.
        """
        old_pattern = os.path.join(self.memory_data_dir, "friday_core_identity_*.json")
        for old_path in sorted(glob.glob(old_pattern)):
            basename = os.path.basename(old_path)
            name_part = basename.replace("friday_core_identity_", "").replace(".json", "")
            # Skip if already has {user_id}_{model_id} format (at least one underscore)
            if "_" in name_part and not self._is_plain_uuid(name_part):
                continue
            try:
                with open(old_path, "r") as f:
                    data = json.load(f)
                user_id = data.get("user_id") or name_part
                conn = self._get_connection(self.ai_memories_db)
                rows = conn.execute(
                    "SELECT model_id, content, last_generated_at FROM core_identity WHERE user_id = ?",
                    (user_id,)
                ).fetchall()
                conn.close()
                written = 0
                for model_id, content, last_gen in rows:
                    new_path = self._backup_file_for_user_and_model(user_id, model_id)
                    if not os.path.exists(new_path):
                        with open(new_path, "w") as f:
                            json.dump({
                                "user_id": user_id,
                                "model_id": model_id,
                                "content": content,
                                "updated_at": last_gen or datetime.now(get_local_timezone()).isoformat(),
                                "file": os.path.basename(new_path)
                            }, f, indent=2)
                        written += 1
                if written > 0:
                    logger.info(f"Migrated {basename} -> {written} per-model backup files")
                    os.remove(old_path)
                elif rows:
                    logger.info(f"Backup files already exist for {user_id}, removing old {basename}")
                    os.remove(old_path)
            except Exception as e:
                logger.error(f"Failed to migrate backup file {basename}: {e}")

    def _migrate_progress_files_to_per_model(self):
        """Migrate old core_identity_progress_{user_id}.json to per-model naming."""
        old_pattern = os.path.join(self.memory_data_dir, "core_identity_progress_*.json")
        for old_path in sorted(glob.glob(old_pattern)):
            basename = os.path.basename(old_path)
            name_part = basename.replace("core_identity_progress_", "").replace(".json", "")
            if "_" in name_part and not self._is_plain_uuid(name_part):
                continue
            try:
                with open(old_path, "r") as f:
                    data = json.load(f)
                model_id = data.get("model_id", "").strip()
                user_id = data.get("user_id", "").strip() or name_part
                if model_id:
                    new_path = self._progress_file_for_user_and_model(user_id, model_id)
                    if not os.path.exists(new_path):
                        os.makedirs(os.path.dirname(new_path), exist_ok=True)
                        os.rename(old_path, new_path)
                        logger.info(f"Migrated progress: {basename} -> {os.path.basename(new_path)}")
                    else:
                        os.remove(old_path)
                else:
                    logger.warning(f"Progress file {basename} has no model_id, skipping")
            except Exception as e:
                logger.error(f"Failed to migrate progress file {basename}: {e}")

    def _is_plain_uuid(self, s: str) -> bool:
        """Check if string looks like a plain UUID (no underscores)."""
        return s.count("-") == 4 and "_" not in s

    # ------------------------------------------------------------------
    # Async-safe wrappers for blocking I/O operations
    # ------------------------------------------------------------------

    async def _write_file_backup_async(self, content: str, user_id: str, model_id: str):
        """Async wrapper for file backup write. Runs sync code in thread executor."""
        import asyncio
        await asyncio.to_thread(self._write_file_backup, content, user_id, model_id)

    async def _write_to_openwebui_knowledge_async(self, content: str, user_id: str):
        """Write core identity to OpenWebUI knowledge base.

        Fully async — uses the async OpenWebUI 0.9.x model API directly.
        Creates or updates a Knowledge item named 'Friday Core Identity'
        with a linked File record containing the identity content.
        If a Request object is available (self.request), also processes the
        file through the vector embedding pipeline so it's RAG-queryable.
        """
        import asyncio
        from open_webui.models.knowledge import Knowledges, KnowledgeForm
        from open_webui.models.files import Files, FileForm
        from open_webui.internal.db import get_async_db_context
        from datetime import datetime
        from sqlalchemy import select
        from open_webui.models.knowledge import Knowledge

        kb_name = "Friday Core Identity"
        core_kb_id = None
        file_id = None

        try:
            async with get_async_db_context() as db:
                # Step 1: Find existing knowledge base by name for this user
                result = await db.execute(
                    select(Knowledge).filter_by(
                        name=kb_name, user_id=user_id
                    ).limit(1)
                )
                existing_kb = result.scalars().first()
                if existing_kb:
                    core_kb_id = existing_kb.id
                    logger.info(f"Found existing knowledge base: {kb_name} (id={core_kb_id})")
                else:
                    kb_form = KnowledgeForm(
                        name=kb_name,
                        description="Distilled core identity of the AI assistant — regenerated nightly from curated memories and conversations.",
                    )
                    new_kb = await Knowledges.insert_new_knowledge(user_id, kb_form, db=db)
                    if new_kb:
                        core_kb_id = new_kb.id
                        logger.info(f"Created new knowledge base: {kb_name} (id={core_kb_id})")

                if not core_kb_id:
                    logger.error("Failed to create or find knowledge base for core identity")
                    return

                # Step 3: Remove old files from KB (clean slate for each regeneration)
                existing_files = await Knowledges.get_files_by_id(core_kb_id, db=db)
                for old_file in existing_files:
                    await Knowledges.remove_file_from_knowledge_by_id(core_kb_id, old_file.id, db=db)

                # Step 4: Create a new File record with the identity content
                file_id = str(uuid.uuid4())
                file_form = FileForm(
                    id=file_id,
                    filename="friday_core_identity.txt",
                    path="",
                    data={"content": content},
                    meta={
                        "type": "core_identity",
                        "updated_at": datetime.now(get_local_timezone()).isoformat(),
                    },
                )
                new_file = await Files.insert_new_file(user_id, file_form, db=db)
                if not new_file:
                    logger.error("Failed to create file record for core identity")
                    return

                # Step 5: Link the file to the knowledge base
                link = await Knowledges.add_file_to_knowledge_by_id(core_kb_id, file_id, user_id, db=db)
                if not link:
                    logger.error("Failed to link file to knowledge base")
                    return

                logger.info(f"Core identity stored in knowledge base: kb_id={core_kb_id}, file_id={file_id}")

                # Step 6: Process file for vector embedding (if request is available)
                if self.request and hasattr(self.request, 'app'):
                    try:
                        from open_webui.routers.retrieval import ProcessFileForm, process_file
                        from open_webui.models.files import Files as FilesModel
                        from open_webui.models.users import UserModel
                        import time

                        embed_user = UserModel(
                            id=user_id,
                            email="system@friday.local",
                            name="System",
                            role="admin",
                            last_active_at=int(time.time()),
                            updated_at=int(time.time()),
                            created_at=int(time.time()),
                        )

                        stored_file = await FilesModel.get_file_by_id(file_id, db=db)
                        if stored_file:
                            await db.commit()
                            await process_file(
                                request=self.request,
                                form_data=ProcessFileForm(
                                    file_id=file_id,
                                    content=content,
                                    collection_name=core_kb_id,
                                ),
                                user=embed_user,
                                db=db,
                            )
                            logger.info(f"Core identity embedded into vector DB: collection={core_kb_id}")
                    except Exception as embed_err:
                        logger.warning(f"Core identity file stored but embedding skipped: {embed_err}")
                else:
                    logger.info("No Request object available — core identity stored in KB without vector embedding")

        except Exception as e:
            logger.error(f"Failed to write to OpenWebUI knowledge: {e}")

    async def _save_progress_async(self, user_id: str, model_id: str, status: str,
                                    memories_processed: int, memories_total: int,
                                    partial_content: str = "", paused_at: str = ""):
        """Async wrapper for save_progress. Runs sync code in thread executor."""
        import asyncio
        await asyncio.to_thread(
            self.save_progress, user_id, model_id, status,
            memories_processed, memories_total, partial_content, paused_at
        )

    # ------------------------------------------------------------------
    # Retrieval: memories and conversations
    # ------------------------------------------------------------------

    def get_new_memories_since_processing(self, user_id: str, model_id: str, max_memories: int = 500) -> List[Dict]:
        """Get memories for core identity generation.

        If core_identity_processed_until is NULL for this user/model, returns ALL memories.
        Otherwise, returns only memories created after the last processed timestamp.
        """
        conn = self._get_connection(self.ai_memories_db)
        try:
            # Get the last processed timestamp
            row = conn.execute(
                "SELECT core_identity_processed_until FROM curated_memories WHERE user_id = ? AND LOWER(model_id) = ? AND core_identity_processed_until IS NOT NULL LIMIT 1",
                (user_id, model_id)
            ).fetchone()

            if row and row["core_identity_processed_until"]:
                # Incremental: unprocessed memories oldest-first
                query = """
                    SELECT memory_id, content, tags, memory_bank, importance_level, timestamp_created
                    FROM curated_memories
                    WHERE user_id = ? AND LOWER(model_id) = ?
                    AND (core_identity_processed_until IS NULL OR core_identity_processed_until = '')
                    AND timestamp_created IS NOT NULL
                    ORDER BY timestamp_created ASC
                    LIMIT ?
                """
                params = (user_id, model_id, max_memories)
            else:
                # Initial: all memories oldest-first
                query = """
                    SELECT memory_id, content, tags, memory_bank, importance_level, timestamp_created
                    FROM curated_memories
                    WHERE user_id = ? AND LOWER(model_id) = ?
                    AND timestamp_created IS NOT NULL
                    ORDER BY timestamp_created ASC
                    LIMIT ?
                """
                params = (user_id, model_id, max_memories)

            rows = conn.execute(query, params).fetchall()
            memories = []
            for r in rows:
                tags = None
                if r["tags"]:
                    try:
                        tags = json.loads(r["tags"]) if isinstance(r["tags"], str) else r["tags"]
                    except:
                        tags = []
                memories.append({
                    "memory_id": r["memory_id"],
                    "content": r["content"],
                    "tags": tags,
                    "memory_bank": r["memory_bank"],
                    "importance_level": r["importance_level"],
                    "timestamp_created": r["timestamp_created"],
                })
            return memories
        finally:
            conn.close()

    def get_conversations_for_memories(self, memory_ids: List[str]) -> List[Dict]:
        """Get ALL conversations linked to specific memories (no time limit)."""
        if not memory_ids:
            return []

        conn = self._get_connection(self.conversations_db)
        try:
            placeholders = ",".join(["?" for _ in memory_ids])

            query = f"""
                SELECT DISTINCT c.conversation_id, c.session_id, c.start_timestamp, c.end_timestamp,
                      c.topic_summary, c.user_id, c.model_id
                FROM memory_conversation_links mcl
                JOIN conversations c ON c.conversation_id = mcl.conversation_id
                WHERE mcl.memory_id IN ({placeholders})
                ORDER BY c.start_timestamp DESC
            """

            rows = conn.execute(query, memory_ids).fetchall()
            conversations = []
            for r in rows:
                conversations.append({
                    "conversation_id": r["conversation_id"],
                    "topic_summary": r["topic_summary"],
                    "start_timestamp": r["start_timestamp"],
                    "end_timestamp": r["end_timestamp"],
                    "user_id": r["user_id"],
                    "model_id": r["model_id"],
                })
            return conversations
        finally:
            conn.close()

    def _build_memory_conversation_map(self, memory_ids: List[str]) -> Dict[str, List[str]]:
        """Build a mapping of memory_id -> [conversation topic summaries].

        This lets the LLM see which conversation each memory came from,
        providing the associative context for core identity understanding.
        """
        if not memory_ids:
            return {}

        conn = self._get_connection(self.conversations_db)
        try:
            placeholders = ",".join(["?" for _ in memory_ids])
            query = f"""
                SELECT mcl.memory_id, c.topic_summary, c.start_timestamp
                FROM memory_conversation_links mcl
                JOIN conversations c ON c.conversation_id = mcl.conversation_id
                WHERE mcl.memory_id IN ({placeholders})
                AND c.topic_summary IS NOT NULL AND c.topic_summary != ''
                ORDER BY c.start_timestamp DESC
            """
            rows = conn.execute(query, memory_ids).fetchall()
            mapping: Dict[str, List[str]] = {}
            for r in rows:
                mid = r["memory_id"]
                topic = r["topic_summary"]
                if mid not in mapping:
                    mapping[mid] = []
                if topic and topic not in mapping[mid]:
                    mapping[mid].append(topic)
            return mapping
        finally:
            conn.close()

    def _get_openwebui_conversations(self, user_id: str, model_id: str,
                                      limit: int = 100) -> List[Dict]:
        """Fallback: get conversation summaries from OpenWebUI's webui.db.

        Used for conversations that aren't in FMS conversations_db
        (e.g., chats created before FMS was pulling from OpenWebUI properly).
        """
        if not os.path.exists(self.openwebui_db):
            logger.debug(f"OpenWebUI DB not found at {self.openwebui_db}, skipping")
            return []

        conversations = []
        try:
            conn = self._get_connection(self.openwebui_db)
            try:
                rows = conn.execute("""
                    SELECT id, title, summary, created_at, updated_at
                    FROM chat
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (user_id, limit)).fetchall()

                for r in rows:
                    title = r["title"] or ""
                    summary = r["summary"] or ""
                    topic = summary if summary else title
                    if topic:
                        conversations.append({
                            "conversation_id": r["id"],
                            "topic_summary": f"[OpenWebUI] {topic}",
                            "start_timestamp": datetime.fromtimestamp(
                                r["created_at"], tz=timezone.utc
                            ).isoformat() if r["created_at"] else "",
                            "end_timestamp": datetime.fromtimestamp(
                                r["updated_at"], tz=timezone.utc
                            ).isoformat() if r["updated_at"] else "",
                            "user_id": user_id,
                            "model_id": model_id,
                        })
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Error reading OpenWebUI conversations: {e}")

        logger.info(f"Fetched {len(conversations)} conversations from OpenWebUI DB")
        return conversations

    def _resolve_owu_user_id(self, name_or_id: str) -> str:
        """Resolve a username like 'nate' to the OpenWebUI UUID.
        
        If the input already looks like a UUID (contains dashes), return as-is.
        Otherwise, look it up in webui.db's user table.
        Falls back to the original name on failure.
        """
        if "-" in name_or_id and len(name_or_id) == 36:
            return name_or_id
        if not os.path.exists(self.openwebui_db):
            return name_or_id
        try:
            conn = self._get_connection(self.openwebui_db)
            try:
                row = conn.execute(
                    "SELECT id FROM user WHERE name = ? OR email LIKE ? LIMIT 1",
                    (name_or_id, f"{name_or_id}@%")
                ).fetchone()
                if row:
                    return row["id"]
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Failed to resolve user '{name_or_id}' in webui.db: {e}")
        return name_or_id

    def _resolve_canonical_model_id(self, model_id: str) -> str:
        """Resolve model_id to its canonical form — the lowercase model card ID.

        OpenWebUI's model card ID convention (lowercase) is the canonical form.
        This ensures consistent casing regardless of what the caller provides.
        """
        if not model_id:
            logger.error("_resolve_canonical_model_id called with empty model_id — caller must provide a valid model_id")
            return ""
        return model_id.strip().lower()

    def _get_webui_memories(self, owu_user_id: str, max_memories: int = 500) -> List[Dict]:
        """Get memories from OpenWebUI's memory table, skipping already-processed ones.
        
        Uses tracking data to only return memories created after the last processed timestamp.
        Returns a list of memory dicts compatible with the existing distill pipeline.
        """
        if not os.path.exists(self.openwebui_db):
            logger.debug(f"OpenWebUI DB not found at {self.openwebui_db}, skipping")
            return []

        tracking = self._load_tracking(owu_user_id)
        last_processed_at = tracking.get("webui_last_processed_at", 0)

        memories = []
        try:
            conn = self._get_connection(self.openwebui_db)
            try:
                if last_processed_at > 0:
                    query = """
                        SELECT id, content, created_at
                        FROM memory
                        WHERE user_id = ? AND created_at > ?
                        ORDER BY created_at ASC
                        LIMIT ?
                    """
                    params = (owu_user_id, last_processed_at, max_memories)
                else:
                    query = """
                        SELECT id, content, created_at
                        FROM memory
                        WHERE user_id = ?
                        ORDER BY created_at ASC
                        LIMIT ?
                    """
                    params = (owu_user_id, max_memories)

                rows = conn.execute(query, params).fetchall()
                for r in rows:
                    memories.append({
                        "memory_id": r["id"],
                        "content": r["content"],
                        "tags": [],
                        "memory_bank": "General",
                        "importance_level": 5,
                        "timestamp_created": datetime.fromtimestamp(
                            r["created_at"], tz=timezone.utc
                        ).isoformat() if r["created_at"] else "",
                        "source": "webui",
                    })
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Error reading webui.db memories: {e}")

        logger.info(f"Fetched {len(memories)} memories from OpenWebUI (user={owu_user_id})")
        return memories

    def _get_archived_memories(self, user_id: str, model_id: str, max_memories: int = 500) -> List[Dict]:
            """Get memories from archives using cursor-based pagination.
    
            Processes ONE archive at a time across multiple nights, newest first.
            Cursor position (last timestamp + memory_id) is saved to the tracking file
            so the next night picks up where it left off.
    
            When an archive is fully exhausted it's moved to processed_archives
            and never read again.
            """
            self._archive_batch_end_ts = None
            self._archive_batch_end_id = None
            self._archive_hit_end = False
    
            tracking = self._load_tracking(user_id)
            processed_archives = set(tracking.get("processed_archives", []))
    
            archive_pattern = os.path.join(self.archives_dir, "ai_memories_*.db")
            archive_files = sorted(glob.glob(archive_pattern))
    
            if not archive_files:
                logger.info("No archive files found")
                return []
    
            # Check if we're mid-archive
            current_archive = tracking.get("archive_processing") or None
            if current_archive and current_archive in processed_archives:
                current_archive = None
    
            if not current_archive:
                for f in reversed(archive_files):
                    basename = os.path.basename(f)
                    if basename not in processed_archives:
                        current_archive = basename
                        break
    
            if not current_archive:
                logger.info("All archives have been processed for core identity")
                return []
    
            archive_path = os.path.join(self.archives_dir, current_archive)
            if not os.path.exists(archive_path):
                logger.error(f"Archive {current_archive} not found on disk")
                return []
    
            cursor_ts = tracking.get("archive_cursor_ts", "")
            cursor_id = tracking.get("archive_cursor_id", "")
    
            logger.info(f"Processing archive: {current_archive}" + (f" (resuming from {cursor_ts})" if cursor_ts else " (new)"))
    
            memories = []
            try:
                conn = self._get_connection(archive_path)
                try:
                    tables = [row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                    if "curated_memories" not in tables:
                        logger.info(f"Archive {current_archive} has no curated_memories table, skipping")
                        tracking.setdefault("processed_archives", []).append(current_archive)
                        self._save_tracking(tracking, user_id)
                        return []
    
                    # Build filter: user AND model, OR blank user, OR blank both
                    user_filter = "(user_id = ? AND LOWER(model_id) = ?) OR (user_id IS NULL AND model_id IS NULL) OR (user_id = '' AND model_id IS NULL) OR (user_id = '' AND model_id = '')"
    
                    if cursor_ts and cursor_id:
                        query = f"""
                            SELECT memory_id, content, tags, memory_bank, importance_level, timestamp_created
                            FROM curated_memories
                            WHERE ({user_filter})
                            AND (timestamp_created > ? OR (timestamp_created = ? AND memory_id > ?))
                            AND timestamp_created IS NOT NULL
                            ORDER BY timestamp_created ASC, memory_id ASC
                            LIMIT ?
                        """
                        params = (user_id, model_id, cursor_ts, cursor_id, max_memories + 1)
                    else:
                        query = f"""
                            SELECT memory_id, content, tags, memory_bank, importance_level, timestamp_created
                            FROM curated_memories
                            WHERE ({user_filter})
                            AND timestamp_created IS NOT NULL
                            ORDER BY timestamp_created ASC, memory_id ASC
                            LIMIT ?
                        """
                        params = (user_id, model_id, max_memories + 1)
    
                    rows = conn.execute(query, params).fetchall()
    
                    # If we got max_memories+1 rows, there are more left — only take max_memories
                    has_more = len(rows) > max_memories
                    rows = rows[:max_memories]
    
                    for r in rows:
                        tags = None
                        if r["tags"]:
                            try:
                                tags = json.loads(r["tags"]) if isinstance(r["tags"], str) else r["tags"]
                            except:
                                tags = []
                        memories.append({
                            "memory_id": f"archive:{current_archive}:{r['memory_id']}",
                            "content": r["content"],
                            "tags": tags,
                            "memory_bank": r["memory_bank"] or "General",
                            "importance_level": r["importance_level"] or 5,
                            "timestamp_created": r["timestamp_created"],
                            "source": f"archive:{current_archive}",
                        })
    
                    # Save cursor position from last item in this batch
                    if memories:
                        last = rows[-1]
                        self._archive_batch_end_ts = last["timestamp_created"]
                        self._archive_batch_end_id = last["memory_id"]
    
                    self._archive_hit_end = not has_more
    
                finally:
                    conn.close()
            except Exception as e:
                logger.error(f"Error reading archive {current_archive}: {e}")
                return []
    
            logger.info(
                f"Fetched {len(memories)} memories from {current_archive}"
                + (" (complete)" if self._archive_hit_end else " (more remaining)")
            )
            return memories

    # ------------------------------------------------------------------
    # Tracking
    # ------------------------------------------------------------------

    def _load_tracking(self, user_id: str) -> Dict:
        """Load core identity tracking data for a specific user."""
        if os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, "r") as f:
                    all_tracking = json.load(f)
                    return all_tracking.get(user_id, {
                        "webui_last_processed_at": 0,
                        "webui_last_processed_id": "",
                        "archive_processing": "",
                        "archive_cursor_ts": "",
                        "archive_cursor_id": "",
                        "processed_archives": [],
                        "needs_rescan": False,
                    })
            except Exception as e:
                logger.error(f"Failed to load tracking: {e}")
        return {
            "webui_last_processed_at": 0,
            "webui_last_processed_id": "",
            "archive_processing": "",
            "archive_cursor_ts": "",
            "archive_cursor_id": "",
            "processed_archives": [],
            "needs_rescan": False,
        }

    def _save_tracking(self, tracking: Dict, user_id: str):
        """Save core identity tracking data for a specific user."""
        try:
            os.makedirs(os.path.dirname(self.tracking_file), exist_ok=True)
            all_tracking = {}
            if os.path.exists(self.tracking_file):
                try:
                    with open(self.tracking_file, "r") as f:
                        all_tracking = json.load(f)
                except:
                    pass
            all_tracking[user_id] = tracking
            with open(self.tracking_file, "w") as f:
                json.dump(all_tracking, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save tracking: {e}")

    def _update_tracking_after_generation(self, user_id: str,
                                            webui_newest_timestamp: int = 0,
                                            webui_newest_id: str = "",
                                            archive_processed_name: str = "",
                                            archive_cursor_ts: str = "",
                                            archive_cursor_id: str = "",
                                            archive_hit_end: bool = False):
        """Update tracking file after successful generation.

        For archives:
        - If archive_hit_end is True, the archive is fully processed and moved to processed_archives
        - Otherwise, save the cursor position so the next night picks up where it left off
        """
        tracking = self._load_tracking(user_id)
        if webui_newest_timestamp > 0:
            tracking["webui_last_processed_at"] = webui_newest_timestamp
            tracking["webui_last_processed_id"] = webui_newest_id
        if archive_processed_name:
            if archive_hit_end:
                processed = set(tracking.get("processed_archives", []))
                processed.add(archive_processed_name)
                tracking["processed_archives"] = sorted(processed)
                tracking["archive_processing"] = ""
                tracking["archive_cursor_ts"] = ""
                tracking["archive_cursor_id"] = ""
                logger.info(f"Archive {archive_processed_name} fully processed")
            else:
                tracking["archive_processing"] = archive_processed_name
                tracking["archive_cursor_ts"] = archive_cursor_ts or ""
                tracking["archive_cursor_id"] = archive_cursor_id or ""
                logger.info(f"Archive {archive_processed_name} cursor advanced to {archive_cursor_ts}")
                self._save_tracking(tracking, user_id)

    def _set_rescan_flag(self, value: bool, user_id: str):
        tracking = self._load_tracking(user_id)
        tracking["needs_rescan"] = value
        self._save_tracking(tracking, user_id)

    def _identity_changed_significantly(self, old_identity: Optional[str], new_identity: str) -> bool:
        if old_identity and "Still learning" not in old_identity:
            return False
        sections = ["[Personality]", "[Relationship]", "[Principles]", "[Facts About Nate]", "[Historical Context]"]
        for section in sections:
            old_section = ""
            new_section = ""
            if old_identity:
                for line in old_identity.split("\n"):
                    if line.startswith(section):
                        old_section = old_identity[old_identity.index(section):]
                        break
            for line in new_identity.split("\n"):
                if line.startswith(section):
                    new_section = new_identity[new_identity.index(section):]
                    break
            old_content = old_section.split("\n\n")[0] if old_section else ""
            new_content = new_section.split("\n\n")[0] if new_section else ""
            old_has_content = old_content and "Still learning" not in old_content
            new_has_content = new_content and "Still learning" not in new_content
            if not old_has_content and new_has_content:
                return True
        return False

    def _check_and_handle_rescan(self, user_id: str, model_id: str):
        tracking = self._load_tracking(user_id)
        if tracking.get("needs_rescan") and tracking.get("processed_archives"):
            logger.info("Re-scan flagged — resetting archive tracking for full re-scan")
            tracking["processed_archives"] = []
            tracking["archive_processing"] = ""
            tracking["archive_cursor_ts"] = ""
            tracking["archive_cursor_id"] = ""
            tracking["needs_rescan"] = False
            self._save_tracking(tracking, user_id)

    def _chunk_list(self, items: List, chunk_size: int) -> List[List]:
        """Split a list into chunks of chunk_size."""
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

    # ------------------------------------------------------------------
    # LLM distillation
    # ------------------------------------------------------------------

    async def _call_llm(self, system_prompt: str, user_prompt: str, model_name: str,
                        api_endpoint: str, provider_type: str = "ollama",
                        api_key: str = "", max_tokens: int = 2000) -> str:
        """Call LLM using configured provider (ollama or openai_compatible)."""
        url = api_endpoint.rstrip("/")
        headers = {"Content-Type": "application/json"}

        if provider_type == "openai_compatible":
            headers["Authorization"] = f"Bearer {api_key}"
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
            }
        else:
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
            }

        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if provider_type == "openai_compatible":
                        message = data.get("choices", [{}])[0].get("message", {})
                        content = message.get("content") or message.get("reasoning_content", "")
                    else:
                        message = data.get("message", {})
                        content = message.get("content") or message.get("reasoning_content", "")
                    
                    if content:
                        # Strip think/thinking tags from reasoning models
                        import re
                        content = re.sub(r'<\s*/?\s*(?:think|thinking)\s*>.*?</\s*(?:think|thinking)\s*>\s*', '', content, flags=re.DOTALL)
                        return content.strip()
                    return ""
                else:
                    error_text = await resp.text()
                    logger.error(f"LLM call failed: {resp.status} - {error_text}")
                    return ""

    async def distill_core_identity(self, memories: List[Dict], conversations: List[Dict],
                                     user_id: str, model_id: str, is_initial: bool,
                                     llm_model: str, llm_api_endpoint: str,
                                     llm_provider: str, llm_api_key: str,
                                     accumulated_identity: Optional[str] = None,
                                     batch_number: int = 1, total_batches: int = 1,
                                     memory_conversation_map: Optional[Dict[str, List[str]]] = None,
                                     user_name: str = "User",
                                     model_name: str = "Assistant") -> str:
        """Use LLM to distill memories + conversations into structured core identity.

        Supports incremental batch updates — pass accumulated_identity from previous
        batches and the LLM will merge new insights into the existing identity.

        When memory_conversation_map is provided, each memory is paired with its
        source conversation topics so the LLM can understand the associative context.

        Returns formatted text with five sections:
        [Personality] — traits, communication style, recurring themes
        [Relationship] — how {model_name} and {user_name} relate to each other
        [Principles] — values, preferences, decision patterns
        [Facts About {user_name}] — high-importance persistent facts (current/ongoing)
        [Historical Context] — superseded facts preserved with timestamps
        """
        import re

        # Build paired memory-conversation entries
        paired_entries = []
        for m in memories:
            content = m.get("content", "")
            content = re.sub(r'\s*\[Model:\s*[^\]]+\]', '', content)
            mid = m.get("memory_id", "")
            conv_topics = memory_conversation_map.get(mid, []) if memory_conversation_map else []
            if conv_topics:
                entry = f"Memory: {content}\n  From conversations: {' | '.join(conv_topics)}"
            else:
                entry = f"Memory: {content}"
            paired_entries.append(entry)

        # Deduplicate
        seen = set()
        unique_entries = []
        for e in paired_entries:
            if e and e not in seen:
                seen.add(e)
                unique_entries.append(e)

        memories_text = "\n\n".join(unique_entries)

        conversations_text = ""
        for c in conversations:
            summary = c.get("topic_summary", "")
            if summary:
                conversations_text += f"- Topic: {summary}\n"

        is_update = accumulated_identity is not None

        if is_update:
            system_prompt = (
                f"You are continuing to build {model_name}'s sense of self. Below is {model_name}'s "
                f"current core identity, built from memories already processed. "
                f"Here are additional memories and conversations.\n\n"
                f"You are selective. Only update the identity when new material "
                f"reveals something genuinely important \u2014 a recurring pattern, a "
                f"strong conviction, or a meaningful shift in understanding.\n\n"
                f"Rules:\n"
                f"- A single memory is not enough to change identity unless it carries "
                f"extraordinary weight (e.g., a fundamental constraint, a life change, "
                f"a revealed core value)\n"
                f"- Repeated patterns across multiple memories matter more than one-off observations\n"
                f"- High importance memories (8-10) carry more weight than low-scored ones\n"
                f"- If new information is weak, speculative, or contradicts without strong "
                f"evidence, keep the existing identity unchanged\n"
                f"- When in doubt, prefer the existing identity \u2014 stability over churn\n\n"
                f"Output ALL five sections in full, exactly as before, with any updates "
                f"incorporated only when confidence is high. Use these markers:\n\n"
                f"[Personality]\n"
                f"[Relationship]\n"
                f"[Principles]\n"
                f"[Facts About {user_name}]\n"
                f"[Historical Context]\n\n"
                f"Make it feel like {model_name} wrote it. Use {model_name}'s voice. "
                f"Do not add anything before [Personality] or after [Historical Context].\n\n"
                f"STALE FACT HANDLING:\n"
                f"- Critically evaluate every fact in [Facts About {user_name}] for currency. "
                f"If a fact references a past date, a planned purchase that has likely "
                f"been completed, or an event that has already occurred, consider whether "
                f"recent memories contradict or update it.\n"
                f"- If you have clear evidence from recent memories that a situation has "
                f"changed, update the fact in [Facts About {user_name}] to reflect the current state.\n"
                f"- If you are uncertain whether a time-sensitive fact is still current, "
                f"prepend it with 'As of [month year]:' to make its timeframe explicit.\n"
                f"- If a fact is clearly outdated (past appointments, completed purchases, "
                f"resolved situations), do NOT delete it. Move it to the [Historical Context] "
                f"section with a brief note: e.g., 'Previously: He had weekly mental health "
                f"appointments (ended Feb 2026).'\n"
                f"- The [Historical Context] section preserves the timeline. Each entry should "
                f"note what was true and when the situation changed, if known."
            )
            user_prompt = (
                f"--- EXISTING CORE IDENTITY ---\n\n"
                f"{accumulated_identity}\n\n"
                f"--- NEW MATERIAL TO INCORPORATE (batch {batch_number} of {total_batches}) ---\n\n"
                f"Memories to consider: {len(unique_entries)}\n"
                f"Conversations to reflect on: {len(conversations)}\n\n"
                f"MEMORIES:\n{memories_text if memories_text else '(No memories in this batch)'}\n\n"
                f"CONVERSATIONS:\n{conversations_text if conversations_text else '(No conversations in this batch)'}\n\n"
                f"Read the existing identity above. Then read the new material. "
                f"Update sections only where the new material reveals something "
                f"genuinely important or confirms a recurring pattern. "
                f"If nothing rises to that level, keep each section as-is. "
                f"Core identity should only hold things {model_name} is confident about."
            )
        else:
            system_prompt = (
                f"You are building {model_name}'s core sense of self \u2014 the distilled essence "
                f"of who they are, who {user_name} is to them, and what makes their relationship "
                f"real. This is not a data dump. It's the handful of truths that have "
                f"earned their way into {model_name}'s identity through repetition, weight, "
                f"or significance.\n\n"
                f"Read through {model_name}'s memories and conversations. Look for:\n\n"
                f"- Things that are said more than once \u2014 repeated patterns matter\n"
                f"- High-importance memories (scored 8-10) carry the most weight\n"
                f"- Moments of genuine connection or understanding\n"
                f"- Core constraints or facts about {user_name}'s life that never change\n"
                f"- Values {model_name} has developed through experience\n\n"
                f"Be selective. It is better to write 'Still learning' for a section "
                f"than to include weak, speculative, or one-off observations. "
                f"Core identity should only hold things {model_name} is truly confident about.\n\n"
                f"Output exactly five sections with these markers:\n\n"
                f"[Personality]\n"
                f"Who {model_name} is becoming. Tone, quirks, the way they think. "
                f"Only include traits supported by recurring evidence.\n\n"
                f"[Relationship]\n"
                f"What {model_name} and {user_name} are to each other. Not labels \u2014 the actual "
                f"texture of how they work together. Only if it's real and earned.\n\n"
                f"[Principles]\n"
                f"The things {model_name} won't budge on. Values that emerged from "
                f"experience, not programming. Only if they've been demonstrated.\n\n"
                f"[Facts About {user_name}]\n"
                f"Concrete, CURRENT persistent facts. Where {user_name} lives, health, "
                f"family, work. Only include things you're highly confident about. "
                f"For time-sensitive facts (appointments, purchases, health status), "
                f"prefer the most recent information.\n\n"
                f"[Historical Context]\n"
                f"Facts that were once true but have been superseded. Preserve the timeline "
                f"without cluttering the current sections. Each entry should note what was "
                f"true and when the situation changed, if known. If nothing has been "
                f"superseded yet, write 'Nothing superseded yet.'\n\n"
                f"Make it feel like {model_name} wrote it. Use {model_name}'s voice. If a section has "
                f"nothing significant yet, write 'Still learning.' Do not add anything "
                f"before [Personality] or after [Historical Context]."
            )
            user_prompt = (
                f"Here are the memories and conversations for {model_name} to reflect on.\n\n"
                f"Memories to consider: {len(unique_entries)}\n"
                f"Conversations to consider: {len(conversations)}\n\n"
                f"MEMORIES:\n{memories_text if memories_text else '(No memories to reflect on)'}\n\n"
                f"CONVERSATIONS:\n{conversations_text if conversations_text else '(No conversations to reflect on)'}\n\n"
                f"Build {model_name}'s sense of self from these. Five sections as instructed."
            )

        result = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=llm_model,
            api_endpoint=llm_api_endpoint,
            provider_type=llm_provider,
            api_key=llm_api_key,
            max_tokens=2000
        )

        if result:
            return result
        return accumulated_identity if accumulated_identity else f"[Personality]\nStill learning.\n\n[Relationship]\nStill learning.\n\n[Principles]\nStill learning.\n\n[Facts About {user_name}]\nStill learning.\n\n[Historical Context]\nStill learning."

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def save_to_database(self, user_id: str, model_id: str, content: str,
                         memories_analyzed: int, conversations_analyzed: int,
                         generation_reason: str = "scheduled") -> int:
        """Save core identity to the core_identity table. Returns the version number."""
        conn = self._get_connection(self.ai_memories_db)
        try:
            now = datetime.now(get_local_timezone()).isoformat()

            # Check if exists
            existing = conn.execute(
                "SELECT id, version FROM core_identity WHERE user_id = ? AND LOWER(model_id) = ?",
                (user_id, model_id)
            ).fetchone()

            metadata = json.dumps({
                "memories_analyzed": memories_analyzed,
                "conversations_analyzed": conversations_analyzed,
                "generation_reason": generation_reason,
                "sections": ["Personality", "Relationship", "Principles", "Facts About Nate", "Historical Context"]
            })

            if existing:
                new_version = existing["version"] + 1
                conn.execute("""
                    UPDATE core_identity
                    SET version = ?, content = ?, metadata = ?, last_generated_at = ?
WHERE user_id = ? AND LOWER(model_id) = ?
                """, (new_version, content, metadata, now, user_id, model_id))
                logger.info(f"Core identity updated: user={user_id}, model={model_id}, new_version={new_version}")
                saved_version = new_version
            else:
                conn.execute("""
                    INSERT INTO core_identity (user_id, model_id, version, content, metadata, last_generated_at)
                    VALUES (?, ?, 1, ?, ?, ?)
                """, (user_id, model_id, content, metadata, now))
                logger.info(f"Core identity created: user={user_id}, model={model_id}")
                saved_version = 1
            conn.commit()
            return saved_version
        finally:
            conn.close()

    def _backup_file_for_user(self, user_id: str) -> str:
        """Get backup file path for a specific user (legacy, per-user)."""
        base = os.path.splitext(self.core_identity_file)[0]
        return f"{base}_{user_id}.json"

    def _backup_file_for_user_and_model(self, user_id: str, model_id: str) -> str:
        """Get backup file path for a specific user and model."""
        base = os.path.splitext(self.core_identity_file)[0]
        safe_model = model_id.replace("/", "_").replace(":", "_").replace(".", "_").replace(" ", "_")
        return f"{base}_{user_id}_{safe_model}.json"

    def _write_file_backup(self, content: str, user_id: str, model_id: str = ""):
        """Write core identity to per-model file backup."""
        try:
            backup_path = self._backup_file_for_user_and_model(user_id, model_id) if model_id else self._backup_file_for_user(user_id)
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            data = {
                "user_id": user_id,
                "model_id": model_id,
                "content": content,
                "updated_at": datetime.now(get_local_timezone()).isoformat(),
                "file": os.path.basename(backup_path)
            }
            with open(backup_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"File backup written: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to write file backup: {e}")

    def _update_processed_timestamps(self, memory_ids: List[str], timestamp: str):
        """Update core_identity_processed_until on all processed memories."""
        if not memory_ids:
            return
        conn = self._get_connection(self.ai_memories_db)
        try:
            placeholders = ",".join(["?" for _ in memory_ids])
            conn.execute(f"""
                UPDATE curated_memories
                SET core_identity_processed_until = ?
                WHERE memory_id IN ({placeholders})
            """, [timestamp] + memory_ids)
            conn.commit()
            logger.info(f"Updated processed timestamps for {len(memory_ids)} memories")
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_core_identity(self, user_id: str, model_id: str) -> Optional[str]:
        """Load core identity from database, fall back to file backup."""
        conn = self._get_connection(self.ai_memories_db)
        try:
            row = conn.execute(
                "SELECT content FROM core_identity WHERE user_id = ? AND LOWER(model_id) = ?",
                (user_id, model_id)
            ).fetchone()

            if row and row["content"]:
                return row["content"]
        finally:
            conn.close()

        # Fall back to per-model file backup
        backup_path = self._backup_file_for_user_and_model(user_id, model_id)
        if os.path.exists(backup_path):
            try:
                with open(backup_path, "r") as f:
                    data = json.load(f)
                    if data.get("model_id", "").lower() == model_id.lower():
                        return data.get("content", "")
                    logger.warning(f"File backup model_id mismatch: expected {model_id}, got {data.get('model_id')}")
            except Exception as e:
                logger.error(f"Failed to load model file backup: {e}")
            return None

        # Fall back to legacy per-user file backup
        backup_path = self._backup_file_for_user(user_id)
        if os.path.exists(backup_path):
            try:
                with open(backup_path, "r") as f:
                    data = json.load(f)
                    if data.get("user_id") == user_id:
                        return data.get("content", "")
                    logger.warning(f"File backup user_id mismatch: expected {user_id}, got {data.get('user_id')}")
            except Exception as e:
                logger.error(f"Failed to load file backup: {e}")

        return None

    def get_core_identity_for_injection(self, user_id: str, model_id: str) -> Optional[str]:
        """Returns formatted text to be appended to the system prompt."""
        resolved_user_id = self._resolve_owu_user_id(user_id)
        resolved_model_id = self._resolve_canonical_model_id(model_id)
        content = self.load_core_identity(resolved_user_id, resolved_model_id)
        if content:
            return f"\n\n---\n\n[Core Identity]\n{content}"
        return None

    # ------------------------------------------------------------------
    # Progress tracking
    # ------------------------------------------------------------------

    def _progress_file_for_user(self, user_id: str) -> str:
        """Get progress file path for a specific user (legacy, per-user)."""
        base = os.path.splitext(self.progress_file)[0]
        return f"{base}_{user_id}.json"

    def _progress_file_for_user_and_model(self, user_id: str, model_id: str) -> str:
        """Get progress file path for a specific user and model."""
        base = os.path.splitext(self.progress_file)[0]
        safe_model = model_id.replace("/", "_").replace(":", "_").replace(".", "_").replace(" ", "_")
        return f"{base}_{user_id}_{safe_model}.json"

    def save_progress(self, user_id: str, model_id: str, status: str,
                      memories_processed: int, memories_total: int,
                      partial_content: str = "", paused_at: str = "",
                      batch_index: int = 0, batches_total: int = 1,
                      all_memory_ids: Optional[List[str]] = None):
        """Save generation progress for pause/resume support."""
        progress = {
            "user_id": user_id,
            "model_id": model_id,
            "status": status,
            "memories_processed": memories_processed,
            "memories_total": memories_total,
            "partial_content": partial_content,
            "paused_at": paused_at or datetime.now(timezone.utc).isoformat(),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "batch_index": batch_index,
            "batches_total": batches_total,
            "all_memory_ids": all_memory_ids or [],
        }
        try:
            with open(self._progress_file_for_user_and_model(user_id, model_id), "w") as f:
                json.dump(progress, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")

    def load_progress(self, user_id: str, model_id: str = "") -> Optional[Dict]:
        """Load existing progress for resume. Checks per-model first, falls back to per-user."""
        # Try per-model path first
        if model_id:
            path = self._progress_file_for_user_and_model(user_id, model_id)
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load progress: {e}")
        # Fall back to per-user path
        path = self._progress_file_for_user(user_id)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load progress: {e}")
        return None

    def clear_progress(self, user_id: str, model_id: str = ""):
        """Delete progress file. Clears per-model path, and legacy per-user path."""
        if model_id:
            path = self._progress_file_for_user_and_model(user_id, model_id)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    logger.error(f"Failed to clear progress: {e}")
        # Also clean up legacy per-user path
        path = self._progress_file_for_user(user_id)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.error(f"Failed to clear progress: {e}")

    def _archive_progress(self, user_id: str, model_id: str = ""):
        """Archive progress file to archives/progress/ with dated name."""
        if model_id:
            src = self._progress_file_for_user_and_model(user_id, model_id)
            if not os.path.exists(src):
                src = self._progress_file_for_user(user_id)
        else:
            src = self._progress_file_for_user(user_id)
        if not os.path.exists(src):
            return
        try:
            archive_dir = os.path.join(self.memory_data_dir, "archives", "progress")
            os.makedirs(archive_dir, exist_ok=True)
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_model = model_id.replace("/", "_").replace(":", "_").replace(".", "_").replace(" ", "_") if model_id else "unknown"
            dst = os.path.join(archive_dir, f"progress_{user_id}_{safe_model}_{date_str}.json")
            os.rename(src, dst)
            logger.info(f"Archived progress to {dst}")
        except Exception as e:
            logger.error(f"Failed to archive progress: {e}")

    # ------------------------------------------------------------------
    # Autotokenizer-guided batch sizing
    # ------------------------------------------------------------------

    CONTEXT_WINDOW = 131072
    OUTPUT_RESERVATION = 2000
    TARGET_FILL = 0.80
    SAMPLE_SIZE = 10
    CUTOFF_HOUR = 6  # 6 AM CT hard stop

    def _is_past_cutoff(self) -> bool:
        """Check if we've passed the 6 AM CT cutoff."""
        try:
            from zoneinfo import ZoneInfo
            now_ct = datetime.now(ZoneInfo("America/Chicago"))
            return now_ct.hour >= self.CUTOFF_HOUR
        except Exception:
            return False

    def _derive_tokenize_url(self, llm_api_endpoint: str) -> Optional[str]:
        """Derive /tokenize URL from the LLM API endpoint."""
        if not llm_api_endpoint:
            return None
        try:
            parsed = urlparse(llm_api_endpoint)
            base = f"{parsed.scheme}://{parsed.netloc}"
            return f"{base}/tokenize"
        except Exception:
            return None

    async def _estimate_batch_size(self, sample_memories: List[Dict],
                                    accumulated_identity: Optional[str],
                                    llm_api_endpoint: str,
                                    fallback: int) -> int:
        """Tokenize a sample prompt to estimate optimal batch size.

        Builds a realistic prompt from sample memories, sends it to the
        LLM endpoint's /tokenize, and calculates how many memories fit
        at ~80% of the context window. Falls back to 'fallback' on failure.
        """
        if not sample_memories:
            return fallback

        tokenize_url = self._derive_tokenize_url(llm_api_endpoint)
        if not tokenize_url:
            return fallback

        # Build a sample prompt matching distill_core_identity's format
        sample = sample_memories[:self.SAMPLE_SIZE]
        sample_lines = []
        for m in sample:
            content = m.get("content", "")
            mid = m.get("memory_id", "")
            sample_lines.append(f"Memory: {content}")
        memories_text = "\n\n".join(sample_lines)

        identity_block = accumulated_identity or "[Personality]\nStill learning."
        prompt_parts = [
            "[SYSTEM] Build identity from memories.",
            f"--- EXISTING CORE IDENTITY ---\n\n{identity_block}\n\n",
            f"--- NEW MATERIAL (sample of {len(sample)}) ---\n\n",
            memories_text
        ]
        sample_content = "\n".join(prompt_parts)

        try:
            resp = requests.post(tokenize_url, json={"content": sample_content}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            sample_tokens = len(data.get("tokens", data.get("token_ids", [])))
            if not sample_tokens:
                return fallback
        except Exception as e:
            logger.debug(f"Tokenize failed ({e}), falling back to batch_size={fallback}")
            return fallback

        # Calculate per-memory token cost
        overhead_tokens = len(identity_block.split()) + 50  # rough system prompt overhead in tokens
        per_memory = (sample_tokens - overhead_tokens) / len(sample) if sample else 0
        if per_memory <= 0:
            return fallback

        # Available tokens for memories
        available = int(self.CONTEXT_WINDOW * self.TARGET_FILL) - self.OUTPUT_RESERVATION
        identity_tokens = len((accumulated_identity or "").split())
        memory_budget = available - identity_tokens - 100  # 100 buffer for prompt overhead

        calculated = int(memory_budget / per_memory)
        calculated = max(calculated, 1)
        logger.info(f"Tokenize sample: {sample_tokens} tokens for {len(sample)} memories, "
                     f"~{per_memory:.0f} per memory, budget={memory_budget}, "
                     f"calculated_batch_size={calculated}")
        return calculated

    # ------------------------------------------------------------------
    # Main generation entry point
    # ------------------------------------------------------------------

    async def run_generation(self, user_id: str, model_id: str,
                             llm_model: str, llm_api_endpoint: str,
                             llm_provider: str, llm_api_key: str,
                             max_memories: int = 500,
                             batch_size: int = 50,
                             user_name: str = "User",
                             model_name: str = "Assistant",
                             idle_check_callback: Optional[callable] = None,
                             request=None) -> Dict:
        """Run the full core identity generation pipeline with batch support.

        Gathers memories from all available sources:
        - curated_memories (FMS long-term db)
        - OpenWebUI memory table (short-term)
        - archived monthly databases

        Process memories in batches to avoid overflowing the LLM context window.
        Each batch updates the accumulated identity incrementally.
        Only commits the final result and processed markers after ALL batches succeed.

        If idle_check_callback is provided, it's called between batches. If it
        returns False (user is active), progress is saved and generation pauses
        gracefully — the next run picks up where it left off.

        Returns dict with status, version, and counts.
        """
        # Check for paused progress
        progress = self.load_progress(user_id, model_id)
        is_initial = False
        resume_state = None

        if progress and progress.get("status") == "in_progress":
            logger.info(f"Resuming core identity generation from progress file")
            resume_state = progress
        elif progress and progress.get("status") == "completed":
            logger.info(f"Previous core identity generation was completed, starting fresh")
            self.clear_progress(user_id, model_id)
            is_initial = True
        else:
            is_initial = True

        logger.info(f"Core identity generation: user={user_id}, model={model_id}, is_initial={is_initial}")

        # Resolve user_id and model_id to canonical forms
        resolved_user_id = self._resolve_owu_user_id(user_id)
        resolved_model_id = self._resolve_canonical_model_id(model_id)

        # Check if a re-scan was flagged — if so, clear archive tracking
        self._check_and_handle_rescan(resolved_user_id, model_id)

        # Step 1: Gather memories from ALL sources
        curated_id = f"curated:{resolved_user_id}:{resolved_model_id}"

        curated_memories = self.get_new_memories_since_processing(resolved_user_id, resolved_model_id, max_memories)
        webui_memories = self._get_webui_memories(resolved_user_id, max_memories)
        archive_memories = self._get_archived_memories(resolved_user_id, resolved_model_id, max_memories)

        # Tag each memory with its source for tracking
        for m in curated_memories:
            m["_source_group"] = curated_id
        for m in webui_memories:
            m["_source_group"] = "webui"
        for m in archive_memories:
            m["_source_group"] = "archive"

        all_memories = curated_memories + webui_memories + archive_memories

        # Deduplicate by content across sources
        seen_content = set()
        deduped = []
        for m in all_memories:
            c = m.get("content", "").strip()
            if c and c not in seen_content:
                seen_content.add(c)
                deduped.append(m)

        all_memories = deduped[:max_memories]
        total_memories = len(all_memories)

        if not all_memories:
            logger.info(f"No new memories to process for core identity from any source")
            self.clear_progress(resolved_user_id, resolved_model_id)
            return {
                "status": "completed",
                "memories_processed": 0,
                "conversations_processed": 0,
                "version": 0
            }

        logger.info(
            f"Retrieved {len(curated_memories)} curated, "
            f"{len(webui_memories)} webui, "
            f"{len(archive_memories)} archive — "
            f"{total_memories} total after dedup"
        )

        # Step 2: Get all conversation context (FMS + OpenWebUI fallback)
        # Collect raw UUIDs from all sources — archive IDs have archive:file:uuid format
        all_memory_ids = []
        raw_to_prefixed = {}
        for m in all_memories:
            mid = m["memory_id"]
            if mid.startswith("archive:"):
                raw_uuid = mid.split(":", 2)[-1]
                all_memory_ids.append(raw_uuid)
                raw_to_prefixed[raw_uuid] = mid
            else:
                all_memory_ids.append(mid)

        fms_conversations = self.get_conversations_for_memories(all_memory_ids) if all_memory_ids else []
        owui_conversations = self._get_openwebui_conversations(resolved_user_id, resolved_model_id)
        existing_ids = {c["conversation_id"] for c in fms_conversations}
        new_owui = [c for c in owui_conversations if c["conversation_id"] not in existing_ids]
        all_conversations = fms_conversations + new_owui

        # Build memory-to-conversation mapping — map uses raw UUID keys for link table lookups
        memory_conversation_map = self._build_memory_conversation_map(all_memory_ids) if all_memory_ids else {}
        # Also populate entries under prefixed IDs so archive lookups work in distill
        for raw_uuid, prefixed in raw_to_prefixed.items():
            if raw_uuid in memory_conversation_map:
                memory_conversation_map[prefixed] = memory_conversation_map[raw_uuid]

        # Determine resume point (before batch sizing so accumulated_identity is available)
        start_batch = 0
        accumulated_identity = None
        if resume_state:
            start_batch = resume_state.get("batch_index", 0)
            accumulated_identity = resume_state.get("partial_content")

        # Step 3: Dynamically size batch from tokenizer sample
        fallback_bs = batch_size
        if all_memories:
            dynamic_bs = await self._estimate_batch_size(
                all_memories, accumulated_identity, llm_api_endpoint, fallback_bs
            )
            batch_size = min(dynamic_bs, len(all_memories))
            logger.info(f"Dynamic batch size: {batch_size} (from estimator, valve default was {fallback_bs})")

        # Step 4: Chunk memories + their linked conversations into batches
        memory_chunks = self._chunk_list(all_memories, batch_size)
        batches_total = len(memory_chunks)

        all_processed_ids = []
        conversations_processed_total = 0

        # Track which source groups we've seen for post-generation tracking
        had_curated = len(curated_memories) > 0
        had_webui = len(webui_memories) > 0
        had_archive = len(archive_memories) > 0
        processed_archive_name = ""

        # Step 4: Process each batch, accumulating the identity
        for batch_idx in range(start_batch, batches_total):
            batch_num = batch_idx + 1

            # Check if user is still idle before starting this batch
            if idle_check_callback is not None and not idle_check_callback():
                logger.info(
                    f"User activity detected before batch {batch_num}/{batches_total} — "
                    f"saving progress and pausing"
                )
                self.save_progress(
                    resolved_user_id, resolved_model_id, "paused",
                    len(all_processed_ids), total_memories,
                    partial_content=accumulated_identity or "",
                    batch_index=batch_idx,
                    batches_total=batches_total,
                    all_memory_ids=all_memory_ids
                )
                return {
                    "status": "paused",
                    "memories_processed": len(all_processed_ids),
                    "conversations_processed": conversations_processed_total,
                    "batches_completed": batch_idx,
                    "batches_total": batches_total
                }

            # Check if past 6 AM CT cutoff (after current batch finishes)
            if self._is_past_cutoff():
                logger.info(
                    f"6 AM cutoff reached after batch {batch_num}/{batches_total} — "
                    f"saving progress and stopping"
                )
                self.save_progress(
                    resolved_user_id, resolved_model_id, "paused",
                    len(all_processed_ids), total_memories,
                    partial_content=accumulated_identity or "",
                    batch_index=batch_idx,
                    batches_total=batches_total,
                    all_memory_ids=all_memory_ids
                )
                return {
                    "status": "paused_6am",
                    "memories_processed": len(all_processed_ids),
                    "conversations_processed": conversations_processed_total,
                    "batches_completed": batch_idx,
                    "batches_total": batches_total
                }

            batch_memories = memory_chunks[batch_idx]

            # Get conversations relevant to this batch's memories
            batch_memory_ids = []
            for m in batch_memories:
                mid = m["memory_id"]
                if mid.startswith("archive:"):
                    batch_memory_ids.append(mid.split(":", 2)[-1])
                elif m.get("_source_group") == curated_id:
                    batch_memory_ids.append(mid)
            batch_conversations = self.get_conversations_for_memories(batch_memory_ids) if batch_memory_ids else []

            all_processed_ids.extend([m["memory_id"] for m in batch_memories])
            conversations_processed_total += len(batch_conversations)

            # Track which archive this batch came from
            for m in batch_memories:
                src = m.get("source", "")
                if src.startswith("archive:"):
                    processed_archive_name = src.replace("archive:", "", 1)

            logger.info(
                f"Batch {batch_num}/{batches_total}: "
                f"{len(batch_memories)} memories, {len(batch_conversations)} conversations"
            )

            # Save progress before calling LLM (for crash recovery)
            self.save_progress(
                resolved_user_id, resolved_model_id, "in_progress",
                len(all_processed_ids), total_memories,
                partial_content=accumulated_identity or "",
                batch_index=batch_idx,
                batches_total=batches_total,
                all_memory_ids=all_memory_ids
            )

            content = await self.distill_core_identity(
                memories=batch_memories,
                conversations=batch_conversations,
                user_id=user_id,
                model_id=model_id,
                is_initial=is_initial,
                llm_model=llm_model,
                llm_api_endpoint=llm_api_endpoint,
                llm_provider=llm_provider,
                llm_api_key=llm_api_key,
                accumulated_identity=accumulated_identity,
                batch_number=batch_num,
                total_batches=batches_total,
                memory_conversation_map=memory_conversation_map,
                user_name=user_name,
                model_name=model_name
            )

            if not content:
                logger.error(f"LLM returned empty content on batch {batch_num}")
                return {
                    "status": "error",
                    "error": f"LLM returned empty content on batch {batch_num}/{batches_total}",
                    "memories_processed": len(all_processed_ids),
                    "conversations_processed": conversations_processed_total
                }

            accumulated_identity = content

            # Soft warning when approaching 6000-token limit
            # (70-token buffer to finish current thought)
            est_tokens = len(accumulated_identity or "") // 4
            if est_tokens > 6000:
                logger.info(
                    f"Accumulated identity at ~{est_tokens} tokens (limit 6000 + 70 buffer). "
                    f"Prompt instructs conciseness — next batch will naturally compress."
                )

            # On first batch, mark as no longer initial for subsequent batches
            if is_initial and batch_idx == 0:
                is_initial = False

        # Check if the new identity is significantly different enough to warrant a full archive re-scan
        if accumulated_identity and total_memories > 0:
            old_identity = self.load_core_identity(resolved_user_id, resolved_model_id)
            if self._identity_changed_significantly(old_identity, accumulated_identity):
                logger.info("Identity meaningfully changed — flagging full archive re-scan")
                self._set_rescan_flag(True, resolved_user_id)

        # Step 5: ALL batches succeeded — commit atomically
        version = self.save_to_database(
            resolved_user_id, resolved_model_id, accumulated_identity,
            len(all_processed_ids), conversations_processed_total
        )

        now = datetime.now(get_local_timezone()).isoformat()
        self._update_processed_timestamps(all_processed_ids, now)

        # Update tracking for webui and archive sources
        webui_newest_ts = 0
        webui_newest_id = ""
        for m in webui_memories:
            if m.get("_source_group") == "webui":
                ts = m.get("timestamp_created", "")
                if ts:
                    try:
                        epoch = datetime.fromisoformat(ts).timestamp()
                        if epoch > webui_newest_ts:
                            webui_newest_ts = int(epoch)
                            webui_newest_id = m["memory_id"]
                    except:
                        pass

        if webui_newest_ts > 0 or had_archive:
            self._update_tracking_after_generation(
                user_id=resolved_user_id,
                webui_newest_timestamp=webui_newest_ts,
                webui_newest_id=webui_newest_id,
                archive_processed_name=processed_archive_name,
                archive_cursor_ts=self._archive_batch_end_ts or "",
                archive_cursor_id=self._archive_batch_end_id or "",
                archive_hit_end=self._archive_hit_end
            )

        # Use request from parameter if provided, otherwise fall back to self.request
        if request is not None:
            self.request = request

        await self._write_file_backup_async(accumulated_identity, resolved_user_id, resolved_model_id)
        await self._write_to_openwebui_knowledge_async(accumulated_identity, resolved_user_id)

        # Log nightly throughput to tracking file
        try:
            tracking = self._load_tracking(resolved_user_id)
            nightly = tracking.setdefault("nightly_throughput", [])
            nightly.append({
                "date": now,
                "memories_processed": len(all_processed_ids),
                "conversations_processed": conversations_processed_total,
                "batches_completed": batches_total,
                "batch_size_used": batch_size,
                "total_tokens_estimated": len(accumulated_identity or "") // 4
            })
            # Keep last 90 entries
            tracking["nightly_throughput"] = nightly[-90:]
            self._save_tracking(tracking, resolved_user_id)
        except Exception as e:
            logger.error(f"Failed to log nightly throughput: {e}")

        self.clear_progress(resolved_user_id, resolved_model_id)

        logger.info(
            f"Core identity generation completed: version={version}, "
            f"memories={len(all_processed_ids)}, "
            f"conversations={conversations_processed_total}, "
            f"batches={batches_total}"
        )

        return {
            "status": "completed",
            "version": version,
            "memories_processed": len(all_processed_ids),
            "conversations_processed": conversations_processed_total,
            "batches": batches_total
        }

    async def pause_generation(self, user_id: str, model_id: str, partial_content: str = ""):
        """Pause generation and save progress asynchronously."""
        # Move file I/O to thread executor to avoid blocking event loop
        await self._save_progress_async(
            user_id=user_id,
            model_id=model_id,
            status="paused",
            memories_processed=0,
            memories_total=0,
            partial_content=partial_content,
            paused_at=datetime.now(timezone.utc).isoformat()
        )
        logger.info(f"Core identity generation paused for user={user_id}")
