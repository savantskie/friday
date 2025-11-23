# Friday Memory System - Tool Interaction Map
**Generated**: 2025-11-20 | **Version**: 1.0

---

## Quick Index

1. [Tool Interaction Flows](#tool-interaction-flows)
2. [Dependency Graph](#dependency-graph)
3. [Category Cross-References](#category-cross-references)
4. [Data Flow Diagram](#data-flow-diagram)
5. [Sequential Patterns](#sequential-patterns)
6. [Parallel Operations](#parallel-operations)

---

## Tool Interaction Flows

### Flow 1: Memory Consolidation (Learning Cycle)
```
START: Interaction with Nate
  ↓
[search_memories] → Check existing knowledge
  ├─ Found: update_memory → Enhance existing memory
  └─ Not found: create_memory → Store new information
  ↓
[store_conversation] → Optional historical record
  ↓
[store_ai_reflection] → Record learning/pattern
  ↓
END: Knowledge consolidated, pattern identified
```
**Key tools**: search_memories → create_memory/update_memory → store_ai_reflection
**Async safe**: Yes (all database operations)
**Common usage**: Every significant conversation

---

### Flow 2: Schedule & Reminder Management
```
START: Nate requests task/event management
  ↓
[get_current_time] → Get accurate datetime
  ↓
Reminder? → [create_reminder] 
  OR
Event? → [create_appointment]
  ↓
Later: [get_active_reminders] or [get_reminders]
  ↓
When complete/cancelled:
  ├─ [complete_reminder] OR [complete_appointment]
  ├─ [reschedule_reminder] (if postponing)
  └─ [cancel_appointment] (if event cancelled)
  ↓
END: Schedule managed
```
**Key tools**: get_current_time → create_reminder/create_appointment → management tools
**Async safe**: Yes
**Depends on**: Accurate timezone handling

---

### Flow 3: Information Gathering & Storage
```
START: Nate asks research question
  ↓
Research needed? → Yes
  ↓
[brave_web_search] or [brave_local_search] or [get_weather_open_meteo]
  ↓
[create_memory] → Store findings
  ↓
[store_ai_reflection] → Note what Nate needed
  ↓
END: Information found and stored for future reference
```
**Key tools**: brave_web_search → create_memory
**Async safe**: Yes
**Note**: All external API calls

---

### Flow 4: Development Context Tracking
```
START: Working on code/project
  ↓
[link_code_context] → Connect conversation to files
  ↓
During development:
  - [store_project_insight] → Record decisions
  - [search_project_history] → Recall past decisions
  ↓
End of session:
  ├─ [save_development_session] → Checkpoint
  └─ [store_ai_reflection] → Session learnings
  ↓
Next session:
  └─ [search_project_history] → Restore context
  ↓
END: Development context preserved
```
**Key tools**: link_code_context → store_project_insight → save_development_session
**Async safe**: Yes
**VS Code specific**: Yes

---

### Flow 5: Self-Improvement & Reflection
```
START: End of work session OR when I notice patterns
  ↓
[get_tool_usage_summary] → What tools did I use?
  ↓
[reflect_on_tool_usage] → Was it effective?
  ↓
[store_ai_reflection] → Record meta-insights
  ↓
[get_ai_insights] → Recall past learnings
  ↓
Next interaction: Apply insights to improve performance
  ↓
END: Continuous self-improvement cycle
```
**Key tools**: get_tool_usage_summary → reflect_on_tool_usage → store_ai_reflection
**Async safe**: Yes
**Purpose**: Meta-learning and effectiveness improvement

---

## Dependency Graph

```
get_current_time (no dependencies)
    ├─→ create_reminder (REQUIRES for datetime)
    └─→ create_appointment (REQUIRES for datetime)

search_memories (no hard dependencies)
    ├─→ update_memory (checks before updating)
    ├─→ create_memory (checks for duplicates)
    └─→ store_ai_reflection (can reference memory searches)

create_memory (optional: search_memories for dedup)
    ├─→ update_memory (source of updates)
    └─→ store_ai_reflection (documents the memory creation)

brave_web_search (no dependencies)
    ├─→ create_memory (store results)
    └─→ store_ai_reflection (note research pattern)

brave_local_search (no dependencies)
    ├─→ create_memory (store results)
    └─→ store_ai_reflection (note location preference)

get_weather_open_meteo (no dependencies)
    ├─→ create_memory (store forecast if important)
    └─→ store_ai_reflection (note weather patterns)

get_reminders (no dependencies)
    ├─→ complete_reminder (dependent: ID comes from get_reminders)
    ├─→ reschedule_reminder (dependent: ID comes from get_reminders)
    └─→ delete_reminder (dependent: ID comes from get_reminders)

create_reminder (REQUIRES get_current_time)
    ├─→ complete_reminder (creates reminder first)
    ├─→ reschedule_reminder (creates reminder first)
    └─→ get_completed_reminders (show past results)

link_code_context (no dependencies)
    ├─→ store_project_insight (parallel documentation)
    └─→ save_development_session (session-level capture)

store_project_insight (no dependencies)
    ├─→ search_project_history (retrieve stored insights)
    └─→ store_ai_reflection (meta-documentation)

get_system_health (no dependencies, diagnostic only)

get_ai_insights (no dependencies)
    └─→ store_ai_reflection (can retrieve prior reflections)

reflect_on_tool_usage (no dependencies, analysis only)

store_ai_reflection (no dependencies, write-only)

store_conversation (no dependencies)
    └─→ search_memories (can retrieve conversation)
```

---

## Category Cross-References

### Memory ↔ Schedule
- **Use case**: Store reminder completion patterns as memories
- **Tools**: get_completed_reminders → create_memory
- **Example**: Track Nate's productivity patterns

### Memory ↔ Search
- **Use case**: Store research findings
- **Tools**: brave_web_search → create_memory
- **Example**: Technical research, local business info

### Schedule ↔ Development
- **Use case**: Track work sessions
- **Tools**: create_reminder (work blocks) ↔ save_development_session
- **Example**: "Remind me to work on vLLM fork for 2 hours"

### Memory ↔ Reflection
- **Use case**: Insights about Nate or patterns
- **Tools**: search_memories → store_ai_reflection
- **Example**: "Nate prefers additive code changes (stored in memory, noted in reflection)"

### Development ↔ Reflection
- **Use case**: Learning from development work
- **Tools**: store_project_insight → store_ai_reflection → get_ai_insights
- **Example**: Architectural decisions and why they were made

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     NATE INTERACTION                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                ┌──────────┴──────────┐
                ↓                     ↓
        Task/Reminder?        Learn/Remember?
                │                     │
        ┌───────┴────────┐    ┌──────┴────────┐
        ↓                ↓    ↓               ↓
    Reminder?    Appointment?  New?    Update?
        │              │        │          │
        ↓              ↓        ↓          ↓
    [TIME CHECK]  [TIME CHECK] [SEARCH]  [SEARCH]
        │              │        │          │
        ├──────────────┴────────┤          │
        │                       │          │
        ↓                       ↓          ↓
    [CREATE REMINDER]    [CREATE MEMORY]  [UPDATE MEMORY]
        │                       │          │
        └───────────┬───────────┴──────────┘
                    │
                    ↓
            [STORE AI REFLECTION]
                    │
                    ↓
            [MEMORY SYSTEM UPDATED]


┌──────────────────────────────────────────────────────┐
│            RESEARCH/INFO QUERIES                     │
└───────────┬────────────────────────────────┬─────────┘
            │                                │
        Research?                      Weather?
            │                                │
            ↓                                ↓
    [WEB/LOCAL SEARCH]            [WEATHER FORECAST]
            │                                │
            └──────────────┬────────────────┘
                           │
                           ↓
                    [CREATE MEMORY]
                           │
                           ↓
                [STORE RESEARCH REFLECTION]


┌──────────────────────────────────────────────────────┐
│            DEVELOPMENT WORK                          │
└───────────┬────────────────────────────────┬─────────┘
            │                                │
        Code change?              Decision/Pattern?
            │                                │
            ↓                                ↓
    [LINK CODE CONTEXT]         [STORE PROJECT INSIGHT]
            │                                │
            └──────────────┬────────────────┘
                           │
                           ↓
                [SAVE DEV SESSION]
                           │
                           ↓
            [STORE DEVELOPMENT REFLECTION]
                           │
                           ↓
            [SEARCH PROJECT HISTORY (next session)]
```

---

## Sequential Patterns

### Pattern A: "Learn and Repeat"
Perfect for: Building up knowledge about Nate's preferences
```
Iteration 1:
  1. Interaction happens
  2. search_memories (don't know yet)
  3. create_memory (new learning)
  4. store_ai_reflection (noted it)

Iteration 2 (similar situation):
  1. Interaction happens
  2. search_memories (find previous learning)
  3. Reference stored preference
  4. update_memory (strengthen/refine)
  5. store_ai_reflection (pattern solidifying)

Iteration 3+: Use get_ai_insights to improve speed
```

### Pattern B: "Just-in-Time Information"
Perfect for: Research questions, weather, locations
```
1. User asks question
2. Parallel:
   - brave_web_search OR brave_local_search OR get_weather_open_meteo
   - get_current_time (if schedule-related)
3. create_memory (store finding)
4. store_ai_reflection (note what Nate researches)
```

### Pattern C: "Decision Documentation"
Perfect for: Development work, architectural choices
```
1. Working on code
2. link_code_context (connect conversation to files)
3. Make decision/solve problem
4. store_project_insight (why this approach?)
5. End session:
   - save_development_session (checkpoint)
   - store_ai_reflection (what I learned)
6. Next session: search_project_history (restore thinking)
```

### Pattern D: "Accomplishment Tracking"
Perfect for: ADHD mood support, celebrating wins
```
1. get_completed_reminders (days=1 for today)
2. For each: create_memory (accomplishment) [Optional]
3. store_ai_reflection (celebrate progress)
4. Next check-in: reference these accomplishments
```

---

## Parallel Operations

### Safe to Run in Parallel
These operations don't depend on each other's results:

```
Group 1: Information Gathering (independent of each other)
  - brave_web_search
  - brave_local_search
  - get_weather_open_meteo
  - get_reminders
  - get_appointments

Group 2: System Checks (independent of each other)
  - get_current_time
  - get_system_health
  - get_tool_usage_summary
  - reflect_on_tool_usage

Group 3: Documentation (can happen simultaneously)
  - link_code_context
  - store_project_insight
  - save_development_session

Group 4: Memories (can parallelize searches, but serialize writes)
  - Multiple search_memories calls (parallel OK)
  - All create_memory/update_memory (serialize - write one at a time)
```

### Optimization Opportunities
```
Scenario 1: Creating reminder + documenting task
  SERIAL: get_current_time → create_reminder → store_ai_reflection
  OPTIMAL: get_current_time, THEN parallel [create_reminder, store_ai_reflection]
  Reasoning: Both depend on current_time, but don't depend on each other

Scenario 2: Research + storing results
  SERIAL: brave_web_search → create_memory → store_ai_reflection
  OPTIMAL: brave_web_search, THEN parallel [create_memory, store_ai_reflection]
  Reasoning: Both depend on search results, but not on each other

Scenario 3: End-of-session save
  SERIAL: save_dev_session → store_proj_insight → store_reflection
  OPTIMAL: Parallel [save_dev_session, store_proj_insight], THEN store_reflection
  Reasoning: First two don't depend on each other, reflection can reference both
```

---

## Tool Call Checklist

Before using each tool, verify:

### For Time-Based Tools
- [ ] Tool: create_reminder, create_appointment
- [ ] Check: Did I call get_current_time first?
- [ ] Check: Is datetime in ISO 8601 format?
- [ ] Check: Is timezone correct? (Nate is Central Time)

### For Search/Query Tools
- [ ] Tool: search_memories, search_project_history, brave_web_search, brave_local_search
- [ ] Check: Have I tried a search before creating/updating?
- [ ] Check: For memories, is database_filter appropriate?

### For Storage Tools
- [ ] Tool: create_memory, update_memory, store_ai_reflection, store_project_insight
- [ ] Check: Is this new information or updating existing?
- [ ] Check: Is importance_level appropriate (1-3/4-6/7-8/9-10)?
- [ ] Check: Can I reference existing memories or insights?

### For Schedule Management
- [ ] Tool: create_reminder, create_appointment
- [ ] Check: Did I get_current_time for accurate datetime?
- [ ] Check: Single or recurring? (recurrence_pattern, recurrence_count)
- [ ] Tool: complete/reschedule/delete
- [ ] Check: Do I have the correct ID? (from get_reminders/get_appointments)

### For Development Work
- [ ] Tool: link_code_context, store_project_insight, save_development_session
- [ ] Check: Are file_paths absolute and correct?
- [ ] Check: Is description clear and actionable?
- [ ] Check: Will I remember this next session? (if not, save session)

### For Reflection/Self-Improvement
- [ ] Tool: store_ai_reflection, get_ai_insights, reflect_on_tool_usage
- [ ] Check: Is this a genuine learning or just noise?
- [ ] Check: Confidence level appropriate? (0.7-0.8/0.8-0.9/0.9+)
- [ ] Check: Can I reference past insights? (get_ai_insights first)

---

## Quick Decision Tree

```
Question: What tool should I use?

START
  ↓
Is this about scheduling?
  ├─ YES → Need to create? 
  │         ├─ Reminder? → create_reminder (get_current_time first)
  │         ├─ Event? → create_appointment (get_current_time first)
  │         └─ Manage? → get_reminders, complete_reminder, etc.
  │
  └─ NO → Is this about information/research?
           ├─ YES → Is it web research?
           │         ├─ YES → brave_web_search
           │         ├─ Location? → brave_local_search
           │         └─ Weather? → get_weather_open_meteo
           │
           └─ NO → Is this about development/code?
                    ├─ YES → link_code_context → store_project_insight
                    │
                    └─ NO → Is this about memories/learning?
                             ├─ YES → search_memories → create_memory/update_memory
                             │
                             └─ NO → Is this about reflection/improvement?
                                      ├─ YES → store_ai_reflection / get_ai_insights
                                      │
                                      └─ NO → Is this system diagnostics?
                                               └─ YES → get_system_health
```

---

## Reference: Tool Parameters Summary

| Tool | Required Params | Optional Params | Returns |
|------|---|---|---|
| search_memories | query OR memory_id | limit, database_filter, memory_type | Memory records |
| create_memory | content | memory_type, importance, tags, user_id | Memory ID |
| update_memory | memory_id | content, importance, tags | Confirmation |
| store_conversation | content, role | session_id, metadata | Conversation ID |
| create_reminder | content, due_datetime | priority, recurrence_*, user_id | Reminder ID(s) |
| get_reminders | (none) | limit, include_completed, days_ahead | Reminder list |
| complete_reminder | reminder_id | | Confirmation |
| create_appointment | title, scheduled_datetime | description, location, recurrence_*, user_id | Appointment ID(s) |
| get_appointments | (none) | limit, days_ahead | Appointment list |
| complete_appointment | appointment_id | | Confirmation |
| brave_web_search | query | count, country, language | Web results |
| brave_local_search | query | location, count, radius | Local results |
| get_weather_open_meteo | (none) | override, lat, lon, tz, update_today | Weather data |
| get_current_time | (none) | (none) | UTC + local time |
| store_ai_reflection | content | reflection_type, insights, recommendations, confidence_level | Reflection ID |
| get_ai_insights | (none) | limit, insight_type, query | Insight records |
| link_code_context | file_path, description | function_name, conversation_id | Context link ID |
| store_project_insight | content | insight_type, related_files, importance | Insight ID |
| save_development_session | workspace_path | active_files, git_branch, summary | Session ID |
| search_project_history | query | limit | History records |
| get_system_health | (none) | (none) | System status |

---

## Common Gotchas & Solutions

| Problem | Cause | Solution |
|---------|-------|----------|
| Reminder created with wrong time | Didn't call get_current_time first | Always call get_current_time before time-based operations |
| Memory not found | Wrong database_filter | Try database_filter="all" first, then narrow down |
| Duplicate memories created | Didn't search first | Always search_memories before create_memory |
| Can't reschedule reminder | Wrong reminder ID | Use get_reminders first to get current ID |
| Project insight not saved | Forgot to call store_ai_reflection | Always follow up storage with reflection |
| Can't find past decision | Didn't use search_project_history | Search before storing (may already exist) |
| Tool not working | Haven't checked system health | Call get_system_health to diagnose |
| Session context lost | Didn't call save_development_session | Save at end of each work session |
| Timezone issues | Assuming system time = Nate's time | Always use get_current_time, specify Central Time |
| Low confidence in insight | Storing with default 0.7 | Adjust confidence_level based on certainty |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-20 | Initial comprehensive map |

---

**For Updates**: Reference `/media/nate/Friday/Friday/AI_HELPER_DOCS.md` for detailed tool documentation.
