# Friday MCP Server - Tools and Descriptions

Source: `/media/nate/Friday/Friday/friday_memory_mcp_server.py`
Tools defined in `_get_client_tools()` method (lines 677-1232) and executed in `_execute_tool()` method (lines 1515-2271).

---

## Common Tools (available to all clients)

### 1. complete_reminder
Mark a reminder as completed
- **Required:** reminder_id, user_id, model_id

### 2. get_active_reminders
Get active (not completed) reminders
- **Required:** user_id, model_id
- **Optional:** limit (default: 10), days_ahead (default: 30)

### 3. get_completed_reminders
Get recently completed reminders
- **Required:** user_id, model_id
- **Optional:** days (default: 7)

### 4. reschedule_reminder
Update the due date of a reminder
- **Required:** reminder_id, new_due_datetime, user_id, model_id

### 5. delete_reminder
Permanently delete a reminder
- **Required:** reminder_id, user_id, model_id

### 6. cancel_appointment
Cancel a scheduled appointment
- **Required:** appointment_id, user_id, model_id

### 7. complete_appointment
Mark an appointment as completed
- **Required:** appointment_id, user_id, model_id

### 8. get_upcoming_appointments
Get upcoming appointments (not cancelled)
- **Required:** user_id, model_id
- **Optional:** limit (default: 5), days_ahead (default: 30)

### 9. search_memories
Search memories using semantic similarity with importance and type filtering, or direct ID lookup. Searches across long-term curated memories, short-term memories, conversations, and schedule. Each result includes a 'source' field (short_term, long_term, conversation, or schedule) for transparency. Either 'query' or 'memory_id' must be provided.
- **Required:** user_id, model_id
- **Optional:** query, limit (default: 10), database_filter (enum: conversations, ai_memories, schedule, all; default: all), min_importance (1-10), max_importance (1-10), memory_type, tags (array), memory_bank, memory_id

### 10. search_memories_by_date
Search all memories and conversations chronologically within a date range. If a query is provided, results are filtered by semantic relevance first then sorted by date. If no query, returns everything in the date range oldest-first. Searches short-term memories, long-term curated memories, and conversation history.
- **Required:** user_id, model_id
- **Optional:** start_date, end_date, query, limit (default: 20), database_filter (enum: all, ai_memories, conversations; default: all), memory_bank, tags (array)

### 11. store_conversation
Store conversation automatically
- **Required:** content, role, user_id, model_id
- **Optional:** session_id, metadata

### 12. create_memory
Create a curated memory entry
- **Required:** content, user_id, model_id
- **Optional:** memory_type, importance_level (default: 5), tags (array), source_conversation_id, memory_bank (default: General)

### 13. update_memory
Update an existing curated memory
- **Required:** memory_id, user_id, model_id
- **Optional:** content, importance_level, tags (array)

### 14. get_conversation_context
Retrieve conversation context linked to a memory in three modes: snippet (4 msgs before/after), summary (count, date range, first/last msgs), or full (all messages)
- **Required:** memory_id, user_id, model_id
- **Optional:** mode (enum: snippet, summary, full; default: snippet)

### 15. create_appointment
Create an appointment, optionally recurring (e.g., weekly mental health appointments)
- **Required:** title, scheduled_datetime, user_id, model_id
- **Optional:** description, location, recurrence_pattern (enum: daily, weekly, monthly, yearly), recurrence_count (min: 1), recurrence_end_date

### 16. create_reminder
Create a reminder or multiple recurring reminders
- **Required:** content, due_datetime, user_id, model_id
- **Optional:** priority_level (default: 5), recurrence_pattern (enum: daily, weekly, monthly, yearly), recurrence_count (min: 1, max: 365), recurrence_end_date

### 17. get_reminders
Get recent reminders, optionally filtered by date range
- **Required:** user_id, model_id
- **Optional:** limit (default: 5), include_completed (default: false), days_ahead (default: 30)

### 18. get_recent_context
Get recent conversation context from the last N days
- **Required:** user_id, model_id
- **Optional:** limit (default: 5), session_id, days_back (default: 7)

### 19. get_system_health
Get comprehensive system health, statistics, and database status
- **Required:** user_id, model_id

### 20. get_error_summary
Get recent error summary from the short-term memory system — failed operations, LLM errors, embedding failures, and JSON parse issues
- **Required:** user_id, model_id

### 21. get_tool_information
Get tool usage statistics OR tool documentation. Pass mode='documentation' to get descriptions of available tools. Optionally specify tool_name to get docs for a specific tool.
- **Required:** user_id, model_id
- **Optional:** mode (default: usage), tool_name, days (default: 7), client_id

### 22. reflect_on_tool_usage
AI self-reflection on tool usage patterns and effectiveness
- **Required:** user_id, model_id
- **Optional:** days (default: 7), client_id

### 23. get_ai_insights
Get recent AI self-reflection insights and patterns
- **Required:** user_id, model_id
- **Optional:** limit (default: 5), insight_type, query

### 24. store_ai_reflection
Store an AI self-reflection/insight record (manual write)
- **Required:** content, user_id, model_id
- **Optional:** reflection_type (default: general), insights (array), recommendations (array), confidence_level (default: 0.7), source_period_days

### 25. write_ai_insights
Alias of store_ai_reflection — write an AI self-reflection/insight record
- **Required:** content, user_id, model_id
- **Optional:** reflection_type (default: general), insights (array), recommendations (array), confidence_level (default: 0.7), source_period_days

### 26. get_current_time
Get the current server time in ISO format (UTC and local)
- **Required:** user_id, model_id

### 27. trigger_database_maintenance
Manually trigger database maintenance (archival, repairs, optimization) outside of the regular 6-hour schedule
- **Required:** user_id, model_id
- **Optional:** force (default: true)

### 28. export_all_tool_calls
Export all tool calls from current and archived databases for LORA training dataset generation (web-only, not for models)
- **Required:** user_id, model_id
- **Optional:** output_filename

### 29. list_available_tags
Get list of available tags from registry with their canonical forms, variations, and usage counts
- **Required:** user_id, model_id
- **Optional:** memory_bank

### 30. list_available_memory_banks
Get list of available memory banks with memory counts per bank
- **Required:** user_id, model_id

### 31. get_appointments
Get recent appointments, optionally filtered by date range
- **Required:** user_id, model_id
- **Optional:** limit (default: 5), days_ahead (default: 30)

---

## VS Code Specific Tools

### 32. save_development_session
Save VS Code development session context
- **Required:** workspace_path, user_id, model_id
- **Optional:** active_files (array), git_branch, session_summary

### 33. store_project_insight
Store development insight or decision
- **Required:** content, user_id, model_id
- **Optional:** insight_type, related_files (array), importance_level (default: 5)

### 34. search_project_history
Search VS Code project development history
- **Required:** query, user_id, model_id
- **Optional:** limit (default: 10)

### 35. link_code_context
Link conversation to specific code context
- **Required:** file_path, description, user_id, model_id
- **Optional:** function_name, conversation_id

### 36. get_project_continuity
Get context to continue development work
- **Required:** workspace_path, user_id, model_id
- **Optional:** limit (default: 5)

---

## SillyTavern Specific Tools

### 37. get_character_context
Get relevant context about characters from memory
- **Required:** character_name, user_id, model_id
- **Optional:** context_type, limit (default: 5)

### 38. store_roleplay_memory
Store important roleplay moments or character developments
- **Required:** character_name, event_description, user_id, model_id
- **Optional:** importance_level (default: 5), tags (array)

### 39. search_roleplay_history
Search past roleplay interactions and character development
- **Required:** query, user_id, model_id
- **Optional:** character_name, limit (default: 10)

---

**Total: 39 tools** (31 common + 5 VS Code + 3 SillyTavern)