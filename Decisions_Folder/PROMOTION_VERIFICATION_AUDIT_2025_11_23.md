# Pruning and Promotion Verification Audit - November 23, 2025

## Current State Analysis

### What You Set
- **Max Total Memories**: 3000 (custom valve)
- **Pruning Strategy**: FIFO or least_relevant (configurable)

### What We Found

#### ✅ GOOD: Max Total Memories Valve IS Respected

**Location**: `Adaptive_Memory_v3.py` line 4249
```python
max_memories = self.valves.max_total_memories  # Uses YOUR 3000 setting
```

The system reads from `self.valves.max_total_memories` directly, so your 3000 setting **overrides the default 200**.

**Verification**: 
- Line 4258: Checks if `current_count + new_count > max_memories` (using your 3000)
- This is respected throughout the pruning logic

✅ **Status**: WORKING CORRECTLY

---

#### ⚠️ PROBLEM: Deletion Happens Without Verification

**Location**: `Adaptive_Memory_v3.py` lines 4434-4460

**Current Flow (WRONG)**:
```python
for memory_id_to_delete in memories_to_prune_ids:
    try:
        # Step 1: Try to promote to Friday
        if memory_to_promote and FRIDAY_MEMORY_SYSTEM_AVAILABLE:
            try:
                memory_system = FridayMemorySystem()
                await memory_system.create_memory(  # ← Promotion happens
                    content=memory_content,
                    importance_level=5,
                    memory_type="archived",
                    tags=["promoted", "pruned", "archived"],
                )
                logger.debug("Successfully promoted...")  # ← Only logs success
            except Exception as promote_error:
                logger.warning(f"Could not promote...")  # ← Logs warning if it fails
        
        # ❌ PROBLEM: This happens REGARDLESS of promotion success!
        # Step 2: Delete from OpenWebUI (even if promotion failed!)
        delete_op = MemoryOperation(operation="DELETE", id=memory_id_to_delete)
        await self._execute_memory_operation(delete_op, user)
        pruned_count += 1
```

**The Issue**: 
1. Tries to promote to Friday
2. **Does NOT wait for confirmation** that memory is actually in Friday database
3. **Does NOT verify** memory_id exists in ai_memories.db
4. If promotion fails (exception caught), it still **deletes from OpenWebUI**
5. Result: **Memory lost** if Friday system promotion failed

---

## What Should Happen (According to Your Requirements)

```
Step 1: Memory exceeds limit in OpenWebUI
  ↓
Step 2: Identify memory to prune
  ↓
Step 3: PROMOTE to Friday
  ├─ Call: friday_memory_system.create_memory()
  ├─ Receive: memory_id from Friday system
  └─ Store this memory_id for verification
  ↓
Step 4: VERIFY in Friday Database
  ├─ Query: ai_memories.db
  ├─ Check: SELECT * FROM curated_memories WHERE memory_id = ?
  ├─ Confirm: Memory actually exists in database
  └─ Only proceed if found
  ↓
Step 5: DELETE from OpenWebUI
  ├─ Only after verification succeeds
  └─ Memory is now safe in Friday
  ↓
✅ Success: Memory preserved, not lost
```

---

## The Fix Needed

Replace the promotion logic (lines 4434-4460) with verification:

**Current Code** (WRONG):
```python
for memory_id_to_delete in memories_to_prune_ids:
    try:
        memory_to_promote = next(...)
        if memory_to_promote and FRIDAY_MEMORY_SYSTEM_AVAILABLE:
            try:
                memory_system = FridayMemorySystem()
                await memory_system.create_memory(...)  # Create but don't check
            except Exception as promote_error:
                logger.warning(...)
        
        delete_op = MemoryOperation(operation="DELETE", ...)  # ❌ Delete anyway!
        await self._execute_memory_operation(delete_op, user)
```

**Should Be** (CORRECT):
```python
for memory_id_to_delete in memories_to_prune_ids:
    try:
        memory_to_promote = next(...)
        promoted_successfully = False
        
        if memory_to_promote and FRIDAY_MEMORY_SYSTEM_AVAILABLE:
            try:
                memory_system = FridayMemorySystem()
                promoted_memory_id = await memory_system.create_memory(...)
                
                # ✅ VERIFY: Check if memory actually made it to database
                if promoted_memory_id:
                    # Query to confirm it's there
                    verification_result = await memory_system.execute_query(
                        "SELECT memory_id FROM curated_memories WHERE memory_id = ?",
                        (promoted_memory_id,)
                    )
                    if verification_result:  # If found in DB
                        promoted_successfully = True
                        logger.info(f"✅ Verified promotion: memory {promoted_memory_id} in Friday DB")
                    else:
                        logger.error(f"❌ Promotion failed verification: {promoted_memory_id} not in Friday DB")
            except Exception as promote_error:
                logger.warning(f"❌ Promotion exception: {promote_error}")
        
        # ✅ ONLY DELETE if promotion was verified
        if promoted_successfully or not FRIDAY_MEMORY_SYSTEM_AVAILABLE:
            delete_op = MemoryOperation(operation="DELETE", id=memory_id_to_delete)
            await self._execute_memory_operation(delete_op, user)
            pruned_count += 1
        else:
            logger.warning(f"⚠️ Skipping deletion of {memory_id_to_delete}: promotion not verified")
```

---

## Additional Checks Needed

### 1. Check if `create_memory()` Returns memory_id

Let me verify that `FridayMemorySystem.create_memory()` actually returns the memory_id:

**Location**: `friday_memory_system.py` - method `async def create_memory(...)`

The current code at line 4441 does NOT capture the return value:
```python
await memory_system.create_memory(...)  # ← Return value not captured!
```

Should be:
```python
promoted_memory_id = await memory_system.create_memory(...)  # ← Capture return value
```

### 2. Verify ai_memories.db Query Method Exists

The fix requires querying ai_memories.db to verify. Need to check if:
```python
await memory_system.execute_query(sql, params)
```

exists and works correctly.

---

## Summary of Issues Found

| Issue | Severity | Status | Impact |
|-------|----------|--------|--------|
| Max Total Memories valve ignored | ✅ FIXED | Working | Not an issue |
| Promotion not verified before deletion | ❌ CRITICAL | Needs fix | Memory can be lost |
| Return value from create_memory not captured | ❌ CRITICAL | Needs fix | Can't verify promotion |
| No database check after promotion | ❌ CRITICAL | Needs fix | Can't confirm memory saved |
| Exceptions don't prevent deletion | ❌ CRITICAL | Needs fix | Deletion happens even on failure |

---

## Risk Assessment

**Current Risk**: **HIGH**

If Friday Memory System fails during `create_memory()` call:
1. Exception is caught and logged as warning
2. **Deletion happens anyway**
3. Memory is lost from both systems
4. No recovery possible

**Scenarios**:
- Network timeout calling Friday system → Memory lost
- Database locked → Memory lost  
- Embedding service down → Memory lost
- Friday system crash → Memory lost
- Bad data → Memory lost

**Your Expectation** (from requirements): "Don't delete until verified in database"
**Current Behavior**: "Delete regardless of verification"

---

## Recommendation

### Immediate (Next Action)

Implement verification before deletion:

1. Capture `memory_id` returned from `create_memory()`
2. Query `ai_memories.db` to verify presence
3. Only delete if verification succeeds
4. Log all verification steps
5. Skip deletion if verification fails (safer to have duplicates than losses)

### Testing Before Production

Test these failure scenarios:
```
✓ Normal promotion → verify → delete
✓ Promotion exception → skip delete (memory stays in OpenWebUI)
✓ Verification fails → skip delete (memory stays in OpenWebUI)
✓ Friday system unavailable → skip delete (memory stays)
✓ Batch: multiple memories pruned with mixed results
```

### Configuration (Safe Defaults)

Set defaults to be conservative:
```python
# If verification fails, what should happen?
fail_behavior = "keep_memory"  # Don't delete
log_level = "error"  # Alert on every failure
retry_promotion = True  # Try again on next cycle
```

---

## What's Working Correctly ✅

1. **Max Total Memories valve IS respected** (uses your 3000)
2. **Pruning strategy selection works** (FIFO or least_relevant)
3. **Memories identified for pruning correctly**
4. **Promotion attempt is made** (just not verified)
5. **Error logging captures some issues**

---

## Files That Need Changes

- `/media/nate/Friday/Friday/Adaptive_Memory_v3.py` (lines 4434-4460)
  - Add verification before deletion
  - Capture and check return value from create_memory()
  - Query Friday DB to verify

---

## Your Request vs Reality

| Your Requirement | Current Behavior | Status |
|------------------|------------------|--------|
| "Don't delete until verified in Friday DB" | Deletes even if verification fails | ❌ NOT WORKING |
| "Pruning only after promotion verified" | Promotion attempted but not verified | ❌ NOT WORKING |
| "Respect my Max Total Memories valve (3000)" | Respects 3000 valve | ✅ WORKING |

---

**Recommendation**: Implement verification check before proceeding. This is a **data safety issue**.

