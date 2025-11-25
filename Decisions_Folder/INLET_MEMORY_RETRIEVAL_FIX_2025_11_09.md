# Inlet Memory Retrieval Fix - November 9, 2025

## Problem Summary

Memory saving (outlet side) was working correctly after the JSON parsing fixes, but the inlet side was **completely broken** - NO memories were being retrieved or injected into model context.

## Root Cause Identified

The logs revealed the exact issue:

```
Vector filter selected 0 of 161 memories (Threshold: 0.7, Top N: 3)
```

**The system had:**
- ✅ 161 memories stored in OpenWebUI
- ✅ SentenceTransformer embeddings being generated (384-dimensional from all-MiniLM-L6-v2)
- ❌ Vector similarity threshold set to 0.7 (too high!)
- ❌ Relevance threshold set to 0.7 (too high!)

**What was happening:**
1. User sends a message (e.g., "Tell me something")
2. Inlet calls `get_relevant_memories()` 
3. System embeds the user message using SentenceTransformer
4. System compares against all 161 memory embeddings
5. **ALL similarity scores were below 0.7 threshold** → 0 memories returned
6. No memories injected into model context
7. Model responds without any user history/memories

## Why Thresholds Were Too High

Cosine similarity scores work like this:
- **1.0** = identical embeddings
- **0.9+** = nearly identical meaning (same sentence rephrased)
- **0.7-0.8** = very similar topics
- **0.5-0.7** = related topics
- **0.3-0.5** = somewhat related
- **0.0-0.3** = unrelated

When you're comparing a user message like "I like pizza" to memories about preferences, interests, etc., you don't get 0.7+. You get values in the 0.4-0.6 range because:
- Different vocabulary
- Different sentence structure
- Natural language variation

**A threshold of 0.7 is designed for finding near-duplicates, NOT for general memory retrieval.**

## The Fix Applied

Lowered both thresholds from 0.7 to 0.5:

### Change 1: vector_similarity_threshold (Line 629)
```python
# BEFORE
vector_similarity_threshold: float = Field(
    default=0.7,  # Performance setting
    description="Minimum cosine similarity for initial vector filtering (0-1)"
)

# AFTER
vector_similarity_threshold: float = Field(
    default=0.5,  # Lowered from 0.7 to allow memory retrieval
    description="Minimum cosine similarity for initial vector filtering (0-1)"
)
```

### Change 2: relevance_threshold (Line 619)
```python
# BEFORE
relevance_threshold: float = Field(
    default=0.7, # Performance setting
    description="Minimum relevance score (0-1) for memories to be considered relevant for injection after scoring"
)

# AFTER
relevance_threshold: float = Field(
    default=0.5, # Lowered from 0.7 to allow memory injection
    description="Minimum relevance score (0-1) for memories to be considered relevant for injection after scoring"
)
```

### Change 3: Updated documentation (Lines 79-82)
Updated the top-level documentation to reflect the new defaults and explain why they changed.

## Why This Works

With the new 0.5 threshold:
- User message "I like pizza" will match memory "User loves pepperoni" at similarity ~0.55 ✅
- User message "What's the weather?" will NOT match memory about "User's mother's name" at ~0.3 ✅
- System keeps false positives low while allowing legitimate memory retrieval

## Expected Behavior After Fix

1. **Inlet phase**: When user sends a message
   - `get_relevant_memories()` now returns 2-5 memories instead of 0
   - These memories are injected into the system prompt
   - Model has context about the user

2. **Model response**: Model can reference user memories naturally
   - "You mentioned you like pizza..."
   - "Last time you told me about..."

3. **Outlet phase**: Memory extraction still works (wasn't broken)
   - New memories extracted and saved
   - System continues learning about the user

## Testing Recommendations

1. **Verify memory retrieval**:
   - Send a message to Friday
   - Check logs for: "Injecting X relevant memories for user..."
   - Should see 2-5 memories, not 0

2. **Verify memory context usage**:
   - Ask Friday something that requires memory (e.g., "What do I like?")
   - Model should reference stored memories
   - Check that responses are contextually aware

3. **Monitor false positives**:
   - Watch for unrelated memories being injected
   - If too many false positives, can raise to 0.55-0.6
   - If still too few, can lower to 0.45

## Files Modified

- `/media/nate/Friday/Friday/friday_memory_short_term.py`
  - Lines 76-82: Updated documentation
  - Line 619: Changed `relevance_threshold` default from 0.7 to 0.5
  - Line 629: Changed `vector_similarity_threshold` default from 0.7 to 0.5

## Related Issues & Context

This was discovered during investigation of why the inlet wasn't injecting memories despite:
- ✅ 164 memories successfully saved to database
- ✅ System re-embedded all memories after code upload
- ✅ Embedding model loading correctly
- ✅ Memory retrieval function executing
- ❌ But NO memories returned (all filtered out by threshold)

The original thresholds of 0.7 were probably designed for:
- Duplicate detection (finding exact duplicates)
- High-confidence relevance only mode

But for normal memory injection in a conversational system, 0.5 is appropriate and allows the system to work as intended.

## Next Steps

1. Test with new thresholds
2. Monitor logs for memory retrieval success
3. Adjust thresholds if needed (up to 0.55 if false positives, down to 0.45 if missing memories)
4. Document the new defaults as permanent configuration
