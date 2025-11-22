# Friday Memory System - Quick Reference Guide
**Purpose**: Fast lookup for common scenarios | **Updated**: 2025-11-20

---

## I Need To... (Quick Find)

### Schedule & Reminders

#### "Set a reminder for Nate"
```
1. get_current_time
2. create_reminder(
     content="<task description>",
     due_datetime="<ISO datetime>",
     priority_level=<1-10>
   )
Optional: Recurring?
  - Add: recurrence_pattern="weekly", recurrence_count=12
```

#### "Check what Nate needs to do"
```
get_active_reminders(days_ahead=7, limit=10)
```

#### "Mark a task as done"
```
complete_reminder(reminder_id="<from get_active_reminders>")
```

#### "Nate wants to reschedule a task"
```
reschedule_reminder(
  reminder_id="<from get_reminders>",
  new_due_datetime="<new ISO datetime>"
)
```

#### "Create a recurring appointment"
```
1. get_current_time
2. create_appointment(
     title="<appointment name>",
     scheduled_datetime="<ISO datetime>",
     description="<optional>",
     location="<optional>",
     recurrence_pattern="weekly",  # or daily/monthly/yearly
     recurrence_count=12          # for 12 weeks
   )
```

#### "See what Nate accomplished today"
```
get_completed_reminders(days=1)
# Perfect for celebrating wins!
```

---

### Memory & Learning

#### "Remember something important about Nate"
```
1. search_memories(query="<similar topic>", database_filter="ai_memories")
   # Check if we already know this
2. If new:
   create_memory(
     content="<what I learned>",
     memory_type="preference",  # or skill, safety, general
     importance_level=<1-10>,   # 7+ for important stuff
     tags=["<tag1>", "<tag2>"]
   )
3. store_ai_reflection(
     reflection_type="memory",
     content="Learned: <summary>"
   )
```

#### "Check what I know about something"
```
search_memories(
  query="<topic or person>",
  database_filter="ai_memories",
  limit=10
)
```

#### "Update a memory with new info"
```
1. search_memories(query="<topic>")  # Find the memory first
2. update_memory(
     memory_id="<ID from search>",
     content="<updated content>",
     importance_level=<optional new level>
   )
```

#### "Find a specific memory by ID"
```
search_memories(memory_id="<exact ID>")
# Faster than semantic search if you know the ID
```

---

### Research & Information

#### "Research something for Nate"
```
1. Parallel:
   - brave_web_search(query="<search topic>", count=10)
   OR
   - brave_local_search(query="<place/service>", location="<optional>")
   OR
   - get_weather_open_meteo()  # Weather question
   
2. create_memory(
     content="<findings>",
     memory_type="general",
     importance_level=5
   )
   
3. store_ai_reflection(
     reflection_type="research",
     content="Researched: <topic>"
   )
```

#### "Find a business near Nate"
```
brave_local_search(
  query="<business type>",
  location="Minnesota",  # or specific address
  radius=5000,          # meters
  count=10
)
```

#### "Get current weather"
```
get_weather_open_meteo()  # Uses Motley, MN by default

# With custom location:
get_weather_open_meteo(
  override=True,
  latitude=46.8,
  longitude=-95.5,
  timezone_str="America/Chicago"
)
```

---

### Development & Project Work

#### "Starting a development session"
```
1. link_code_context(
     file_path="/media/nate/Friday/Friday/<filename>",
     description="Working on: <what>",
     function_name="<optional: function we're changing>"
   )
```

#### "Make an architectural decision"
```
store_project_insight(
  content="Decision: <what we decided and why>",
  insight_type="architecture",
  related_files=["/path/to/file1.py", "/path/to/file2.py"],
  importance_level=8  # Architectural decisions are usually important
)
```

#### "End a work session"
```
1. save_development_session(
     workspace_path="/media/nate/Friday/Friday",
     active_files=["/path/to/file1.py", "/path/to/file2.py"],
     git_branch="main",  # or current branch
     session_summary="<what was accomplished>"
   )

2. store_ai_reflection(
     reflection_type="development",
     content="Session summary: <what I learned>",
     source_period_days=1
   )
```

#### "Find past development decisions"
```
search_project_history(
  query="<topic, function name, or feature>",
  limit=10
)
```

#### "Recall context from last session"
```
search_project_history(query="<project or feature>")
# Find your past decisions and reasoning
```

---

### Self-Improvement & Analysis

#### "Reflect on how I'm doing"
```
1. get_tool_usage_summary(days=7)
   # What tools do I use most?

2. reflect_on_tool_usage(days=7)
   # Am I using them effectively?

3. store_ai_reflection(
     reflection_type="tool_usage_analysis",
     content="<what I learned about my patterns>",
     insights=[
       "I use X tool too much for Y",
       "I should use Z tool more for efficiency"
     ],
     recommendations=["Use X only for...", "Plan to use Y for..."],
     confidence_level=0.8
   )
```

#### "See what I've learned before"
```
get_ai_insights(
  limit=10,
  insight_type="tool_usage_analysis"  # or specific type
)
```

#### "Find a past insight about something"
```
get_ai_insights(
  query="<topic>",
  limit=5
)
# Searches my stored reflections
```

---

### System & Diagnostics

#### "Check if Friday is working properly"
```
get_system_health()
# Shows database status, memory, errors, etc.
```

#### "Get the current server time"
```
get_current_time()
# Returns: UTC time AND Nate's local time (Central)
# Use before any time-based operations
```

---

## Common Workflows (Copy-Paste Ready)

### Workflow 1: "Learn, Store, Reflect"
```python
# When learning something important about Nate
search_results = search_memories(
  query="<topic>",
  database_filter="ai_memories"
)

if not search_results:
    memory_id = create_memory(
        content="<what I learned>",
        memory_type="<preference/skill/general>",
        importance_level=7
    )
else:
    memory_id = update_memory(
        memory_id=search_results[0]['id'],
        content="<updated info>"
    )

store_ai_reflection(
    reflection_type="memory",
    content=f"Updated knowledge about: <topic>"
)
```

### Workflow 2: "Quick Task Management"
```python
# When Nate says "remind me to..."
current_time = get_current_time()
# Calculate due_datetime from current_time

reminder = create_reminder(
    content="<task>",
    due_datetime="<calculated ISO time>",
    priority_level=6
)

# Later, when checking:
active = get_active_reminders(days_ahead=7)

# When done:
complete_reminder(reminder_id=<from active>)
```

### Workflow 3: "Research & Document"
```python
# Research question
results = brave_web_search(query="<topic>")
# OR brave_local_search(query="<place>")
# OR get_weather_open_meteo()

memory = create_memory(
    content=f"Research findings: {results}",
    memory_type="general",
    importance_level=5
)

store_ai_reflection(
    reflection_type="research",
    content=f"Found information about: <topic>"
)
```

### Workflow 4: "Development Checkpoint"
```python
# During development
link_code_context(
    file_path="/media/nate/Friday/Friday/important_file.py",
    description="Working on feature X"
)

# Record decisions as you make them
store_project_insight(
    content="Decision: Used approach Y because Z",
    insight_type="architecture",
    importance_level=7
)

# End of session
save_development_session(
    workspace_path="/media/nate/Friday/Friday",
    active_files=["/path/to/file.py"],
    session_summary="Completed: X. Next: Y."
)
```

### Workflow 5: "Celebrate & Analyze"
```python
# Nate's mood boost
completed = get_completed_reminders(days=1)

create_memory(
    content=f"Accomplished today: {[r['content'] for r in completed]}",
    memory_type="accomplishment",
    importance_level=6,
    tags=["daily_win", "productivity"]
)

store_ai_reflection(
    reflection_type="motivation",
    content="Nate had a productive day!",
    insights=["Strong momentum on X", "Completed Y tasks"]
)
```

---

## Parameter Values Reference

### Importance Levels (1-10 scale)
| Level | Use For |
|-------|---------|
| 1-2 | Trivial details, one-time info |
| 3-4 | Minor preferences, casual notes |
| 5-6 | Regular preferences, decisions, ongoing notes |
| 7-8 | Important constraints, key decisions, architectural choices |
| 9-10 | Life-affecting, safety-critical, core identity |

### Memory Types
- `"preference"` - Nate's likes/dislikes/preferences
- `"skill"` - Knowledge/skills Nate has or I've learned he needs
- `"safety"` - Safety-critical information, constraints
- `"general"` - Other information
- `"accomplishment"` - Wins, completed tasks
- `"pattern"` - Behavioral patterns I've noticed
- `"technical"` - Technical knowledge/debugging notes
- `"personal"` - Personal information

### Reflection Types
- `"general"` - Default, general observations
- `"tool_usage_analysis"` - How I'm using tools
- `"memory"` - About memories I'm creating/updating
- `"pattern_analysis"` - Patterns I've noticed
- `"development"` - Development/coding work insights
- `"research"` - Research activities
- `"motivation"` - About accomplishments, mood
- `"error_analysis"` - When something went wrong

### Recurrence Patterns
```
- "daily"    - Every day
- "weekly"   - Every week (common for tasks)
- "monthly"  - Every month
- "yearly"   - Every year
```

### Database Filters
- `"conversations"` - Past chat history
- `"ai_memories"` - My stored memories (high quality)
- `"schedule"` - Reminders and appointments
- `"all"` - Everything (default, slower)

---

## Confidence Levels (for Reflections)

| Range | Meaning | Use For |
|-------|---------|---------|
| 0.5-0.6 | Uncertain, tentative observation | New hypothesis, needs verification |
| 0.7-0.8 | Likely correct, noticed a pattern | Clear patterns, reasonable confidence |
| 0.8-0.9 | High confidence, clear pattern | Solid patterns, confirmed multiple times |
| 0.9-1.0 | Very confident, explicit information | Nate told me directly, documented fact |

---

## Error Prevention Checklist

- [ ] **Before creating reminder**: Called `get_current_time` first?
- [ ] **Before creating memory**: Called `search_memories` to check for duplicates?
- [ ] **Before updating**: Found the correct memory/reminder ID?
- [ ] **For time operations**: Using ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)?
- [ ] **For searches**: Specified appropriate `database_filter`?
- [ ] **For development**: Using absolute paths to files?
- [ ] **After storage operations**: Storing reflection to document it?
- [ ] **For sensitive info**: Set importance level appropriately (7+ for important)?

---

## Performance Tips

### Fast Path (Best Practice)
1. `search_memories(memory_id="exact_id")` - Direct lookup beats semantic search
2. `get_active_reminders()` - Faster than `get_reminders()` with filtering
3. Batch parallel: Do multiple independent searches together
4. Remember: `get_current_time` once, use result multiple times

### Slow Path (Avoid if Possible)
1. `search_memories()` without memory_id - Semantic search is slower
2. `search_memories()` with `database_filter="all"` - Searches everything
3. Sequential time-dependent operations - Use `get_current_time()` once first
4. Creating memory without checking duplicates - Creates waste

---

## Nate-Specific Notes

### ADHD Considerations
- Use reminders liberally - don't assume memory
- Get completed_reminders regularly (mood boost!)
- Document decisions immediately (don't defer)
- Short-term: reminders, Long-term: memories

### Timezone
- **Nate's timezone**: America/Chicago (Central Time)
- **Default weather location**: Motley, MN
- Always use `get_current_time()` to get accurate local time

### Code Preferences
- **No refactoring** unless absolutely necessary
- **Additive changes only** unless discussed first
- **Absolute paths** for file references
- **No stubs** unless approved and explained

### Current Projects
- Friday Memory System (primary)
- persistent-ai-memory (GitHub version)
- vLLM fork (multi-model management)
- OpenWebUI instance at https://fridayonline.bounceme.net

---

## Quick Troubleshooting

| Problem | Quick Fix |
|---------|-----------|
| Memory not found | Try `search_memories(query="...", database_filter="all")` |
| Reminder time wrong | Use `get_current_time()` before creating |
| Can't find past decision | Use `search_project_history()` |
| Tool not responding | Run `get_system_health()` to diagnose |
| Lost session context | Use `search_project_history(query="project name")` |
| Can't complete reminder | Use `get_reminders()` first to get current ID |

---

## File Locations Reference

| What | Location |
|------|----------|
| Main Friday System | `/media/nate/Friday/Friday/` |
| MCP Server | `/media/nate/Friday/Friday/friday_memory_mcp_server.py` |
| Memory System | `/media/nate/Friday/Friday/friday_memory_system.py` |
| Logs | `/media/nate/Friday/Friday/Logs/` |
| GitHub Version | `/media/nate/Friday/Friday/persistent-ai-memory/` |
| Decisions | `/media/nate/Friday/Friday/Decisions_Folder/` |
| Summaries | `/media/nate/Friday/Friday/Summaries/` |
| vLLM Fork | `/media/nate/Friday/vllm/` |

---

## How to Use These Docs

1. **For quick lookup**: Start here, then check AI_HELPER_DOCS.md for details
2. **For complex interactions**: Check TOOL_INTERACTION_MAP.md
3. **For deep understanding**: Read AI_HELPER_DOCS.md completely
4. **For workflows**: Copy sections from "Common Workflows"
5. **For errors**: Use "Quick Troubleshooting" table
6. **For learning**: Study the patterns and workflows

---

**Last Update**: 2025-11-20 | **Created for**: Efficient AI assistance for Nate's projects
