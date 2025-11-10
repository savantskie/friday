# Inlet Memory Retrieval Issue Analysis - November 9, 2025

## Problem Summary
Memories are saving correctly to the outlet (after fixes), but the inlet side is NOT retrieving and injecting memories into the model context. The LLM is not getting user memories to work with.

## Code Flow Analysis

### Inlet Function Entry Point
**Location**: `/media/nate/Friday/Friday/Adaptive_Memory_v3.py`, Line 1742

The inlet function should:
1. Extract user ID from `__user__`
2. Load valves (user config)
3. Check guard flags
4. Retrieve memories via `get_relevant_memories()`
5. Inject memories into `body["messages"]` via `_inject_memories_into_context()`

### Current Inlet Memory Retrieval Code (Lines 1954-1972)

```python
# --- Memory Injection --- #
if self.valves.show_memories and not self._embedding_feature_guard_active:
    try:
        logger.debug(f"Retrieving relevant memories for user {user_id}")
        relevant_memories = await self.get_relevant_memories(
            current_message=final_message if final_message else "",
            user_id=user_id,
            user_timezone=user_valves.timezone
        )
        if relevant_memories:
            logger.info(f"Injecting {len(relevant_memories)} relevant memories for user {user_id}")
            self._inject_memories_into_context(body, relevant_memories)
        else:
            logger.debug(f"No relevant memories found for user {user_id}")
    except Exception as e:
        logger.error(f"Error retrieving/injecting memories: {e}\n{traceback.format_exc()}")
        await self._safe_emit(__event_emitter__, {"type": "error", "content": "Error retrieving relevant memories."})
```

### Key Problems Identified

#### 1. **Guard Conditions Blocking Retrieval**
```python
if self.valves.show_memories and not self._embedding_feature_guard_active:
```

The code checks `_embedding_feature_guard_active`. This flag is initialized in `__init__` (line 1133) as `False`, but if it's being set to `True` somewhere, it will block ALL memory retrieval. 

**Search Results**: `_embedding_feature_guard_active` is:
- Initialized to `False` in `__init__` (line 1133)
- Checked in inlet (line 1816, 1954)
- May be set to `True` by guard logic elsewhere

**Missing**: No code path currently SETS this flag to `True` based on error conditions.

#### 2. **Embedding Generation Issue**
The current version uses async LM Studio embeddings via `get_nomic_embedding()` (line 351):

**Location**: Line 3423-3493 in `get_relevant_memories()`

```python
try:
    user_embedding = await get_nomic_embedding(current_message)
    if user_embedding is None:
        logger.warning("Failed to get embedding for user message from LM Studio.")
        if not self.valves.use_llm_for_relevance:
            logger.warning("Cannot calculate relevance without embedding...")
            return []
except Exception as e:
    self.error_counters["embedding_errors"] += 1
    logger.error(f"Error computing embedding for user message: {e}...")
    if not self.valves.use_llm_for_relevance:
        logger.warning("Cannot calculate relevance due to embedding error...")
        return []
```

**Potential Issue**: If `get_nomic_embedding()` fails (LM Studio not responding, endpoint wrong, etc.), and `use_llm_for_relevance` is `False`, the function returns empty list immediately.

**Default Configuration**: 
- `use_llm_for_relevance` = `False` (see Valves, performance setting)
- `vector_similarity_threshold` = 0.7
- `top_n_memories` = 3
- `related_memories_n` = 5

So: **If embeddings fail → returns empty → no memories injected**

#### 3. **Embedding Model URL Hardcoded**
**Location**: Line 351

```python
async def get_nomic_embedding(text: str, lm_studio_url: str = "http://192.168.1.50:1234/v1/embeddings") -> Optional[np.ndarray]:
```

**Problem**: URL is hardcoded to `192.168.1.50:1234`. This is Nate's LOCAL IP on his network.

In OpenWebUI running in Docker, this URL likely doesn't resolve correctly. It should probably be:
- `http://host.docker.internal:1234/v1/embeddings` (Docker bridge for host)
- OR: `http://localhost:1234/v1/embeddings` (if LM Studio in same container)
- OR: configurable via valves

#### 4. **Memory Retrieval Function Logic Issue**
**Location**: Line 3389-3780 in `get_relevant_memories()`

The function structure:
1. Gets existing memories
2. Tries to embed user message
3. If embedding fails and no LLM fallback → **returns empty list**
4. If embedding succeeds → calculates similarities
5. Filters by `vector_similarity_threshold`
6. Either returns directly or calls LLM for relevance

**Critical Path**: If `get_nomic_embedding()` returns `None` for any reason, the inlet fails silently and returns empty.

#### 5. **Missing Final Debug Output**
The inlet logs say it's attempting retrieval, but no indication of whether embeddings succeeded/failed, or why memories aren't found.

Added logging shows:
- Line 3408: `logger.info(f"🔍 get_relevant_memories START: vector_similarity_threshold={self.valves.vector_similarity_threshold}...")`
- But no similar logging at end of the embedding section

## Root Cause Hypothesis

**Most Likely**: `get_nomic_embedding()` is failing because:
1. LM Studio endpoint URL is wrong (192.168.1.50 unreachable from Docker)
2. LM Studio is not running/not accessible
3. Embedding model not loaded in LM Studio
4. Timeout on embedding call

Result: User embedding = `None` → Function returns `[]` → No memories injected

## Comparison with Original

**Original Code** (Adaptive_Memory_v3_original.md, line 2971):
```python
if self.embedding_model:
    user_embedding = self.embedding_model.encode(
        current_message, normalize_embeddings=True
    )
else:
    logger.warning("Embedding model not available...")
    if not self.valves.use_llm_for_relevance:
        return []
```

Uses synchronous embedding with `self.embedding_model` (SentenceTransformer).

**Current Code**:
Uses async LM Studio embedding with hardcoded IP.

## What Needs to Be Fixed

1. **Fix the hardcoded LM Studio URL** - Make it configurable or use Docker-friendly default
2. **Add better error logging** - Understand exactly why embeddings are failing
3. **Add fallback mechanism** - If embeddings fail but memories exist, try LLM-only mode
4. **Verify embedding call** - Test that LM Studio embedding endpoint is actually working
5. **Check guard condition** - Ensure `_embedding_feature_guard_active` isn't being set to True inappropriately

## Testing Strategy

1. Check LM Studio logs for embedding requests
2. Add temporary verbose logging in `get_nomic_embedding()` to see if it's being called
3. Test embedding endpoint manually
4. Check if `get_relevant_memories()` returns empty vs. populated
5. Verify memories exist in OpenWebUI (check database)

## Files to Investigate

- `/media/nate/Friday/Friday/Adaptive_Memory_v3.py` - Main file with inlet/outlet
  - Line 351: `get_nomic_embedding()` function
  - Line 1742: `inlet()` function
  - Line 1954: Memory retrieval in inlet
  - Line 3389: `get_relevant_memories()` function
  - Line 3423: Embedding call and error handling

- `/media/nate/Friday/Friday/Logs/` - LM Studio and OpenWebUI logs (if available)

## Next Steps

1. Verify LM Studio embedding endpoint is accessible
2. Fix hardcoded URL to work in Docker environment
3. Add comprehensive logging to trace the failure
4. Test memory retrieval with a simple test case
