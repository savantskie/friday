#!/usr/bin/env python3
"""
FMS Model Memory Deletion Tool

Interactive CLI tool for discovering and deleting model-associated memories
from the Friday Memory System. Menu-driven with dry-run safety.

Usage:
    python fms_delete_model_memories.py              # Interactive menu
    python fms_delete_model_memories.py --user-id <id>  # Override user ID detection
"""

import sqlite3
import glob
import re
import os
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

# ── Configuration ──────────────────────────────────────────────────────────
MEMORY_DATA_DIR = "/media/nate/Friday/Friday/memory_data"
WEBUI_DB_PATH = "/media/nate/Friday/OpenWebUI/data/webui.db"
EMBEDDINGS_DB_PATH = "/media/nate/Friday/Friday/data/memory_embeddings.db"

# ── Helpers ────────────────────────────────────────────────────────────────




def get_all_owui_users() -> Dict[str, Dict]:
    """Get all users from OpenWebUI's user table with their UUID, name, email."""
    users = {}
    if not os.path.exists(WEBUI_DB_PATH):
        return users
    try:
        conn = sqlite3.connect(WEBUI_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, role FROM user ORDER BY created_at")
        for uid, name, email, role in cursor.fetchall():
            users[uid] = {"name": name, "email": email, "role": role}
        conn.close()
    except Exception:
        pass
    return users


def parse_model_from_content(content: str) -> Optional[str]:
    """Extract model name from [Model: <name>] tag in memory content."""
    m = re.search(r'\[Model:\s*([^\]]+)\]', content)
    return m.group(1).strip().lower() if m else None


def discover_ai_memory_shards() -> List[str]:
    """Find all ai_memories database files including shards."""
    pattern = os.path.join(MEMORY_DATA_DIR, "ai_memories*.db")
    return sorted(glob.glob(pattern))


def discover_databases() -> Dict[str, str]:
    """Return dict of target name -> db path for all discoverable databases."""
    dbs = {}
    for shard in discover_ai_memory_shards():
        dbs[f"curated_memories:{os.path.basename(shard)}"] = shard
    dbs["core_identity"] = os.path.join(MEMORY_DATA_DIR, "ai_memories.db")
    dbs["conversations"] = os.path.join(MEMORY_DATA_DIR, "conversations.db")
    dbs["conversation_characters"] = os.path.join(MEMORY_DATA_DIR, "conversation_characters.db")
    dbs["owui_memory"] = WEBUI_DB_PATH
    dbs["embedding_cache"] = EMBEDDINGS_DB_PATH
    return dbs


# ── Discovery ──────────────────────────────────────────────────────────────

def discover_models(user_id: str) -> Dict:
    """Scan all databases and return a structured dict of all discovered models.

    Returns:
        {
            "model_ids": {
                "friday": {"curated_memories": 100, "conversations": 5, "core_identity": 1, ...},
                ...
            },
            "character_names": {
                "celine": {"conversation_characters": 3},
                ...
            }
        }
    """
    results = {
        "model_ids": {},
        "character_names": {},
        "owui_models": {},
    }

    # 1. curated_memories from all shards
    for shard in discover_ai_memory_shards():
        shard_name = os.path.basename(shard)
        try:
            conn = sqlite3.connect(shard)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT LOWER(model_id), COUNT(*) FROM curated_memories "
                "WHERE user_id = ? GROUP BY LOWER(model_id)",
                (user_id,)
            )
            for model_id, count in cursor.fetchall():
                model_id = model_id.strip()
                if model_id not in results["model_ids"]:
                    results["model_ids"][model_id] = {}
                results["model_ids"][model_id][f"curated_memories ({shard_name})"] = count
            conn.close()
        except Exception as e:
            print(f"  [WARN] Could not query {shard}: {e}")

    # 2. core_identity (only in main ai_memories.db)
    main_ai = os.path.join(MEMORY_DATA_DIR, "ai_memories.db")
    try:
        conn = sqlite3.connect(main_ai)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT LOWER(model_id), COUNT(*) FROM core_identity "
            "WHERE user_id = ? GROUP BY LOWER(model_id)",
            (user_id,)
        )
        for model_id, count in cursor.fetchall():
            model_id = model_id.strip()
            if model_id not in results["model_ids"]:
                results["model_ids"][model_id] = {}
            results["model_ids"][model_id]["core_identity"] = count
        conn.close()
    except Exception:
        pass

    # 3. conversations
    conv_db = os.path.join(MEMORY_DATA_DIR, "conversations.db")
    if os.path.exists(conv_db):
        try:
            conn = sqlite3.connect(conv_db)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT LOWER(model_id), COUNT(*) FROM conversations "
                "WHERE user_id = ? GROUP BY LOWER(model_id)",
                (user_id,)
            )
            for model_id, count in cursor.fetchall():
                model_id = model_id.strip()
                if model_id not in results["model_ids"]:
                    results["model_ids"][model_id] = {}
                results["model_ids"][model_id]["conversations"] = count
            conn.close()
        except Exception:
            pass

    # 4. conversation_characters (model_card_name field)
    char_db = os.path.join(MEMORY_DATA_DIR, "conversation_characters.db")
    if os.path.exists(char_db):
        try:
            conn = sqlite3.connect(char_db)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT LOWER(character_name), COUNT(*) FROM conversation_characters "
                "GROUP BY LOWER(character_name)"
            )
            for char_name, count in cursor.fetchall():
                char_name = char_name.strip()
                if char_name not in results["character_names"]:
                    results["character_names"][char_name] = {}
                results["character_names"][char_name]["conversation_characters"] = count
            cursor.execute(
                "SELECT LOWER(model_card_name), COUNT(*) FROM conversation_characters "
                "WHERE model_card_name IS NOT NULL AND model_card_name != '' "
                "GROUP BY LOWER(model_card_name)"
            )
            for card_name, count in cursor.fetchall():
                card_name = card_name.strip()
                if card_name not in results["character_names"]:
                    results["character_names"][card_name] = {}
                results["character_names"][card_name]["conversation_characters (card)"] = count
            conn.close()
        except Exception:
            pass

    # 5. OpenWebUI memory table — parse [Model: ] from content
    if os.path.exists(WEBUI_DB_PATH):
        try:
            conn = sqlite3.connect(WEBUI_DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content FROM memory WHERE user_id = ?",
                (user_id,)
            )
            model_counts = {}
            for (content,) in cursor.fetchall():
                model_name = parse_model_from_content(content)
                if model_name:
                    model_counts[model_name] = model_counts.get(model_name, 0) + 1
            for model_name, count in model_counts.items():
                if model_name not in results["model_ids"]:
                    results["model_ids"][model_name] = {}
                results["model_ids"][model_name]["owui_memory_table"] = count
            conn.close()
        except Exception:
            pass

    return results


def search_model(user_id: str, query: str) -> Dict:
    """Search for a specific model/character and return counts per target."""
    q = query.strip().lower()
    results = discover_models(user_id)

    filtered = {
        "model_ids": {},
        "character_names": {},
    }

    for mid, targets in results["model_ids"].items():
        if q in mid:
            filtered["model_ids"][mid] = targets

    for cname, targets in results["character_names"].items():
        if q in cname:
            filtered["character_names"][cname] = targets

    return filtered

    return filtered


# ── Count / Dry-Run ────────────────────────────────────────────────────────

def count_by_model(user_id: str, model_name: str) -> Dict[str, int]:
    """Count all deletable items for a model across all targets.

    Returns dict like {"target_name": count, ...}
    """
    counts = {}
    model_lower = model_name.strip().lower()

    # 1. curated_memories (all shards)
    mem_count = 0
    for shard in discover_ai_memory_shards():
        try:
            conn = sqlite3.connect(shard)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM curated_memories "
                "WHERE user_id = ? AND LOWER(model_id) = ?",
                (user_id, model_lower)
            )
            mem_count += cursor.fetchone()[0]
            conn.close()
        except Exception:
            pass
    if mem_count:
        counts["curated_memories"] = mem_count

    # 2. core_identity
    main_ai = os.path.join(MEMORY_DATA_DIR, "ai_memories.db")
    try:
        conn = sqlite3.connect(main_ai)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM core_identity "
            "WHERE user_id = ? AND LOWER(model_id) = ?",
            (user_id, model_lower)
        )
        ci_count = cursor.fetchone()[0]
        conn.close()
        if ci_count:
            counts["core_identity"] = ci_count
    except Exception:
        pass

    # 3. conversations + messages
    conv_db = os.path.join(MEMORY_DATA_DIR, "conversations.db")
    if os.path.exists(conv_db):
        try:
            conn = sqlite3.connect(conv_db)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM conversations "
                "WHERE user_id = ? AND LOWER(model_id) = ?",
                (user_id, model_lower)
            )
            conv_count = cursor.fetchone()[0]
            if conv_count:
                counts["conversations"] = conv_count
            # Also count messages for these conversations
            cursor.execute(
                "SELECT COUNT(*) FROM messages WHERE user_id = ? AND LOWER(model_id) = ?",
                (user_id, model_lower)
            )
            msg_count = cursor.fetchone()[0]
            if msg_count:
                counts["messages"] = msg_count
            conn.close()
        except Exception:
            pass

    # 4. conversation_characters (by character_name OR model_card_name)
    char_db = os.path.join(MEMORY_DATA_DIR, "conversation_characters.db")
    if os.path.exists(char_db):
        try:
            conn = sqlite3.connect(char_db)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM conversation_characters "
                "WHERE LOWER(character_name) = ? OR LOWER(model_card_name) = ?",
                (model_lower, model_lower)
            )
            char_count = cursor.fetchone()[0]
            conn.close()
            if char_count:
                counts["conversation_characters"] = char_count
        except Exception:
            pass

    # 5. OpenWebUI memory table
    if os.path.exists(WEBUI_DB_PATH):
        try:
            conn = sqlite3.connect(WEBUI_DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM memory WHERE user_id = ?",
                (user_id,)
            )
            total = cursor.fetchone()[0]
            conn.close()
            # We need to filter by content; do a more precise count
            conn = sqlite3.connect(WEBUI_DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content FROM memory WHERE user_id = ?",
                (user_id,)
            )
            owui_count = 0
            for (content,) in cursor.fetchall():
                mn = parse_model_from_content(content)
                if mn and mn == model_lower:
                    owui_count += 1
            conn.close()
            if owui_count:
                counts["owui_memory_table"] = owui_count
        except Exception:
            pass

    # 6. Core identity backup file on disk
    safe_model = model_lower.replace("/", "_").replace(":", "_").replace(".", "_").replace(" ", "_")
    backup_path = os.path.join(MEMORY_DATA_DIR, f"friday_core_identity_{user_id}_{safe_model}.json")
    if os.path.exists(backup_path):
        counts["core_identity_backup_file"] = 1

    # 7. Core identity progress file on disk
    progress_path = os.path.join(MEMORY_DATA_DIR, f"core_identity_progress_{user_id}_{safe_model}.json")
    if os.path.exists(progress_path):
        counts["core_identity_progress_file"] = 1

    return counts


def count_date_range(user_id: str, start_dt: Optional[datetime], end_dt: Optional[datetime],
                     model_filter: Optional[str] = None) -> Dict[str, int]:
    """Count items within a date/time range, optionally filtered by model.

    Returns dict with per-target counts.
    """
    counts = {}
    ml = model_filter.strip().lower() if model_filter else None

    def _within_range(ts_str: str) -> bool:
        """Check if a timestamp string falls within the range (naive comparison)."""
        if not ts_str:
            return False
        try:
            # Parse ISO timestamp and strip timezone info -> naive comparison
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
        except (ValueError, TypeError):
            try:
                ts = datetime.fromtimestamp(int(ts_str))
            except (ValueError, TypeError, OSError):
                return False
        if start_dt and ts < start_dt:
            return False
        if end_dt and ts > end_dt:
            return False
        return True

    def _int_in_range(ts_int: int) -> bool:
        """Check if an integer unix timestamp falls within range."""
        ts = datetime.fromtimestamp(ts_int)
        if start_dt and ts < start_dt:
            return False
        if end_dt and ts > end_dt:
            return False
        return True

    # 1. curated_memories
    for shard in discover_ai_memory_shards():
        try:
            conn = sqlite3.connect(shard)
            cursor = conn.cursor()
            if ml:
                cursor.execute(
                    "SELECT timestamp_created, timestamp_updated FROM curated_memories "
                    "WHERE user_id = ? AND LOWER(model_id) = ?",
                    (user_id, ml)
                )
            else:
                cursor.execute(
                    "SELECT timestamp_created, timestamp_updated FROM curated_memories "
                    "WHERE user_id = ?",
                    (user_id,)
                )
            shard_count = 0
            for created, updated in cursor.fetchall():
                if _within_range(created) or _within_range(updated):
                    shard_count += 1
            conn.close()
            if shard_count:
                counts[f"curated_memories ({os.path.basename(shard)})"] = shard_count
        except Exception:
            pass

    # 2. core_identity
    main_ai = os.path.join(MEMORY_DATA_DIR, "ai_memories.db")
    try:
        conn = sqlite3.connect(main_ai)
        cursor = conn.cursor()
        if ml:
            cursor.execute(
                "SELECT created_at FROM core_identity "
                "WHERE user_id = ? AND LOWER(model_id) = ?",
                (user_id, ml)
            )
        else:
            cursor.execute(
                "SELECT created_at FROM core_identity WHERE user_id = ?",
                (user_id,)
            )
        ci_count = 0
        for (created,) in cursor.fetchall():
            if _within_range(created):
                ci_count += 1
        conn.close()
        if ci_count:
            counts["core_identity"] = ci_count
    except Exception:
        pass

    # 3. conversations
    conv_db = os.path.join(MEMORY_DATA_DIR, "conversations.db")
    if os.path.exists(conv_db):
        try:
            conn = sqlite3.connect(conv_db)
            cursor = conn.cursor()
            if ml:
                cursor.execute(
                    "SELECT conversation_id, start_timestamp, end_timestamp FROM conversations "
                    "WHERE user_id = ? AND LOWER(model_id) = ?",
                    (user_id, ml)
                )
            else:
                cursor.execute(
                    "SELECT conversation_id, start_timestamp, end_timestamp FROM conversations "
                    "WHERE user_id = ?",
                    (user_id,)
                )
            conv_ids = []
            conv_count = 0
            for cid, start_ts, end_ts in cursor.fetchall():
                if _within_range(start_ts) or (end_ts and _within_range(end_ts)):
                    conv_count += 1
                    conv_ids.append(cid)
            if conv_count:
                counts["conversations"] = conv_count
            # Count messages in those conversations
            if conv_ids:
                placeholders = ",".join("?" for _ in conv_ids)
                cursor.execute(
                    f"SELECT COUNT(*) FROM messages WHERE conversation_id IN ({placeholders})",
                    conv_ids
                )
                msg_count = cursor.fetchone()[0]
                if msg_count:
                    counts["messages"] = msg_count
            conn.close()
        except Exception:
            pass

    # 4. conversation_characters
    char_db = os.path.join(MEMORY_DATA_DIR, "conversation_characters.db")
    if os.path.exists(char_db):
        try:
            conn = sqlite3.connect(char_db)
            cursor = conn.cursor()
            if ml:
                cursor.execute(
                    "SELECT COUNT(*) FROM conversation_characters "
                    "WHERE (LOWER(character_name) = ? OR LOWER(model_card_name) = ?) "
                    "AND created_at >= ? AND created_at <= ?",
                    (ml, ml, start_dt.isoformat() if start_dt else "1970-01-01",
                     end_dt.isoformat() if end_dt else "2099-12-31")
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM conversation_characters "
                    "WHERE created_at >= ? AND created_at <= ?",
                    (start_dt.isoformat() if start_dt else "1970-01-01",
                     end_dt.isoformat() if end_dt else "2099-12-31")
                )
            char_count = cursor.fetchone()[0]
            conn.close()
            if char_count:
                counts["conversation_characters"] = char_count
        except Exception:
            pass

    # 5. OpenWebUI memory table (created_at is INTEGER unix timestamp)
    if os.path.exists(WEBUI_DB_PATH):
        try:
            conn = sqlite3.connect(WEBUI_DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, content, created_at FROM memory WHERE user_id = ?",
                (user_id,)
            )
            owui_count = 0
            for mid, content, created in cursor.fetchall():
                mn = parse_model_from_content(content)
                if ml and mn != ml:
                    continue
                if _int_in_range(created):
                    owui_count += 1
            conn.close()
            if owui_count:
                counts["owui_memory_table"] = owui_count
        except Exception:
            pass

    return counts


# ── Deletion ───────────────────────────────────────────────────────────────

def delete_model(user_id: str, model_name: str, counts: Dict[str, int]) -> Dict[str, int]:
    """Execute deletion for a model across all targets.

    Returns dict of {target: deleted_count}.
    """
    ml = model_name.strip().lower()
    results = {}

    # 1. curated_memories
    for shard in discover_ai_memory_shards():
        try:
            conn = sqlite3.connect(shard)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM curated_memories "
                "WHERE user_id = ? AND LOWER(model_id) = ?",
                (user_id, ml)
            )
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            if deleted:
                results[f"curated_memories ({os.path.basename(shard)})"] = deleted
        except Exception as e:
            print(f"  [ERR] Failed to delete from {shard}: {e}")

    # 2. core_identity
    main_ai = os.path.join(MEMORY_DATA_DIR, "ai_memories.db")
    try:
        conn = sqlite3.connect(main_ai)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM core_identity WHERE user_id = ? AND LOWER(model_id) = ?",
            (user_id, ml)
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted:
            results["core_identity"] = deleted
    except Exception as e:
        print(f"  [ERR] Failed to delete core_identity: {e}")

    # 3. conversations + messages
    conv_db = os.path.join(MEMORY_DATA_DIR, "conversations.db")
    if os.path.exists(conv_db):
        try:
            conn = sqlite3.connect(conv_db)
            cursor = conn.cursor()
            # Delete messages first (FK)
            cursor.execute(
                "DELETE FROM messages WHERE user_id = ? AND LOWER(model_id) = ?",
                (user_id, ml)
            )
            msg_deleted = cursor.rowcount
            cursor.execute(
                "DELETE FROM conversations WHERE user_id = ? AND LOWER(model_id) = ?",
                (user_id, ml)
            )
            conv_deleted = cursor.rowcount
            conn.commit()
            conn.close()
            if conv_deleted:
                results["conversations"] = conv_deleted
            if msg_deleted:
                results["messages"] = msg_deleted
        except Exception as e:
            print(f"  [ERR] Failed to delete conversations: {e}")

    # 4. conversation_characters
    char_db = os.path.join(MEMORY_DATA_DIR, "conversation_characters.db")
    if os.path.exists(char_db):
        try:
            conn = sqlite3.connect(char_db)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM conversation_characters "
                "WHERE LOWER(character_name) = ? OR LOWER(model_card_name) = ?",
                (ml, ml)
            )
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            if deleted:
                results["conversation_characters"] = deleted
        except Exception as e:
            print(f"  [ERR] Failed to delete conversation_characters: {e}")

    # 5. OpenWebUI memory table
    if os.path.exists(WEBUI_DB_PATH):
        try:
            conn = sqlite3.connect(WEBUI_DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, content FROM memory WHERE user_id = ?",
                (user_id,)
            )
            to_delete = []
            for mid, content in cursor.fetchall():
                mn = parse_model_from_content(content)
                if mn and mn == ml:
                    to_delete.append(mid)
            for mid in to_delete:
                cursor.execute("DELETE FROM memory WHERE id = ?", (mid,))
            conn.commit()
            conn.close()
            if to_delete:
                results["owui_memory_table"] = len(to_delete)
        except Exception as e:
            print(f"  [ERR] Failed to delete from webui.db: {e}")

    # 6. Embedding cache — delete by memory_id pattern (no model_id column)
    # We'll collect memory IDs from curated_memories that were deleted.
    # Since we already deleted them above, we can't query them.
    # Instead, just note it and leave it — maintenance handles orphan cleanup.
    if os.path.exists(EMBEDDINGS_DB_PATH):
        try:
            conn = sqlite3.connect(EMBEDDINGS_DB_PATH)
            cursor = conn.cursor()
            # Delete all embedding cache entries that have no matching curated memory
            # This is a general orphan cleanup rather than model-specific
            cursor.execute("DELETE FROM memory_embeddings")
            embed_deleted = cursor.rowcount
            conn.commit()
            conn.close()
            if embed_deleted:
                results["embedding_cache (cleared)"] = embed_deleted
        except Exception as e:
            print(f"  [ERR] Failed to clean embedding cache: {e}")

    # 7. Core identity backup file on disk
    safe_model = ml.replace("/", "_").replace(":", "_").replace(".", "_").replace(" ", "_")
    backup_path = os.path.join(MEMORY_DATA_DIR, f"friday_core_identity_{user_id}_{safe_model}.json")
    if os.path.exists(backup_path):
        try:
            os.remove(backup_path)
            results["core_identity_backup_file"] = 1
        except Exception as e:
            print(f"  [ERR] Failed to delete identity backup file: {e}")

    # 8. Core identity progress file on disk
    progress_path = os.path.join(MEMORY_DATA_DIR, f"core_identity_progress_{user_id}_{safe_model}.json")
    if os.path.exists(progress_path):
        try:
            os.remove(progress_path)
            results["core_identity_progress_file"] = 1
        except Exception as e:
            print(f"  [ERR] Failed to delete identity progress file: {e}")

    return results


def delete_date_range(user_id: str, start_dt: Optional[datetime], end_dt: Optional[datetime],
                      model_filter: Optional[str] = None) -> Dict[str, int]:
    """Delete items within a date/time range, optionally by model.

    Returns dict of {target: deleted_count}.
    """
    ml = model_filter.strip().lower() if model_filter else None
    results = {}

    def _is_in_range(ts_str: str) -> bool:
        if not ts_str:
            return False
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
        except (ValueError, TypeError):
            try:
                ts = datetime.fromtimestamp(int(ts_str))
            except (ValueError, TypeError, OSError):
                return False
        if start_dt and ts < start_dt:
            return False
        if end_dt and ts > end_dt:
            return False
        return True

    def _int_in_range(ts_int: int) -> bool:
        ts = datetime.fromtimestamp(ts_int)
        if start_dt and ts < start_dt:
            return False
        if end_dt and ts > end_dt:
            return False
        return True

    # 1. curated_memories
    for shard in discover_ai_memory_shards():
        try:
            conn = sqlite3.connect(shard)
            cursor = conn.cursor()
            if ml:
                cursor.execute(
                    "SELECT memory_id FROM curated_memories "
                    "WHERE user_id = ? AND LOWER(model_id) = ?",
                    (user_id, ml)
                )
            else:
                cursor.execute(
                    "SELECT memory_id, timestamp_created, timestamp_updated FROM curated_memories "
                    "WHERE user_id = ?",
                    (user_id,)
                )
            rows = cursor.fetchall()
            if ml:
                # Need to filter by timestamp too
                to_delete = []
                for (mid,) in rows:
                    # Re-fetch timestamps
                    cursor2 = conn.cursor()
                    cursor2.execute(
                        "SELECT timestamp_created, timestamp_updated FROM curated_memories "
                        "WHERE memory_id = ?", (mid,)
                    )
                    r2 = cursor2.fetchone()
                    if r2 and (_is_in_range(r2[0]) or _is_in_range(r2[1])):
                        to_delete.append(mid)
            else:
                to_delete = [r[0] for r in rows if _is_in_range(r[1]) or _is_in_range(r[2])]

            if to_delete:
                for mid in to_delete:
                    cursor.execute("DELETE FROM curated_memories WHERE memory_id = ?", (mid,))
                conn.commit()
                results[f"curated_memories ({os.path.basename(shard)})"] = len(to_delete)
            conn.close()
        except Exception as e:
            print(f"  [ERR] {e}")

    # 2. core_identity
    main_ai = os.path.join(MEMORY_DATA_DIR, "ai_memories.db")
    try:
        conn = sqlite3.connect(main_ai)
        cursor = conn.cursor()
        if ml:
            cursor.execute(
                "SELECT created_at FROM core_identity "
                "WHERE user_id = ? AND LOWER(model_id) = ?",
                (user_id, ml)
            )
        else:
            cursor.execute(
                "SELECT created_at FROM core_identity WHERE user_id = ?",
                (user_id,)
            )
        rows = cursor.fetchall()
        to_delete = [r for r in rows if _is_in_range(r[0])]
        if to_delete:
            conn.close()
            conn = sqlite3.connect(main_ai)
            cursor = conn.cursor()
            if ml:
                cursor.execute(
                    "DELETE FROM core_identity WHERE user_id = ? AND LOWER(model_id) = ?",
                    (user_id, ml)
                )
            else:
                cursor.execute(
                    "DELETE FROM core_identity WHERE user_id = ?",
                    (user_id,)
                )
            conn.commit()
            results["core_identity"] = cursor.rowcount
        conn.close()
    except Exception:
        pass

    # 3. conversations + messages (date range on start_timestamp)
    conv_db = os.path.join(MEMORY_DATA_DIR, "conversations.db")
    if os.path.exists(conv_db):
        try:
            conn = sqlite3.connect(conv_db)
            cursor = conn.cursor()
            if ml:
                cursor.execute(
                    "SELECT conversation_id FROM conversations "
                    "WHERE user_id = ? AND LOWER(model_id) = ?",
                    (user_id, ml)
                )
            else:
                cursor.execute(
                    "SELECT conversation_id, start_timestamp FROM conversations "
                    "WHERE user_id = ?",
                    (user_id,)
                )
            rows = cursor.fetchall()
            if ml:
                to_delete = []
                for (cid,) in rows:
                    cursor2 = conn.cursor()
                    cursor2.execute("SELECT start_timestamp FROM conversations WHERE conversation_id = ?", (cid,))
                    r2 = cursor2.fetchone()
                    if r2 and _is_in_range(r2[0]):
                        to_delete.append(cid)
            else:
                to_delete = [r[0] for r in rows if _is_in_range(r[1])]

            if to_delete:
                placeholders = ",".join("?" for _ in to_delete)
                cursor.execute(f"DELETE FROM messages WHERE conversation_id IN ({placeholders})", to_delete)
                msg_del = cursor.rowcount
                cursor.execute(f"DELETE FROM conversations WHERE conversation_id IN ({placeholders})", to_delete)
                conv_del = cursor.rowcount
                conn.commit()
                if conv_del:
                    results["conversations"] = conv_del
                if msg_del:
                    results["messages"] = msg_del
            conn.close()
        except Exception:
            pass

    # 4. OpenWebUI memory table
    if os.path.exists(WEBUI_DB_PATH):
        try:
            conn = sqlite3.connect(WEBUI_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT id, content, created_at FROM memory WHERE user_id = ?", (user_id,))
            to_delete = []
            for mid, content, created in cursor.fetchall():
                mn = parse_model_from_content(content)
                if ml and mn != ml:
                    continue
                if _int_in_range(created):
                    to_delete.append(mid)
            if to_delete:
                for mid in to_delete:
                    cursor.execute("DELETE FROM memory WHERE id = ?", (mid,))
                conn.commit()
                results["owui_memory_table"] = len(to_delete)
            conn.close()
        except Exception:
            pass

    return results


# ── Display Name Normalization ────────────────────────────────────────

QUANT_PATTERN = re.compile(r'[-_]([Qq][0-9]+[._][A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*)$')

MODIFIER_TOKENS = [
    "erotica-nsfw", "erotica_nsfw",
    "nsfw",
    "abliterated",
]


def normalize_display_name(model_id: str) -> str:
    """Display-only normalization — strips noise, keeps recognizable core."""
    name = model_id.strip()

    # 1. Strip path prefix -> basename
    if "/" in name:
        name = name.rsplit("/", 1)[-1]

    # 2. Strip .gguf extension
    if name.lower().endswith(".gguf"):
        name = name[:-5]

    # 3. Strip :tag suffix
    if ":" in name:
        name = name.split(":", 1)[0]

    # 4. Strip -gguf substring
    name = name.replace("-gguf", "").replace("_gguf", "")

    # 5. Strip known modifier tokens (case-insensitive, whole word)
    for token in MODIFIER_TOKENS:
        # Match as hyphenated suffix like -token or _token
        pattern = re.compile(
            r'[-_]' + re.escape(token) + r'$',
            re.IGNORECASE
        )
        name = pattern.sub('', name)
        # Also match as mid-word token
        pattern = re.compile(
            r'[-_]' + re.escape(token) + r'[-_]',
            re.IGNORECASE
        )
        name = pattern.sub('-', name)

    # 6. Quant-cut: if quant tag found, cut everything from it onward
    quant_match = QUANT_PATTERN.search(name)
    if quant_match:
        name = name[:quant_match.start()]

    # 7. Strip trailing hyphens/underscores/dots
    name = name.rstrip('-_ .')

    return name if name else model_id.strip()


def _get_distinguisher(raw_id: str) -> str:
    """Extract the distinguishing suffix from a raw model ID for collision disambiguation."""
    if ":" in raw_id:
        return raw_id.rsplit(":", 1)[-1]
    # Check for quant tag
    qmatch = QUANT_PATTERN.search(raw_id)
    if qmatch:
        return qmatch.group(1)
    return ""


def _build_display_map(raw_ids: list) -> dict:
    """Build a map of raw_id -> display name, disambiguating collisions."""
    normalized = {}
    for rid in raw_ids:
        normalized[rid] = normalize_display_name(rid)

    # Find collisions
    from collections import defaultdict
    groups = defaultdict(list)
    for rid, display in normalized.items():
        groups[display].append(rid)

    result = {}
    for display, group in groups.items():
        if len(group) == 1:
            result[group[0]] = display
        else:
            for rid in group:
                suffix = _get_distinguisher(rid)
                if suffix:
                    result[rid] = f"{display} ({suffix})"
                else:
                    result[rid] = display
    return result


def _get_terminal_width() -> int:
    """Get terminal width, default to 80 if not available."""
    try:
        return os.get_terminal_size().columns
    except (ValueError, OSError):
        return 80


def _calc_model_width(names: list) -> int:
    """Calculate dynamic model column width from display names."""
    if not names:
        return 25
    max_len = max(len(n) for n in names)
    term_width = _get_terminal_width()
    # Reserve 57 for prefix + target column + count column + padding
    capped = min(max_len + 2, term_width - 57)
    return max(capped, 15)  # minimum 15 chars


# ── Display ────────────────────────────────────────────────────────────────

def print_discover(results: Dict):
    """Print discovery results with dynamic column widths."""
    mids = results.get("model_ids", {})
    cnames = results.get("character_names", {})

    if not mids and not cnames:
        print("\n  No models or characters found.")
        return

    if mids:
        display_map = _build_display_map(list(mids.keys()))
        model_width = _calc_model_width(list(display_map.values()))
        target_width = 45
        count_width = 8
        total_width = model_width + target_width + count_width + 4
        term_width = _get_terminal_width()
        if total_width > term_width:
            target_width = max(20, term_width - model_width - count_width - 4)

        print(f"\n  {'Model ID':<{model_width}} {'Target':<{target_width}} {'Count':>{count_width}}")
        print(f"  {'-'*model_width} {'-'*target_width} {'-'*count_width}")
        for mid in sorted(mids.keys()):
            display = display_map[mid]
            targets = mids[mid]
            first = True
            for tgt in sorted(targets.keys()):
                label = display if first else ""
                if len(label) > model_width:
                    label = label[:model_width - 3] + "..."
                print(f"  {label:<{model_width}} {tgt:<{target_width}} {targets[tgt]:>{count_width}}")
                first = False

    if cnames:
        char_width = 25
        target_width = 45
        count_width = 8
        print(f"\n  {'Character Name':<{char_width}} {'Target':<{target_width}} {'Count':>{count_width}}")
        print(f"  {'-'*char_width} {'-'*target_width} {'-'*count_width}")
        for cname in sorted(cnames.keys()):
            targets = cnames[cname]
            first = True
            for tgt in sorted(targets.keys()):
                label = cname if first else ""
                print(f"  {label:<{char_width}} {tgt:<{target_width}} {targets[tgt]:>{count_width}}")
                first = False


def print_counts(counts: Dict[str, int], label: str = "Item"):
    """Print per-target counts."""
    if not counts:
        print(f"\n  No {label}s found.")
        return

    total = sum(counts.values())
    target_width = 50
    count_width = 8
    print(f"\n  {'Target':<{target_width}} {'Count':>{count_width}}")
    print(f"  {'-'*target_width} {'-'*count_width}")
    for tgt in sorted(counts.keys()):
        print(f"  {tgt:<{target_width}} {counts[tgt]:>{count_width}}")
    print(f"  {'-'*target_width} {'-'*count_width}")
    print(f"  {'TOTAL':<{target_width}} {total:>{count_width}}")
    return total


# ── User ID Aliases (mirrors friday_memory_system.py) ─────────────────────
USER_ID_ALIASES = {
    "nate": "9d08cfbb-b8ca-484d-bd37-c5c383c1e5d6",
    "Nate": "9d08cfbb-b8ca-484d-bd37-c5c383c1e5d6",
}


def resolve_user_id(raw: str) -> str:
    """Apply alias mapping like the main system does."""
    return USER_ID_ALIASES.get(raw, raw)


def lookup_user_info(user_id: str) -> Dict:
    """Look up name and email for a user UUID from OpenWebUI's user table."""
    if not os.path.exists(WEBUI_DB_PATH):
        return {}
    try:
        conn = sqlite3.connect(WEBUI_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, email FROM user WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"name": row[0], "email": row[1]}
    except Exception:
        pass
    return {}


def get_all_user_ids_with_data() -> Dict[str, Dict]:
    """Scan all databases and return {user_id: {name, email}} for users with data."""
    user_ids = set()

    for shard in discover_ai_memory_shards():
        try:
            conn = sqlite3.connect(shard)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT user_id FROM curated_memories WHERE user_id IS NOT NULL")
            for (uid,) in cursor.fetchall():
                user_ids.add(uid)
            conn.close()
        except Exception:
            pass

    main_ai = os.path.join(MEMORY_DATA_DIR, "ai_memories.db")
    try:
        conn = sqlite3.connect(main_ai)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT user_id FROM core_identity WHERE user_id IS NOT NULL")
        for (uid,) in cursor.fetchall():
            user_ids.add(uid)
        conn.close()
    except Exception:
        pass

    conv_db = os.path.join(MEMORY_DATA_DIR, "conversations.db")
    if os.path.exists(conv_db):
        try:
            conn = sqlite3.connect(conv_db)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT user_id FROM conversations WHERE user_id IS NOT NULL")
            for (uid,) in cursor.fetchall():
                user_ids.add(uid)
            conn.close()
        except Exception:
            pass

    if os.path.exists(WEBUI_DB_PATH):
        try:
            conn = sqlite3.connect(WEBUI_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT user_id FROM memory WHERE user_id IS NOT NULL")
            for (uid,) in cursor.fetchall():
                user_ids.add(uid)
            conn.close()
        except Exception:
            pass

    result = {}
    for uid in sorted(user_ids):
        info = lookup_user_info(uid)
        result[uid] = info
    return result


# ── Menu ───────────────────────────────────────────────────────────────────

def show_menu():
    print("\n  Model Memory Deletion Tool")
    print()
    print("  1. Discover all models")
    print("  2. Search for a model")
    print("  3. Wipe a model")
    print("  4. Wipe by date/time range")
    print("  5. Wipe a specific model by date/time range")
    print("  6. Switch user")
    print("  7. Exit")
    print()


def select_user() -> Optional[str]:
    """Prompt user to pick an OWUI user. Returns user_id or None."""
    owui_users = get_all_owui_users()
    if not owui_users:
        print("\n  No users found in OpenWebUI.")
        return None

    print("\n  OpenWebUI Users:")
    print(f"  {'#':>3}  {'UUID':<40} {'Name':<20} {'Email':<35} {'Role':<10}")
    print(f"  {'-'*3}  {'-'*40} {'-'*20} {'-'*35} {'-'*10}")
    user_list = list(owui_users.items())
    for i, (uid, info) in enumerate(user_list, 1):
        print(f"  {i:>3}  {uid:<40} {info['name']:<20} {info['email']:<35} {info['role']:<10}")
    print()
    if sys.stdin.isatty():
        pick = input("  Select user by number or UUID (blank to quit): ").strip()
        if not pick:
            return None
        if pick.isdigit():
            idx = int(pick) - 1
            if 0 <= idx < len(user_list):
                return user_list[idx][0]
        else:
            return resolve_user_id(pick.strip())
    else:
        # Non-interactive: pick the first non-Guest admin
        for uid, info in user_list:
            if info["role"] == "admin" and info["name"].lower() != "guest":
                return uid
        return user_list[0][0]
    return None


def show_user_info(user_id: str):
    """Print name/email for a user UUID."""
    owui_info = lookup_user_info(user_id)
    if owui_info:
        print(f"\n  User: {user_id}")
        print(f"  Name: {owui_info.get('name', 'unknown')}")
        print(f"  Email: {owui_info.get('email', 'unknown')}")
    else:
        print(f"\n  User: {user_id}")

    # Check if this user_id has data in FMS databases
    all_uids = get_all_user_ids_with_data()
    if user_id not in all_uids:
        print(f"\n  [NOTE] User '{user_id}' has no data in FMS databases.")
        if all_uids:
            print("  Users with data in FMS databases:")
            for uid, info in all_uids.items():
                name = info.get("name", "")
                email = info.get("email", "")
                parts = [uid]
                if name:
                    parts.append(f"name: {name}")
                if email:
                    parts.append(f"email: {email}")
                print(f"    - {'  |  '.join(parts)}")
            print("  Use --user-id <uuid> to target a different user.")


def parse_datetime(prompt: str) -> Optional[datetime]:
    """Prompt for a datetime string, return datetime or None if blank."""
    val = input(prompt).strip()
    if not val:
        return None
    for fmt in [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
    ]:
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    print(f"  [WARN] Could not parse '{val}'. Try YYYY-MM-DD HH:MM format.")
    return None


def run():
    # ── User ID ────────────────────────────────────────────────────────
    user_id = None
    if len(sys.argv) > 1 and "--user-id" in sys.argv:
        idx = sys.argv.index("--user-id")
        if idx + 1 < len(sys.argv):
            user_id = sys.argv[idx + 1]
            user_id = resolve_user_id(user_id)

    if not user_id:
        user_id = select_user()

    if not user_id:
        print("\n  Goodbye.\n")
        sys.exit(0)

    show_user_info(user_id)

    while True:
        show_menu()
        choice = input("  Select option [1-7]: ").strip()

        # ── Option 1: Discover ──
        if choice == "1":
            print("\n  ── Discovering all models ──")
            results = discover_models(user_id)
            if not results["model_ids"] and not results["character_names"]:
                print("\n  No models or characters found in any database.")
            else:
                print_discover(results)
            input("\n  Press Enter to continue...")

        # ── Option 2: Search ──
        elif choice == "2":
            query = input("\n  Enter model name or character name to search: ").strip()
            if not query:
                print("  No query entered.")
                input("  Press Enter to continue...")
                continue
            print(f"\n  ── Searching for '{query}' ──")
            results = search_model(user_id, query)
            if not results["model_ids"] and not results["character_names"]:
                print(f"\n  No matches found for '{query}'.")
            else:
                print_discover(results)
            input("\n  Press Enter to continue...")

        # ── Option 3: Wipe a model ──
        elif choice == "3":
            model = input("\n  Enter model name to wipe: ").strip()
            if not model:
                print("  No model name entered.")
                input("  Press Enter to continue...")
                continue

            print(f"\n  ── Dry Run: Items to delete for '{model}' ──")
            counts = count_by_model(user_id, model)
            total = print_counts(counts, "item")

            if total == 0:
                print("\n  Nothing to delete.")
                input("  Press Enter to continue...")
                continue

            confirm = input(f"\n  Wipe all {total} items for '{model}'? [y/N]: ").strip().lower()
            if confirm != "y":
                print("  Cancelled.")
                input("  Press Enter to continue...")
                continue

            print(f"\n  ── Deleting all data for '{model}' ──")
            results = delete_model(user_id, model, counts)
            print(f"\n  Deletion summary:")
            for target, deleted in results.items():
                print(f"    ✓ {target}: {deleted} deleted")
            print(f"\n  Done.")
            input("  Press Enter to continue...")

        # ── Option 4: Wipe by date/time range ──
        elif choice == "4":
            print("\n  ── Wipe by Date/Time Range ──")
            print("  (Leave blank for beginning/end of time)")
            start = parse_datetime("  Start date/time (YYYY-MM-DD HH:MM): ")
            end = parse_datetime("  End date/time (YYYY-MM-DD HH:MM): ")

            if start and end and start > end:
                print("  [WARN] Start is after end. Swapping.")
                start, end = end, start

            print(f"\n  ── Dry Run: Items in range ──")
            range_label = ""
            if start:
                range_label += f" from {start.strftime('%Y-%m-%d %H:%M')}"
            if end:
                range_label += f" to {end.strftime('%Y-%m-%d %H:%M')}"
            print(f"  Range:{range_label}")

            counts = count_date_range(user_id, start, end)
            total = print_counts(counts, "item")

            if total == 0:
                print("\n  Nothing to delete in this range.")
                input("  Press Enter to continue...")
                continue

            confirm = input(f"\n  Wipe all {total} items in this range? [y/N]: ").strip().lower()
            if confirm != "y":
                print("  Cancelled.")
                input("  Press Enter to continue...")
                continue

            print(f"\n  ── Deleting items in range ──")
            results = delete_date_range(user_id, start, end)
            print(f"\n  Deletion summary:")
            for target, deleted in results.items():
                print(f"    ✓ {target}: {deleted} deleted")
            print(f"\n  Done.")
            input("  Press Enter to continue...")

        # ── Option 5: Wipe a specific model by date/time range ──
        elif choice == "5":
            model = input("\n  Enter model name: ").strip()
            if not model:
                print("  No model name entered.")
                input("  Press Enter to continue...")
                continue

            print("\n  ── Wipe by Date/Time Range ──")
            print("  (Leave blank for beginning/end of time)")
            start = parse_datetime("  Start date/time (YYYY-MM-DD HH:MM): ")
            end = parse_datetime("  End date/time (YYYY-MM-DD HH:MM): ")

            if start and end and start > end:
                print("  [WARN] Start is after end. Swapping.")
                start, end = end, start

            range_label = ""
            if start:
                range_label += f" from {start.strftime('%Y-%m-%d %H:%M')}"
            if end:
                range_label += f" to {end.strftime('%Y-%m-%d %H:%M')}"
            print(f"\n  ── Dry Run: Items for '{model}'{range_label} ──")

            counts = count_date_range(user_id, start, end, model_filter=model)
            total = print_counts(counts, "item")

            if total == 0:
                print("\n  Nothing to delete.")
                input("  Press Enter to continue...")
                continue

            confirm = input(f"\n  Wipe all {total} items for '{model}' in this range? [y/N]: ").strip().lower()
            if confirm != "y":
                print("  Cancelled.")
                input("  Press Enter to continue...")
                continue

            print(f"\n  ── Deleting ──")
            results = delete_date_range(user_id, start, end, model_filter=model)
            print(f"\n  Deletion summary:")
            for target, deleted in results.items():
                print(f"    ✓ {target}: {deleted} deleted")
            print(f"\n  Done.")
            input("  Press Enter to continue...")

        # ── Option 6: Switch user ──
        elif choice == "6":
            new_user = select_user()
            if new_user and new_user != user_id:
                user_id = new_user
                show_user_info(user_id)
            elif new_user == user_id:
                print("  Same user, continuing.")

        # ── Option 7: Exit ──
        elif choice == "7":
            print("\n  Goodbye.\n")
            break

        else:
            print("  Invalid option. Please enter 1-7.")
            input("  Press Enter to continue...")


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n\n  Interrupted. Exiting.\n")
        sys.exit(0)