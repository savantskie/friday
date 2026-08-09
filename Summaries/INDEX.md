# SUMMARIES FOLDER INDEX
**Friday Memory System + Adaptive Memory v3 Integration**
**Last Updated**: August 7, 2026

---

## Start Here

### SESSION_SUMMARY_20260807.md
**mmproj-only vision server (--mmproj-only flag) -- August 7, 2026**

Added `--mmproj-only` flag to llama-server, allowing the multimodal projector (vision encoder) to run in a separate server instance without a text model. Saves ~36GB VRAM by not duplicating the 26B model. Includes startup compatibility check against the main server, new `mtmd_encode_bitmap()` API for direct image encoding without vocab, and null-safe endpoint handling. Full investigation into mtmd initialization, image tiling, n_embd validation, and server endpoint behavior.

### SESSION_SUMMARY_20260729.md
**Role-aware KV cache, --keep-roles flag, datetime context injection -- July 29-30, 2026**

Replaced flat --keep N flag with role-aware --keep-roles that uses message_spans to preserve specific role tokens (e.g., system, identity) during context shift. Added datetime role block to the Jinja template and FMS inlet so the main chat model sees current time without modifying the system prompt. Full investigation into how llama.cpp's autoparser handles custom roles, the message_spans delimiter system, and Gemma4's trained role handling.

### SESSION_SUMMARY_20260622.md
**Core identity system fixed to read from all memory sources — June 22, 2026**

Comprehensive fix for core identity, memory promotion, and archive processing. Three bugs found: (1) memory promotion crashed nightly with `Users.get_all_users()` removed from OWU API, (2) core identity only queried curated_memories (5 entries) while 10K+ short-term memories sat in webui.db untouched, (3) model_id case mismatch ("Friday" vs "friday") caused wasted runs. Added: user_id resolver (nate → OWU UUID), webui.db memory reader, cursor-paginated archive processor, selectivity-focused LLM prompts. Archive pagination means one archive database processed per night until all 10 are caught up.

### CORE_IDENTITY_OVERHAUL_20260513.md
**Core identity system fixed, batched, and personality-driven -- May 13, 2026**

Three-layer fix: (1) valve timing bug preventing coordinator from ever registering the core_identity task, (2) schedule changed from `interval:12h` to `daily@00:00`, (3) prompt rewritten from clinical extraction to narrative character-building. Added batch processing (50 memories/call with incremental LLM updates), memory-conversation pairing so the LLM sees associative context, and OpenWebUI DB fallback for chats missing from FMS.

### FMS_CODEBASE_AUDIT_20260504.md
**Systematic audit of Short-Term and Long-Term memory systems -- May 4, 2026**

16 issues found: 2 CRITICAL, 3 HIGH, 5 MODERATE, 6 MINOR.
- CRITICAL: development_conversations table missing user_id/model_id/source columns
- CRITICAL: _is_message_in_mcp queries non-existent message_hash column
- HIGH: Logs directory split (logs/ vs Logs/)
- HIGH: Duplicate FridayMemorySystem instances in MCP server
- HIGH: Default timezone is Asia/Dubai instead of America/Chicago
- Plus 11 more issues with line numbers, severity, and fix guidance

**Status**: Audit complete, fixes pending

### FMS_ERROR_INJECTION_AND_STUB_CLEANUP_20260503.md
**Error injection system + code audit cleanup -- May 3, 2026**

Removed stub slash commands, fixed broken promotion loop, ported reverse-index cache invalidation, fixed get_local_timezone NameError, pydantic v2 compat, and more. New error injection system captures failures to Logs/error_buffer.json and injects [System Notes] into context. New get_error_summary MCP tool.

### QUALITY_OF_LIFE_IMPROVEMENTS_IMPLEMENTATION_20260501.md
**5 QoL improvements to Short-Term Memory -- May 1, 2026**

JSON parsing verification, dynamic tag registry, tag & bank injection into extraction prompt, persistent retry queue (45-second backoff, 5-minute background processor), enhanced status messages, LM Studio detection.

### SESSION_SUMMARY_20260505.md
**Complete session summary for May 5, 2026**

Reasoning model tolerance (5 changes for think tags, reasoning_content fallback), long-term memory maintenance (new friday_memory_maintenance.py with formatting, contradiction scanner, relationship linking), MCP hot-reload fix (ServerRestartSignal exception instead of sys.exit(0)).

### REASONING_MODEL_TOLERANCE_20260505.md
**Reasoning model support detail -- May 5, 2026**

Detail merged into SESSION_SUMMARY_20260505.md. Central sanitization in query_llm_with_retry, reasoning_content fallback, expanded think tag regex.

### memory_fixes2026.txt
**Memory fixes notes -- May 3, 2026**

Terse notes on recent memory system fixes.

---

## PAM Infrastructure

### PAM_Async_Audit_20260423.md
**Async compatibility audit for OpenWebUI 0.9.0 -- April 23, 2026**

12 async issues: 1 CRITICAL, 2 HIGH, 9 LOW. 9 unregistered asyncio.create_task() calls causing resource leaks.

### PAM_Async_Validation_Fixes_20260423.md
**Async fixes applied to PAM -- April 23, 2026**

6 critical async issues fixed. 16 unregistered tasks registered. 9 helper files validated. 100% async parity with FMS for core operations.

### PAM_CoreIdentity_Integration_20260423.md
**Core identity system for PAM -- April 23, 2026**

Full CoreIdentityManager integration, all Friday/Nate hardcoding removed, 100% async-safe, generalized for any AI companion.

### PAM_HELPER_FILES_ASYNC_FIX_COMPLETE_20260423.md
**Helper files async fix completion -- April 23, 2026**

---

## Organization

### Active Summaries (Main Folder)
```
SESSION_SUMMARY_20260807.md                            ← START HERE (most recent, Aug 7)
SESSION_SUMMARY_20260729.md                            ← Role-aware KV cache, --keep-roles, datetime injection
SESSION_SUMMARY_20260505.md                            ← Long-term maintenance, reasoning models
FMS_ERROR_INJECTION_AND_STUB_CLEANUP_20260503.md        ← Error injection system
QUALITY_OF_LIFE_IMPROVEMENTS_IMPLEMENTATION_20260501.md ← QoL improvements
REASONING_MODEL_TOLERANCE_20260505.md                   ← Reasoning model support
memory_fixes2026.txt                                    ← Memory fixes notes
PAM_Async_Audit_20260423.md                             ← OpenWebUI 0.9.0 audit
PAM_Async_Validation_Fixes_20260423.md                  ← OpenWebUI 0.9.0 fixes
PAM_CoreIdentity_Integration_20260423.md                ← Core identity system
PAM_HELPER_FILES_ASYNC_FIX_COMPLETE_20260423.md         ← Helper files fix
```

### Archived Summaries (ARCHIVE Folder)
```
ARCHIVE/
  README_ARCHIVE.md
  Historical/                             (completed phase reports)
  Migration/                              (data migration records)
  Superseded/                             (older versions)
  FEATURES/                               (feature-specific docs)
  +47 individual summary files            (Nov 2025 - Apr 2026)
```

All summaries older than April 21, 2026 have been archived. See ARCHIVE/ for historical reference.

---

## Quick Lookup Guide

### What's been implemented recently?
SESSION_SUMMARY_20260807.md (Aug 7: mmproj-only vision server, --mmproj-only flag)
SESSION_SUMMARY_20260729.md (July 29-30: role-aware KV cache, --keep-roles, datetime injection)
FMS_Complete_System_Map.md (System Map, updated Aug 3)

### What's critically broken?
See System_Map/FMS_Complete_System_Map.md — Known Issues section
(memory_promotion still disabled since April)

### How does error injection work?
FMS_ERROR_INJECTION_AND_STUB_CLEANUP_20260503.md

### What QoL changes were just made?
QUALITY_OF_LIFE_IMPROVEMENTS_IMPLEMENTATION_20260501.md

### Is PAM ready for OpenWebUI 0.9.0?
PAM_Async_Audit_20260423.md then PAM_Async_Validation_Fixes_20260423.md

### How does core identity work in PAM?
PAM_CoreIdentity_Integration_20260423.md

### Why is the memory system failing with reasoning models?
REASONING_MODEL_TOLERANCE_20260505.md

### What changed to support reasoning models?
SESSION_SUMMARY_20260505.md (Workstream 1)

### What about older decisions/information?
See the Decisions_Folder (current) or ARCHIVE/ in this folder (historical)

---

## Status at a Glance

| Area | Status | Reference |
|------|--------|-----------|
| mmproj-Only Vision Server | Implemented | SESSION_SUMMARY_20260807.md |
| Role-Aware KV Cache | Implemented | SESSION_SUMMARY_20260729.md |
| --keep-roles Flag | Implemented + integrated | SESSION_SUMMARY_20260729.md |
| datetime Context Injection | Implemented | SESSION_SUMMARY_20260729.md |
| Timestamp-Aware Truncation | Implemented (Jul 23) | LLAMACPP_TIMESTAMP_TRUNCATION.md |
| Appointment Query Bug | Fixed (Aug 3) | System Map |
| Appointment Auto-Complete | Implemented (Aug 3) | System Map |
| Reasoning Model Tolerance | Implemented | SESSION_SUMMARY_20260505.md |
| Long-Term Memory Maintenance | Implemented | SESSION_SUMMARY_20260505.md |
| MCP Hot-Reload | Fixed | SESSION_SUMMARY_20260505.md |
| Error Injection System | Implemented | FMS_ERROR_INJECTION... |
| Tag Registry | Implemented | QUALITY_OF_LIFE... |
| Retry Queue | Implemented | QUALITY_OF_LIFE... |
| Code Audit (16 items) | All Resolved | System Map |
| memory_promotion | Still disabled (since Apr 20) | System Map |
| PAM Async 0.9.0 | Fixed | PAM_Async_Validation_Fixes... |
| PAM Core Identity | Implemented | PAM_CoreIdentity_Integration... |

---

## How This Was Organized

On May 7, 2026:
- Reviewed all ~66 summary files
- Retained only summaries from the last 2 weeks (April 21 - May 5, 2026)
- Moved 47 older files + FEATURES/ subdirectory to ARCHIVE/
- Updated this INDEX.md to reflect current organization
- All historical summaries preserved in ARCHIVE/ for reference
