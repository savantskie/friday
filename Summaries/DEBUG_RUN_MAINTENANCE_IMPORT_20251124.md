# DEBUG INVESTIGATION: run_maintenance Import Error
**Date**: November 24, 2025  
**Issue**: MCP tool `trigger_database_maintenance` fails with `"cannot import name 'run_maintenance' from 'database_maintenance'"`

## Root Cause Analysis

### What Happened
Friday attempted to call the `trigger_database_maintenance` MCP tool, which resulted in:
```
Error: cannot import name 'run_maintenance' from 'database_maintenance' 
(/media/nate/Friday/Friday/database_maintenance.py)
```

### Why It Failed
The MCP tool handler at line 1778-1781 in `friday_memory_mcp_server.py` attempted:
```python
from database_maintenance import run_maintenance
await run_maintenance(force=force)
```

But `run_maintenance` is **not** a module-level function - it's a **method** of the `DatabaseMaintenance` class:
- Located at line 1762 in `database_maintenance.py`
- Signature: `async def run_maintenance(self, force: bool = False) -> Dict:`

### Correct Implementation
The `FridayMemorySystem` already initializes `DatabaseMaintenance` as `self.db_maintenance` (line 4799 in friday_memory_system.py), so the correct call should be:
```python
await self.memory_system.db_maintenance.run_maintenance(force=force)
```

## Solution

**File**: `/media/nate/Friday/Friday/friday_memory_mcp_server.py`  
**Lines to fix**: 1778-1790

Replace:
```python
elif tool_name == "trigger_database_maintenance":
    # Import database_maintenance module
    from database_maintenance import run_maintenance
    
    force = arguments.get("force", True)
    logger.info(f"Database maintenance triggered manually (force={force})")
    
    try:
        await run_maintenance(force=force)
```

With:
```python
elif tool_name == "trigger_database_maintenance":
    force = arguments.get("force", True)
    logger.info(f"Database maintenance triggered manually (force={force})")
    
    try:
        await self.memory_system.db_maintenance.run_maintenance(force=force)
```

Also need to fix the upgrade version at:  
**File**: `/media/nate/Friday/Friday/Friday_Memory_System_Update/friday_memory_mcp_server.py`  
**Lines**: ~1296-1308

## Status
- [x] Root cause identified
- [x] Solution documented
- [x] Fix implemented in both versions
- [ ] Awaiting testing
- [ ] Awaiting deployment confirmation

## Related Issues
- Task 6: model_id/user_id parameter errors (separate investigation)
- Task 7: create_memory memory_bank parameter error (separate investigation)
