# COMPREHENSIVE IMPLEMENTATION PLAN
## Friday Short-Term Memory System Quality-of-Life Improvements

**Date**: May 1, 2026
**Status**: LOCKED-IN PLAN (Ready for execution approval)
**Scope**: Friday production system first, then PAM upgrade folder
**Author**: Eddie

---

## EXECUTIVE SUMMARY

This plan implements 5 key improvements to the Friday short-term memory system, focusing on:

1. Verifying JSON parsing is working (quick diagnostic)
2. Building live tag registry tracking
3. Injecting available tags/banks into Friday's memory extraction context
4. Persistent retry queue for failed memories (survive restarts)
5. Better status messages for users

**Expected Impact**: 
- No data loss during llama.cpp memory issues
- Friday gets visibility into existing tags/banks before creating memories
- Better transparency for users about memory status
- Smoother experience with fewer validation failures

**Total Implementation Time**: ~4-5 hours
**Risk Level**: LOW (mostly additive, one refactor on error handling)

---

## PHASE 1: DIAGNOSTIC & VERIFICATION (30 minutes)

### Verify JSON parsing is working in recent logs

**Why**: 
Friday said it's working now, but the implementation is relatively recent. Want to confirm 
before moving forward.

**What to check**:
- Look at Friday logs from last 7 days for JSON parsing errors
- Search for "Expecting value: line 1 column 1" errors (the old pattern)
- Verify `_strip_markdown_json_response()` is being called
- Check if error count is actually down compared to pre-fix

**Outcome**: 
- If errors still present → debug the stripping logic
- If errors gone → confirm fix is working, proceed to Phase 2
- Document findings in memory for future reference

**Files to examine**:
- `/media/nate/Friday/Friday/Logs/friday_short_term_memory.log` (recent entries)
- `/media/nate/Friday/Friday/Logs/memory_validation_errors.json` (compare dates)

**Action**: Read-only investigation only. Report findings.

**Documentation**: Document findings in `/media/nate/Friday/Friday/Results/` folder (not just in memory).

---

## PHASE 2: DYNAMIC TAG REGISTRY BUILDING (1.5 hours)

### Build tag registry incrementally as memories are created

**Current State**:
- Tag extraction works (regex pattern `[Tags: ...]` is functional)
- Tag manager infrastructure exists but is never invoked
- `tag_registry.json` exists but is empty
- No dynamic discovery of tags Friday creates

**What's Missing**:
- Tag registry building process (infrastructure exists, never called)
- Tag tracking across memory creation
- Automatic registry updates when new tags are seen

**What We'll Build**:

#### 1. Auto-Registry Building on Memory Save
   - After memory is validated and before database save
   - Call `TagManager.build_tag_registry()` on new memories
   - Add any new tags to registry
   - Update registry file with timestamp

#### 2. Registry Incremental Updates
   - When Friday extracts a memory with tags, check registry
   - If tag not in registry, add it
   - Track when each tag was first seen
   - Keep usage count updated
   - **Also scan existing memories in short-term memory store** on startup to build initial registry
   - Deduplicate tags (manage canonical forms so same tag doesn't get listed multiple times)
   - Append new tags to registry, don't replace

#### 3. Validation Phase
   - Ensure tag_registry.json gets populated as memories arrive
   - Verify tags are being tracked correctly
   - Check that duplicate tags are normalized

**Files to Modify**:
- `/media/nate/Friday/Friday/friday_memory_short_term.py` (add registry update calls)
- `/media/nate/Friday/Friday/tag_manager.py` (may need tweaks to build_tag_registry)

**Key Functions**:
- `_store_extracted_memories()` → add registry update
- `TagManager.build_tag_registry()` → ensure handles incremental updates
- `TagManager.save_registry()` → ensure atomic writes

**Expected Result**:
- tag_registry.json populated with tags as memories are created
- Each tag has: canonical_form, variations, usage_count, first_seen timestamp

---

## PHASE 3: INJECT TAG/BANK REGISTRY INTO MEMORY EXTRACTION PROMPT (1.5 hours)

### Give Friday visibility into available tags and banks before memory creation

**Current State**:
- Banks are injected at line 7912-7916 (memory identification prompt)
- Tags are NOT injected
- Friday creates tags without knowing what already exists
- Can lead to tag proliferation and inconsistency

**What We'll Add**:

#### 1. Available Tags Context
   - Load current tag registry after Phase 2 is built
   - Format as: "Available tags: authentication, technical_state, emotional, behavior_pattern..."
   - Include note: "New tags will be auto-discovered if you create them"
   - Append to existing banks context at line 7916

#### 2. Recent Tags Used (optional, for context)
   - Show 5-10 most recently used tags
   - Helps Friday understand current conversation themes
   - Format: "Recently used: behavior, user_request, technical_issue"

#### 3. Integration Point
   - Line 7912-7916: Where banks are already being injected
   - Add parallel injection for tags right after banks
   - Modify `system_prompt` construction to include both

**Files to Modify**:
- `/media/nate/Friday/Friday/friday_memory_short_term.py` (inject tags into prompt)

**Key Functions**:
- `identify_memories()` → add tags to context
- `_load_tag_registry()` → new function to load registry into memory
- Create `_get_available_tags_context()` → format tags for prompt

**Expected Result**:
- When Friday creates memories, he sees available tags
- Can choose to reuse existing tags or create new ones intentionally
- Tag registry grows organically but remains usable

---

## PHASE 4: PERSISTENT RETRY QUEUE FOR FAILED MEMORIES (1.5 hours)

### Survive restarts, auto-retry when model recovers

**Current State**:
- Memory queue exists but is in-memory only (lost on restart)
- Failed memories are logged but not automatically retried
- If llama.cpp crashes during memory extraction, memories are lost

**What We'll Build**:

#### 1. Persistent Failed Memory Log

Create new file: `/media/nate/Friday/Friday/memory_data/failed_memories_queue.json`

Format:
```json
{
  "version": 1,
  "last_updated": "ISO timestamp",
  "failed_memories": [
    {
      "id": "uuid",
      "conversation_id": "uuid",
      "content": "memory content",
      "tags": ["tag1", "tag2"],
      "memory_bank": "Personal",
      "model_id": "friday",
      "user_id": "nate",
      "failed_at": "ISO timestamp",
      "failure_reason": "LLM call failed: Model unloaded",
      "retry_count": 0,
      "max_retries": 3
    }
  ]
}
```

#### 2. Queue Management Functions
   - `_add_to_retry_queue()` → when memory extraction fails, save to queue
   - `_load_retry_queue()` → on startup, load failed memories
   - `_process_retry_queue()` → background task to retry failed memories
   - `_remove_from_queue()` → when memory successfully saved

#### 3. Retry Logic
   - On startup: load retry queue
   - Every 5 minutes: attempt to retry up to 3 memories
   - Max retry attempts: 3
   - Remove from queue after successful save
   - Remove from queue if max retries exceeded (log as persistent failure)

#### 4. Integration Points
   - When memory extraction fails → add to queue instead of just logging
   - Inlet method → check/load retry queue on startup
   - New background task → periodic retry processor

**Files to Modify**:
- `/media/nate/Friday/Friday/friday_memory_short_term.py` (add queue functions + task)

**Key Functions**:
- `_add_to_retry_queue()` → new
- `_load_retry_queue()` → new
- `_process_retry_queue()` → new background task
- Error handling in `_process_memory_queue()` → add queue save

**Expected Result**:
- Failed memories survive restart
- Automatically retried when system recovers
- No data loss from transient llama.cpp failures

---

## PHASE 5: ENHANCED STATUS MESSAGES (1 hour)

### Better transparency about memory operations

**Current State**:
- Status messages terse: "Memory save skipped", "llm_error"
- Users don't understand what happened
- No visibility into memory counts

**What We'll Improve**:

#### 1. Memory Extraction Status
- Current: "Memory save skipped"
- New: "Memory extraction skipped: [reason] (3 memories identified but topic filtered)"

**Reasons to show**:
- Topic filtered (show filter reason)
- Duplicate detected (show which memory it matched)
- Model unavailable (show model name)
- LLM error (show error type)
- Successfully saved (show count + banks)

#### 2. Memory Success Summary
- Current: (none shown to user)
- New: "✓ Stored 4 memories: 2x Personal, 1x Technical, 1x Projects | Tags: behavior, user_request, technical_state"

#### 3. Error Messages
- Current: "llm_error"
- New: "Memory extraction failed: LLM returned 400 (model unloaded) - will retry automatically"

#### 4. Implementation
   - Modify status message generation at end of outlet
   - Build descriptive messages based on extraction results
   - Keep tone "normie-friendly" not overly technical
   - Include action-relevant info (retrying, filtering reason, etc.)

**Files to Modify**:
- `/media/nate/Friday/Friday/friday_memory_short_term.py` (status message generation)

**Key Functions**:
- `_generate_memory_status_message()` → new function
- End of `outlet()` → call status message generator

**Expected Result**:
- Users understand what happened to their memories
- Better transparency without information overload
- Maintainer can relay clearer status to you

---

## PHASE 6: PORT TO PAM UPGRADE FOLDER (1 hour)

### Apply same improvements to persistent-ai-memory

After Friday is verified working:

**What gets ported**:
- Phase 2 changes: tag registry building
- Phase 3 changes: tag injection into prompt
- Phase 4 changes: persistent retry queue
- Phase 5 changes: status messages

**Special Considerations for PAM**:
- Use `AI_MEMORY_DATA_DIR` environment variable (already in place)
- Use `AI_MEMORY_LOG_DIR` for logs
- Same user_id/model_id isolation requirements
- Test with PAM's ai_memory_short_term.py
- **Important**: Delete any files PAM creates during testing (failed_memories_queue.json, 
  tag_registry.json, etc.) before porting code to repo. Do NOT commit test data.

**Files to Modify**:
- `/media/nate/Friday/Friday/persistent-ai-memory-update/ai_memory_short_term.py`
- `/media/nate/Friday/Friday/persistent-ai-memory-update/tag_manager.py`

---

## INVESTIGATION: OpenWebUI 0.9.0 Changes (Parallel, Read-Only)

### What's new that we should consider?

**Scope**: Compare `/media/nate/Games/Openwebuifork/` vs `/media/nate/Friday/Friday/OpenWebUIstock/`

**Look for**:
- New memory/knowledge APIs
- Changes to plugin/filter system
- New tool capabilities
- New error handling mechanisms
- Changes to message format/structure
- Performance improvements we should leverage

**Constraints**: 
- Focus on memory system integration points
- Ignore built-in memory features (we keep yours)
- Report findings only, no changes yet

**Expected Output**: Summary document with findings + recommendations

---

## TESTING & VALIDATION STRATEGY

### Phase 1 Validation
- Check logs for JSON errors (read-only)
- Compare error counts before/after

### Phase 2 Validation
- Verify tag_registry.json gets populated as memories save
- Check tag deduplication is working
- Confirm registry format matches expected structure

### Phase 3 Validation
- Manually check Friday's memory extraction prompts
- Verify available tags/banks are shown in logs
- Confirm Friday uses existing tags when appropriate

### Phase 4 Validation
- Simulate memory extraction failure
- Kill process and restart
- Verify failed memory is retried on restart
- Confirm successful save removes from queue

### Phase 5 Validation
- Check status messages for clarity
- Verify they contain actionable info
- Test edge cases (multi-memory, all filtered, mixed success)

### Phase 6 Validation
- Same tests as Phase 2-5 but in PAM upgrade folder
- Verify environment variables work correctly
- Test user_id/model_id isolation

---

## ROLLOUT STRATEGY

1. Implement Phase 1 (diagnostic) - verify JSON fix works
2. Implement Phases 2-3 together (tag registry + injection)
3. Test and validate Phases 2-3 with live Friday
4. Implement Phase 4 (retry queue)
5. Test and validate Phase 4
6. Implement Phase 5 (status messages)
7. Full system test (all phases together)
8. Port to PAM upgrade folder (Phase 6)
9. Final validation

---

## VERSION BUMPING

Current version: 0.0.24

After all changes:
- Increment to: 0.0.25 (minor feature additions, all backward compatible)
- Update in both Friday production and upgrade folder
- Update in PAM when porting

---

## RISKS & MITIGATION

### Risk 1: Tag Registry Corruption
- Mitigation: Atomic JSON writes, backup before each write

### Risk 2: Retry Queue Grows Too Large
- Mitigation: Max queue size cap (e.g., 1000 items), cleanup old items

### Risk 3: Status Messages Too Verbose
- Mitigation: Test with multiple scenarios, keep to 1-2 lines

### Risk 4: Performance Impact from Tag Lookup
- Mitigation: Keep registry in memory after first load, only sync to disk periodically

### Risk 5: Infinite Retry Loop
- Mitigation: Max 3 retries per memory, track failure patterns

---

## DEPENDENCIES & ASSUMPTIONS

### Assumptions
- JSON markdown stripping is working (Phase 1 validates this)
- Memory banks auto-discovery is working (confirmed in codebase)
- llama.cpp crashes/recovers occasionally (why retry queue is needed)
- Friday creates 5-10 memories per turn consistently

### Dependencies
- tag_manager.py working (already is)
- Database access for memory storage (already is)
- File I/O permissions for queue/registry files (should be fine)

---

## QUESTIONS FOR NATE - ANSWERED

1. **Tag Registry Backup**: Current version is enough (no daily backups needed)

2. **Status Message Detail Level**: Medium detail
   - Format: "Memory extraction failed: LLM error (will retry)"

3. **Retry Backoff**: Wait 45 seconds before first retry, then check if blocker is resolved.
   - If still blocked, retry in background every 5 minutes with exponential backoff

4. **Max Queue Size**: 1000 items max (after however long the first creation takes)

5. **OpenWebUI Investigation**: Broad exploration
   - Ignore their built-in memory system (we manage that database)
   - Short-term system already manipulates their memory database

---

## ADDITIONAL CLARIFICATIONS FROM NATE

### Phase 1 Documentation
- Results go in `/media/nate/Friday/Friday/Results/` folder (not just in memory)
- Document findings in file for easy review

### Phase 2 Tag Registry
- Tag registry should scan existing memories in short-term memory store on startup
- Build initial registry from all existing memories
- Manage and deduplicate tags so same tag doesn't get listed multiple times
- Only append new tags, don't replace

### Phase 6 PAM Testing
- Delete any test files PAM creates during testing (failed_memories_queue.json, tag_registry.json, etc.)
- Do NOT commit test data to the repo

---

## DOCUMENT HISTORY

- **2026-05-01**: Plan created based on Nate's QoL improvement analysis
- **2026-05-01**: Updated with Nate's clarifications and answers
- Status: READY FOR IMPLEMENTATION
