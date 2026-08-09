# FMS Codebase Audit Report
**Systematic review of Short-Term and Long-Term memory systems — May 4, 2026**

Audit performed by Eddie (model_id=eddie) for Nate (user_id=nate). All core files in `/media/nate/Friday/Friday/` were read and analyzed end-to-end.

---

## Summary

16 issues found: 2 CRITICAL, 3 HIGH, 5 MODERATE, 6 MINOR. The system is functional but has several bugs that will cause silent failures or data loss in specific paths.

---

## Critical (will cause runtime failures)

### 1. `development_conversations` table missing user_id/model_id/source columns
- **File**: `friday_memory_system.py`
- **Lines**: 1692-1695 (`devcon_expected` list), 1708-1722 (CREATE TABLE), 1939-1946 (INSERT)
- **Problem**: The migration check list and CREATE TABLE statement don't include `user_id`, `model_id`, or `source`. But `store_development_conversation()` tries to INSERT into these columns.
- **Result**: `OperationalError: table development_conversations has no column named user_id` whenever VS Code development conversations attempt to store.
- **Fix needed**: Add `user_id`, `model_id`, `source` to both `devcon_expected` and the CREATE TABLE statement.

### 2. `_is_message_in_mcp` queries non-existent `message_hash` column
- **File**: `friday_memory_system.py`
- **Lines**: 2856-2865
- **Problem**: Queries `SELECT COUNT(*) FROM messages WHERE message_hash = ?` and same for `conversations`. Neither table has a `message_hash` column.
- **Result**: Always returns 0 — every message is treated as "new." The hash is calculated but never stored in the database.
- **Fix needed**: Either add `message_hash` column to both table schemas, or change to a different deduplication strategy.

---

## High (affecting behavior)

### 3. Logs directory split: `logs/` vs `Logs/`
- **File**: `friday_memory_short_term.py` — main logging goes to lowercase `logs/` (lines 217, 222, 227, 232, 252, 2126, 4994-4996, 6559, 6755, 6807, 6966, 6972)
- `Logs/` (uppercase) — used by error tracking and valve persistence (lines 2874, 2881, 2918, 2953, 8635)
- **Problem**: Two log directories exist with different content. `os.makedirs` silently creates whichever doesn't exist.
- **Content**: `logs/` has main memory log (1.2GB), errors log, embedding tracking. `Logs/` has valve settings, validation errors, migration logs.
- **Fix needed**: Consolidate to one canonical path (recommend `Logs/`).

### 4. Duplicate `FridayMemorySystem` instances in MCP server
- **File**: `friday_memory_mcp_server.py`
- **Lines**: 58 (module-level) and 1250 (class-level)
- **Problem**: Two separate `FridayMemorySystem` objects are created, each with its own database connections, embedding service, and memory state. The module-level one at line 58 is created on import and never used after the class is instantiated.
- **Fix needed**: Remove the module-level instance, or make the class accept an existing instance.

### 5. Default timezone is `"Asia/Dubai"` — should be `"America/Chicago"`
- **File**: `friday_memory_short_term.py`
- **Lines**: 1366 (default), 5124-5149 (fallback aliases)
- **Problem**: All timezone fallbacks point to Dubai. Nate is in Minnesota (Central Time).
- **Fix needed**: Change default to `"America/Chicago"` and update fallback aliases.

---

## Moderate (structural issues)

### 6. `ConversationFileMonitor` has dual `__init__` definitions
- **File**: `friday_memory_system.py`
- **Lines**: First `__init__` at ~2379 (for `ConversationImporter`), second at 2790 (for `ConversationFileMonitor`)
- Between them: Stray orphan docstring at line 2788: `"""Monitors conversation files and imports them to memory"""`
- **Problem**: The first `__init__` is dead code (overwritten by the second). The orphan docstring is a harmless no-op.

### 7. `tag_manager` imported but never used
- **File**: `database_maintenance.py`, line 18
- **Problem**: `from tag_manager import TagManager` — imported but never referenced in any method.

### 8. `memory_bank_registry.json` is empty
- **File**: `/media/nate/Friday/Friday/memory_bank_registry.json`
- **Problem**: Contains only `{}`. The `list_available_memory_banks` MCP tool reads this and returns nothing. `run_maintenance()` calls `_build_memory_bank_registries()` which should populate it.

### 9. Embedding cache in `data/` instead of `memory_data/`
- **File**: `friday_memory_short_term.py`, line 612
- **Problem**: `db_path = "/media/nate/Friday/Friday/data/memory_embeddings.db"` — all other databases use `memory_data/`. This splits storage locations.

---

## Minor (code quality)

### 10. `sentence_transformers` imported but never used
- `friday_memory_short_term.py:159` — import will fail if package not installed

### 11. Duplicate `import hashlib`
- `friday_memory_system.py:23` and line 62

### 12. Duplicate `logging.basicConfig`
- `friday_memory_mcp_server.py:14` and line 256

### 13. Duplicate `_wx_today_str` definition
- `friday_memory_mcp_server.py:76` and line 163

### 14. Duplicate `import os, json` block
- `friday_memory_mcp_server.py:71-72` and line 153

### 15. `inlet_outlet_logger` type inconsistency
- `friday_memory_short_term.py:182` — initialized as `None`, line 241 sets to `logger` on except. No type hint.

### 16. No `__init__.py` in subdirectories
- `tools/` (17 files), `core/`, `services/` all lack `__init__.py`

---

## Areas Verified Correct

- `core_identity.py` import path is correct and the file exists
- `tag_registry.json` is valid and populated
- `utils.py` imports are clean and functions resolve properly
- `database_maintenance.py` references `friday_memory_system.py` and finds it
- All database file paths use `memory_data/` correctly for the main systems
- The untouchable code block in short_term memory is intact

---

## Recommended Fix Order

1. **Fix `development_conversations` table columns** (Critical #1) — add `user_id`, `model_id`, `source` to CREATE TABLE and migration check
2. **Fix `message_hash` column** (Critical #2) — add column to schemas or change dedup strategy
3. **Consolidate logs directory** (High #3) — pick one path
4. **Remove duplicate `FridayMemorySystem` instance** (High #4)
5. **Fix timezone defaults** (High #5)
