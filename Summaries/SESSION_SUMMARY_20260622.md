# Session Summary — June 22, 2026
## Core Identity System Investigation and Fix

### Initial Question

Nate reported that the Core Identity system (Friday's nightly identity distillation) had never successfully run. He asked me to investigate where the system resides, what it was supposed to write to, what it was called, and why it wasn't working.

### Investigation Path

**1. Finding the system**

The core identity system lives in two places:
- `/media/nate/Friday/Friday/core_identity.py` — standalone `CoreIdentityManager` class
- `friday_memory_short_term.py:4468` — `_core_identity_work` method, scheduled via TaskCoordinator as `daily@00:00,idle`

It writes to three locations:
- `core_identity` table in `ai_memories.db` (primary)
- `friday_core_identity.json` file backup
- OpenWebUI knowledge base (attempts, silently fails)

**2. Discovering the system IS running (but doing nothing)**

Logs at `/media/nate/Friday/Friday/logs/short_term_memory.log` showed `CORE_IDENTITY: Generation completed` every night at midnight from May 15 through June 21. But `memories_analyzed=0` on nearly every run. The system ran nightly but found no data to process.

**3. Root cause: Chain of broken links**

**Link 1 — Memory promotion crashes every night**
`_memory_promotion_work` calls `Users.get_all_users()` which was removed in OpenWebUI's API. The correct method is `Users.get_users()` which returns `{'users': [...], 'total': N}`. This has been erroring since June 4 with `AttributeError: 'UsersTable' object has no attribute 'get_all_users'`.

Result: Zero memories have ever been promoted from short-term to long-term storage.

**Link 2 — Core identity only reads curated_memories (which was cleared by maintenance)**
`CoreIdentityManager.get_new_memories_since_processing()` exclusively queries the `curated_memories` table in `ai_memories.db`. That table only has **5 total entries** — 2 for `nate/friday`, 3 for test data.

The reason curated_memories is nearly empty: on **May 6, 2026**, the database maintenance system (`database_maintenance.py`) archived ALL old curated memories into monthly archive databases at `/media/nate/Friday/Friday/memory_data/archives/`. The current ai_memories.db was cleared down to near-zero and has only accumulated 5 new entries since then. The real memory history (1.5M+ entries) lives in the archives.

Additionally, the memory promotion pipeline that should be moving short-term memories into curated_memories has been broken since June 4, so no new memories are arriving via that path either. The 10,354 short-term memories in OpenWebUI's `memory` table (webui.db) were never seen by core identity because it never looked there.

**Link 3 — Model ID case mismatch**
`_core_identity_work` defaults to `model_id="Friday"` (capital F), but all stored data uses `model_id="friday"` (lowercase). A `_normalize_name()` method exists but was never applied here. Half the nightly runs produced version-0 entries for the wrong model_id.

**Link 4 — Archives exist (from successful maintenance) but core identity never read them**
On May 6, 2026, the database maintenance system successfully archived all old curated memories into monthly snapshots. 10 archived databases sit in `/media/nate/Friday/Friday/memory_data/archives/` with ~1.5M historical memory entries spanning August 2025 through May 2026. Many entries have blank user_id/model_id from before the schema migration. Neither core identity nor any other system read them for distillation purposes.

**4. Additional discoveries**

- The `memories` table in `ai_memories.db` has 0 rows and a broken schema (`model_id` is INTEGER instead of TEXT)
- `ai_memories.db` is 3.3GB with 805,613 free pages — this is the space left behind after the May 6 archival moved ~1.5M entries to archives. Needs VACUUM to reclaim.
- Conversations.db has 226 conversations and 10,523 messages across multiple user_ids (OWU UUIDs, not "nate")
- The deployed function code in webui.db (`function` table, 12,302 lines) IS the running version — it's compiled from a string when OpenWebUI loads the valve

**5. The user_id naming problem**

The FMS uses user_id="nate" but OpenWebUI's databases use the UUID `9d08cfbb-b8ca-484d-bd37-c5c383c1e5d6`. The core_identity system needs to map between these.

### Solutions Applied

**File: `friday_memory_short_term.py`**
- Line 4166: `Users.get_all_users()` → `Users.get_users()`, unpack the `{'users': [...], 'total': N}` response
- Line 4479: `model_id = getattr(self, "_current_model_id", "Friday")` → `model_id = self._normalize_name(getattr(self, "_current_model_id", "friday"))`
- Applied to both main file and Friday_Memory_System_Update folder

**File: `core_identity.py`** (full rewrite of memory gathering)

- **`_resolve_owu_user_id(name)`** — maps "nate" to the OWU UUID `9d08cfbb-b8ca-484d-bd37-c5c383c1e5d6` by querying webui.db's user table
- **`_get_webui_memories(owu_user_id, max_memories)`** — queries webui.db's `memory` table (10,354 entries), incremental via `core_identity_tracking.json`
- **`_get_archived_memories(user_id, model_id, max_memories)`** — cursor-paginated archive processing. One archive per night, newest first. Uses cursor-based pagination (timestamp + memory_id) to resume across nights. When an archive is exhausted, it's moved to `processed_archives`.
- **`core_identity_tracking.json`** — new tracking file for webui cursor (`webui_last_processed_at`) and archive cursor (`archive_processing`, `archive_cursor_ts`, `archive_cursor_id`, `processed_archives`)
- **`run_generation()`** — gathers from all three sources (curated_memories + webui.db + archives), deduplicates by content, feeds to LLM
- **Distill prompts updated** — both initial and update prompts now emphasize selectivity: only strong, repeated, high-importance observations make it into core identity. "Still learning" is preferred over weak guesses.

**Applied to all three locations:**
- `/media/nate/Friday/Friday/core_identity.py`
- `/media/nate/Friday/Friday/Friday_Memory_System_Update/core_identity.py`
- `/media/nate/Friday/Friday/persistent-ai-memory-update/core_identity.py`

**File: `persistent-ai-memory-update/ai_memory_short_term.py`**
- Same `Users.get_all_users()` → `Users.get_users()` fix

### What Tonight's Run Will Do

1. **Memory promotion** runs for the first time successfully
2. **Core identity** gathers from curated_memories + webui.db (10K+ memories) + the newest archive
3. All sources are deduplicated, capped at 500 memories, chunked in batches of 50
4. LLM distills a selective identity — only confident, repeated observations
5. Result saved to `core_identity` table (version 12+) and file backup
6. Archives continue processing nightly until caught up to current date

### Files Changed

| File | Changes |
|------|---------|
| `core_identity.py` | Added OWU user resolver, webui memory query, cursor-paginated archive query, tracking file, updated distill prompts, multi-source run_generation |
| `friday_memory_short_term.py` | Fixed memory promotion API call, normalized model_id default |
| `Friday_Memory_System_Update/core_identity.py` | Copy of main file changes |
| `Friday_Memory_System_Update/friday_memory_short_term.py` | Same fixes as main |
| `persistent-ai-memory-update/core_identity.py` | Copy of main file changes |
| `persistent-ai-memory-update/ai_memory_short_term.py` | Fixed memory promotion API call only |

### Linked Conversation Injection Fix

Found an instruction mismatch in `friday_memory_short_term.py`: the `[Linked Conversation: ...]` tag injected with each memory was carrying the **conversation_id**, but the `get_conversation_context` MCP tool expects a **memory_id** as input. The instruction text told the LLM to "call the get_conversation_context tool with that conversation id" — but the tool does `WHERE memory_id = ?` to look up the link.

Fixed:
- Line 6860: instruction text "conversation id" → "memory id"
- Lines 6930, 6959, 6988 (bullet, numbered, paragraph): tag value `{conversation_id}` → `{memory_id}`

Now the LLM sees `[Linked Conversation: <memory_id>]` on each linked memory, calls `get_conversation_context(memory_id="...")`, and the tool returns the full source conversation.

### Archive Re-scan Trigger (selective reprocessing)

Added a significance detection system to `core_identity.py`:

- **`_identity_changed_significantly()`** — compares old vs new identity after each nightly incremental update. If any section went from "Still learning" to real content, the change is flagged as significant.
- **`_set_rescan_flag()`** — writes `needs_rescan: true` to `core_identity_tracking.json` (file-based, survives restarts)
- **`_check_and_handle_rescan()`** — at the start of each nightly run, if `needs_rescan` is true, wipes the `processed_archives` list and starts archive processing over from the newest archive

Processed markers are already file-based in `core_identity_tracking.json` — so they persist across restarts and only get cleared when a meaningful identity change triggers a re-scan.

### Open Questions / Future Work

- The user_id mapping ("nate" → OWU UUID) should ideally be centralized rather than just in core_identity.py
- `ai_memories.db` should be vacuumed to reclaim 800K+ free pages (3.3GB → much smaller)
- The `memories` table in ai_memories.db has broken schema (INTEGER model_id) — needs cleanup
- Core identity re-processing logic: once archives are caught up, the system should only re-process if genuinely new material warrants it (not implemented yet)