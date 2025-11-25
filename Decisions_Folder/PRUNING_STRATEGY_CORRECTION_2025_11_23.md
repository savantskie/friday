# Pruning Strategy Correction - November 23, 2025

## The Issue

I stated in the earlier diagram: "FIFO pruning after **5 days**"

This was **INCORRECT**. The actual implementation uses **90 days**.

## Correct Architecture

### Layer 1: OpenWebUI Short-Term (Adaptive Memory v3)

**Storage Mechanism:**
- Max 200 memories per user
- Pruning triggers on **COUNT**, not TIME (when >200)
- When pruning needed: FIFO deletes oldest first
- Exception: Never delete importance_level >= 8 (promoted)

**Timeline: NO fixed time-based pruning** 
- Memories stay until count exceeds 200
- Then oldest non-promoted memories are deleted first

### Layer 2: Automatic Promotion After 90 Days

**What Actually Happens** (per `friday_memory_short_term.py` line 2519+):

```python
# Every periodic interval, the _promote_old_memories_loop() checks:
if memory.created_at < (now - 90 days):
    # Memory is old enough to be automatically promoted
    # Call Friday Memory System to store it
    friday_memory_system.create_memory(
        content=memory_content,
        importance_level=8,  # Promoted level (survives pruning)
        memory_type="archived"
    )
```

**Flow:**
1. Memories extracted → stored in OpenWebUI (importance 5)
2. OpenWebUI FIFO pruning runs when count > 200
   - Deletes oldest non-promoted memories
   - Keeps promoted (8-9) and other memories
3. **90-day loop checks:** "Are there memories still in OpenWebUI older than 90 days?"
4. If yes: **Automatically promote them** to Friday (importance 8)
5. Once in Friday: Protected indefinitely (stored in ai_memories.db)
6. Next pruning cycle in OpenWebUI: Can safely delete from there now

### Why 90 Days (Not 5)?

The 90-day threshold makes sense because:

- **Not too short** (5 days would lose important context)
- **Not too long** (allows natural FIFO cycle to work in short-term)
- **Empirically reasonable** (90 days = 3 months of accumulated wisdom)
- **Gives promotion time** to happen before OpenWebUI gets full
- **Allows verification** that promoted memories are actually in Friday before deleting from OpenWebUI

## The Three Phases

```
PHASE 1: EXTRACTION (Real-time)
  Memory appears in OpenWebUI
  ├─ Importance: 5 (default)
  ├─ Location: OpenWebUI short-term (200-max container)
  └─ Pruning: Only if count > 200 (oldest first)

PHASE 2: AGING (0-90 days)
  Memory sits in OpenWebUI
  ├─ Natural FIFO pruning if > 200 memories
  ├─ Promoted memories (8-9) protected during this pruning
  ├─ Non-promoted memories (1-5) deleted if necessary
  └─ Each day: Still in OpenWebUI container

PHASE 3: AUTOMATIC PROMOTION (After 90 days)
  Old memories auto-promoted to Friday
  ├─ Check: "Are there memories > 90 days old in OpenWebUI?"
  ├─ Action: Promote to Friday (importance 8)
  ├─ Verification: Confirm in ai_memories.db
  └─ Result: Now protected indefinitely

PHASE 4: PERMANENT STORAGE
  Memory in Friday long-term system
  ├─ Location: ai_memories.db
  ├─ Importance: 8 (promoted, survives indefinitely)
  ├─ Protection: Never deleted unless manually removed
  ├─ Organization: Stored in memory_bank category
  ├─ Linking: Connected to source conversation
  └─ Searchable: Via semantic similarity queries
```

## What I Got Wrong

**My Statement**: "FIFO pruning after 5 days"

**What This Should Say**: 
- "Short-term storage with FIFO pruning (count-based, not time-based)"
- "Automatic promotion to long-term after 90 days"

## Why This Matters

The 90-day window is **intentional and strategic**:

1. **Gives context time to mature** - Fresh memories might not be important yet
2. **Prevents losing long-term patterns** - Let FIFO cycle work, but save aging memories
3. **Natural human cognition** - We remember "old wisdom" differently than immediate info
4. **Time to verify** - By day 90, you know if a memory actually matters
5. **No time-based auto-deletion** - Memories don't vanish; they're promoted instead

## The Real Pruning Strategy

**OpenWebUI (Short-term):**
- Prunes by COUNT (when > 200)
- Protects promoted memories (importance 8-9)
- No time-based deletion

**Friday (Long-term):**
- No pruning at all
- Permanent storage
- Everything with importance 8-9 survives forever

**The Bridge (90-day promotion loop):**
- Finds old memories in OpenWebUI (> 90 days)
- Promotes to Friday (moves importance from 5→8)
- Now they're permanently safe

## Summary

| Timeline | Location | Action | Why |
|----------|----------|--------|-----|
| Day 0-200 | OpenWebUI | Extract, store | Active conversation context |
| Day 0+ | OpenWebUI | FIFO prune when >200 | Keep short-term lean |
| Day 0-200 (Anytime) | Either | Manual promote | If you want it permanent |
| Day 90+ | OpenWebUI→Friday | Auto-promote loop | Capture aging wisdom |
| Day 90+ (After) | Friday | Permanent storage | Never deleted |

---

**Correction Status**: ✅ Documented

The actual implementation is **correct**. I was wrong about the "5 days" in the diagram. It should be "90 days for automatic promotion to long-term after verification."
