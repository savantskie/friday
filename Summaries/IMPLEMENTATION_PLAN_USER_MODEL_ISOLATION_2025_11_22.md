# Implementation Plan: User/Model Memory Isolation - AWAITING APPROVAL

## What You've Told Me (Confirmed Understanding)

### Architecture Decision ✅ APPROVED
1. **user_id is MANDATORY** - every record MUST have it, cannot be NULL
2. **model_id is MANDATORY** - every record MUST have it, cannot be NULL
3. **Together they're the isolation key** - user "Nate" + model "Friday" is different from user "Nate" + model "OtherModel"
4. **Multi-user multi-model support** - Friend uses Friday → separate memories. You use different model → separate memories.
5. **Scope: Memory tools only** - search_memories, create_memory, get_recent_context, etc. Not other system tools.
6. **Backwards compatibility**: Old records default to user="Nate" (your default user)
7. **Duration minutes** - Already added to appointments table with CHECK constraint. Need to include in responses.

---

## Implementation Plan - PHASE BY PHASE

### PHASE 1: Fix Simple Issues (30 minutes)
**Changes needed:**
1. **get_upcoming_appointments()** - Add duration_minutes to response (1 line)
   - File: `friday_memory_system.py` line ~4663
   - Change: Add `"duration_minutes": r["duration_minutes"],` to response dict

2. **Debug complete_reminder error**
   - File: `friday_memory_system.py` line ~4424
   - Find: What exact key is failing in the Row object
   - Fix: Appropriate None check or column selection

### PHASE 2: Add user_id/model_id to Messages/Conversations (1 hour)
**What exists:**
- ✅ Conversations table ALREADY has user_id and model_id columns

**What needs checking:**
- Messages table - does it have user_id and model_id? If not, add them.
- Update schema if needed

**Actions:**
1. Verify messages table schema
2. If missing: Add user_id and model_id columns to messages
3. Add migration logic for old records (default to "Nate")

### PHASE 3: Fix get_recent_messages() Signature (45 minutes)
**File:** `friday_memory_system.py` line 427

**Current:**
```python
async def get_recent_messages(self, limit: int = 10, session_id: str = None, days_back: int = 7) -> List[Dict]:
```

**New:**
```python
async def get_recent_messages(
    self, 
    limit: int = 10, 
    session_id: str = None, 
    days_back: int = 7,
    user_id: str = "Nate",  # MANDATORY, defaults to Nate for legacy
    model_id: str = "Friday"  # MANDATORY, defaults to Friday
) -> List[Dict]:
```

**Update the query to filter:**
```sql
WHERE m.timestamp >= ? 
AND m.user_id = ? 
AND m.model_id = ?
```

### PHASE 4: Fix get_recent_context() to Pass Parameters Correctly (15 minutes)
**File:** `friday_memory_system.py` line 5256

**Current issue:**
- Passes user_id/model_id to get_recent_messages()
- Method now accepts them, so this should just work

**Action:** Add default values and ensure parameters flow through

### PHASE 5: Update All Memory Tool Signatures (2 hours)
**Tools to update:**
- search_memories() - add user_id, model_id parameters
- create_memory() - already has them, ensure default "Nate"
- update_memory() - add user_id, model_id for context
- get_ai_insights() - add user_id, model_id
- store_ai_reflection() - add user_id, model_id
- store_conversation() - add user_id, model_id
- etc.

**Pattern for each:**
```python
async def search_memories(
    self, 
    query: str,
    limit: int = 10,
    user_id: str = "Nate",  # NEW - MANDATORY
    model_id: str = "Friday",  # NEW - MANDATORY
    ...other params...
):
    # Update query to filter by user_id AND model_id
    rows = await self.ai_memory_db.search_memories(
        query, limit, user_id=user_id, model_id=model_id, ...
    )
```

### PHASE 6: Update Database Methods in Each Database Class (2 hours)
**Files affected:**
- AIMemoryDatabase (line 668) - search_memories, create_memory, update_memory, etc.
- ConversationDatabase (line 106) - store_conversation, get_recent_messages already updated
- ScheduleDatabase (line 868) - appointments, reminders

**For each method:**
1. Add user_id, model_id parameters (MANDATORY, defaults to "Nate", "Friday")
2. Update WHERE clause to filter by both
3. Add to INSERT statements

### PHASE 7: Update MCP Server Tool Wrappers (1 hour)
**File:** `friday_memory_mcp_server.py`

**Current:** Tools call memory system methods without user_id/model_id
**New:** Extract user_id/model_id from context or request

**Example change:**
```python
# Current
result = await self._protected_tool_call(self.memory_system.search_memories(**filtered_args))

# New
user_id = arguments.get("user_id", "Nate")
model_id = arguments.get("model_id", "Friday")
filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
result = await self._protected_tool_call(
    self.memory_system.search_memories(**filtered_args, user_id=user_id, model_id=model_id)
)
```

---

## Database Changes Needed

### Tables that MUST have user_id and model_id:
- ✅ appointments (line 945) - ALREADY HAS
- ✅ reminders (line 1018) - ALREADY HAS  
- ✅ curated_memories (line 681) - ALREADY HAS
- ✅ conversations (you said already done)
- ❓ messages (in conversations table) - NEED TO VERIFY
- Other tables?

### New Constraints:
```sql
-- All new inserts MUST provide user_id and model_id
-- These cannot be NULL
-- DEFAULT values: user_id='Nate', model_id='Friday'

-- Example migration for old records:
UPDATE conversations SET user_id = 'Nate', model_id = 'Friday' WHERE user_id IS NULL;
UPDATE messages SET user_id = 'Nate', model_id = 'Friday' WHERE user_id IS NULL;
```

---

## Checklist Before We Start

**APPROVAL NEEDED for:**

- [ ] Should I use defaults "Nate" and "Friday" for all new user_id/model_id params?
- [ ] Should ALL memory tool parameters include user_id and model_id in the MCP schema?
- [ ] Or should user_id/model_id be extracted from OpenWebUI context instead?
- [ ] Messages table - should it get user_id/model_id columns too?
- [ ] Do you want me to update the persistent-ai-memory repo too, or just the main Friday system?

---

## Execution Timeline (If Approved)

**If you approve the plan:**

1. **Phase 1** (30 min): Fix duration_minutes and debug complete_reminder
2. **Phase 2** (1 hour): Verify/add user_id, model_id to messages table
3. **Phase 3-4** (1 hour): Fix get_recent_messages() and get_recent_context()
4. **Phase 5-6** (4 hours): Update all memory tools and database classes
5. **Phase 7** (1 hour): Update MCP server wrappers

**Total: ~7-8 hours of work**

**Can be split into multiple sessions if needed**

---

## Questions Before Implementation

1. **MCP Tool Schema**: When calling tools via MCP, should user_id and model_id be:
   - **Option A**: Automatically extracted from message context (cleaner, fewer params)
   - **Option B**: Passed as explicit parameters to each tool (explicit, clear)
   - **Option C**: Set once in a "context" call, then assumed for all tools?

2. **OpenWebUI Integration**: Does OpenWebUI pass user info? Should we:
   - Extract it automatically?
   - Use it if available, default to "Nate" if not?

3. **Backwards Compatibility**: For existing databases without these columns:
   - Should we auto-migrate on startup?
   - Add the columns if missing?

4. **Permissions**: Any other files I should check/update?
   - persistent-ai-memory repo?
   - friday_memory_short_term.py?
   - Other plugins?

---

## Ready to Proceed?

**Please confirm:**
1. ✅ or ❌ Approve the general plan?
2. Answer the questions above (or let me decide if you trust me)
3. Any specific changes or concerns?

Once approved, I'll execute systematically and update you after each phase completes.
