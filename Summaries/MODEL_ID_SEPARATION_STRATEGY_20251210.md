# Model ID Separation Integration Strategy
**Date:** December 10, 2025  
**Status:** Pre-Implementation Analysis  
**Author:** Eddie & Nate

---

## Current Architecture Analysis

### How Short-Term System Currently Works
1. **Model ID Source**: `body.get("model")` in both inlet (line 3227) and outlet (line 3820)
   - This pulls the **backend model identifier** (e.g., "llama3:latest", "mistral")
   - Not the OpenWebUI model card name

2. **Current Usage**:
   - Stored in `self._current_model` (line 3820)
   - Used for composite `conversation_id`: `f"{chat_id}_{user_id}_{model_id}"`
   - **Problem**: All conversations with same backend model share the same model ID, regardless of which preset they use

3. **Memory Storage** (via `_execute_memory_operation()`):
   - `AddMemoryForm()` accepts `metadata` dict (line 6436-6441)
   - Current metadata includes: `tags`, `memory_bank`, `timestamp`, `source`
   - **Missing**: No model/persona identifier in stored memories

### Where Metadata Comes From
- OpenWebUI sends `metadata["model"]["name"]` = the friendly preset name (e.g., "Friday", "Tara")
- This is passed to the filter functions but **we're not currently extracting it**
- The `__metadata__` parameter is NOT being captured in inlet/outlet signatures

---

## Proposed Solution: Non-Blocking Integration

### Key Principle
**Pre-populate `model_card_name` field at memory creation time** so that long-term memory promotion can later separate memories by actual model card name without requiring code changes to the retrieval flow.

### Implementation Strategy

#### Step 1: Extract Model Card Name in Inlet
```
Location: inlet() method, after user_id extraction (around line 3227)

ACTION:
- Add parameter `__metadata__: Optional[Dict[str, Any]] = None` to inlet() signature
- Extract: model_card_name = __metadata__.get("model", {}).get("name") if __metadata__ else None
- Fallback: Use body.get("model") if metadata unavailable
- Store: self._current_model_card_name = model_card_name
```

**Why non-blocking:**
- Gracefully falls back to body.get("model") if metadata not provided
- No changes to existing memory retrieval logic
- Optional parameter means backward compatible

#### Step 2: Add `model_card_name` to MemoryOperation Class
```
Location: MemoryOperation class definition (line 278)

ADDITION:
class MemoryOperation(BaseModel):
    operation: Literal["NEW", "UPDATE", "DELETE"]
    id: Optional[str] = None
    content: Optional[str] = None
    tags: List[str] = []
    memory_bank: Optional[str] = None
    model_card_name: Optional[str] = None  # NEW FIELD
```

**Why non-blocking:**
- Optional field, so existing code creating MemoryOperation continues to work
- No validation required, just passes through

#### Step 3: Populate `model_card_name` When Creating MemoryOperation
```
Location: Every place MemoryOperation(...) is created

EXAMPLE (from identify_memories):
    operation = MemoryOperation(
        operation="NEW",
        content=memory_content,
        tags=tags,
        memory_bank=memory_bank,
        model_card_name=self._current_model_card_name  # ADD THIS
    )
```

**Why non-blocking:**
- Uses instance variable `self._current_model_card_name` set in inlet
- Gracefully handles None if not available
- No changes to memory processing logic

#### Step 4: Store `model_card_name` in Memory Metadata
```
Location: _execute_memory_operation() metadata dict (line 6436-6441)

CHANGE FROM:
    metadata={
        "tags": tags_for_save,
        "memory_bank": operation.memory_bank or self.valves.default_memory_bank,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "adaptive_memory_v3",
    }

CHANGE TO:
    metadata={
        "tags": tags_for_save,
        "memory_bank": operation.memory_bank or self.valves.default_memory_bank,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "adaptive_memory_v3",
        "model_card_name": operation.model_card_name or "unknown",  # ADD THIS
    }
```

**Why non-blocking:**
- Metadata is already a dict, we're just adding another key
- OpenWebUI's memory system doesn't validate metadata keys, accepts anything
- Retrieval filters simply ignore unknown metadata fields

#### Step 5: Update outlet() Signature (Same as inlet)
```
Location: outlet() method signature (around line 3768)

ACTION:
- Add parameter: __metadata__: Optional[Dict[str, Any]] = None
- Extract and store model_card_name same as in inlet
```

**Why non-blocking:**
- outlet() just stores the value, doesn't use it immediately
- All downstream code continues to work normally

---

## What This Achieves

### Immediate Benefits (Short-term)
1. ✅ **Model card names are now pre-populated** in every memory created
2. ✅ **Non-invasive** - existing memory retrieval/injection unchanged
3. ✅ **Graceful degradation** - if metadata unavailable, falls back to backend model ID

### Future Benefits (Long-term Memory Promotion)
When memory promotion happens:
1. Memory promotion code can read `metadata["model_card_name"]`
2. Separate "Friday" memories from "Tara" memories during migration
3. **No changes needed to inlet/outlet/retrieval logic now** - promotion logic handles it

---

## Code Changes Required

### Minimal, Non-Blocking Changes

| File | Location | Change | Impact |
|------|----------|--------|--------|
| `friday_memory_short_term.py` | Line ~3180 | Add `__metadata__` param to `inlet()` | Backward compatible (optional param) |
| `friday_memory_short_term.py` | After user_id extraction (inlet) | Extract and store `model_card_name` | No functional impact, just storage |
| `friday_memory_short_term.py` | Line 278 | Add `model_card_name` field to `MemoryOperation` | Optional field, all existing code still works |
| `friday_memory_short_term.py` | All `MemoryOperation()` creations | Pass `model_card_name=self._current_model_card_name` | Fills new optional field |
| `friday_memory_short_term.py` | Line ~6436 | Add `"model_card_name"` to metadata dict | Just adds a key to dict |
| `friday_memory_short_term.py` | Line ~3768 | Add `__metadata__` param to `outlet()` | Same as inlet |

---

## Verification Strategy

1. **Short-term**: After changes, check that memories are being created with `model_card_name` in metadata
   - Query OpenWebUI memory database, inspect metadata field
   - Should see `"model_card_name": "Friday"` instead of `"model_card_name": "unknown"`

2. **Long-term**: When memory promotion is implemented
   - Memories with `model_card_name: "Friday"` go to Friday's long-term store
   - Memories with `model_card_name: "Tara"` go to Tara's long-term store
   - No conflicts between personae

---

## Potential Issues & Mitigations

| Issue | Mitigation |
|-------|-----------|
| `__metadata__` not provided by OpenWebUI | Graceful fallback to `body.get("model")` |
| `model_card_name` is None/missing | Store as `"unknown"` in metadata |
| Existing memories without `model_card_name` | Long-term promotion can handle both old and new formats |
| Order of operations confusion | This change doesn't affect order, just adds data |

---

## Why This Approach is Better Than Alternatives

**Option A: Immediate memory separation in retrieval (BLOCKED)**
- Would require changing query logic immediately
- Risk of breaking existing memory retrieval
- More complex

**Option B: Add model_card_name field later (CURRENT APPROACH)**
- Pre-populate now while it's easy
- Let long-term promotion handle the separation
- No immediate changes to business logic
- Lower risk, additive only

**Option C: Only use backend model ID (CURRENT STATE)**
- "Friday" and "Tara" share memories if on same backend
- Defeats the purpose of persona separation
- Unacceptable for role-playing models

---

## Next Steps

1. ✅ **Current**: Analysis complete, you understand the approach
2. **When ready**: Implement the 5 code changes listed above
3. **Verify**: Check that memories are storing `model_card_name` correctly
4. **Later**: Update long-term memory promotion to use this field
5. **Later**: Consider memory retrieval filtering by `model_card_name` (optional enhancement)

