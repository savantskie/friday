# Phase 5: MCP Server Functional Parity Implementation Plan

**Date:** January 1, 2026  
**Status:** IN PROGRESS  
**Priority:** HIGH  
**Estimated Duration:** 4-5 days  

## Objective
Achieve complete functional parity between persistent-ai-memory MCP server and Friday Memory System's MCP server while maintaining generic, configurable design.

## Current Status

### Tools Already Declared (33 total)
In `ai-memory-mcp_server.py` `_get_client_tools()`:
- search_memories
- store_conversation
- create_memory
- update_memory
- create_appointment
- create_reminder
- get_reminders
- get_recent_context
- get_system_health
- get_tool_usage_summary
- reflect_on_tool_usage
- get_ai_insights
- get_active_reminders
- get_completed_reminders
- complete_reminder
- reschedule_reminder
- delete_reminder
- cancel_appointment
- complete_appointment
- get_upcoming_appointments
- get_appointments
- store_ai_reflection
- write_ai_insights
- get_current_time
- get_weather_open_meteo
- save_development_session
- store_project_insight
- search_project_history
- link_code_context
- get_project_continuity
- get_character_context (SillyTavern-specific)
- store_roleplay_memory (SillyTavern-specific)
- search_roleplay_history (SillyTavern-specific)

### Methods Implemented in ai_memory_core.py (~10)

- search_memories
- store_conversation
- create_memory
- update_memory
- create_appointment
- create_reminder
- get_active_reminders
- get_weather_open_meteo (partial)
- save_development_session
- search_project_history

### Missing/Incomplete in ai_memory_core.py
**Critical Memory Operations:**
- delete_memory
- list_available_memory_banks
- list_available_tags

**Schedule Operations (need completion):**
- get_reminders (basic implementation)
- get_upcoming_appointments
- get_appointments
- cancel_appointment
- complete_appointment
- complete_reminder
- reschedule_reminder
- delete_reminder

**System Operations (need integration):**
- get_system_health (exists but may need enhancement)
- get_tool_usage_summary
- reflect_on_tool_usage
- get_ai_insights
- store_ai_reflection (exists, needs testing)
- write_ai_insights (alias, needs implementation)
- get_current_time (basic)

**External Integrations:**
- brave_web_search (not in current implementation)
- brave_local_search (not in current implementation)
- get_weather_open_meteo (exists but may need enhancement)

**Development/Project Tools (need completion):**
- store_project_insight
- link_code_context
- get_project_continuity
- trigger_database_maintenance
- export_all_tool_calls

**Character/Roleplay Tools (SillyTavern-specific):**
- get_character_context
- store_roleplay_memory
- search_roleplay_history

## Implementation Strategy

### Phase 5a: Core Memory Operations (Days 1-2)
**Files to modify:** `ai_memory_core.py`

1. **delete_memory** - Remove memory by ID with verification
2. **list_available_memory_banks** - Return all memory bank names with counts
3. **list_available_tags** - Return all tags with usage counts

### Phase 5b: Complete Schedule Operations (Day 2)
**Files to modify:** `ai_memory_core.py`, `ai-memory-mcp_server.py`

1. **get_reminders** - Enhance basic implementation
2. **get_upcoming_appointments** - Already in MCP server routing
3. **get_appointments** - Already in MCP server routing
4. **cancel_appointment** - Remove appointment by ID
5. **complete_appointment** - Mark appointment as completed
6. **complete_reminder** - Mark reminder as done
7. **reschedule_reminder** - Update reminder due date
8. **delete_reminder** - Remove reminder by ID

### Phase 5c: System Operations (Day 3)
**Files to modify:** `ai_memory_core.py`

1. **Enhance get_system_health** - Full database statistics, memory counts, health status
2. **get_tool_usage_summary** - Statistics on tool usage from MCP call logs
3. **reflect_on_tool_usage** - AI analysis of tool usage patterns
4. **get_ai_insights** - Retrieve AI self-reflection records
5. **store_ai_reflection** - Store AI reflection/insights
6. **write_ai_insights** - Alias for store_ai_reflection
7. **get_current_time** - Return current time in user's timezone

### Phase 5d: External Integrations (Day 3-4)
**Files to modify:** `ai_memory_core.py`

Optional features (graceful degradation if not available):
1. **brave_web_search** - Web search using Brave Search API
2. **brave_local_search** - Local business search using Brave
3. **get_weather_open_meteo** - Enhance existing weather implementation

### Phase 5e: Development/Project Tools (Day 4)
**Files to modify:** `ai_memory_core.py`

1. **Enhance store_project_insight** - Already exists, verify implementation
2. **link_code_context** - Already exists, verify implementation
3. **get_project_continuity** - Already exists, verify implementation
4. **trigger_database_maintenance** - Call maintenance from MCP
5. **export_all_tool_calls** - Export tool call history for training

### Phase 5f: Character/Roleplay Tools (Day 5)
**Files to modify:** `ai_memory_core.py`

Optional SillyTavern integration:
1. **get_character_context** - Get context for roleplay character
2. **store_roleplay_memory** - Store conversation memory for character
3. **search_roleplay_history** - Search character conversation history

### Phase 5g: Testing & Validation (Day 5+)
1. Test all 40 tools with mock data
2. Verify chat isolation (user_id, model_id preservation)
3. Verify memory bank/tag functionality
4. Test external integrations with graceful fallbacks
5. Performance validation - ensure tools respond <2s
6. Documentation and error message clarity

## Technical Notes

### Graceful Degradation
- External integrations (Brave API, weather) should fail gracefully if not configured
- SillyTavern tools are optional - should not break core system
- All tools return consistent JSON structure with "status" field

### Chat Isolation
- All tools must respect user_id, model_id, character_name isolation
- Memory operations should be isolated by these fields
- Schedule operations may share across characters but maintain logs

### Consistency Requirements
- All tool responses follow pattern: `{"status": "success|error", "data": ...}`
- All dates in ISO 8601 format with timezone
- All arrays have consistent ordering (by date DESC, alphabetical ASC)
- All limits respect user-provided values with sensible defaults

### File Locations
- Tool definitions: `/media/nate/Friday/Friday/persistent-ai-memory-upgrade/ai-memory-mcp_server.py` (~lines 87-500)
- Tool routing: `/media/nate/Friday/Friday/persistent-ai-memory-upgrade/ai-memory-mcp_server.py` (lines 554-640)
- Method implementations: `/media/nate/Friday/Friday/persistent-ai-memory-upgrade/ai_memory_core.py`

## Reference Implementation
- Friday Memory System MCP: `/media/nate/Friday/Friday/friday_memory_mcp_server.py` (146KB, 40 tools)
- Friday Memory Core: `/media/nate/Friday/Friday/friday_memory_system.py` (2483 lines)
- Persistent AI Memory Core: `/media/nate/Friday/Friday/persistent-ai-memory-upgrade/ai_memory_core.py`

## Success Criteria
- ✅ All 33+ declared tools have working implementations
- ✅ All tools route correctly in `_execute_tool()`
- ✅ All tools follow consistent response format
- ✅ External integrations fail gracefully if not configured
- ✅ Chat isolation working across all memory operations
- ✅ Memory banks and tags fully functional
- ✅ MCP server syntax verified (py_compile)
- ✅ All tools tested with mock data
- ✅ Documentation complete

## Blockers/Dependencies
- None identified - all required modules (sqlite3, asyncio, json) are available
- External APIs (Brave, Weather) are optional

## Next Phase
- Phase 6: Testing & Documentation
- Phase 7: Short-term Memory System (optional)
