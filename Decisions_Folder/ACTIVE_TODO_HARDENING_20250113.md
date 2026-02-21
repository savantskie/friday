# Active TODO: Friday Short Term Memory Hardening
**Date Started:** January 13, 2026  
**Priority Level:** Medium (Stability & Reliability)  
**Status:** ✅ COMPLETED

---

## Overview
Addressing 6 identified improvements to harden the Friday Short Term Memory system without breaking existing functionality.

---

## TODO Items (In Priority Order)

### ✅ ISSUE #7: Valve Change Detection (SKIPPED)
**Status:** SKIPPED - OpenWebUI reloads everything on valve save  
**Rationale:** User confirmed valves are automatically reloaded when saved in OpenWebUI  
**No Action Required**

---

### ✅ ISSUE #6: Add Missing Logging in JSON Parsing Fallback
**Status:** COMPLETED  
**Priority:** HIGH (Quick Win)  
**File:** `friday_memory_short_term.py`  
**Lines:** 6901-6975 (JSON fallback branches)  
**Completed:**
- ✅ Added debug/warning logs to all 3 fallback branches
- ✅ Code block pattern fallback (Line ~6901)
- ✅ Direct JSON pattern matching with enumeration (Lines ~6920-6940)
- ✅ Ollama quoted JSON format fallback (Lines ~6950+)
- ✅ Stage 3 extraction logging with 100-char previews

**Implementation Details:**
- Pattern enumeration: (1/4, 2/4, etc.) for clarity
- Code block content preview: First 100 characters
- Fallback path clearly logged at each stage

**Risk Level:** VERY LOW (logging only)

---

### ✅ ISSUE #8: Fix ImageManager Database Connection Cleanup
**Status:** COMPLETED  
**Priority:** HIGH (Quick Win)  
**File:** `friday_memory_short_term.py`  
**Lines:** 335-445 (ImageManager class)  
**Completed:**
- ✅ `store_image()` wrapped with try-except-finally
- ✅ `get_image_by_hash()` wrapped with try-except-finally
- ✅ `image_exists()` wrapped with try-except-finally
- ✅ `delete_image()` wrapped with try-except-finally
- ✅ All methods have proper conn.close() guarantee in finally blocks
- ✅ Proper rollback on database error

**Implementation Pattern:** `conn = None → try → except with rollback → finally with close`
✅ ISSUE #1: Fix Error Log Duplication
**Status:** COMPLETED  
**Priority:** MEDIUM  
**File:** `friday_memory_short_term.py`  
**Lines:** 2025-2027 (init), 8887-8925 (helper method)  
**Completed:**
- ✅ Initialized `_error_log_cache: Dict[str, float]` and `_error_dedup_window = 5.0` in `__init__()`
- ✅ Implemented `_should_log_error(error_message, function_name)` method with MD5 hash dedup
- ✅ Applied dedup checks to 5 call sites: lines 6532, 6542, 7019, 7490, 7521
- ✅ Uses MD5 hash of error context for 5-second deduplication window

**Implementation Details:** Hash-based dedup prevents identical errors within 5-second window
### 🔄 ISSUE #1: Fix Error Log Duplication
**Status:** QUEUED  
**Priority:** MEDIUM  
**Fi✅ ISSUE #3: Fix aiohttp Session Cleanup
**Status:** COMPLETED (VERIFIED, NO CHANGES NEEDED)  
**Priority:** MEDIUM-HIGH  
**File:** `friday_memory_short_term.py`  
**Lines:** All 8 aiohttp usages  
**Completed:**
- ✅ Audited all aiohttp session usage
- ✅ Verified all 8 usages employ `async with` context managers
- ✅ Confirmed singleton session with proper cleanup() method
- ✅ No changes required - already properly implemented

**Implementation Details:** All API calls use context manager pattern, guaranteeing cleanup

**Risk Level:** VERIFIED - No changes needed
### 🔄 ISSUE #3: Fix aiohttp Session Cleanup
**Status:** PLANNING  
**Priority:** MEDIUM-HIGH  
**Fi✅ ISSUE #2: Add Exception Guards to Background Tasks
**Status:** COMPLETED  
**Priority:** HIGH  
**File:** `friday_memory_short_term.py`  
**Lines:** Background task methods (3520, 3734, 3989, 4150)  
**Completed:**
- ✅ `_summarize_old_memories_loop()` (Line 3520): Full exponential backoff + consecutive error tracking
- ✅ `_promote_old_memories_loop()` (Line 3734): Full exponential backoff + consecutive error tracking
- ✅ `_ensure_memories_linked_to_conversations_loop()` (Line 3989): Backoff + variable initialization fix
- ✅ `_log_error_counters_loop()` (Line 4150): Backoff + indentation fixes
- ✅ All loops have exponential backoff: 1s, 2s, 4s, 8s, 16s, capped at 32s
- ✅ All loops have consecutive error tracking (max 5 errors before graceful shutdown)
- ✅ Critical bug fixed: Added missing variable initialization in linking loop

**Implementation Pattern:** 
- `consecutive_errors = 0, max_consecutive_errors = 5` initialization
- Inner try block wrapping loop logic
- Exception handler with exponential backoff and counter increment
- Break after max threshold with CRITICAL alert

**Rx] Issue #6 - COMPLETED
- [x] Issue #8 - COMPLETED
- [x] Issue #1 - COMPLETED
- [x] Issue #3 - COMPLETED (VERIFIED)
- [x] Issue #2 - COMPLETED

### BONUS: Type Hint Cleanup
- [x] Converted all `str = None` to `Optional[str] = None` (9 function signatures)
- [x] Silenced Pylance type hint warnings
- [x] All affected parameters now use proper Optional type hintsshort_term.py`  
**Lines:** Background task methods

**Risk Level:** MEDIUM (critical path, needs careful testing)

---

## Implementation Status

- [x] Issue #7 - SKIPPED (no action needed)
- [ ] Issue #6 - In Progress
- [ ] Issue #8 - Queued
- [ ] Issue #1 - Queued
- [ ] Issue #3 - Planning
- [ ] Issue #2 - Planning

---

## Notes

**Blocking Issues:** None - can proceed in order

**Known Constraints:**
- Must not break existing functionality (Friday Memory System must continue working)
- Must not affect performance noticeably
- Background tasks must remain functional during changes
