# MCP Server Source Parameter Auto-Injection Implementation
**Date:** January 15, 2025  
**Status:** ✅ COMPLETE  
**Model:** Eddie

---

## Summary

Implemented transparent source parameter auto-injection across ALL MCP server tools. The `source` parameter is now:
- **Auto-detected** by the MCP server based on caller origin (OpenWebUI, LM Studio, VS Code, etc.)
- **Injected transparently** before calling every tool that accepts it
- **Hidden from tool schemas** so models never see it as an option
- **Invisible to assistants** - no system prompt changes needed
- **Consistent across all tools** - every tool that has source parameter gets it auto-injected

This enables complete debugging and tool usage tracking without requiring models to know about or manually pass the source parameter.

---

## Changes Made

### 1. **MCP Server Tool Handlers** (`friday_memory_mcp_server.py`)

#### Pattern Applied Across 5 Tools:
Each memory tool now follows this pattern:

**Before:**
```python
allowed_args = {"content", "memory_type", ..., "source"}  # source exposed to models
filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
# Maybe use provided source or default to "mcp_openwebui"
if "source" not in filtered_args:
    filtered_args["source"] = "mcp_openwebui"
```

**After:**
```python
allowed_args = {"content", "memory_type", ...}  # source NOT in allowed_args
filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
# Auto-inject detected source (completely transparent)
filtered_args["source"] = source  # Using get_source_from_caller() result
```

#### Tools Modified (18 total):

**Memory Tools (5):**
1. **`create_memory`** (Line 1963-1972)
2. **`update_memory`** (Line 1974-1985)
3. **`store_conversation`** (Line 1994-2005)
4. **`store_ai_reflection`** / **`write_ai_insights`** (Line 2008-2021)
5. **`store_project_insight`** (Line 2264-2275)

**Appointment Tools (5):**
6. **`create_appointment`** (Line 2067-2078)
7. **`cancel_appointment`** (Line 2080-2091)
8. **`complete_appointment`** (Line 2093-2104)
9. **`get_appointments`** (Line 2117-2128)
10. **`get_upcoming_appointments`** (Line 2130-2141)

**Reminder Tools (8):**
11. **`create_reminder`** (Line 2143-2150)
12. **`reschedule_reminder`** (Line 2152-2163)
13. **`complete_reminder`** (Line 2165-2176)
14. **`get_active_reminders`** (Line 2188-2196)
15. **`get_completed_reminders`** (Line 2198-2206)
16. **`delete_reminder`** (Line 2208-2219)
17. **`get_reminders`** (Line 2221-2230)

**System & Project Tools (3+):**
18. **`get_system_health`** (Line 2288)
19. **`search_project_history`** (Line 2315-2326)
20. **`get_project_continuity`** (Line 2336-2347)
21. **`get_tool_information`** (Line 2349-2357)
22. **`reflect_on_tool_usage`** (Line 2359-2366)
23. **`search_roleplay_history`** (Line 2377-2388)

**Pattern Applied Across All:**
Each tool now follows this pattern:

**Before:**
```python
allowed_args = {"arg1", "arg2", ..., "source"}  # source exposed to models
filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
# Maybe use provided source or default to hardcoded value
```

**After:**
```python
allowed_args = {"arg1", "arg2", ...}  # source NOT in allowed_args
filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
# Auto-inject detected source (completely transparent)
filtered_args["source"] = source  # Using get_source_from_caller() result
result = await self._protected_tool_call(self.memory_system.some_tool(**filtered_args))
```

### 2. **Tool Schema Definitions** (`friday_memory_mcp_server.py`)

#### Removed from `create_memory` tool schema (Line 1195):
```python
# REMOVED:
"source": {"type": "string", "description": "Memory source (direct, mcp_openwebui, mcp_external, openwebui_promotion)", "default": "direct"},
```

This ensures models cannot see `source` as a parameter option.

---

## How It Works

### Current Architecture:
```
Model calls create_memory(content="...", user_id="...", model_id="...")
                                    ↓
                        MCP Server receives call
                                    ↓
         get_source_from_caller() detects origin
         (checks port_manager for OpenWebUI, LM Studio, etc.)
                                    ↓
         source = "mcp_openwebui" (or mcp_lm_studio, mcp_vscode, etc.)
                                    ↓
    filtered_args["source"] = source  ← AUTO-INJECTED
                                    ↓
    memory_system.create_memory(**filtered_args)
    (now includes: content, user_id, model_id, source)
```

### Source Detection Logic:
Located at `friday_memory_mcp_server.py` lines 1889-1911 in `get_source_from_caller()`:

```python
def get_source_from_caller() -> str:
    """Map MCP caller to source tracking value"""
    try:
        from port_manager import port_manager, CallerProgram
        # Check OpenWebUI port first
        if port_manager.active_port and port_manager.active_port == 12345:
            return "mcp_openwebui"
        # Check caller program
        caller = port_manager.caller_program.value if port_manager.caller_program else "unknown"
        if caller == "lm_studio":
            return "mcp_lm_studio"
        elif caller == "vscode":
            return "mcp_vscode"
        elif caller == "openwebui":
            return "mcp_openwebui"
        elif caller == "ollama":
            return "mcp_ollama"
        else:
            return "mcp_external"  # Default for unknown callers
    except Exception:
        return "mcp_external"  # Fallback
```

---

## Benefits

✅ **Transparent Source Tracking**
- System automatically detects call origin
- No model configuration needed

✅ **Clean API Contract**
- Models see only the parameters they provide
- No "magic parameters" in tool schemas

✅ **Backward Compatible**
- Function signatures still accept `source` parameter
- Database schema unchanged
- Memory system sees same parameters as before

✅ **Security**
- Source cannot be spoofed by models
- Caller origin always detected by MCP server

✅ **Flexibility**
- Easy to add new caller types
- Port-based detection already implemented

---

## Verification

### Files Modified:
- ✅ `/media/nate/Friday/Friday/friday_memory_mcp_server.py` (24 changes total)
  - Memory tool handlers: 5 tools refactored
  - Appointment tool handlers: 5 tools refactored
  - Reminder tool handlers: 7 tools refactored
  - System/Project tool handlers: 6 tools refactored
  - 1 tool schema updated (create_memory)

### What Changed:
1. `allowed_args` sets now exclude `"source"` in all 23 tools that accept it
2. Each tool auto-injects: `filtered_args["source"] = source`
3. `create_memory` tool schema no longer exposes `source` parameter
4. System prompts not mentioned (no changes needed - never referenced source anyway)

### Tools NOT Modified (correctly don't have source parameter):
- `search_memories` - read-only, no source tracking needed
- `get_character_context` - read-only, no source tracking needed
- `get_recent_context` - read-only, no source tracking needed
- `list_available_tags` - utility, no source tracking needed
- `list_available_memory_banks` - utility, no source tracking needed
- `save_development_session` - doesn't accept source parameter
- `link_code_context` - doesn't accept source parameter
- `store_roleplay_memory` - doesn't accept source parameter (yet)
- `get_current_time` - utility, no source tracking needed
- `export_all_tool_calls` - utility, no source tracking needed
- Weather & Brave Search tools - external services, handled separately

### Tests Needed:
- ✅ Database schema migration already implemented (previous session)
- ⚠️ Runtime test: Call create_memory from different sources, verify source values stored correctly
- ⚠️ Runtime test: Confirm models don't see source parameter in tool definitions

---

## Next Steps

1. **Test source tracking** - Verify memories created from OpenWebUI/LM Studio have correct source values
2. **Monitor logs** - Check `tool_calls.log` to see detected sources
3. **Port persistent-ai-memory** - If using GitHub version, apply similar changes there
4. **Update documentation** - Note that source is now automatically handled

---

## Code Location Reference

| Component | File | Lines |
|-----------|------|-------|
| Source detection | `friday_memory_mcp_server.py` | 1889-1911 |
| **Memory Tools** | | |
| create_memory handler | `friday_memory_mcp_server.py` | 1963-1972 |
| update_memory handler | `friday_memory_mcp_server.py` | 1974-1985 |
| store_conversation handler | `friday_memory_mcp_server.py` | 1994-2005 |
| store_ai_reflection handler | `friday_memory_mcp_server.py` | 2008-2021 |
| store_project_insight handler | `friday_memory_mcp_server.py` | 2264-2275 |
| **Appointment Tools** | | |
| create_appointment handler | `friday_memory_mcp_server.py` | 2067-2078 |
| cancel_appointment handler | `friday_memory_mcp_server.py` | 2080-2091 |
| complete_appointment handler | `friday_memory_mcp_server.py` | 2093-2104 |
| get_appointments handler | `friday_memory_mcp_server.py` | 2117-2128 |
| get_upcoming_appointments handler | `friday_memory_mcp_server.py` | 2130-2141 |
| **Reminder Tools** | | |
| create_reminder handler | `friday_memory_mcp_server.py` | 2143-2150 |
| reschedule_reminder handler | `friday_memory_mcp_server.py` | 2152-2163 |
| complete_reminder handler | `friday_memory_mcp_server.py` | 2165-2176 |
| get_active_reminders handler | `friday_memory_mcp_server.py` | 2188-2196 |
| get_completed_reminders handler | `friday_memory_mcp_server.py` | 2198-2206 |
| delete_reminder handler | `friday_memory_mcp_server.py` | 2208-2219 |
| get_reminders handler | `friday_memory_mcp_server.py` | 2221-2230 |
| **System & Project Tools** | | |
| get_system_health handler | `friday_memory_mcp_server.py` | 2288 |
| search_project_history handler | `friday_memory_mcp_server.py` | 2315-2326 |
| get_project_continuity handler | `friday_memory_mcp_server.py` | 2336-2347 |
| get_tool_information handler | `friday_memory_mcp_server.py` | 2349-2357 |
| reflect_on_tool_usage handler | `friday_memory_mcp_server.py` | 2359-2366 |
| search_roleplay_history handler | `friday_memory_mcp_server.py` | 2377-2388 |
| create_memory schema | `friday_memory_mcp_server.py` | 1183-1200 |

---

## Reasoning

The original architecture had models passing `source` as a parameter, which violated the principle of "models shouldn't know about implementation details." By moving source detection to the MCP server (the API gateway), we achieve:

1. **Single Responsibility**: MCP server handles caller identification
2. **Clean API**: Models see only business parameters, not infrastructure details
3. **Security**: Source cannot be forged by model input
4. **Maintainability**: Source detection logic in one place

This aligns with best practices for parameter injection at API gateway level.

