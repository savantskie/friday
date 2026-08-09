# CORE IDENTITY SYSTEM OVERHAUL 2026-05-13

**What was wrong**: The core identity system (`core_identity.py`) was designed to distill Friday's personality from memories and conversations, but it had never actually run. The system prompt was clinical data extraction. The scheduling was broken. The valve settings were never persisted properly.

**Three root causes fixed:**

## 1. Valve-timing bug in friday_memory_short_term.py

The coordinator registers background tasks during `__init__`, but at that point `self.valves` still has Python defaults because OpenWebUI sets the real values on the Pydantic model *after* init runs. So `enable_core_identity_task = False` at registration time regardless of what the admin panel says.

**Fix**: Extracted valve-gated coordinator registrations into `_register_valve_gated_tasks()`. This method is called once during `__init__` (with defaults, unchanged behavior) and then called **again** during the first `inlet` call after OpenWebUI has set the real valves. The persisted settings file (`Logs/valve_settings.json`) now saves `self.valves` during the first inlet, so the next boot loads correct values from the start.

**Files**: `friday_memory_short_term.py`, `persistent-ai-memory-update/ai_memory_short_term.py`

## 2. Core identity scheduled for midnight instead of arbitrary 12-hour intervals

Changed the schedule from `"interval:12h,idle"` to `"daily@00:00,idle"`. Core identity runs once per night at midnight, requires 10+ minutes of idle time (you're asleep), and uses the coordinator's existing scheduling infrastructure.

The `core_identity_interval` valve is now marked deprecated — it was never actually consumed by the registration code.

**Files**: `friday_memory_short_term.py`, `persistent-ai-memory-update/ai_memory_short_term.py`

## 3. Prompt rewritten and batched processing added

### New narrative prompt (core_identity.py)

The old prompt was clinical: "extract facts, write a list of traits." The new prompt treats the identity as **Friday's sense of self** — a growing, evolving understanding of who he is and who Nate is to him. Sections were renamed: `[Relationships]` → `[Relationship]`, `[Facts]` → `[Facts About Nate]`. Fallback text changed from "No significant data collected yet" to "Still learning."

The prompt file was saved to `Assistant System PROMPTS/core_identity_prompt.txt` for review.

### Batch processing (core_identity.py)

Instead of sending all memories in one LLM call (which overflows the 262k context window), memories are processed in **batches of 50**:

1. Batch 1: LLM builds identity from scratch with the initial prompt
2. Batches 2+: LLM receives existing identity + new batch, uses an update prompt that says "merge this new material into what you already know"
3. Only after ALL batches succeed: identity is committed to the database, processed timestamps are set
4. If any batch fails: nothing is committed, next midnight run restarts from the progress file

### Memory-conversation pairing (core_identity.py)

The LLM now sees each memory paired with its source conversation topics:
```
Memory: "User really liked the dark theme implementation"
  From conversations: UI preferences discussion (Jan 15)
```
This was achieved by:
- Removing the 24-hour limit from `get_conversations_for_memories()`
- Adding `_build_memory_conversation_map()` that creates a `memory_id → [topics]` mapping
- Passing the map through the batch loop into `distill_core_identity()`

### OpenWebUI chat fallback (core_identity.py)

For conversations that exist in OpenWebUI's `webui.db` but were never imported into FMS `conversations.db` (there was a period where chat import wasn't working), `_get_openwebui_conversations()` pulls up to 100 recent chats by title/summary from the `chat` table. These are deduplicated against FMS conversations and labeled with `[OpenWebUI]` so Friday knows the source.

### Progress tracking for crash recovery (core_identity.py)

The `core_identity_progress.json` file now tracks `batch_index`, `batches_total`, `all_memory_ids`, and `accumulated_identity`. If the server restarts mid-batch, the next midnight run picks up where it left off.

## Files changed (all syntax-validated)

| File | Changes |
|---|---|
| `core_identity.py` | New prompt, batch processing, memory-conversation pairing, OpenWebUI fallback, progress tracking, 24h limit removed |
| `friday_memory_short_term.py` | Valve-gated task extraction, `_register_valve_gated_tasks()`, guard flag, persisted settings save, schedule to `daily@00:00` |
| `persistent-ai-memory-update/ai_memory_short_term.py` | Same schedule + persisted save ported to PAM staging copy |
| `Assistant System PROMPTS/core_identity_prompt.txt` | New file with full prompt documentation |

## What happens now

1. Save the three Python files into OpenWebUI
2. Send one message — inlet fires, real valves load, persisted file created, core_identity registered at `daily@00:00`
3. At midnight (idle = asleep), first batch run begins. Processes 50 memories, builds initial identity. Next batch picks up where it left off.
4. Next morning, first conversation gets the core identity injected into the system prompt
