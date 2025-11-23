# Analysis: Memory Tool Failures - November 22, 2025

## Summary of Three Failures

### 1. `get_upcoming_appointments` - Error: "No item with that key"

**Root Cause**: The method tries to access dictionary keys on a `sqlite3.Row` object that may not exist.

**Code Location**: Line 4629-4675 in `friday_memory_system.py`

**Problem Code**:
```python
return {
    "status": "success",
    "count": len(rows),
    "appointments": [
        {
            "appointment_id": r["appointment_id"],  # ← May fail if key not in Row
            "title": r["title"],
            "scheduled_datetime": r["scheduled_datetime"],
            "duration_minutes": r["duration_minutes"],  # ← NOT IN TABLE SCHEMA!
            "description": r["description"]
        }
        for r in rows
    ]
}
```

**Issues**:
1. Requesting `duration_minutes` which doesn't exist in the appointments table
2. The table schema has NO `duration_minutes` column (checked lines 945-980)
3. Other columns should exist but may be NULL or missing from old database records

**Database Schema Check**:
Appointments table has these columns:
- appointment_id ✅
- timestamp_created ✅
- scheduled_datetime ✅
- title ✅
- description ✅
- location ✅
- status ✅
- cancelled_at ✅
- completed_at ✅
- source_conversation_id ✅
- embedding ✅
- created_at ✅
- **user_id** ✅ (New)
- **model_id** ✅ (New)

Missing: `duration_minutes` ❌

---

### 2. `get_recent_context` - Error: "Unexpected keyword argument 'user_id'"

**Root Cause**: Method signature mismatch. The wrapper passes `user_id` but the underlying method doesn't accept it.

**Code Location**: Line 5256-5289 (wrapper) calling Line 427 (implementation)

**Problem Code**:
```python
# In get_recent_context() at line 5267:
messages = await self.conversations_db.get_recent_messages(
    limit, session_id, days_back, user_id=user_id, model_id=model_id  # ← Passing user_id
)

# In get_recent_messages() at line 427:
async def get_recent_messages(self, limit: int = 10, session_id: str = None, days_back: int = 7) -> List[Dict]:
    # ↑ NO user_id or model_id parameters!
```

**The Design Issue**:
- `get_recent_context()` (the public API) accepts `user_id` and `model_id`
- But it delegates to `get_recent_messages()` which doesn't support them
- This is a **user/model isolation** feature that was planned but not fully implemented

**Current Database Structure**:
```sql
-- messages table has NO user_id or model_id columns
-- conversations table may have them, but query doesn't filter by them
```

---

### 3. `complete_reminder` - Error: "No item with that key"

**Root Cause**: Similar to get_upcoming_appointments - accessing keys that don't exist in Row objects.

**Code Location**: Line 4424-4520 in `friday_memory_system.py`

**Problem Code**:
```python
def _select_by_due(due: str):
    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.execute(
            "SELECT reminder_id, title, due_datetime "  # ← Only 3 columns
            "FROM reminders "
            "WHERE due_datetime = ? AND (completed IS NULL OR completed = 0)",
            (due,)
        )
        return cur.fetchall()

# Later, tries to access:
options = [
    {"reminder_id": row[0], "title": row[1], "due_datetime": row[2]}
    for row in matches
]
```

**Issue**: Using tuple indexing `row[0]`, `row[1]`, `row[2]` is actually CORRECT here - tuples don't return dict-like rows.

**The Real Issue**: The query returns tuples (not sqlite3.Row objects) because this method uses direct `sqlite3.connect()` instead of the DatabaseManager class.

Let me verify the full context...

---

## User/Model Isolation Investigation

This is the deeper architectural question: **How should user_id be implemented?**

### Current State

**Option A: Already Done - Columns Added to Tables**
- ✅ `curated_memories` table has `user_id` and `model_id` columns (line 681)
- ✅ `appointments` table has `user_id` and `model_id` columns (line 928)  
- ✅ `reminders` table has `user_id` and `model_id` columns (line 1002)
- ✅ Conversations table likely has them (need to verify)

**Option B: Partially Done - Methods Accept But Don't Use**
- ✅ `create_memory(user_id, model_id)` accepts them (line 5299)
- ✅ `get_recent_context(user_id, model_id)` accepts them (line 5257)
- ❌ `get_recent_context` tries to pass to `get_recent_messages()` which DOESN'T accept them
- ❌ Query in `get_recent_messages()` doesn't filter by user_id or model_id (line 437-453)

### Key Questions for Discussion

1. **Should user_id be:**
   - A column in EVERY table (memories, conversations, appointments, reminders)?
   - A separate "user_namespace" table that all records reference?
   - Part of a composite key (user_id + model_id + memory_id)?

2. **What is user_id supposed to represent?**
   - The person using Friday (your Discord ID or username)?
   - The source system (LM Studio vs Ollama vs OpenWebUI)?
   - The workspace/organization?

3. **Should filtering be automatic?**
   - When a tool is called, should it ALWAYS filter by the calling user's ID?
   - Should tools have visibility into the current_user_id from context?

4. **Backwards compatibility:**
   - Old records have user_id = NULL - how should they be handled?
   - Should NULL user_id mean "visible to all" or "orphaned/invalid"?

5. **Performance:**
   - Should we add indexes on (user_id, model_id, created_at)?
   - Should we have a "default" user for single-user setups?

---

## Files Affected

### Needs Fixing Now
- `friday_memory_system.py` line 4629-4675: `get_upcoming_appointments()`
  - Remove or handle `duration_minutes` key access
  
- `friday_memory_system.py` line 427-453: `get_recent_messages()`
  - Add `user_id` and `model_id` parameters
  - Add filtering logic

- `friday_memory_system.py` line 4424-4520: `complete_reminder()`
  - Verify if this is actually failing or if the error is elsewhere

### Architecture Decisions Needed
- Should user_id filtering be AUTOMATIC or OPTIONAL?
- How should NULL user_id records be handled?
- Should we add a "user context" to the MCP server that flows through all calls?

---

## Recommended Approach (Awaiting Discussion)

**Before implementing any fix:**
1. ✋ **STOP** - Don't change database schema yet
2. 🤔 **DISCUSS** - What is user_id for? Isolation? Multi-tenancy? Audit?
3. 📋 **DESIGN** - Should it be optional or mandatory? Default value?
4. ✅ **IMPLEMENT** - Once architecture is clear

**Quick Fixes (Can do immediately):**
1. Remove `duration_minutes` from `get_upcoming_appointments()` response
2. Make `user_id` and `model_id` optional in `get_recent_context()`

**Architectural Fixes (Need discussion):**
1. Add user_id filtering to `get_recent_messages()`
2. Decide if all tools should accept user_id/model_id
3. Implement consistent handling across all 40+ tools
