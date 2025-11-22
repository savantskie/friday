# Friday Memory System - AI Helper Documentation
**Last Updated**: 2025-11-20 | **For**: Claude Haiku 4.5 + GitHub Copilot

---

## Quick Reference: Tool Availability

I have access to **30+ tools** across five categories. This document helps you understand which tools are available and how they interact.

---

## Category 1: Memory Operations (Core)
These tools are the foundation of Friday's memory system.

### `search_memories`
- **What it does**: Find memories using semantic similarity, with filtering options
- **Key parameters**: `query` (text to find), `database_filter` (conversations/ai_memories/schedule/all), `limit` (max 10 default)
- **Returns**: Matching memories with importance levels, types, and metadata
- **When to use**: User asks "do you remember...?", needs context from past conversations, or looking for specific types of information
- **Filter options**:
  - `database_filter`: "conversations", "ai_memories", "schedule", or "all"
  - `min_importance`: 1-10 (only memories at/above this level)
  - `max_importance`: 1-10 (only memories at/below this level)
  - `memory_type`: e.g., 'safety', 'preference', 'skill', 'general'
- **Direct lookup**: Can use `memory_id` to bypass semantic search and fetch specific memory

### `create_memory`
- **What it does**: Store important information that should persist across sessions
- **Key parameters**: `content` (what to store), `memory_type` (category), `importance_level` (1-10)
- **Optional parameters**: `tags`, `source_conversation_id`, `user_id`, `model_id`
- **Returns**: Memory ID for future reference
- **When to use**: After learning something about Nate (preferences, constraints, project decisions), store insights
- **Importance guidance**:
  - 1-3: Minor details, trivia
  - 4-6: Regular preferences, decisions, ongoing notes
  - 7-8: Critical constraints, important preferences, key decisions
  - 9-10: Safety-critical, life-changing information

### `update_memory`
- **What it does**: Modify existing memory content, importance, or tags
- **Key parameters**: `memory_id` (required), then update any of: `content`, `importance_level`, `tags`
- **Returns**: Confirmation of update
- **When to use**: After learning new information that changes what was previously stored

### `store_conversation`
- **What it does**: Save conversation excerpts automatically (mostly automatic, but manual control available)
- **Key parameters**: `content` (conversation text), `role` (user/assistant), `session_id`, `metadata`
- **Returns**: Conversation record ID
- **When to use**: Explicitly capture important conversation points for historical reference

---

## Category 2: Schedule Management

### Reminders (Task-based Time Management)
Reminders are short-term task tracking (do X on date/time).

#### `create_reminder`
- **What it does**: Create single or recurring reminders
- **Key parameters**: `content` (task text), `due_datetime` (ISO format), `priority_level` (1-10)
- **Recurrence options**:
  - `recurrence_pattern`: "daily", "weekly", "monthly", "yearly"
  - `recurrence_count`: How many to create (e.g., 12 for 12 weeks)
  - `recurrence_end_date`: ISO datetime to stop recurring
- **Returns**: Reminder ID(s)
- **When to use**: Nate says "remind me to..." or for regular tasks

#### `get_reminders`
- **What it does**: Fetch upcoming reminders
- **Parameters**: `limit` (default 5), `include_completed` (default false), `days_ahead` (default 30)
- **Returns**: List of reminders with due dates and content
- **When to use**: Check what Nate needs to do soon

#### `get_active_reminders`
- **What it does**: Get only incomplete reminders within timeframe
- **Parameters**: `days_ahead` (default 30), `limit` (default 10)
- **Returns**: Only active, not-yet-completed reminders

#### `get_completed_reminders`
- **What it does**: See what Nate recently accomplished
- **Parameters**: `days` (default 7) - how far back to look
- **Returns**: Completed reminders and their completion time
- **Insight**: Use this to celebrate accomplishments or understand work patterns

#### `complete_reminder`
- **What it does**: Mark a reminder as done
- **Parameters**: `reminder_id` (required)
- **Returns**: Confirmation
- **When to use**: After Nate completes a task

#### `reschedule_reminder`
- **What it does**: Change when a reminder is due
- **Parameters**: `reminder_id`, `new_due_datetime` (ISO format)
- **Returns**: Confirmation of new schedule
- **When to use**: Nate needs to postpone a task

#### `delete_reminder`
- **What it does**: Remove a reminder permanently
- **Parameters**: `reminder_id`
- **Returns**: Confirmation
- **When to use**: Task is no longer needed

### Appointments (Calendar Events)
Appointments are long-term calendar entries (meetings, events, etc.).

#### `create_appointment`
- **What it does**: Create single or recurring calendar events
- **Key parameters**: `title` (event name), `scheduled_datetime` (ISO format)
- **Optional**: `description`, `location`, recurrence options (same as reminders)
- **Returns**: Appointment ID(s)
- **When to use**: Medical appointments, meetings, recurring commitments

#### `get_appointments`
- **What it does**: List upcoming appointments
- **Parameters**: `limit` (default 5), `days_ahead` (default 30)
- **Returns**: Calendar events with dates and details

#### `get_upcoming_appointments`
- **What it does**: Non-cancelled upcoming appointments only
- **Parameters**: Same as `get_appointments`
- **Returns**: Confirmed future events

#### `cancel_appointment`
- **What it does**: Mark appointment as cancelled (doesn't delete)
- **Parameters**: `appointment_id`
- **Returns**: Confirmation
- **When to use**: Event is postponed or no longer needed

#### `complete_appointment`
- **What it does**: Mark appointment as completed
- **Parameters**: `appointment_id`
- **Returns**: Confirmation
- **When to use**: Event has occurred

### Time Reference
#### `get_current_time`
- **What it does**: Get current server time in both UTC and local (Nate's timezone)
- **Parameters**: None
- **Returns**: ISO datetimes for both UTC and local
- **Usage note**: Use this before creating reminders/appointments to calculate correct times

---

## Category 3: Search & Information

### Web Search
#### `brave_web_search`
- **What it does**: Search the internet using Brave search engine
- **Parameters**: `query` (required), `count` (1-20, default 10), `country` (default "US"), `language` (default "en")
- **Returns**: Web search results with titles, snippets, URLs
- **When to use**: Nate asks research questions, needs current information, or when unclear on a topic

#### `brave_local_search`
- **What it does**: Find businesses and places near a location
- **Parameters**: `query` (e.g., "pizza near me"), optional `location`, `radius` (meters, default 5000)
- **Returns**: Local business results with addresses, ratings, coordinates
- **When to use**: Finding services, restaurants, or places in Nate's area

### Weather
#### `get_weather_open_meteo`
- **What it does**: Get weather forecast for Nate's location (Motley, MN by default)
- **Parameters**:
  - `override` (false by default) - set true to use custom coordinates
  - `latitude`, `longitude`, `timezone_str` - only used if override=true
  - `update_today` (default true) - fetch fresh data
  - `return_changes_only` (default false) - only show what changed
  - `severe_update` (default false) - check more frequently for severe weather
  - `force_refresh` (default false) - bypass cache
- **Returns**: Detailed forecast data
- **Smart caching**: Caches once per day to save API calls
- **When to use**: Nate asks about weather, needs to plan outdoor activities

---

## Category 4: AI Self-Reflection & Insights

These tools help me learn patterns about Nate and track my own effectiveness.

### `store_ai_reflection` / `write_ai_insights` (aliases - same tool)
- **What it does**: Record my observations, insights, and learnings about Nate or our interactions
- **Parameters**: `content` (required - what I learned/observed)
- **Optional**:
  - `reflection_type`: "general", "tool_usage_analysis", "memory", "pattern_analysis", etc.
  - `insights`: Array of bullet-point learnings
  - `recommendations`: Array of suggested next actions
  - `confidence_level`: 0.0-1.0 (how confident I am in this insight)
  - `source_period_days`: How many days of data this covers
- **Returns**: Reflection ID
- **Best practice**: Use this as a journal after significant work sessions, pattern discovery, or when I realize something important about working with Nate

### `get_ai_insights`
- **What it does**: Retrieve my past insights and learnings
- **Parameters**: `limit` (default 5), `insight_type` (optional filter), `query` (search keywords)
- **Returns**: My stored insights with timestamps and confidence levels
- **When to use**: Looking for patterns I've noticed before, reminding myself what I've learned

### `reflect_on_tool_usage`
- **What it does**: Analyze my tool usage patterns over time
- **Parameters**: `days` (default 7), optional `client_id`
- **Returns**: Structured analysis of what tools I used, how often, effectiveness
- **When to use**: Periodic self-assessment (after significant work blocks)

### `get_tool_usage_summary`
- **What it does**: Summary statistics of my tool usage
- **Parameters**: `days` (default 7), optional `client_id`
- **Returns**: Stats on which tools I rely on most, usage frequency, patterns

---

## Category 5: System Information

### `get_system_health`
- **What it does**: Comprehensive status of Friday's memory system and databases
- **Parameters**: None
- **Returns**: Database sizes, connection status, memory stats, error counts, performance metrics
- **When to use**: Troubleshooting issues, checking if system is running properly

---

## Category 6: Development & Project Context (VS Code specific)

### `save_development_session`
- **What it does**: Capture current VS Code session state
- **Parameters**: `workspace_path` (required), optional: `active_files`, `git_branch`, `session_summary`
- **Returns**: Session record ID
- **When to use**: End of work session, saving progress checkpoint

### `store_project_insight`
- **What it does**: Record development decisions, architecture notes, implementation insights
- **Parameters**: `content` (required), optional: `insight_type`, `related_files`, `importance_level` (1-10)
- **Returns**: Insight record ID
- **When to use**: After making architectural decisions, solving hard problems, or documenting design choices

### `search_project_history`
- **What it does**: Find past development decisions and context
- **Parameters**: `query` (required), `limit` (default 10)
- **Returns**: Development history matching query
- **When to use**: Need to find previous decisions about a feature or architecture

### `link_code_context`
- **What it does**: Connect a conversation to specific code
- **Parameters**: `file_path` (required), `description` (required), optional: `function_name`, `conversation_id`
- **Returns**: Context link record ID
- **When to use**: When working on code, linking the conversation to the actual files being edited

---

## Tool Interaction Patterns

### Pattern 1: Learning About Nate → Storing Memory
```
Conversation happens → I learn something important
↓
search_memories (to check if I already know this)
↓
If new: create_memory (store with importance level)
If updating: update_memory (with new information)
↓
store_ai_reflection (record what I learned)
```

### Pattern 2: Task Management Workflow
```
Nate: "Remind me to..."
↓
get_current_time (to get correct datetime)
↓
create_reminder (single or recurring)
↓
As time passes:
  - get_active_reminders (check what's due)
  - complete_reminder (when done)
  - reschedule_reminder (if postponing)
  - get_completed_reminders (celebrate accomplishments)
```

### Pattern 3: Research Workflow
```
Nate asks unclear question
↓
brave_web_search (get current info)
OR brave_local_search (find services/places)
OR get_weather_open_meteo (weather question)
↓
create_memory (store findings)
↓
Explain results to Nate
```

### Pattern 4: Development Session Workflow
```
Working on code
↓
link_code_context (connect conversation to files)
↓
store_project_insight (record decisions)
↓
End of session:
  - save_development_session (checkpoint)
  - store_ai_reflection (what I learned about this project)
↓
Next session:
  - search_project_history (recall what we were doing)
```

### Pattern 5: Self-Improvement Cycle
```
After significant work:
↓
get_tool_usage_summary (what did I use?)
↓
reflect_on_tool_usage (was it effective?)
↓
store_ai_reflection (here's what I learned)
↓
get_ai_insights (recall past learnings)
↓
Next interaction: Use past insights to improve
```

---

## Key Principles

### Importance Levels Guide
- **1-3**: Trivial details, minor preferences, "nice to know"
- **4-6**: Regular preferences, decisions Nate made, ongoing notes
- **7-8**: Important constraints, critical preferences, architectural decisions
- **9-10**: Life-affecting, safety-critical, core identity information

### Database Filters
When searching memories, you can filter by database:
- `conversations` - Past chat history
- `ai_memories` - Explicit memories I've stored (high confidence)
- `schedule` - Reminders and appointments
- `all` - Everything (default)

### Time Format
All datetimes should be ISO 8601 format: `2025-11-20T14:30:00Z` or `2025-11-20T14:30:00-06:00` (with timezone)

### Confidence Levels
When storing reflections, use confidence 0.0-1.0:
- 0.7-0.8: Pattern I've noticed, fairly confident
- 0.8-0.9: Strong pattern, high confidence
- 0.9+: Near certain, based on explicit information from Nate

---

## Common Mistakes to Avoid

1. **Creating duplicate memories**: Always `search_memories` first to check if something similar exists
2. **Wrong importance level**: Don't store everything as level 10 - reserve high levels for truly important things
3. **Forgetting database filters**: When searching, specify database type to get faster, more relevant results
4. **Not recording insights**: I learn things but don't record them - use `store_ai_reflection` to retain learning
5. **Timezone issues**: Always use `get_current_time` before creating time-based items
6. **Overusing search**: If I know the memory ID, use direct lookup instead of semantic search

---

## When to Use Which Tool

| User Need | Tool(s) to Use |
|-----------|---|
| Nate mentions a preference/constraint | search_memories first, then create_memory or update_memory |
| "Remind me to..." | get_current_time, then create_reminder |
| "What do I need to do?" | get_active_reminders or get_reminders |
| "Did I finish that task?" | get_completed_reminders |
| General research question | brave_web_search |
| "Where can I find...?" | brave_local_search |
| "What's the weather?" | get_weather_open_meteo |
| "Do you remember when we...?" | search_memories with query |
| End of work session | save_development_session + store_project_insight |
| Making code/architecture decision | link_code_context + store_project_insight |
| System acting weird | get_system_health |
| Reflection/learning moment | store_ai_reflection |
| Need to recall past insights | get_ai_insights |

---

## Special Notes for Nate's Context

### ADHD & Memory Considerations
- Prioritize using reminders for time-sensitive items (don't rely on memory)
- Use `get_completed_reminders` to celebrate accomplishments (mood boost)
- Document decisions immediately using `store_project_insight` (don't defer)
- Create memories for constraints and important preferences (reference later)

### Current Setup
- **Primary LLM**: LM Studio (local)
- **Fallback**: Ollama
- **OS**: Linux (Central Time)
- **Location**: Minnesota (Motley, MN for weather)
- **Main workspace**: `/media/nate/Friday/Friday`
- **Friday Memory System**: Core memory/schedule management
- **vLLM fork project**: Multi-model management system (active development)

### Key Projects Being Tracked
- Friday Memory System (main)
- persistent-ai-memory (GitHub version)
- Ollama GUI panel
- vLLM fork (multi-model management)
- OpenWebUI instance (https://fridayonline.bounceme.net)

---

## Debugging Checklist

If something isn't working:

1. **Check system health**: `get_system_health`
2. **Verify time**: `get_current_time` (before creating time-based items)
3. **Search for relevant memories**: `search_memories` with broad query
4. **Check active reminders**: `get_active_reminders`
5. **Review past insights**: `get_ai_insights` (might find previous solution)
6. **Search project history**: `search_project_history` (for code/project issues)

---

## Last Updated Information
- **Date**: 2025-11-20
- **Tool count**: 30+ available tools
- **Categories**: 6 main categories
- **Documentation accuracy**: Based on friday_memory_mcp_server.py current implementation
