# Duplicate Memory Cleanup Feature
**Date**: November 24, 2025  
**Issue**: Accidental duplicate memories from tagging bug were filling up memory store  
**Status**: IMPLEMENTED ✅

## Problem
The tagging bug (now fixed) was calling `add_memory()` twice, creating duplicate memories:
- Memory A: Without embedding tag (the original)
- Memory B: With embedding tag (the duplicate from the second call)

These pairs accumulated and were wasting storage space.

## Solution: Automatic Cleanup

### How It Works
When `process_memories()` is called:

1. **Retrieves existing memories** for the user
2. **Calls `_cleanup_tagged_duplicates()`** to identify and remove pairs
3. **Proceeds with normal deduplication** on new memories

### The Cleanup Algorithm

```python
1. Group all memories by content (stripping tags)
   Example:
   - "User likes coffee" (ID: abc123, tags: [preference])
   - "User likes coffee" (ID: def456, tags: [preference, __embedding_model:...])
   
2. For each group with duplicates:
   - Sort by: has embedding tag first (prefers tagged version)
   - Keep the FIRST one (tagged if available)
   - DELETE all others

3. Result:
   - Only one "User likes coffee" memory remains
   - It has the embedding tag (metadata preserved)
```

### Why Keep the Tagged Version?
- ✅ Has the embedding model metadata
- ✅ Already embedded and cached
- ✅ Skipped on next retroactive embedding run
- ✅ More complete record

## Implementation Details

### Function: `_cleanup_tagged_duplicates()`
- **Location**: `Adaptive_Memory_v3.py` after `process_memories()`
- **When Called**: During `process_memories()` initialization, if deduplication is enabled
- **Non-blocking**: Errors don't stop memory processing
- **User Retrieval**: Gets user object for delete operations

### Detection Logic
- Strips `[Tags: ...]` prefix from memory content
- Normalizes to lowercase and strips whitespace
- Groups memories by cleaned content
- Identifies groups with >1 memory as duplicates

### Logging
When duplicates are found:
```
[CLEANUP] Removing duplicate memory: def456 (content: User likes coffee...) - keeping abc123 with tags
[CLEANUP] Removed 5 duplicate memories for user user_12345
```

## Performance Impact
- **Minimal**: Only runs during memory processing, not on every message
- **One-time cleanup**: Removes old duplicates as memories are accessed
- **Non-blocking**: Errors don't affect normal operation

## Expected Behavior

### First Run (after deployment)
```
When you process a memory:
[CLEANUP] Removed 15 duplicate memories for user user_12345
[CLEANUP] Removed 8 duplicate memories for user user_67890
```

### Subsequent Runs
```
[CLEANUP] Removed 0 duplicate memories for user user_12345  # (if no duplicates exist)
```

## Testing

### To Verify It's Working:
1. Check logs for `[CLEANUP]` messages
2. Count memories before and after - should decrease
3. Verify no duplicate pairs remain in OpenWebUI

### Example Log Output:
```
Starting memory processing for user abc123
[CLEANUP] Removing duplicate memory: mem_456 (content: I like pizza...) - keeping mem_123 with tags
[CLEANUP] Removing duplicate memory: mem_789 (content: I like pizza...) - keeping mem_123 with tags
[CLEANUP] Removed 2 duplicate memories for user abc123
Processing 1 new memory operations
```

## Edge Cases Handled

### 1. No Duplicates
- Function returns early (not enough memories)
- No log spam

### 2. Group with Multiple Duplicates
- Keeps tagged version first, deletes ALL others
- Example: 1 tagged + 3 untagged → keeps 1, deletes 3

### 3. All Untagged Duplicates
- Sorts by ID alphabetically
- Keeps first by ID, deletes rest
- (This shouldn't happen with the fix in place)

### 4. Deletion Fails
- Logs warning but continues
- Non-blocking error
- Duplicate may remain, but won't break system

## Combined with Deduplication Fix
This cleanup feature **complements** the deduplication fix:

**Deduplication Fix** (earlier changes):
- Prevents NEW duplicates from being created
- Tags memories on initial save

**Cleanup Feature** (this change):
- Removes OLD duplicates from tagging bug
- Consolidates pairs into single memory
- Gradually frees up storage

Together they:
1. ✅ Stop creating duplicates (fix prevents them)
2. ✅ Clean up existing duplicates (cleanup removes them)
3. ✅ Preserve metadata (keeps tagged versions)

## Files Modified
- `/media/nate/Friday/Friday/Adaptive_Memory_v3.py`
  - Added `_cleanup_tagged_duplicates()` function
  - Modified `process_memories()` to call cleanup on initialization

## Code References
- Function: `_cleanup_tagged_duplicates()` (lines ~6050-6127)
- Call site: `process_memories()` (line ~5831)
- Uses: `delete_memory_by_id()` from OpenWebUI
- Uses: `Users.get_user_by_id()` from OpenWebUI
