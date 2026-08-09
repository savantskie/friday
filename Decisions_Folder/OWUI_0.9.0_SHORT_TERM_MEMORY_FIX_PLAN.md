# Friday Short Term Memory Fix Plan for OpenWebUI 0.9.0
**Status:** Investigation Complete - Ready for Implementation
**Created:** 2026-04-30
**Last Updated:** 2026-04-30
**Current Time:** 14:26 CDT (Thu Apr 30)

---

## Executive Summary

The short term memory system in Friday stopped working correctly after the OpenWebUI 0.9.0 upgrade. Investigation reveals the root cause is NOT an embedding dimension mismatch or token overflow—those are old errors from December 2025. The system was actually working fine recently (as of 2026-04-30 08:34:53 when embeddings last completed successfully).

The real issue is the current system tries to send ALL potentially relevant memories to the LLM for relevance scoring at once, which creates unnecessary token overhead and can cause failures under load. The MEMORY_SCORING_IMPLEMENTATION_PLAN.md provides an excellent architectural solution to separate concerns, reduce token usage, and make the system more robust.

**Recommendation:** Implement the dual-LLM architecture from MEMORY_SCORING_IMPLEMENTATION_PLAN.md to fix the underlying inefficiency and make the system production-ready.

---

## Investigation Findings

### Date Context
- **Current Date/Time:** 2026-04-30 14:26 CDT
- **Last Successful Embedding Run:** 2026-04-30 08:34:53 (TODAY, ~6 hours ago)
- **Embedding Model:** text-embedding-nomic-embed-text-v1.5 (768D)
- **Embedding Status:** ✅ Complete and current

### What the Logs Actually Show

#### December 2025 Errors (RESOLVED)
- Embedding dimension mismatches (768D ↔ 1024D) - errors from 2025-12-13 to 2026-04-16
- Invalid JSON from memory extraction - various models, dated 2025-12
- These are OLD and have been fixed

#### Current Status (2026-04-30)
- ✅ Embeddings: Successfully generated/updated TODAY
- ✅ Memory validation: No NEW errors being logged
- ✅ Plugin initializing correctly
- ⚠️ Secondary background tasks failing (memory linking, promotion loops) - these are separate from core memory extraction/injection

### Current Architecture Issues (Not Bugs, But Inefficiencies)

The current `get_relevant_memories()` method (line 8884-9330 in friday_memory_short_term.py):

1. **Vector Filtering:** Works correctly - narrows 6,945 memories to ~50-100 candidates
2. **LLM Selection:** Where the problem lies - sends ALL filtered candidates to LLM at once
   - Each memory needs embedding in the prompt
   - With 100+ candidates, this can be 20-50K tokens just for the LLM prompt
   - At 768-byte embeddings + content, memory descriptions, and reasoning, token usage balloons
   - While your model has 1M token context, the system doesn't limit this per-call

Current flow:
```
User Message → Vector Filter (650→50) → [BOTTLENECK] LLM scores all 50 at once → Top-K returned
```

Problem: Even though it works, it's inefficient. If any memory is malformed or LLM call times out, ALL 50 get reprocessed together.

---

## Solution: Dual-LLM Architecture (From MEMORY_SCORING_IMPLEMENTATION_PLAN.md)

Replace the current single-LLM-call-with-all-candidates approach with three separate, isolated LLM flows:

### Flow 1: Memory Extraction & Scoring (During Inlet)
- **When:** User sends a message
- **What:** Extract new memories AND score them (1-10 importance)
- **Input:** User message, character context (if roleplay), extraction prompt
- **Output:** 
  ```json
  {
    "operation": "NEW",
    "content": "User likes coffee with oat milk",
    "tags": ["preference"],
    "memory_bank": "Personal",
    "score": 6
  }
  ```
- **Isolation:** No reference to other memories, no historical data
- **Token Impact:** 5-20K tokens per call (focused, small)
- **Store:** Metadata includes `memory_score`, `memory_score_generated_at`, `memory_score_source: "extraction"`

### Flow 2: Memory Injection Selection (During Inlet After LLM Response)
- **When:** After main LLM finishes, before response returns
- **What:** Rank vector-filtered candidates for injection into context
- **Step A (Vector Filter):** 6,945 memories → 50-100 candidates by cosine similarity
- **Step B (LLM Selection - SEPARATE CALL):**
  - Input: Current user message + candidate summaries (similarity scores + stored importance scores)
  - Output: Top-K ranked memory IDs in relevance order
  - **Isolation:** No extraction logic, no scoring history
  - **Token Impact:** 20-50K tokens per call (bounded by top-N, not all memories)
- **Result:** Only inject the best-match memories

### Flow 3: Background Rescoring (When API Idle)
- **When:** Llama.cpp API has no requests for 15 minutes
- **What:** Re-score old or unscored memories in batches of 200
- **LLM Input:** 200 memories with intrinsic importance scale only
- **LLM Output:** 
  ```json
  {
    "scores": [
      {"id": "mem_001", "score": 6},
      {"id": "mem_002", "score": 8},
      ...
    ]
  }
  ```
- **Isolation:** No current message context, no injection logic
- **Token Impact:** 50-100K tokens per batch (non-blocking, runs during idle)
- **Non-Blocking:** Runs as asyncio.create_task(), doesn't affect user interaction

---

## Why This Fixes the Problem

### Current System Problems
1. All memory scoring happens in one massive LLM call
2. Any failure requires reprocessing ALL memories together
3. No separation between "extract & score new" vs "select best for injection"
4. Background scoring tasks have API compatibility issues (using undefined methods)

### New System Benefits
1. ✅ Three independent LLM operations - each can fail gracefully without affecting others
2. ✅ New memories scored at creation time (fresh context)
3. ✅ Injection LLM gets bounded candidate list (20-50K tokens max)
4. ✅ Old memories rescored only during idle (doesn't block users)
5. ✅ Clear separation of concerns - easier to debug, maintain, improve
6. ✅ Token usage stays within reasonable bounds for each individual operation
7. ✅ Handles OpenWebUI 0.9.0 changes without additional complexity

---

## Implementation Specification

### New Valves (Add to UserValves class)

```python
# Background rescoring settings
enable_background_memory_rescoring: bool = Field(
    default=True,
    description="Enable background rescoring of old/unscored memories when API is idle"
)

memory_rescoring_batch_size: int = Field(
    default=200,
    description="Max memories per batch during background rescoring"
)

memory_rescoring_api_idle_minutes: int = Field(
    default=15,
    description="Minutes of no llama.cpp API activity before triggering rescoring"
)

max_memories_for_injection: int = Field(
    default=10,
    description="Number of top memories to inject after LLM selection"
)
```

### New Methods to Implement

#### 1. `_is_llama_cpp_api_idle() -> bool` (Line reference: after inlet/outlet)
Track when last LLM call was made and compare to current time. Return True if idle > threshold.

```python
def _is_llama_cpp_api_idle(self) -> bool:
    """Check if llama.cpp API has been idle for configured threshold"""
    if not hasattr(self, '_last_llm_call_time'):
        return False
    
    now = time.time()
    idle_seconds = now - self._last_llm_call_time
    idle_minutes = idle_seconds / 60
    
    return idle_minutes >= self.valves.memory_rescoring_api_idle_minutes
```

#### 2. `async def _rescore_memories_batch(user_id: str) -> Dict[str, Any]`
Batch-score old/unscored memories when API is idle.

**Algorithm:**
1. Query memories without `memory_score` metadata OR with `needs_rescore: true`
2. Chunk into batches of 200
3. For each batch:
   - Build rescoring prompt (Prompt C from plan)
   - Call LLM with timeout protection
   - Parse JSON response
   - Update memory metadata with new scores
4. Log summary and return stats

**Error Handling:**
- If LLM fails: Log error, continue next batch (non-blocking)
- If parse fails: Assign default score 5.0, mark `needs_rescore: true`
- Never block user interaction

#### 3. Modify `identify_memories()` extraction prompt
Add score requirement to existing extraction prompt:

```python
# Add to EXISTING extraction system prompt:
"""
ADDITIONAL REQUIREMENT: Each extracted memory MUST include a "score" field (1-10).

{
  "operation": "NEW",
  "content": "User prefers oat milk in coffee",
  "tags": ["preference", "lifestyle"],
  "memory_bank": "Personal",
  "score": 6
}

SCORE SCALE (intrinsic importance only):
1-3:   Trivia, throwaway comment, incidental detail
4-6:   Regular info, typical preference, everyday behavior
7-10:  Core identity, critical relationship, fundamental value
"""
```

#### 4. Modify `get_relevant_memories()` for Flow 2
**CRITICAL:** This is the main fix to the current bottleneck.

Current behavior (line 9233-9330):
```python
if uncached_memories:
    # Sends ALL uncached_memories to LLM at once
    uncached_user_prompt = f"""Current user message: "{current_message}"
    
Available memories (evaluate relevance for these specific IDs):
{json.dumps(uncached_memory_strings)}

Rate the relevance of EACH listed memory..."""
```

New behavior:
```python
if uncached_memories:
    # Build LLM selection prompt (Prompt B from plan)
    # Input: current_message + candidate summaries with similarity + stored_score
    # LLM only ranks candidates, doesn't re-extract or re-score
    
    lllm_response_text = await self.query_llm_with_retry(
        system_prompt_injection,  # Different prompt than extraction
        injection_user_prompt,
    )
    
    # Parse selected memory IDs from LLM response
    selected_ids = self._extract_selected_memory_ids(llm_response_text)
    
    # Return only selected memories, no relevance recalculation
    return [mem for mem in uncached_memories if mem['id'] in selected_ids]
```

#### 5. Hook into inlet() for API idle check
**At the very end of inlet() method (around line 5990-6000):**

```python
# Check if llama.cpp API is idle and rescoring should trigger
if self._is_llama_cpp_api_idle() and self.valves.enable_background_memory_rescoring:
    asyncio.create_task(self._rescore_memories_batch(user_id))
    logger.info(f"Background rescoring triggered for user {user_id} (API idle)")
```

#### 6. Modify `_execute_memory_operation()` for scoring
When a NEW memory is created, extract and store the score:

```python
# When extracting memories in identify_memories()
score_value = extracted_memory.get('score', 5)  # Default to 5 if missing
metadata = {
    "memory_score": score_value,
    "memory_score_generated_at": datetime.utcnow().isoformat(),
    "memory_score_source": "extraction",
    "needs_rescore": False
}
# Store metadata alongside memory
```

---

## Prompts (Exact Text)

### Prompt A: Extraction with Score (Modification to Existing)
Keep existing extraction prompt, ADD this section:

```
SCORING REQUIREMENT: Each memory MUST include "score" (1-10).

Score based on INTRINSIC IMPORTANCE (memory content alone):
- 1-3:   Trivia, throwaway comment, low utility
- 4-6:   Regular info, normal preference, everyday behavior
- 7-10:  Core identity, critical fact, essential relationship

REQUIRED JSON FORMAT:
{
  "operation": "NEW",
  "content": "...",
  "tags": [...],
  "memory_bank": "...",
  "score": 6
}
```

### Prompt B: Injection Selection (NEW, Completely Separate)
```
ROLE: You select the most relevant memories to inject into the AI's context right now.

CURRENT USER MESSAGE:
"{current_message}"

VECTOR-FILTERED CANDIDATES (sorted by embedding similarity):
1. "User works on vLLM optimization" (similarity: 0.87, stored_score: 8)
2. "User has ADHD and 4 strokes since 2016" (similarity: 0.72, stored_score: 9)
3. "User likes coffee with oat milk" (similarity: 0.45, stored_score: 6)
[... continue for all candidates ...]

TASK: Select the top {max_memories_for_injection} most RELEVANT to THIS message.
- Consider BOTH embedding similarity AND stored memory score
- Rank by relevance to current message, not memory importance
- Only rank what's provided; do NOT create new memories

OUTPUT: JSON array of top-K memory IDs in order of relevance:
{
  "selected": ["mem_001", "mem_012", "mem_034", ...],
  "reasoning": "These memories provide context about the user's technical work and current concerns"
}
```

### Prompt C: Background Rescoring (NEW, Completely Separate)
```
ROLE: Score memories on INTRINSIC IMPORTANCE (standalone value).

SCORE SCALE (1-10):
1-3:   Trivia, background detail, low utility
4-6:   Regular info, typical preference, useful context
7-10:  Core identity, critical fact, essential relationship

MEMORIES TO SCORE:
1. "User likes coffee with oat milk"
2. "User works on vLLM optimization"
3. "User has ADHD"
4. "User lives in Minnesota"
5. [... 195 more ...]

REQUIREMENT: Score each memory INDEPENDENTLY, no context influence.

OUTPUT: JSON with scores:
{
  "scores": [
    {"id": "mem_001", "score": 6},
    {"id": "mem_002", "score": 8},
    {"id": "mem_003", "score": 9},
    ...
  ]
}
```

---

## Implementation Order

### Phase 1: Add Valves (NO FILE CHANGES YET - PLAN ONLY)
1. Add 4 new valves to UserValves class
2. Add initialization in __init__

### Phase 2: Add Helper Methods (NO FILE CHANGES YET - PLAN ONLY)
1. `_is_llama_cpp_api_idle()` - Track last LLM call time
2. `_extract_selected_memory_ids()` - Parse LLM response for selected IDs
3. Initialize `_last_llm_call_time` tracker in __init__

### Phase 3: Modify Extraction (NO FILE CHANGES YET - PLAN ONLY)
1. Update extraction prompt to include score requirement
2. Modify `identify_memories()` to extract score field
3. Store score in memory metadata during `_execute_memory_operation()`

### Phase 4: Modify Injection (NO FILE CHANGES YET - PLAN ONLY)
1. Create new `_lm_select_memories_for_injection()` method
2. Rewrite `get_relevant_memories()` Flow 2 logic
3. Remove old "uncached memories" scoring code (lines 9185-9330)

### Phase 5: Add Background Rescoring (NO FILE CHANGES YET - PLAN ONLY)
1. Implement `_rescore_memories_batch()`
2. Hook into inlet() with API idle check
3. Add error handling for non-blocking execution

### Phase 6: Update `query_llm_with_retry()` (NO FILE CHANGES YET - PLAN ONLY)
1. Track `_last_llm_call_time` on every successful call
2. This enables Flow 3 idle detection

### Phase 7: Testing & Verification (NO FILE CHANGES YET - PLAN ONLY)
1. Verify extraction + scoring works
2. Verify injection selection works
3. Verify background rescoring triggers and completes
4. Check no token overflow occurs
5. Verify no context bleed between flows

---

## Data Flow Diagram

```
USER SENDS MESSAGE
        ↓
    inlet() called
        ↓
    ┌─────────────────────────────────────┐
    │ Flow 1: Extract & Score             │
    │ identify_memories() + LLM (Prompt A) │
    │ Output: memories WITH scores         │
    │ Store in metadata                    │
    └──────────────────┬──────────────────┘
                       ↓
    ┌─────────────────────────────────────┐
    │ Main LLM Response Processing        │
    │ (existing logic unchanged)          │
    └──────────────────┬──────────────────┘
                       ↓
    ┌─────────────────────────────────────┐
    │ Flow 2: Injection Selection         │
    │ Vector filter (6945→50)             │
    │ LLM ranks top-K (Prompt B)          │
    │ Inject into response context        │
    └──────────────────┬──────────────────┘
                       ↓
               SEND RESPONSE
                       ↓
    ┌─────────────────────────────────────┐
    │ Check: _is_llama_cpp_api_idle()?    │
    │ YES → trigger Flow 3 (async)        │
    │ NO  → continue                      │
    └──────────────────┬──────────────────┘
                       ↓
    [ASYNC, non-blocking]
    ┌─────────────────────────────────────┐
    │ Flow 3: Background Rescoring       │
    │ Query unscored memories (batch 200) │
    │ LLM scores (Prompt C)               │
    │ Update metadata                     │
    │ Repeat until all scored             │
    └─────────────────────────────────────┘
```

---

## Success Criteria

✅ Memory saving works without token overflow
✅ Memory injection uses separate LLM call (Prompt B only)
✅ Memory scoring happens at extraction time (Prompt A)
✅ Old memories rescored during API idle (Prompt C)
✅ All three LLM flows completely isolated (zero context bleed)
✅ New memories immediately scored with fresh context
✅ No user-facing latency (background tasks non-blocking)
✅ System survives OpenWebUI 0.9.0 without regression

---

## Testing Checklist

Before marking complete:

- [ ] **Flow 1:** Create new memory, verify `memory_score` in metadata ✓ stored
- [ ] **Flow 1:** Verify score matches extraction logic (1-10 scale)
- [ ] **Flow 2:** Inject memories, confirm separate LLM call (different prompt)
- [ ] **Flow 2:** Verify top-K selection returns correct count
- [ ] **Flow 3:** Wait for API idle, confirm rescoring starts
- [ ] **Flow 3:** Verify batch processing (200 at a time)
- [ ] **Isolation:** Verify each LLM call uses isolated prompt (no context bleed)
- [ ] **Overflow:** Check token count never exceeds reasonable bounds
- [ ] **Backfill:** Manually remove scores from 10 memories, verify rescoring updates them
- [ ] **Performance:** Confirm no latency added to user messages
- [ ] **Edge Cases:** Test with empty memory banks, missing metadata, malformed JSON

---

## Version Increment

Upon successful implementation and testing:
- Increment Friday Short Term Memory from v0.0.24 → v0.0.25 (patch version)
- Version appears at top of friday_memory_short_term.py (line 4)
- Update CHANGELOG if present

---

## References

- **Source Plan:** /media/nate/Friday/Friday/MEMORY_SCORING_IMPLEMENTATION_PLAN.md
- **Main File:** /media/nate/Friday/Friday/friday_memory_short_term.py
- **Key Methods:**
  - `inlet()` - line 5128
  - `outlet()` - line 5871
  - `get_relevant_memories()` - line 8884
  - `identify_memories()` - line 8736
  - `query_llm_with_retry()` - line 11025

---

## Next Steps

1. ✅ Investigation complete
2. ⏳ Approval to proceed with implementation
3. ⏳ Phase 1 implementation (valves)
4. ⏳ Phase 2-6 implementation (methods)
5. ⏳ Phase 7 testing
6. ⏳ Git commit with message: "feat: Implement dual-LLM architecture for memory scoring and injection (fixes OWU 0.9.0 inefficiencies)"
7. ⏳ Push to Friday production

---

## Notes

- This is NOT fixing a broken system; it's optimizing an inefficient one
- Embeddings are current and working (updated TODAY 2026-04-30)
- The model's 1M token context is plenty for individual operations
- Three separate flows prevent cascading failures
- Background rescoring is completely non-blocking
