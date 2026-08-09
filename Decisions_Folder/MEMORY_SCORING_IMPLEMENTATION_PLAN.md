# FINAL IMPLEMENTATION PLAN: Dual-LLM Architecture with API Idle Monitoring

**Status:** Ready for independent AI implementation  
**No file modifications yet.** Plan only.

---

## Executive Summary

**Problem:** April 20-30, memory saving fails because memory injection tries to LLM-score 6,945 memories in real-time (625K tokens > 128K limit).

**Solution:** Separate the two LLM operations completely with NO context bleed:

1. **Flow 1 - Memory Extraction & Scoring** (during inlet): LLM extracts memories AND scores them
2. **Flow 2 - Memory Injection Selection** (separate inlet call): LLM receives vector-filtered candidates, ranks by relevance
3. **Flow 3 - Background Rescoring** (when llama.cpp API idle): Re-score old/unscored memories

Each operation has its own isolated prompt. No memory overflow. No context bleed.

---

## System Architecture

### Flow 1: Memory Extraction & Scoring (happens during `inlet()`)

**Trigger:** User sends message  
**Component:** `identify_memories()` calls LLM

**Input to LLM:**
- User message
- Character context (if roleplay)
- System prompt with extraction guidelines

**LLM Output:** JSON
```json
{
  "status": "success",
  "memories": [
    {
      "operation": "NEW",
      "content": "User likes coffee with oat milk",
      "tags": ["preference"],
      "memory_bank": "Personal",
      "score": 6
    },
    {
      "operation": "NEW",
      "content": "User works on vLLM optimization",
      "tags": ["work", "projects"],
      "memory_bank": "Work",
      "score": 8
    }
  ]
}
```

**Store in metadata:**
```json
{
  "memory_score": 6,
  "memory_score_generated_at": "2026-04-30T15:23:14Z",
  "memory_score_source": "extraction",
  "needs_rescore": false
}
```

**Context size:** ~5-20K tokens  
**Isolation:** No reference to other memories, no injection candidates, no historical rankings

---

### Flow 2: Memory Injection Selection (separate call during `inlet()`)

**Trigger:** After all message processing, before sending response  
**Component:** `get_relevant_memories()` modified

**Step A - Vector Filtering (NO LLM):**
1. Get user's message embedding
2. Query top-N memories by vector similarity (e.g., 50-100 candidates)
3. Filter by `vector_similarity_threshold` valve
4. Result: ranked list of candidate memory IDs

**Step B - LLM Selection (SEPARATE LLM call, completely isolated):**

**Input to LLM:**
```
Current user message: "I'm working on fixing the memory system for Friday"

Candidate memories (filtered by similarity):
- mem_001: "User works on vLLM optimization" (similarity: 0.87, score: 8)
- mem_005: "User likes coffee with oat milk" (similarity: 0.45, score: 6)
- mem_012: "User has ADHD" (similarity: 0.52, score: 7)
[... 47 more candidates ...]

Task: Select the top 10 most relevant memories to inject into context.
Output: ["mem_001", "mem_012", "mem_034", ...]
```

**LLM Output:** Array of top-K memory IDs, in order of relevance to CURRENT message

**Context size:** ~20-50K tokens  
**Isolation:** No reference to extraction process, memory scoring history, or scoring formulas

---

### Flow 3: Background Rescoring (triggered when llama.cpp API idle)

**Trigger:** When `_is_llama_cpp_api_idle()` returns True  
**Timing:** Monitor llama.cpp API; if NO requests for 15 minutes, trigger  
**Component:** New method `_rescore_memories_batch()`

**Input to LLM (batch of 200):**
```
Score each memory 1-10 on INTRINSIC IMPORTANCE (standalone, no context):

- 1-3: Trivia, throwaway comments, low utility
- 4-6: Regular info, normal preferences, everyday stuff  
- 7-10: Core identity, critical facts, essential relationships

Memories to score:
1. "User likes coffee with oat milk" → score: ?
2. "User works on vLLM optimization" → score: ?
3. "User has ADHD" → score: ?
...200 total

Output JSON:
{
  "scores": [
    {"id": "mem_001", "score": 6},
    {"id": "mem_005", "score": 8},
    ...
  ]
}
```

**Context size:** ~50-100K tokens per batch  
**Isolation:** No reference to injection, extraction, or current conversation

---

## Implementation Specifications

### New Valves (UserValves class)

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

# Injection settings
max_memories_for_injection: int = Field(
    default=10,
    description="Number of top memories to inject after LLM selection"
)
```

---

### New Methods to Implement

#### 1. `_is_llama_cpp_api_idle() -> bool`
**Purpose:** Detect when llama.cpp API has no requests for N minutes

**Implementation approach:**
- Query OpenWebUI's API call logs or llama.cpp metrics
- Check: last_request_time vs current_time
- Return: True if idle > `memory_rescoring_api_idle_minutes`

**Usage:** Called at end of `inlet()` to check if background task should trigger

---

#### 2. `async def _rescore_memories_batch(user_id: str) -> Dict[str, Any]`
**Purpose:** Background batch-score old/unscored memories

**Algorithm:**
1. Query all memories for user without `memory_score` in metadata OR `needs_rescore: true`
2. Chunk into batches of `memory_rescoring_batch_size` (e.g., 200)
3. For each batch:
   - Build rescoring prompt (Prompt C from below)
   - Call LLM
   - Parse JSON response
   - For each memory, update metadata: `memory_score`, `memory_score_updated_at`
4. Log summary: `{scored: N, failed: N, elapsed_seconds: X}`
5. Return stats dict

**Error handling:**
- If LLM call fails: log error, continue next batch (non-blocking)
- If parse fails: assign default score 5.0, mark `needs_rescore: true`
- DO NOT block user interaction

---

#### 3. Modify `identify_memories()` extraction prompt
**Add to existing prompt:**
```
NEW: Each extracted memory MUST include a "score" field (1-10).

Score represents intrinsic importance (standalone value):
- 1-3: Trivia, throwaway comment, low utility
- 4-6: Regular info, normal preference, everyday behavior
- 7-10: Core identity, critical relationship, fundamental value

REQUIRED JSON FORMAT:
{
  "operation": "NEW",
  "content": "...",
  "tags": [...],
  "memory_bank": "...",
  "score": 6
}

Score based on MEMORY CONTENT ALONE, not context relevance.
```

---

#### 4. Modify `get_relevant_memories()` for Flow 2
**Current behavior:** Tries to score 6,945 memories with LLM (WRONG)

**New behavior:**
1. **Vector filter** (existing logic, keep unchanged):
   - Get embeddings
   - Find top-N by cosine similarity
   - Filter by `vector_similarity_threshold`
   - Result: 50-100 candidates

2. **LLM Selection** (NEW, completely separate):
   - Build injection selection prompt (Prompt B from below)
   - Input: current message + candidate summaries
   - LLM OUTPUT: top-K ranked memory IDs
   - Return these K memories to inject

3. **Remove:** All existing "uncached_memories" LLM scoring code

---

#### 5. Modify `_execute_memory_operation()` for scoring
**When NEW memory created:**
- Extract `score` field from LLM response in `identify_memories()`
- Store in metadata:
  ```json
  {
    "memory_score": score_value,
    "memory_score_generated_at": timestamp,
    "memory_score_source": "extraction",
    "needs_rescore": false
  }
  ```

**When UPDATE memory:**
- Preserve existing `memory_score`
- Update timestamp only

---

#### 6. Hook into `inlet()` for API idle check
**At very end of `inlet()`:**
```python
# Check if llama.cpp API is idle and rescoring should trigger
if self._is_llama_cpp_api_idle() and self.valves.enable_background_memory_rescoring:
    asyncio.create_task(self._rescore_memories_batch(user_id))
    logger.info(f"Background rescoring triggered for user {user_id} (API idle)")
```

---

## Prompts (Exact Text)

### Prompt A: Extraction with Score (modify existing)
```
[Existing extraction system prompt remains unchanged]

ADDITIONAL REQUIREMENT: Each extracted memory MUST include a "score" field:

{
  "operation": "NEW",
  "content": "User prefers oat milk in coffee",
  "tags": ["preference", "lifestyle"],
  "memory_bank": "Personal",
  "score": 6
}

SCORE SCALE (1-10, intrinsic importance only):
1-3:   Trivia, throwaway comment, incidental detail
4-6:   Regular info, typical preference, everyday behavior
7-10:  Core identity, critical relationship, fundamental value

SCORING RULE: Rate based on memory content ALONE, not context or conversation.
```

### Prompt B: Injection Selection (NEW, completely separate)
```
ROLE: You select the most relevant memories to inject into the AI's context right now.

CURRENT USER MESSAGE:
"{current_message}"

VECTOR-FILTERED CANDIDATES (N memories, sorted by embedding similarity):
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

### Prompt C: Background Rescoring (NEW, completely separate)
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

## API Idle Monitoring Implementation Notes

**Requirement:** Detect when llama.cpp has NO requests for 15 minutes

**Option 1: Query OpenWebUI's request logs**
- OpenWebUI logs all API calls to its database
- Query: most recent request timestamp to llama.cpp API
- If `(now - last_request_time) > 15 minutes`: idle

**Option 2: Query llama.cpp metrics**
- If llama.cpp exposes metrics endpoint
- Check timestamp of last request processed
- Same logic as Option 1

**Option 3: Track within plugin**
- Maintain `_last_llm_call_time` in plugin
- Update every time `query_llm_with_retry()` is called
- Check if idle before triggering rescoring

**Recommendation:** Option 3 (simplest, no external dependencies)

---

## Backfill Strategy for 6,945 Existing Memories

**On first startup after deployment:**

1. Query all memories without `memory_score` in metadata
2. If count > 0:
   - Log: `"Backfill initiated: {count} memories need scoring"`
   - Wait until llama.cpp API is idle (don't force rescoring during active use)
   - Trigger `_rescore_memories_batch()` immediately (don't wait 15 min)
3. Monitor progress in logs

**Result:** All old memories get scored gradually as API becomes idle

---

## Decision Summary (locked in)

| Decision | Answer | Rationale |
|----------|--------|-----------|
| **Backfill trigger** | API idle, not user idle | Don't block during active chat |
| **Vector first** | Yes | Embed model filters, LLM ranks |
| **Score when writing** | Yes | LLM extracts + scores together |
| **Idle threshold** | 15 minutes | Good balance |
| **Batch size** | 200 | 50-100K tokens per batch |
| **LLM in injection** | YES (Prompt B) | Separate isolated call |
| **Context bleed** | Zero | 3 independent prompts |

---

## Data Flow Diagram

```
USER SENDS MESSAGE
        ↓
   inlet() called
        ↓
   ┌─────────────────────────────────────────┐
   │ Flow 1: Extraction & Scoring            │
   │ identify_memories() + LLM (Prompt A)   │
   │ Output: memories WITH scores            │
   │ Store in metadata                       │
   └──────────────────┬──────────────────────┘
                      ↓
   ┌─────────────────────────────────────────┐
   │ Flow 2: Injection Selection             │
   │ get_relevant_memories() +  LLM (Prompt B)│
   │ Input: vector-filtered candidates      │
   │ Output: top-K ranked memories          │
   │ Inject into response context           │
   └──────────────────┬──────────────────────┘
                      ↓
              SEND RESPONSE
                      ↓
   ┌─────────────────────────────────────────┐
   │ Check: _is_llama_cpp_api_idle()?        │
   │ YES → trigger Flow 3                    │
   │ NO  → continue                          │
   └──────────────────┬──────────────────────┘
                      ↓
   [ASYNC, non-blocking]
   ┌─────────────────────────────────────────┐
   │ Flow 3: Background Rescoring            │
   │ _rescore_memories_batch() + LLM (C)     │
   │ Input: 200 unscored memories            │
   │ Output: scores, update metadata         │
   │ Repeat until all scored                 │
   └─────────────────────────────────────────┘
```

---

## Testing Checklist

- [ ] **Flow 1:** Create new memory, verify `memory_score` in metadata
- [ ] **Flow 2:** Inject memories, confirm separate LLM call (not extraction)
- [ ] **Flow 3:** Wait for API idle, confirm rescoring starts
- [ ] **Isolation:** Verify each LLM call uses isolated prompt (no context bleed)
- [ ] **Overflow:** Check token count never exceeds 128K per call
- [ ] **Backfill:** Manually remove scores from 10 memories, verify rescoring updates them
- [ ] **Performance:** Confirm no latency added to user messages

---

## Success Criteria

✅ Memory saving works without 625K token overflow  
✅ Memory injection uses Prompt B (separate isolated call)  
✅ Memory scoring happens during API idle (Prompt C)  
✅ New memories scored during extraction (Prompt A)  
✅ All 6,945 old memories eventually get scored  
✅ Zero context bleed between the 3 flows  
✅ No user-facing latency (background tasks non-blocking)
