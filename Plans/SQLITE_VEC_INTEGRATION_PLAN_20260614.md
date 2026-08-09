# SQLite-vec Integration Plan for Friday Memory System

## Step 0: Backup All FMS Files
- Create `/media/nate/Friday/Friday/backupstxt/` folder
- Copy every .py, .json, .sh, and .md file from `/media/nate/Friday/Friday/` into `backupstxt/` with `.txt` extension appended
- Include files from subdirectories: `memory_data/`, `Logs/`, `Decisions_Folder/`, `Summaries/`, `Friday_Memory_System_Update/`
- Use a script to do this recursively

## Step 1: Add WAL Mode to EmbeddingCache (prerequisite)
- Location: `friday_memory_short_term.py`, `EmbeddingCache._init_db()` method, line ~625
- Add: `self.conn.execute("PRAGMA journal_mode=WAL")` right after `self.conn = sqlite3.connect(...)`
- Effect: Eliminates read-block-on-write contention that caused the 3-day stall
- Cost: 1 line of code, no dependencies

## Step 2: Install sqlite-vec Extension
- Run: `pip install sqlite-vec`
- Load in Python: `sqlite3.enable_load_extension(True)` then `conn.load_extension("vec0")`
- Effect: Adds virtual table support for vector similarity search directly in SQLite

## Step 3: Replace EmbeddingCache with VectorCache
Current EmbeddingCache:
- Stores embeddings as pickle BLOBs in a regular table
- get/put/delete operations per memory ID
- No native vector search — requires full Python loop + numpy

New VectorCache:
- Uses sqlite-vec virtual table with native float[] column
- HNSW index for fast approximate nearest neighbor search
- API: get(id), put(id, text, embedding), delete(id), search(embedding, threshold, top_n)
- search() replaces the entire 10k-item Python vector loop with one SQL query
- Backward compatible: same database file, same API for get/put/delete

## Step 4: Eliminate Vector Loop in get_relevant_memories
Current (lines ~9012-9079):
```python
for mem in existing_memories:
    mem_emb = embedding_cache.get(mem_id)  # SQLite per memory
    sim = float(np.dot(user_embedding, mem_emb))  # numpy per memory
```

Replacement:
```python
results = vector_cache.search(user_embedding, threshold, top_n)
# Results are [(mem_id, score), ...] - already sorted, already filtered
```

Effect: O(n) Python loop over 10k items becomes O(log n) HNSW index search. Time drops from ~0.2s to ~0.001s regardless of memory count.

## Step 5: Update All embedding_cache References
~20 references across the file:
- `embedding_cache.get(mem_id)` → `vector_cache.get(mem_id)`
- `embedding_cache.put(mem_id, text, emb)` → `vector_cache.put(mem_id, text, emb)`
- `embedding_cache.delete(memory_id)` → `vector_cache.delete(memory_id)`
- `embedding_cache.clear()` → `vector_cache.clear()`
- `embedding_cache.get_all_memory_ids()` → `SELECT memory_id FROM vec_memory_embeddings`

## Step 6: Migration Script
Write a one-time script that:
1. Reads all existing pickle-blob embeddings from current `memory_embeddings.db`
2. Deserializes each with pickle
3. Creates new sqlite-vec virtual table
4. Inserts all embeddings with their metadata
5. Backs up old database as `memory_embeddings.db.bak`

## Step 7: Apply to Long-Term Memory System (`friday_memory_system.py`)
- Search for embedding storage/lookup patterns
- Apply same VectorCache pattern if similar embedding cache exists
- Can share the same sqlite-vec database

## Step 8: Apply to Upgrade Folders
- `/media/nate/Friday/Friday/Friday_Memory_System_Update/friday_memory_short_term.py`
- `/media/nate/Friday/Friday/persistent-ai-memory-update/ai_memory_short_term.py`

---

# Comprehensive Eddie Summary: FMS Performance Problem (June 11-14, 2026)

## What Happened
On June 11, 2026, the v0.0.25 upgrade was applied to `friday_memory_short_term.py` (4660-line diff vs HEAD). The upgrade included: TaskCoordinator integration, TagManager, conversation stub creation for FK compliance, _is_lm_studio_running check, error buffer system, memory_to_cache_keys reverse index, reasoning content support, and relocation of many inner functions to class methods.

After the upgrade was applied at ~11:10 AM, the short term memory system was restarted (process 94029 at 21:03). For the first 8 minutes, everything was fast (0.42-0.89s memory retrievals). Then memory extraction via LLM started timing out (wrong llama.cpp endpoint configured in valves). By 21:11, memory retrieval degraded from 0.42s to 2.62s. By 22:01, it hit 1065s. The degradation persisted for 3 days, even through multiple OpenWebUI restarts, until my logging edits today fixed it.

## Root Cause Analysis
I could not find a specific logic change that caused the 1000x slowdown. The `get_relevant_memories` function is functionally identical between pre-6/11 and post-6/11 versions (only 2 trivial additions). The functions it calls (_get_formatted_memories, get_nomic_embedding, embedding_cache) are also identical.

My best theory: The EmbeddingCache uses synchronous SQLite (`sqlite3.connect()`, `check_same_thread=False`) with NO WAL mode. When the outlet's memory extraction timed out repeatedly (wrong LLM endpoint), each failed extraction still called `embedding_cache.put()` which does a synchronous INSERT+COMMIT. These writes blocked every `embedding_cache.get()` from the concurrent inlet's `get_relevant_memories` call. Over 3 days and thousands of operations, this accumulated into 8-minute stalls as SQLite lock contention compounded.

The "fix" was likely killing process 94029's 3-day accumulated state (corrupted error buffer, stale _embedding_model_validated flag, bloated _memory_to_cache_keys dict, and accumulated SQLite transaction state). My logging edits didn't change any logic — just added additive timing instrumentation. The restart that followed the edits properly cleared the corrupted process state.

## Key Code Architecture Issues Found
1. **No WAL mode** on EmbeddingCache SQLite connection — reads block on writes
2. **Synchronous SQLite in async code** — every get/put/commit blocks the event loop
3. **Fresh aiohttp.ClientSession per get_nomic_embedding call** — no connection reuse
4. **_last_embedding_dimension initialized to None** — set at line 2231 during pre-load, then RESET to None at line 2420 later in __init__, causing false dimension_changed on first call
5. **Error buffer persists to disk** — could accumulate corrupted state over days
6. **Missing `await`** on `Memories.get_memories_by_user_id()` in the upgrade folder (not the running file, but the upgrade copy was broken)

## Files Involved
- Main plugin: `/media/nate/Friday/Friday/friday_memory_short_term.py`
- Long-term system: `/media/nate/Friday/Friday/friday_memory_system.py`
- MCP server: `/media/nate/Friday/Friday/friday_memory_mcp_server.py`
- Task coordinator: `/media/nate/Friday/Friday/task_coordinator.py`
- Upgrade folder: `/media/nate/Friday/Friday/Friday_Memory_System_Update/friday_memory_short_term.py`
- PAM: `/media/nate/Friday/Friday/persistent-ai-memory-update/`
- Backups: `/media/nate/Friday/Friday/FMS Backups/`
- Log: `/media/nate/Friday/Friday/logs/friday_short_term_memory.log` (1.2GB)
- Embedding cache DB: `/media/nate/Friday/Friday/data/memory_embeddings.db` (42MB, 9797 embeddings)
- Other DBs: `memory_data/ai_memories.db`, `memory_data/conversations.db`, `memory_data/schedule.db`, etc.
- Config: `embedding_config.json`, `memory_bank_registry.json`, `tag_registry.json`

## Key Number
9797 memories with all embeddings pre-loaded, 0 embedding misses, 0.2s vector loop when healthy.
