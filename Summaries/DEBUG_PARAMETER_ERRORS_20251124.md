# DEBUG INVESTIGATION: Parameter Handling Errors in MCP Tools
**Date**: November 24, 2025  
**Issues**: 
1. Multiple tools complaining about `model_id` and `user_id` parameters
2. `create_memory` tool failing with `"got an unexpected keyword argument 'memory_bank'"`

## Investigation Findings

### Issue 1: model_id/user_id Parameter Errors

Friday reported that "more tools are complaining about the model_id and user_id tags".

**Status**: Need more specific error messages to identify which tools are failing. The MCP handler at line 1473-1515 in `friday_memory_mcp_server.py` is already designed to filter and pass these parameters to tools:

```python
model_id = (
    self.client_context.get("model_id")
    or arguments.get("model_id")
    or os.getenv("FRIDAY_DEFAULT_MODEL", "Friday")
)
```

And includes them in `allowed_args` for multiple tools:
- search_memories (line 1490)
- create_memory (line 1498)
- update_memory (line 1504)
- get_recent_context (line 1512)

**Hypotheses**:
1. Some tools in the handler don't include `user_id` in their `allowed_args` set
2. The underlying memory methods don't accept these parameters
3. There's a mismatch between tool definition and handler implementation

### Issue 2: create_memory memory_bank Parameter Error

Friday reported: `"Error: FridayMemorySystem.create_memory() got an unexpected keyword argument 'memory_bank'"`

**Verification**:
- ✓ Method signature in `friday_memory_system.py` line 787 DOES accept `memory_bank: str = "General"`
- ✓ MCP handler at line 1498 includes `"memory_bank"` in `allowed_args`
- ✓ Comment says "create_memory accepts: content, memory_type, importance_level, tags, source_conversation_id, memory_bank, user_id, model_id"

**Possible causes**:
1. OpenWebUI might be using a cached/different version of the memory system
2. There could be a wrapper or proxy layer intercepting calls
3. The actual method being called might be different from the FridayMemorySystem one

## Key Code Locations

**MCP Handler for memory tools**:
- File: `/media/nate/Friday/Friday/friday_memory_mcp_server.py`
- Lines: 1489-1530 (memory tool handling section)
- Method: `_execute_tool()`

**Memory System Methods**:
- File: `/media/nate/Friday/Friday/friday_memory_system.py`
- create_memory: Line 787
- search_memories: Line ~1200
- update_memory: Line ~1100
- get_recent_context: Line ~1400

**Upgrade Version**:
- File: `/media/nate/Friday/Friday/Friday_Memory_System_Update/friday_memory_system.py`
- create_memory: Line 744
- (Other methods at corresponding lines)

## Next Steps for Investigation

1. **Get detailed error traces**: Need full stack traces from OpenWebUI showing exactly which method is rejecting which parameter
2. **Check if wrapper layer exists**: Search for any proxy/wrapper around FridayMemorySystem that might be stripping parameters
3. **Verify tool handler consistency**: Audit all memory tools in MCP handler to ensure they all include required parameters in `allowed_args`
4. **Check parameter filtering logic**: Verify that parameters aren't being filtered out before reaching the actual methods

## Status
- [x] Root cause analysis started
- [ ] Need error traces from Friday
- [ ] Awaiting implementation
- [ ] Awaiting testing

## Related Issues
- Task 5: run_maintenance import error (IDENTIFIED, ready to fix)
- Task 7: Closely related - both are about parameter handling
