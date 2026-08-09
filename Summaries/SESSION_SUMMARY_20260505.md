# Session Summary: May 5, 2026
**Reasoning Model Tolerance + Long-Term Memory Maintenance + MCP Hot-Reload Fix**

---

## Overview

Three major workstreams completed in this session:
1. Made the memory system tolerant of reasoning models (Qwen 3 with thinking enabled)
2. Built long-term memory maintenance features (format reformatting, contradiction scanning, assisted linking)
3. Fixed the MCP server hot-reload mechanism that was causing crashes on file change

---

## Workstream 1: Reasoning Model Tolerance

### Motivation
Nate is testing Qwen 3.6 35B A3b as the memory LLM with reasoning enabled. Reasoning models output chain-of-thought in `<think>` or `<thinking>` tags within the `content` field, or store the actual output in `reasoning_content` while leaving `content` empty. The memory system was not handling either case properly.

### Investigation
Three defense layers already existed from a previous GLM-4.7-flash fix, but had critical gaps:

1. **Request level** (line ~10812): `chat_template_kwargs: { enable_thinking: False }` sent to OpenAI-compatible endpoints. Not all providers respect this.

2. **Response level** (line ~10906): `reasoning_content` field was logged and skipped during content extraction. But if the model put everything in `reasoning_content` and nothing in `content`, the content field check failed entirely -- no content was extracted, causing empty response errors.

3. **Content level** (`_sanitize_reasoning_content`, line ~8951): Stripped `<think>` tags from content. But only ran inside `_extract_and_parse_json`, not in `query_llm_with_retry` itself. And the regex only handled `<think>`, not `<thinking>`.

Two critical gaps found:
- Gap A: `query_llm_with_retry` returned raw content with no sanitization. Callers bypassing `_extract_and_parse_json` got untagged content.
- Gap B: Two callers (tag inference at line ~6895, memory scoring at line ~7142) used bare `json.loads()` with only a markdown fence strip (`re.sub(r'```json|```', '', response)`). No thinking tag stripping at all.

### Changes Made

**Change 1: reasoning_content fallback (Phase 1B)**
- Location: `query_llm_with_retry`, OpenAI-compatible chat completions path
- Before: Required `message.get("content")` to be truthy; `reasoning_content` was logged and skipped
- After: Only checks for `message` existence. Uses `message.get("content") or message.get("reasoning_content")` -- reasoning fields become a fallback source when content is empty
- Same pattern applied to the Ollama path

**Change 2: Central sanitization in query_llm_with_retry (Phase 1A)**
- Location: Before `return content` in `query_llm_with_retty`
- Added: `content = self._sanitize_reasoning_content(content)` before return
- Result: ALL callers get clean text automatically, regardless of code path

**Change 3: Tag inference path fix (Phase 2C)**
- Location: Line ~6893, retroactive memory normalization
- Before: `clean_response = re.sub(r'```json|```', '', response).strip()` then `json.loads(clean_response)`
- After: Uses `self._extract_and_parse_json(response)` with fallback to empty dict

**Change 4: Memory scoring path fix (Phase 2D)**
- Location: Line ~7141, batch importance scoring
- Before: Same bare json.loads pattern
- After: Uses `self._extract_and_parse_json(response)` with fallback to empty list

**Change 5: Expanded think tag regex (Phase 3E)**
- Location: `_sanitize_reasoning_content`, line ~8953
- Before: `re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL)`
- After: `re.sub(r'<\s*/?\s*(?:think|thinking)\s*>.*?</\s*(?:think|thinking)\s*>\s*', '', text, flags=re.DOTALL)`
- Now handles: `<think>`, `</think>`, `<thinking>`, `</thinking>`, and variants with optional whitespace

**Change 6: core_identity _call_llm fix**
- Location: `core_identity.py`, `_call_llm`, line ~283
- Same two issues: no content fallback, no think tag stripping
- Fixed with same pattern: `message.get("content") or message.get("reasoning_content")` plus regex sanitization before return

**PAM port**
- All six changes ported identically to `persistent-ai-memory-update/ai_memory_short_term.py` and `core_identity.py`

### Architecture
Data flow after the fix:
1. `query_llm_with_retry` sends request with `enable_thinking: False` (best-effort)
2. LLM responds with content in `content`, `reasoning_content`, or both
3. Response parser tries `content` first, falls back to `reasoning_content`
4. Raw content is sanitized (think/thinking tags stripped) before return
5. All callers receive clean text
6. Callers needing JSON go through `_extract_and_parse_json` (defense-in-depth)

### Risk Assessment (Workstream 1)
- Low risk: All changes are additive (additional fallbacks, expanded regex matching) or replace stricter parsing with more tolerant parsing
- No existing functionality removed
- The `_sanitize_reasoning_content` call in `query_llm_with_retry` is the only behavioral change visible to all callers -- it strips think tags before JSON parsing, which is strictly better than leaving them in
- If the regex is too aggressive (e.g., matches unintended content), it would only strip text from the LLM response, never cause a crash

---

## Workstream 2: Long-Term Memory Maintenance

### Motivation
Two features were supposed to exist but were never properly implemented:
1. Convert old long-term memories to match the short-term system's format style (first-person perspective, proper tags/banks)
2. Scan long-term memories for contradictions or updates and handle them without culling

### Investigation

**Format conversion**: The existing `_retroactively_normalize_old_memories()` only touched short-term memories. Long-term memories in `curated_memories` (FMS DB) were never corrected. The `_migration_needs_run` flag was set in init but never consumed. No format conversion existed in `database_maintenance.py`.

**Contradiction detection**: Partial at best. The merge prompt mentioned contradiction handling. Semantic duplicates during promotion triggered `_synthesize_merged_memory()`. But there was NO standalone contradiction scanner that proactively checked the long-term database. No way to link related memories to each other.

### Changes Made

**New File: friday_memory_maintenance.py (FMS production, 340 lines)**
**New File: ai_memory_maintenance.py (PAM upgrade folder, genericized)**

Contains `LongTermMemoryMaintenance` class with:

1. **`reformat_memories()`** -- Scans `curated_memories` for entries missing format markers. For each non-conforming memory, strips existing markers, sends bare content to LLM at `http://192.168.1.50:8080/v1/chat/completions` (FMS) or `$AI_MEMORY_LLM_ENDPOINT` (PAM) with a prompt adapted from the short-term extraction prompt style. The LLM reformats using proper perspective (first-person for assistant, "User is..." for user info), proper tags, and proper bank. Updates the memory content. Preserves all conversation links. Runs as step 9 in `run_maintenance()`.

2. **`scan_for_updates()`** -- Batches long-term memories (10 at a time), sends them to the LLM to identify pairs covering the same topic with differing/updated information. For each identified pair: appends an `[Updated: date: note]` to the older memory, creates a `memory_relationships` link. Never deletes or overwrites anything. Runs as step 10 in `run_maintenance()`.

3. **`assist_linking()`** -- Supplements the existing retroactive linking with text-overlap matching for unlinked memories. Runs as part of step 10.

4. **`_call_llm()`** -- Internal helper using `httpx` to call the LLM with think-tag stripping. FMS uses hardcoded address, PAM uses `$AI_MEMORY_LLM_ENDPOINT` env var.

5. **`run_all()`** -- Convenience method to run all three operations in sequence.

**Modified: friday_memory_system.py (FMS) / ai_memory_core.py (PAM)**

Added `memory_relationships` table with columns:
- `relationship_id TEXT PRIMARY KEY`
- `source_memory_id TEXT NOT NULL`
- `target_memory_id TEXT NOT NULL`
- `relationship_type TEXT NOT NULL` -- `updated_by`, `complements`, or `related_to`
- `notes TEXT` -- LLM-generated explanation
- `created_at TEXT DEFAULT CURRENT_TIMESTAMP`

Created via `CREATE TABLE IF NOT EXISTS` during normal schema init, so existing databases pick it up on next startup.

**Modified: database_maintenance.py (both FMS and PAM)**

- Imports `LongTermMemoryMaintenance` 
- Initializes it in `__init__`
- Adds steps 9-10 to `run_maintenance()`:
  - Step 9: `reformat_memories(limit=100)` -- format reformatting
  - Step 10: `scan_for_updates(limit=200)` + `assist_linking(limit=50)` -- contradiction detection and link assistance

### Safety Rules (hardcoded in scanner):
- Never modifies the newer memory -- only appends to the older one
- Never overwrites or deletes any memory
- Relationship links are added, never removed
- LLM failures are caught per-batch, maintenance cycle continues
- Already-linked pairs are skipped

### LLM Format Prompt Style (adapted from short-term extraction prompt):
- About the user: "User is...", "User prefers...", "User mentioned..."
- About the assistant's own experiences: First-person ("I noticed...", "I found that...")
- About characters in roleplay: Appropriate character perspective
- Tags: Comma-separated, lowercase, descriptive
- Banks: General, Personal, Work, Projects, Technical, Tasks, Research, Context, Patterns, Preferences, Temporary, Character, Character_Interaction, Intimate, Adult_Content

---

## Workstream 3: MCP Server Hot-Reload Fix

### Problem
Editing any watched file triggered `_reload_memory_modules()` which called `sys.exit(0)` directly inside a running asyncio task. `SystemExit` is a `BaseException` that propagated unpredictably through the event loop, collided with starlette/uvicorn's lifespan handler, and left the server in a frozen state with `CancelledError` traces.

### Fix
Three changes in `friday_memory_mcp_server.py`:

1. Added `ServerRestartSignal(Exception)` custom exception class with documentation explaining why a regular Exception is used instead of `sys.exit()`.

2. Replaced `sys.exit(0)` in `_reload_memory_modules()` with `raise ServerRestartSignal()`. This propagates cleanly through asyncio tasks without corrupting the event loop.

3. Changed the main block's `except SystemExit:` to `except (SystemExit, ServerRestartSignal):` and replaced the inner `raise` with `sys.exit(0)` at the outermost level -- where it is safe to call because the event loop context has been fully unwound.

### Architecture
1. File change detected by file monitor task (every 2 seconds)
2. `_reload_memory_modules()` cancels tasks, runs cleanup, raises `ServerRestartSignal`
3. `ServerRestartSignal` propagates through the event loop naturally (it is a regular `Exception`)
4. Caught by the outer `except (SystemExit, ServerRestartSignal):` handler
5. Cleanup runs, then `sys.exit(0)` is called at the outermost program level
6. Supervisor (systemd/docker) sees exit code 0 and restarts the process

---

## Files Modified/Created

### FMS Production (/media/nate/Friday/Friday/)

| File | Action | Changes |
|------|--------|---------|
| `friday_memory_short_term.py` | Modified | 5 edits: reasoning_content fallback, central sanitization, 2 direct json.loads fixes, expanded regex |
| `core_identity.py` | Modified | reasoning_content fallback + think tag stripping |
| `friday_memory_maintenance.py` | **NEW** | LongTermMemoryMaintenance class (340 lines) |
| `friday_memory_system.py` | Modified | Added memory_relationships table |
| `database_maintenance.py` | Modified | Import + init + steps 9-10 |
| `friday_memory_mcp_server.py` | Modified | ServerRestartSignal exception + hot-reload fix |

### PAM Upgrade (/media/nate/Friday/Friday/persistent-ai-memory-update/)

| File | Action | Changes |
|------|--------|---------|
| `ai_memory_short_term.py` | Modified | Same 5 edits as production |
| `core_identity.py` | Modified | Same fix as production |
| `ai_memory_maintenance.py` | **NEW** | Genericized LongTermMemoryMaintenance (env vars for LLM endpoint) |
| `ai_memory_core.py` | Modified | Added memory_relationships table |
| `database_maintenance.py` | Modified | Import + init + steps 6 (PAM numbering) |

---

## Key Decisions
- No memory culling ever. Contradictions are handled by appending update notes and creating relationship links.
- Format reformatting uses the same prompt style as the short-term extraction prompt for consistency.
- PAM uses environment variables (`AI_MEMORY_LLM_ENDPOINT`, `AI_MEMORY_LLM_MODEL`) instead of hardcoded addresses.
- Hot-reload uses a custom Exception class instead of sys.exit() to avoid asyncio corruption.
- All changes are additive -- no existing functionality was removed or altered.
