# Error Injection System & Code Cleanup

## Overview
Session focused on two things: cleaning up stubs and incomplete code across the long-term memory system, and building an error injection system so Friday sees failures in context without having to query log files.

## Stubs & Incomplete Code Fixes

### Removed: `/memory` Slash Commands
- Deleted all `/memory` subcommand handlers: `list_banks`, `assign_bank`, and the generic catch-all stub
- These exposed OpenWebUI memory management features through chat that are now available via mcpo
- Kept the `/note` stub intact for the planned scratchpad feature

### Fixed: Broken Promotion Loop
- Added `clean_promoted_memories: bool = Field(default=True)` to the Valves class — it was referenced at line 4554 but never defined, causing an `AttributeError` every time the promotion loop tried to clean up memories after promoting them to FMS
- Meanings: promoted memories were accumulating indefinitely in short-term storage even after successful FMS promotion

### Fixed: Cache Invalidation Placeholder
- The relevance cache had placeholder `pass` loops on UPDATE and DELETE paths — cache entries for modified or deleted memories were never evicted, only expired via 24h TTL
- Ported the reverse-index system (`_memory_to_cache_keys`) from the PAM backup into all three active files
- Cache writes now track which memory_id each cache key belongs to
- UPDATE and DELETE paths now use the reverse index to `del self.relevance_cache[key]` precisely

### Fixed: External DELETE Blocked (UPDATE Restored)
- UPDATE and DELETE operations from external LLM operations are now handled differently:
  - UPDATE allowed through (when a duplicate is found with higher importance)
  - DELETE blocked and logged — only the promotion/pruning loop may delete memories
- The UPDATE case in `_execute_memory_operation` was removed and restored with reverse-index cache invalidation

### Fixed: `get_local_timezone` NameError
- Line 4955 in `_core_identity_generation_loop` called `get_local_timezone()` without defining or importing it
- Replaced with `self.get_formatted_datetime().isoformat()` which uses OpenWebUI's existing valve-based timezone system

### Cleaned Up: Stale Comments
- Removed `ISSUE 2 FIX` and `ISSUE 3 FIX` historical markers
- Removed dead `keys_to_delete = []` variables from the placeholder cache invalidation loops

### Fixed: Bare `except` in utils.py
- Changed `except:` to `except Exception:` to avoid catching `KeyboardInterrupt` and `SystemExit`

### Fixed: pydantic v2 Compat (PAM)
- `settings.dict()` in PAM's `settings.py` changed to support both v1 (`.dict()`) and v2 (`.model_dump()`)

### Created: PAM Migration File
- Created `persistent-ai-memory-update/ai_memory_normalization_migration.py` with environment-variable-based paths

## Error Injection System (New Feature)

### Problem
Friday had no way to know when things went wrong. Error counters were in-memory (lost on restart), and the dedicated error log file was never surfaced to context. The guard mechanism only monitored `json_parse_errors`, and two guard flags (`_llm_feature_guard_active`, `_embedding_feature_guard_active`) were initialized but never set to True anywhere.

### Solution: Error Buffer Injected into Context

**Architecture:**
- 20-entry `deque` (`_error_buffer`) on the Filter class
- Persisted to `Logs/error_buffer.json` — loaded on startup, saved on every error + cleanup
- Drained into context on next injection so errors are reported exactly once

**Capture Points (6 categories):**

| Category | Triggers When |
|---|---|
| `memory_create` | `add_memory()` throws in NEW case |
| `memory_update` | `delete_memory_by_id()` or `add_memory()` throws in UPDATE case |
| `memory_delete` | `delete_memory_by_id()` throws in DELETE case |
| `llm_call` | LLM connection fails, returns "Error:", or throws |
| `json_parse` | LLM response cannot be parsed as JSON after all attempts |
| `embedding` | Embedding computation fails |

**Injection Format:**
Appended as a `[System Notes]` section at the end of the memory context:
```
[System Notes]
- [memory_create] Failed to create memory: timeout (14:32:15)
- [llm_call] LLM error: Error: LLM_CONNECTION_FAILED (14:35:01)
```
Also injects error-only notes when there are no memories to inject (was previously a silent return).

**MCP Tool: `get_error_summary`**
Added to the MCP server — reads `error_buffer.json` and returns the full buffer. Friday can call it directly to ask "what went wrong recently" without waiting for the next injection.

### Files Modified
- `friday_memory_short_term.py` (production) — all error buffer + injection changes
- `friday_memory_system.py` (production) — added `get_error_summary()` method
- `friday_memory_mcp_server.py` (production) — added Tool definition + routing
- `Friday_Memory_System_Update/` — all changes mirrored
- `persistent-ai-memory-update/` — all changes mirrored (ai_memory_short_term.py, ai_memory_core.py, ai-memory-mcp_server.py)
- `utils.py` + both upgrade copies — bare except fix
- `persistent-ai-memory-update/settings.py` — pydantic v2 fix
