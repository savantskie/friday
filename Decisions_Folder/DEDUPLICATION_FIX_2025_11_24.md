# Deduplication Fix - Duplicate Memory Saving Issue

**Date**: November 24, 2025  
**Issue**: Memories were being saved twice in short-term memory store despite deduplication being enabled  
**Status**: FIXED ✅

## Problem Analysis

### Root Cause
In `_execute_memory_operation()` function (lines 6054-6176 of `Adaptive_Memory_v3.py`), the code was calling `add_memory()` **twice** for each new memory:

1. **First call (line ~6054)**: Create the memory with initial content
2. **Second call (line ~6166)**: Attempt to "tag" the memory with the embedding model tag

The second call was problematic because:
- `add_memory()` without a memory ID parameter creates a **NEW** memory instead of updating an existing one
- This resulted in a duplicate memory being created with the same content
- The deduplication system couldn't catch this because both memories were created before the next deduplication check

### Why This Happened
The code was trying to add the embedding model tag (e.g., `__embedding_model:nomic_embed_text_v1.5_768d`) to the memory AFTER creation. This was based on a misunderstanding of OpenWebUI's `add_memory()` function, which creates new memories rather than updating existing ones.

### Evidence from Logs
```
NEW memory created: [Tags: identity, behavior] User identifies themself...
NEW memory created: [Tags: emotional_tone, intent_signal] User is expressing frustration...
NEW memory created: [Tags: behavior, preference] User has observed that the system...
Successfully processed and saved 3 memories
```

The logs show the memories being created, but the actual duplicates in the UI showed pairs of identical memories.

## Solution

### Implementation
Move the embedding model tag into the **initial `add_memory()` call** metadata, eliminating the need for a second call.

**Changes Made:**

1. **Lines 6048-6054**: Compute the embedding model tag and add it to the tags list BEFORE calling `add_memory()`
   ```python
   tags_for_save = list(operation.tags) if operation.tags else []
   EMBEDDING_MODEL_TAG = self._get_embedding_model_tag()
   if EMBEDDING_MODEL_TAG not in tags_for_save:
       tags_for_save.append(EMBEDDING_MODEL_TAG)
   ```

2. **Lines 6054-6066**: Use `tags_for_save` in the metadata of the first (and only) `add_memory()` call
   ```python
   form_data=AddMemoryForm(
       content=formatted_content,
       metadata={
           "tags": tags_for_save,  # Include embedding tag here
           "memory_bank": ...,
           ...
       },
   )
   ```

3. **Lines 6150-6176**: REMOVED the second `add_memory()` call that was attempting to tag the memory
   - The embedding is now generated and cached in memory, but no second DB write occurs
   - This eliminates the duplicate memory creation

### Impact
- **Before**: 2 `add_memory()` calls → 2 memories created (duplicates)
- **After**: 1 `add_memory()` call → 1 memory created (no duplicates)

## Testing

### How to Verify
1. Save a new memory preference (e.g., "I like chocolate")
2. Check the short-term memory store - should see ONLY ONE copy
3. Check deduplication valve is enabled in OpenWebUI settings
4. Verify the embedding model tag is present in memory tags

### Related Valves
- `deduplicate_memories` = True (enabled)
- `use_embeddings_for_deduplication` = True (enabled)
- `embedding_similarity_threshold` = 0.97

## Code References
- File: `/media/nate/Friday/Friday/Adaptive_Memory_v3.py`
- Function: `_execute_memory_operation()`
- Lines changed: 6045-6176

## Notes
- The embedding model tag will now be saved in the memory's metadata on first creation
- The embedding is still generated and cached for vector similarity searches
- No changes needed to deduplication logic - it was working correctly, just receiving duplicate inputs
