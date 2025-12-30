# Active Debug Investigation: Memory Filtering Issue
**Date Started:** December 27, 2025  
**Issue:** "Memory save skipped – filtered or duplicate" message appearing despite new permissive extraction prompt  
**User Context:** Nate returning from cigarette break

---

## Problem Statement
- User reports memory creation being silently blocked with "Memory save skipped – filtered or duplicate"
- No memories exist in database, so "duplicate" claim is false
- Recent surgical changes to `memory_identification_prompt` are in place (lines 1410-1445)
- Changes made the prompt explicitly permissive ("ALWAYS store it", no content filter)
- Issue persists despite these changes

---

## Investigation Findings

### 1. **Root Cause Location Identified**
**File:** `friday_memory_short_term.py`  
**Function:** `identify_memories()` (starts line 6306)  
**Critical Flow:**
1. Line 6538: LLM is called via `query_llm_with_retry()`
2. Line 6540-6551: JSON stripping happens if `enable_json_stripping=True`
3. Line 6660-6670: LLM response is parsed
4. Line 6681: When status is `"no_memories_found"`, memories array is empty `[]`
5. Line 6692: `if not result:` triggers, returns empty list
6. Back in `save_memory()` at line 5706: Empty `memories` list causes filter message

### 2. **Why Prompt Changes Didn't Help**
The problem is NOT with the prompt being ignored. The problem is:
- **LLM IS correctly returning** `{"status": "success", "memories": [...]}`
- **BUT** the memories array IS coming back empty `[]`
- This causes the "filtered_or_duplicate" message

**Evidence from logs:**
- File: `/media/nate/Friday/Friday/Logs/memory_validation_errors.json`
- Model "tara" (10 attempts): Shows LLM returning wrapped JSON like `{"status": "success", "reason": "...", "memories": [...]}`
- The response IS being parsed correctly
- But the memories array is empty

### 3. **Possible Secondary Filters**
After LLM extraction (`identify_memories()` returns a list of memories), the flow continues to:
1. **Blacklist filtering** (lines 5774-5808): Removes memories matching blacklisted topics
2. **Whitelist checking** (lines 5789-5798): Can override blacklist
3. **Meta-request filtering** (lines 5765-5772): Removes meta-requests like "remember this"
4. **Minimum length filtering** (lines 5758-5762): Removes memories shorter than configured minimum

**None of these should affect an empty memories list** (they only process what exists).

### 4. **The Real Problem: LLM Is Still Filtering**
Despite our prompt changes, the LLM is returning empty memories. This means:

**Option A:** The prompt changes aren't being loaded
- Prompt was modified but code needs to be reloaded
- OpenWebUI/LM Studio caches the filter code
- System hasn't picked up the new prompt definition

**Option B:** The LLM itself has built-in restrictions
- The LLM model (Tara, Friday, etc.) has its own filtering
- Model refuses to return memories for roleplay content
- Not something the system prompt can override

**Option C:** The extraction is failing silently
- LLM is returning error response or empty response
- System is interpreting as "no_memories_found"
- Prompt changes made to correct behavior but LLM not reached

### 5. **JSON Stripping Issue (Secondary)**
**Location:** `_clean_llm_json_response()` lines 2552-2589

The function handles:
```python
if response.startswith("```"):
    start_idx = response.find("\n")
    if start_idx == -1:
        start_idx = 3
    else:
        start_idx += 1
```

**Potential bug:** If LLM returns ```` ```json\n{...}\n``` ````, the find("\n") gets the first newline after "json", which is correct. But if the format is different (like no newline after json), it might skip to char 3 and include extra content.

**However:** This would cause JSON PARSE errors, which ARE being logged in error file. So stripping might be working but parsing is still catching them.

---

## What We Know For Certain
✅ Prompt changes were applied surgically to lines 1410-1445
✅ Changes make extraction explicitly permissive ("ALWAYS store it")  
✅ LLM is being called (confirmed by log entries showing LLM responses)
✅ Responses ARE being wrapped in markdown code blocks (confirmed by error logs)
✅ `enable_json_stripping=True` by default (should strip markdown)
✅ JSON parsing is failing per the validation error logs (line 1 column 1 errors)
✅ This causes memories to be returned as empty arrays

## What We Need to Investigate Further

1. **Is the new prompt definition actually being used?**
   - Check if system is loading `memory_identification_prompt` from updated code
   - Or is it using a cached/persisted version?

2. **Is the JSON stripping function working correctly?**
   - The error logs show it's NOT stripping properly (still getting parse errors)
   - `_clean_llm_json_response()` might have a bug

3. **Is the LLM actually returning empty memories?**
   - Or is the parsing/stripping/validation pipeline rejecting everything?
   - Need to see actual raw LLM response before any processing

4. **Are there persisted settings overriding valves?**
   - OpenWebUI might have stored different settings
   - Check database/config for persisted filter settings

5. **Is the prompt being sent to the LLM at all?**
   - Or is there a cached version being used?
   - Need to verify exact prompt being sent

---

## Hypotheses (Priority Order)

**HIGH PRIORITY:**
1. **Code is not reloaded** - OpenWebUI/filter needs restart to pick up changes
2. **JSON stripping is broken** - Markdown still wrapping JSON, parse fails, empty array returned
3. **Persisted settings exist** - OpenWebUI has stored old filter configuration overriding code

**MEDIUM PRIORITY:**
4. **LLM model has restrictions** - Model itself filters roleplay content regardless of prompt
5. **Prompt not reaching LLM** - Somehow the old prompt is cached

**LOW PRIORITY:**
6. **Character context extraction failing** - Special character extraction interfering

---

## Next Steps (When Nate Returns)

1. **Check if system needs reload:**
   - Restart OpenWebUI filter or Python process
   - Verify code is actually running new version

2. **Add debug logging:**
   - Log raw LLM response before stripping
   - Log response after stripping
   - Log what gets parsed

3. **Test JSON stripping directly:**
   - Create test with markdown-wrapped JSON
   - Verify `_clean_llm_json_response()` actually removes wrappers

4. **Inspect persisted settings:**
   - Check if OpenWebUI stored old filter config
   - Reset to defaults if needed

5. **Monitor next memory attempt:**
   - Watch for what prompt is actually sent to LLM
   - Capture raw LLM response
   - Trace through entire pipeline

---

## Files Involved
- **Prompt definition:** `friday_memory_short_term.py` lines 1332-1645
- **Memory identification:** `friday_memory_short_term.py` lines 6306-6750
- **JSON stripping:** `friday_memory_short_term.py` lines 2552-2589
- **Filtering logic:** `friday_memory_short_term.py` lines 5700-5880
- **Error logs:** `/media/nate/Friday/Friday/Logs/memory_validation_errors.json`

---

## Summary
The system is functioning but the extraction pipeline is returning empty memory arrays from the LLM, triggering the "filtered_or_duplicate" message. This is either because:
1. The prompt changes haven't taken effect (most likely)
2. The JSON stripping is broken, causing parse failures (secondary)
3. The LLM model itself has built-in restrictions (tertiary)

**DO NOT PROCEED WITH CHANGES** until root cause is identified and confirmed.
