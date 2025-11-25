# DECISION DOCUMENT: MCP Tool Debug Issues - November 24, 2025

**Status**: ACTIVE INVESTIGATION  
**Priority**: CRITICAL (blocking Friday's ability to use trigger_database_maintenance tool and other memory tools)  
**Started**: November 24, 2025 ~14:00 CST  
**Assigned**: Nate + AI Assistant  

---

## Executive Summary

Three critical issues have been identified in the MCP tool implementations that are preventing Friday from using database maintenance and memory management tools in OpenWebUI:

1. **run_maintenance import error** (Task 5) - Identified and root cause understood
2. **model_id/user_id parameter errors** (Task 6) - Under investigation
3. **memory_bank parameter error** (Task 7) - Under investigation

All issues stem from mismatches between:
- What the MCP tool handler is trying to do
- What the underlying memory system methods actually accept/require
- How OpenWebUI is calling these tools

---

## Issue 1: run_maintenance Import Error (TASK 5)

### Error Message
```
Error: cannot import name 'run_maintenance' from 'database_maintenance' 
(/media/nate/Friday/Friday/database_maintenance.py)
```

### Root Cause - IDENTIFIED
The MCP handler at `friday_memory_mcp_server.py` line 1778 attempted:
```python
from database_maintenance import run_maintenance
await run_maintenance(force=force)
```

But `run_maintenance` is a **method** of the `DatabaseMaintenance` class (line 1762), not a module-level function.

### Correct Solution
Replace with:
```python
await self.memory_system.db_maintenance.run_maintenance(force=force)
```

The FridayMemorySystem already initializes this as `self.db_maintenance` at line 4799 in `friday_memory_system.py`.

### Files to Fix
- `/media/nate/Friday/Friday/friday_memory_mcp_server.py` (lines 1778-1790)
- `/media/nate/Friday/Friday/Friday_Memory_System_Update/friday_memory_mcp_server.py` (corresponding lines ~1296-1308)

### Status
- [x] Root cause identified and documented
- [x] Solution documented in `Summaries/DEBUG_RUN_MAINTENANCE_IMPORT_20251124.md`
- [x] Fix implemented in both versions (November 24, 2025 ~15:30 CST)
- [ ] Testing completed
- [ ] Deployed to production

### Implementation Details
**Fixed Code** (both versions):
```python
# BEFORE (BROKEN):
elif tool_name == "trigger_database_maintenance":
    from database_maintenance import run_maintenance
    force = arguments.get("force", True)
    try:
        await run_maintenance(force=force)  # <- ImportError here

# AFTER (FIXED):
elif tool_name == "trigger_database_maintenance":
    force = arguments.get("force", True)
    try:
        await self.memory_system.db_maintenance.run_maintenance(force=force)  # <- Correct method call
```

**Changed Lines:**
- Main: Lines 1778-1786 in `/media/nate/Friday/Friday/friday_memory_mcp_server.py`
- Upgrade: Lines 1294-1302 in `/media/nate/Friday/Friday/Friday_Memory_System_Update/friday_memory_mcp_server.py`

---

## Issue 2: model_id/user_id Parameter Errors (TASK 6)

### Error Message
Multiple tools complaining: "unexpected keyword argument 'model_id'" or "unexpected keyword argument 'user_id'"

### Investigation Status
**Partial** - Need more detailed error traces from Friday to identify exactly which tools are failing.

### Current Findings
The MCP handler is already designed to include these parameters (lines 1473-1515):

```python
model_id = (
    self.client_context.get("model_id")
    or arguments.get("model_id")
    or os.getenv("FRIDAY_DEFAULT_MODEL", "Friday")
)
```

And includes them in `allowed_args` for:
- `search_memories` ✓
- `create_memory` ✓
- `update_memory` ✓
- `get_recent_context` ✓

### Hypotheses
1. Some tools' `allowed_args` sets don't include these parameters
2. The underlying memory methods might not accept them despite MCP handler thinking they do
3. There could be a wrapper/proxy layer stripping parameters
4. OpenWebUI might be using a cached/different version of the code

### Files Involved
- `/media/nate/Friday/Friday/friday_memory_mcp_server.py` lines 1436-1600
- `/media/nate/Friday/Friday/friday_memory_system.py` (memory method implementations)
- `/media/nate/Friday/Friday/Friday_Memory_System_Update/friday_memory_system.py` (upgrade version)

### Status
- [ ] Need detailed error traces from Friday showing exact stack traces
- [ ] Awaiting Nate to run trigger that generates the error
- [ ] Root cause analysis pending

---

## Issue 3: create_memory memory_bank Parameter Error (TASK 7)

### Error Message
```
Error: FridayMemorySystem.create_memory() got an unexpected keyword argument 'memory_bank'
```

### Investigation Status
**CONTRADICTION FOUND** - The method signature shows it SHOULD accept this parameter.

### Verification Performed
✓ Method signature in `friday_memory_system.py` line 787 DOES accept:
```python
async def create_memory(
    self,
    content: str,
    memory_type: str = None,
    importance_level: int = 5,
    tags: List[str] = None,
    source_conversation_id: str = None,
    memory_bank: str = "General",  # <-- ACCEPTS THIS
    user_id: str = "",
    model_id: str = "",
) -> str:
```

✓ MCP handler includes `"memory_bank"` in allowed_args at line 1498

### Possible Causes
1. OpenWebUI is using a cached/compiled version of the code
2. There's a wrapper layer intercepting calls
3. The code was modified after OpenWebUI loaded it
4. The actual method being called is different (possibly from `Adaptive_Memory_v3.py` or another wrapper)

### Files Involved
- `/media/nate/Friday/Friday/friday_memory_system.py` line 787 (create_memory implementation)
- `/media/nate/Friday/Friday/Friday_Memory_System_Update/friday_memory_system.py` line 744 (upgrade version)
- `/media/nate/Friday/Friday/friday_memory_mcp_server.py` line 1497-1502 (MCP handler)

### Status
- [ ] Need stack trace showing exactly which `create_memory` method is being called
- [ ] May need to restart OpenWebUI to refresh cached code
- [ ] Awaiting Nate to provide detailed error logs

---

## Investigation Documentation

Detailed findings documented in:
- `Summaries/DEBUG_RUN_MAINTENANCE_IMPORT_20251124.md` - Tasks 5 & analysis
- `Summaries/DEBUG_PARAMETER_ERRORS_20251124.md` - Tasks 6 & 7 analysis
- `.github/copilot-instructions.md` - Updated with active investigations section

## Next Steps

### Immediate (Awaiting Nate Decision)
1. **Task 5**: Approve fix for run_maintenance import - solution is clear and ready to implement
2. **Tasks 6 & 7**: Provide detailed error logs from OpenWebUI including full stack traces

### Implementation Order
1. Fix Task 5 (run_maintenance) - straightforward, clear solution
2. Investigate Tasks 6 & 7 (parameter errors) - need more data before fixing

### After Fixes
1. Test each tool independently
2. Verify in OpenWebUI at https://fridayonline.bounceme.net/mcpo
3. Update documentation
4. Port fixes to upgrade version if needed

---

## Decision Points for Nate

### Decision 1: Proceed with Task 5 Fix?
- [ ] YES - Fix the run_maintenance import immediately
- [ ] NO - Investigate further first

### Decision 2: How to Get Debug Info for Tasks 6 & 7?
- [ ] Have Friday try tools again and capture full error logs
- [ ] Check OpenWebUI logs directly
- [ ] Restart OpenWebUI and try again (might be cache issue)

---

## Related Work
- Database Maintenance Deployment (November 24, 2025) - Added trigger_database_maintenance tool
- Archival Integrity Fix (November 24, 2025) - Fixed orphaned records in archives

---

**Document Status**: ACTIVE - Ready for Nate's decisions and implementation
