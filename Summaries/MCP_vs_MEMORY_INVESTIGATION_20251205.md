# Investigation Report: MCP Server vs Memory Server Responsibility
**Date:** December 5, 2025  
**Investigation Focus:** Whether the `store_ai_reflection` and `write_ai_insights` tool parameter definitions should be in the memory server instead of the MCP server.

---

## Architecture Overview

### Two-Server Design:
1. **Friday Memory System** (`friday_memory_system.py`)
   - Contains all database logic and core memory operations
   - Provides business logic and data persistence
   - Does NOT define MCP Tool schemas or tool interfaces
   
2. **Friday Memory MCP Server** (`friday_memory_mcp_server.py`)
   - Acts as interface layer between MCP clients (VS Code, LM Studio, Ollama UIs)
   - Defines all Tool schemas and input validation
   - Routes tool calls to memory system methods
   - Handles user_id/model_id separation at the protocol layer

---

## Investigation Results: store_ai_reflection & write_ai_insights

### Current State

#### Memory System (`friday_memory_system.py`)
- **Method Signature:** `async def store_ai_reflection(self, reflection_type: str, content: str, insights: List[str] = None, recommendations: List[str] = None, confidence_level: float = 0.5, source_period_days: int = None) -> str:`
  - Line 2038-2055
  - Takes 6 parameters: reflection_type, content, insights, recommendations, confidence_level, source_period_days
  - **NO user_id parameter in signature**
  - **NO model_id parameter in signature**
  - Does NOT use user_id/model_id for any database operations

- **Database Schema:** `ai_reflections` table
  - Line 1888-1901: CREATE TABLE definition
  - Columns: reflection_id, timestamp_created, reflection_type, content, insights, recommendations, confidence_level, source_period_days, embedding, created_at
  - **NO user_id column**
  - **NO model_id column**

#### MCP Server (`friday_memory_mcp_server.py`)
- **Tool Definition:** Lines 1118-1172 for `store_ai_reflection`, 1174-1228 for `write_ai_insights`
  - **RECENTLY FIXED**: Now includes user_id and model_id in properties section
  - Required parameters: content, user_id, model_id
  - Tool handler at line 1688: Filters out user_id/model_id before passing to memory system

- **Tool Handler:**
  ```python
  # Line 1691: Only passes these parameters
  allowed_args = {"reflection_type", "content", "insights", "recommendations", "confidence_level", "source_period_days"}
  filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
  reflection_id = await self._protected_tool_call(self.memory_system.mcp_db.store_ai_reflection(**filtered_args))
  ```

#### get_ai_insights Status
- **Memory System Signature:** Line 7952: Has user_id and model_id parameters
- **Usage:** Only for logging and return metadata, NOT for querying/filtering
  - Lines 7957-7958: Sets defaults if not provided
  - Line 7959: Logs them
  - Line 7963: Returns them in metadata
- **Database Query:** Returns ALL reflections regardless of user_id/model_id (line 7962: `get_recent_reflections()`)

---

## Key Findings

### Finding 1: Architectural Mismatch - Store Operation
**Status:** ⚠️ ISSUE IDENTIFIED

The tool definition requires user_id and model_id, but:
1. The memory system doesn't accept these parameters (they're filtered out)
2. The database schema doesn't have columns to store these parameters
3. All AI reflections are shared globally (no separation)

**Analysis:**
- **MCP Server expects:** user_id, model_id to be passed through
- **Memory System has:** No support for these parameters
- **Database supports:** No columns for these parameters

**Current Workaround:** MCP server silently filters them out, no error but parameters are lost

### Finding 2: Architectural Consistency - Get Operation
**Status:** ⚠️ INCONSISTENCY

The memory system's `get_ai_insights()` accepts user_id/model_id but doesn't use them for filtering:
- They're only used for logging and return metadata
- All users/models get the same reflections
- This is inconsistent with other memory operations that DO filter by user_id/model_id

### Finding 3: Tool Definition Location
**Status:** ✅ CORRECT LOCATION

Tool definitions are **correctly in the MCP server**:
- Tool schemas are about the MCP interface contract, not business logic
- MCP server is the right place for defining what parameters clients must provide
- Memory system should focus on data operations, not protocol definitions
- This follows established pattern: all 26+ tools are defined in MCP server

---

## Comparison with Other Tools

### Tools WITH user_id/model_id filtering:
- **create_appointment** (line 1000+): Accepts and passes through to memory system
- **create_reminder** (line 1027+): Accepts and passes through to memory system
- **get_reminders** (line 1039+): Uses _ensure_user_id() and _apply_model_filter() helpers
- **get_appointments** (line 1231+): Uses the same helpers
- Pattern: These tools properly implement user_id/model_id separation at both levels

### Tools WITHOUT separation support in either layer:
- **store_ai_reflection** ← INCONSISTENT (requires in schema but not used)
- **write_ai_insights** ← INCONSISTENT (requires in schema but not used)
- **get_ai_insights** ← INCONSISTENT (accepts parameters but doesn't filter)

---

## Root Cause Analysis

### Why This Happened:
1. **Phase 1 (Recent):** Added user_id/model_id to MCP Tool definitions for consistency with other tools
2. **Issue:** Didn't update the memory system layer to actually support these parameters
3. **Result:** Tool definitions now require parameters that are immediately discarded

### Why It Works Despite the Issue:
- MCP server filters parameters before passing to memory system
- Memory system method doesn't raise an error for missing parameters
- No immediate failure, but parameters are silently lost
- System appears to work but doesn't provide the intended separation

---

## What Should Be in Memory Server vs MCP Server

### ✅ Correctly in MCP Server (No change needed):
- Tool inputSchema definitions with all parameters
- Parameter validation at the protocol level
- Filtering logic (_ensure_user_id, _apply_model_filter)
- Tool routing and error handling
- Logging of tool calls for analytics

### Should ALSO Be in Memory System (Currently Missing):
- **For store_ai_reflection:**
  - Add user_id and model_id columns to ai_reflections table
  - Update method signature to accept these parameters
  - Store them in the database
  - Update documentation
  
- **For get_ai_insights:**
  - Use user_id/model_id for filtering (not just logging)
  - Return only reflections for the requesting user/model
  - Update method signature to perform actual filtering

---

## Implementation Status of Recent Fix

### What Was Fixed:
✅ Added user_id and model_id to tool inputSchema properties for `store_ai_reflection` and `write_ai_insights`

### What Was NOT Fixed:
❌ Memory system methods don't actually accept user_id/model_id as functional parameters  
❌ Database schema doesn't have columns for user_id/model_id  
❌ Filtering/storage doesn't actually use these parameters  
❌ Same issue exists for get_ai_insights (accepts but doesn't filter)  

### Current State:
- MCP tool definitions are now correct ✅
- MCP server handler is correct (filters before passing) ✅
- Memory system implementation is incomplete ❌
- Database schema is incomplete ❌

---

## Recommendations

### Option A: Add Full User/Model Separation (Recommended)
**Effort:** Medium  
**Impact:** High

1. Add migration to ai_reflections table to add user_id, model_id columns
2. Update `store_ai_reflection()` to accept and store these parameters
3. Update `get_ai_insights()` to accept and filter by these parameters
4. Update MCP server handler to pass these parameters through instead of filtering
5. Ensure backward compatibility with existing reflections (NULL user_id/model_id)

**Files to modify:**
- `friday_memory_system.py`: Database schema migration and method signatures
- `friday_memory_mcp_server.py`: Tool handlers to pass parameters through

### Option B: Remove Parameters from Tool Definitions (Not Recommended)
**Effort:** Low  
**Impact:** Low (regression)

1. Remove user_id and model_id from store_ai_reflection and write_ai_insights tool schemas
2. Remove from required parameters
3. Back to previous state, but tools were complaining before

**Drawback:** Removes consistency with other tools, user_id/model_id requirements for system context

### Option C: Create Separate Global vs User-Specific Reflection Tools
**Effort:** High  
**Impact:** Medium

1. Keep current store_ai_reflection as global (no user/model filtering)
2. Create new store_user_reflection that includes separation
3. Same for get operations

**Drawback:** Tool explosion, adds complexity

---

## Conclusion

### Is code in the right place?
✅ **YES** - Tool definitions correctly belong in MCP Server

### Is there an architectural issue?
⚠️ **YES** - The tool definitions promise user_id/model_id support that the memory system doesn't actually implement

### What's the immediate impact?
🟡 **MEDIUM** - System works but parameters are silently discarded:
- All users/models see the same reflections
- No cross-contamination between users
- But also no isolation when intended

### Next Steps:
The fix made (adding user_id/model_id to tool properties) is correct and necessary, but incomplete. To fully implement the feature:
1. Database schema needs columns for user_id/model_id
2. Memory system methods need to use these for actual filtering/storage
3. MCP server handlers need to pass parameters through instead of filtering them out
