FRIDAY MEMORY SYSTEM (FMS) -- COMPLETE SYSTEM MAP
===================================================
Generated: August 3, 2026
Location: /media/nate/Friday/Friday/
===================================================
Version: 0.0.29 (friday_memory_short_term.py)


1. SYSTEM ARCHITECTURE OVERVIEW
================================

The Friday Memory System is a two-layer AI memory infrastructure:

  Layer 1 -- Short-Term Memory (OpenWebUI Plugin)
    Runs inside OpenWebUI as a pipe filter. Handles real-time memory
    extraction and injection via the inlet/outlet pattern. Operates on
    OpenWebUI's own memory table AND bridges to the long-term system.

  Layer 2 -- Long-Term Memory System (MCP Server)
    Standalone MCP server with HTTP API and stdio transport. Manages
    all persistent databases: conversations, curated memories, schedule,
    MCP tool calls, VS Code projects, and AI reflections.


2. FILE-BY-FILE INDEX
================================
  Legend:  [OWNER] = primary owner of a database or table
           [READS] = reads from a database owned by another file
           [COORD]  = participates in coordinator task scheduling

  -----------------------------------------------------------------------
  FILE: friday_memory_system.py  (~10,443 lines)
  ROLE: Core long-term memory system. Contains all database classes,
        the FridayMemorySystem orchestrator, EmbeddingService, and
        ConversationFileMonitor.

  CLASSES:
    DatabaseManager         -- Base class: get_connection(), execute_query(),
                               execute_update(), PRAGMA foreign_keys=ON
    ConversationDatabase     [OWNER: conversations.db]
    AIMemoryDatabase         [OWNER: ai_memories.db]
    ScheduleDatabase         [OWNER: schedule.db]
    VSCodeProjectDatabase    [OWNER: vscode_project.db]
    MCPToolCallDatabase      [OWNER: mcp_tool_calls.db]
    ConversationFileMonitor  -- Watches external chat dirs, imports
    EmbeddingService         -- Generates embeddings via LM Studio/Ollama
    FridayMemorySystem       -- Main orchestrator, delegates all MCP tools

  USER_ID/MODEL_ID NORMALIZATION:
    - USER_ID_ALIASES map: {"nate", "Nate"} -> canonical UUID
    - All DB queries use LOWER(model_id) = ? (case-insensitive)
    - Missing user_id/model_id returns hard error dict

  -----------------------------------------------------------------------
  FILE: friday_memory_mcp_server.py  (~2,914 lines)
  ROLE: MCP server interface. Exposes all Friday memory tools via both
        stdio transport and HTTP API (FastAPI). Client-aware tool
        registration (VS Code, SillyTavern, or core tools).

  CLASSES:
    FridayMemoryMCPServer    -- Server init, tool registration, maintenance loop
    MCPStreamableSessionManager -- Streamable HTTP session management
    MCPASGIHandler           -- ASGI adapter for FastAPI integration

  SERVER LIFECYCLE:
    1. Creates FridayMemoryMCPServer
    2. Claims maintenance ownership via TaskCoordinator
    3. Starts HTTP server (FastAPI on port 21434+) 
    4. Runs MCP stdio server
    5. Delayed start: 60s before file monitoring, maintenance, OWUI import

  ENDPOINTS:
    GET  /api/health
    GET  /api/diagnostics
    /mcp/sse (MCP transport)
    (POST /api/memories/promote and DELETE /api/memories/cleanup were never
     implemented — memory promotion runs via TaskCoordinator, not HTTP)

  TOOLS (all require user_id + model_id):
    Core: search_memories, create_memory, update_memory,
          get_conversation_context, search_memories_by_date,
          store_conversation, get_recent_context, get_system_health,
          get_error_summary, get_tool_information, reflect_on_tool_usage,
          get_ai_insights, store_ai_reflection, write_ai_insights,
          get_current_time, trigger_database_maintenance,
          export_all_tool_calls, list_available_tags,
          list_available_memory_banks

    Schedule: create_reminder, create_appointment, complete_reminder,
              get_active_reminders, get_completed_reminders,
              reschedule_reminder, delete_reminder, cancel_appointment,
              complete_appointment, get_upcoming_appointments,
              get_reminders, get_appointments

    VS Code (vscode client only): save_development_session,
              store_project_insight, search_project_history,
              link_code_context, get_project_continuity

    SillyTavern: get_character_context, store_roleplay_memory,
              search_roleplay_history

  -----------------------------------------------------------------------
  FILE: friday_memory_short_term.py  (~11,255 lines)
  ROLE: Short-term memory plugin inside OpenWebUI. Handles memory
        extraction from chat messages, relevance scoring, injection
        into prompts, and memory promotion to long-term system.
        [COORD] Registers background tasks on the TaskCoordinator.

  CLASSES:
    Filter (main class)
      EmbeddingCache (nested) -- SQLite cache for embeddings
      Valves (nested)         -- All configuration parameters
      UserValves (nested)     -- Per-user configuration
    ImageManager              -- Persistent image storage
    ConversationCharacterTracker -- Character context tracking
    MemoryOperation           -- Pydantic model for memory ops

  LOG FILES:
    friday_short_term_memory.log
    friday_short_term_inlet_outlet.log
    friday_short_term_errors.log
    friday_core_identity.log

  -----------------------------------------------------------------------
  FILE: database_maintenance.py  (~2,917 lines)
  ROLE: Automated database cleanup, optimization, retention policies,
        sharding/rotation management. [COORD]

  CLASSES:
    DatabaseMaintenance
      ltm_maintenance -- LongTermMemoryMaintenance instance

  RETENTION POLICIES:
    conversations.db          -- INDEFINITE (no pruning)
    curated_memories (ai_memories.db) -- INDEFINITE (no pruning)
    schedule.db              -- 90 days, cleanup completed items
    mcp_tool_calls.db        -- INDEFINITE
    memory_conversation_links -- INDEFINITE, remove orphans only
    memory_processing_queue   -- 90 days, cleanup completed
    memory_processing_log     -- 90 days, max 100k entries
    image_database.db         -- INDEFINITE

  MAINTENANCE PIPELINE (13 steps, called from coordinator):
    1.  check_and_rotate_all_databases()     -- 3GB or month boundary
    2.  archive_rotate_to_sharded_structure() -- moves data to archives/
    3.  _upgrade_schemas()                    -- adds missing columns
    4.  _apply_retention_policies()           -- schedule + processing logs only
    5.  _remove_duplicates()
    6.  _optimize_databases()
    7.  _collect_statistics()
    8.  _build_tag_registries()
    9.  _build_memory_bank_registries()
    10. _retroactively_link_memories()
    11. ltm_maintenance.reformat_memories()    -- LLM-powered reformat
    12. ltm_maintenance.scan_for_updates()      -- contradiction detection
    13. ltm_maintenance.assist_linking()        -- text-overlap linker

  ROTATION: DB files > 3GB or crossing month boundary get sharded.
    Archives are PERMANENT. Old data is never deleted.

  -----------------------------------------------------------------------
  FILE: friday_memory_maintenance.py  (595 lines)
  ROLE: LLM-powered maintenance for long-term memories.

  CLASS: LongTermMemoryMaintenance
    _call_llm()           -- Calls qwen-3 on port 8080
    reformat_memories()   -- Scans for missing [Tags:]/[Memory Bank:] markers
    scan_for_updates()    -- Detects contradictions/updates between pairs
    assist_linking()      -- Text-overlap matcher for unlinked memories

  -----------------------------------------------------------------------
   FILE: core_identity.py  (1,686 lines)
  ROLE: Distills Friday's personality, relationships, principles, and
        facts about Nate from curated memories and conversations.
        Generates structured text for system prompt injection.
        [OWNER: core_identity table in ai_memories.db]

  CLASS: CoreIdentityManager
    Memory sources (3):
      1. curated_memories (FMS long-term db, incremental)
      2. OpenWebUI memory table (webui.db, cursor-tracked)
      3. Archived monthly databases (cursor-paginated, newest first)

Output format (5 sections):
       [Personality]    -- traits, communication style
       [Relationship]   -- how Friday and Nate relate
       [Principles]     -- values, preferences, decision patterns
       [Facts About Nate] -- concrete, current persistent facts
       [Historical Context] -- superseded facts preserved with timestamps

    Batch processing: chunks of 50 memories, incremental LLM calls.
    Progress saved for crash recovery (core_identity_progress.json) --
    NOTE: this file does not currently exist on disk; crash recovery
    during generation is non-functional.

  FILES WRITTEN:
    memory_data/friday_core_identity_<uuid>_<model_id>.json   -- Per-user+model JSON backup (migrated Aug 2026 from old per-user naming)
    core_identity_progress_<uuid>_<model_id>.json       -- pause/resume state per user+model
    memory_data/core_identity_tracking.json       -- cursor state for webui/archives
    (system_prompt.txt path defined in __init__ but never read or written — orphaned)

  -----------------------------------------------------------------------
  FILE: task_coordinator.py  (419 lines)
  ROLE: Centralized clock-based scheduler replacing sleep-loop patterns.
        Manages task concurrency, idle gating, and maintenance ownership.

  CLASSES:
    ScheduleExpr   -- Parses "daily@HH:MM", "interval:Xs/Xm/Xh"
                      with ",idle" and ",quiet" suffixes
    TaskDef        -- Task state: errors, disabled, last_run, next_run
    TaskCoordinator (singleton)
      Category concurrency:
        "db_light"  -- free (no mutex)
        "db_heavy"  -- per-db mutex
        "llm"       -- global mutex (one LLM call at a time)

      Idle detection: 10+ minutes since last inlet activity
      Quiet hours: midnight-6am CT
      Maintenance ownership: claim file with 60s heartbeat, 120s stale threshold

  -----------------------------------------------------------------------
  FILE: port_manager.py  (414 lines)
  ROLE: Intelligent port binding and caller program detection.

  CLASS: PortManager
    PRIMARY_PORT: 21434
    BACKUP_PORTS: 21435-21439
    PORT_INFO_FILENAME: mcp_server_port.json (in memory_data/)
    Caller detection: multi-level process hierarchy inspection

  -----------------------------------------------------------------------
  FILE: tag_manager.py  (309 lines)
  ROLE: Tag extraction, normalization, and registry management.

  CLASS: TagManager
    extract_tags_from_content()  -- regex [Tags: ...] extraction
    normalize_tag()             -- lowercase
    build_tag_registry()        -- {canonical: {variations, components, count}}
    save_registry()/load_registry() -- JSON file persistence
    get_canonical_form()        -- registry lookup

  FILE: tag_registry.json  -- Current state: 4 tags (from recent rebuild; prior 32 tags lost in rebuild)

  -----------------------------------------------------------------------
FILE: memory_bank_registry.json
ROLE: Tracks available memory banks with counts. 8 banks discovered:
      context, general, personal, preferences, projects, tasks,
      technical, work

  -----------------------------------------------------------------------
  FILE: embedding_config.json
  ROLE: Embedding provider configuration.

  Primary:   lm_studio, text-embedding-nomic-embed-text-v1.5, 768d
             http://192.168.1.50:1234/v1/embeddings
  Fallback:  ollama, nomic-embed-text:latest
             http://localhost:11434/api/embeddings

  -----------------------------------------------------------------------
  FILE: utils.py  (60 lines)
  ROLE: Timezone handling.

  FUNCTIONS:
    get_local_timezone()  -- ZoneInfo from system, fallback America/Chicago
    parse_timestamp()     -- Converts ISO strings, Unix seconds/millis


3. DATABASE SCHEMAS (WHO OWNS WHAT)
=====================================

  conversations.db   [OWNER: friday_memory_system.py :: ConversationDatabase]
  -------------------------------------------------------------------------
  sessions: (session_id PK, start_timestamp, end_timestamp, context,
             embedding, created_at)
  conversations: (conversation_id PK, session_id FK, start_timestamp,
                  end_timestamp, topic_summary, embedding, user_id,
                  model_id, created_at)
  messages: (message_id PK, conversation_id FK, timestamp, role, content,
             source_type, source_id, source_url, source_metadata,
             sync_status, last_sync, metadata, embedding, created_at,
             source, user_id, model_id, message_hash)
  source_tracking: (source_id PK, source_type, source_name, source_path,
                    last_check, last_sync, status, error_count, created_at)
  conversation_relationships: (relationship_id PK, source_conversation_id FK,
                              related_conversation_id FK, relationship_type,
                              metadata, created_at)
  memory_conversation_links: (link_id PK, memory_id, conversation_id FK,
                              link_type, link_strength, source_system,
                              created_at, updated_at, metadata)
  memory_processing_queue: (queue_id PK, conversation_id, memory_id,
                           status, processing_type, priority, attempts,
                           message_count, marked_processed, last_attempt,
                           created_at, updated_at)
  memory_processing_log: (log_id PK, conversation_id, memory_id,
                          processing_type, status, action, reason,
                          result_metadata, created_at)
  memory_relationships: (relationship_id PK, source_memory_id,
                          target_memory_id, relationship_type, notes,
                          created_at)

  ai_memories.db   [OWNER: friday_memory_system.py :: AIMemoryDatabase]
  -------------------------------------------------------------------------
  curated_memories: (memory_id PK, timestamp_created, timestamp_updated,
                     source_conversation_id, source_message_ids,
                     memory_type, content, importance_level, tags,
                     embedding, embedding_dimension, user_id, model_id,
                     memory_bank, source, created_at, updated_at,
                     core_identity_processed_until)
  core_identity: (id PK AUTOINCREMENT, user_id, model_id, version,
                  content, metadata, last_generated_at, created_at,
                  updated_at, UNIQUE(user_id, model_id))
     [NOTE: core_identity table is ALSO managed by core_identity.py]

  schedule.db   [OWNER: friday_memory_system.py :: ScheduleDatabase]
  -------------------------------------------------------------------------
  appointments: (appointment_id PK, timestamp_created, scheduled_datetime,
                 title, description, location, status CHECK(scheduled|
                 cancelled|completed), cancelled_at, completed_at,
                 source_conversation_id, embedding, created_at,
                 user_id, model_id)
  reminders: (reminder_id PK, timestamp_created, due_datetime, content,
              priority_level, completed, is_completed, completed_at,
              source_conversation_id, conversation_title, urgency_level,
              notification_sent_at, notification_status CHECK(pending|sent|
              read|dismissed), escalation_count, last_escalated_at,
              embedding, created_at, user_id, model_id)
  reminder_notifications: (notification_id PK, reminder_id FK,
                          urgency_level, created_at, updated_at,
                          user_id, model_id, UNIQUE(reminder_id,
                          urgency_level, user_id, model_id))

  mcp_tool_calls.db   [OWNER: friday_memory_system.py :: MCPToolCallDatabase]
  -------------------------------------------------------------------------
  tool_calls: (call_id PK, timestamp, client_id, tool_name, parameters,
               execution_time_ms, status, result, error_message,
               embedding, created_at, source)
  usage_patterns: (pattern_id PK, timestamp_created, analysis_period_days,
                   pattern_type, insight, confidence_score,
                   supporting_data, embedding, created_at)
  ai_reflections: (reflection_id PK, timestamp_created, reflection_type,
                   content, insights, recommendations, confidence_level,
                   source_period_days, embedding, created_at, user_id,
                   model_id, source)

  vscode_project.db   [OWNER: friday_memory_system.py :: VSCodeProjectDatabase]
  -------------------------------------------------------------------------
  project_sessions: (session_id PK, start_timestamp, end_timestamp,
                     workspace_path, active_files, git_branch,
                     git_commit_hash, session_summary, embedding,
                     created_at, user_id, model_id)
  development_conversations: (conversation_id PK, session_id FK, timestamp,
                              chat_context_id, conversation_content,
                              decisions_made, code_changes,
                              source_metadata, embedding, created_at,
                              user_id, model_id, source)
  project_insights: (insight_id PK, timestamp_created, timestamp_updated,
                     insight_type, content, related_files,
                     source_conversation_id, importance_level, embedding,
                     created_at, user_id, model_id, source)
  code_context: (context_id PK, timestamp, file_path, function_name,
                 description, purpose, related_insights, embedding,
                 created_at, user_id, model_id)

  image_database.db   [OWNER: friday_memory_short_term.py :: ImageManager]
  -------------------------------------------------------------------------
  images: (image_hash PK, image_url, image_data BLOB, image_description,
           created_at)

  memory_embeddings.db   [OWNER: friday_memory_short_term.py :: EmbeddingCache]
  -------------------------------------------------------------------------
  memory_embeddings: (content_hash PK, embedding BLOB, created_at)

  character_tracker.db   [OWNER: friday_memory_short_term.py :: ConversationCharacterTracker]
  -------------------------------------------------------------------------
  conversation_characters: (conversation_id PK, character_name,
                            is_persistent, model_card_name, created_at,
                            last_used)


4. DATA FLOW BETWEEN COMPONENTS
================================

    [User types message in OpenWebUI]
                |
                v
    +-----------------------+
    | Filter.inlet()         |  <-- friday_memory_short_term.py
    | Line 4727-5236         |
    | (1) Extract user/model |
    | (2) Normalize names    |
    | (3) Load core identity |
    | (4) Check summaries    |
    | (5) Fetch reminders    |
    | (6) Get relevant mems  |
    | (7) Inject all roles   |
    | (8) Return body        |
    +-----------+-----------+
                |
                v
    [OpenWebUI sends body to LLM]
                |
                v
    [LLM generates response]
                |
                v
    +-----------------------+
    | Filter.outlet()        |  <-- friday_memory_short_term.py
    | Line 5238-5456         |
    | (1) Extract user/model |
    | (2) Find last msg pair |
    | (3) Queue memory extrn |
    | (4) Get relevant mems  |
    | (5) Inject for next    |
    | (6) Store conversation |
    +-----------+-----------+
                |
        +-------v--------+
        | Memory Task Q   |  (asyncio.Queue)
        | (async worker)  |
        +-------+--------+
                |
    +-----------v----------------------+
    | Memory extraction (LLM call)     |
    | - Save to OpenWebUI memory table |
    | - Save to FMS curated_memories   |  --> friday_memory_system.py
    | - Link to source conversation    |
    +----------------------------------+

  PARALLEL FLOWS (MCP Server -- friday_memory_mcp_server.py):
    [MCP client (VS Code / LM Studio / OWUI / external)]
                |
                v
    +-------------------------------+
    | FridayMemoryMCPServer         |
    | (tool dispatch)               |
    |                               |
    | -> all operations delegate to |
    |    FridayMemorySystem methods |
    |    in friday_memory_system.py |
    +-------------------------------+

  BACKGROUND TASKS (registered by friday_memory_short_term.py):

    TaskCoordinator (singleton, task_coordinator.py)
    |
    +-- summarization      (every 2hr,      "db_heavy", requires_idle)
    +-- error_logging      (every 30min,    "db_light")
    +-- date_update        (every 1hr,      "db_light")
    +-- retry_queue        (every 5min,     "db_light")
    +-- memory_promotion   (every 24hr,     "db_heavy")
    +-- memory_linking     (daily@02:00,    "db_heavy", requires_idle)
    +-- registry_sync      (every 2hr,      "db_heavy", requires_idle)
    +-- nightly_sync       (daily@02:30,    "db_heavy", requires_idle)
    +-- core_identity      (daily@00:30,    "llm", requires_idle)
    +-- model_discovery    (disabled by default)
    +-- openwebui_import   (every 3hr,      "db_light")
    +-- maintenance_mcp    (every 6hr,      "db_heavy", only if maintenance owner)
    +-- maintenance_24h    (daily@05:00,    "db_heavy", only if maintenance owner)
    +-- linking_validation (every 6hr,      "db_heavy", only if maintenance owner)

    MCP Server tasks:
    +-- database_maintenance (every 6hr, via _maintenance_loop)
    +-- OpenWebUI chat import (every 3hr)
    +-- module file monitor   (every 2s, _check_and_reload_modules)


5. INLET/OUTLET PIPELINE INJECTION ORDER
=========================================

  INLET (before LLM sees the message) -- from furthest to closest:

    1. [datetime]   Current date and time (every turn)
                    Inserted as <|turn>datetime...<turn|>
                    Seconds precision: Weekday, Month DD, YYYY, HH:MM:SS TZ

    2. [identity]    Core Identity text (every turn)
                     Inserted as <|turn>identity...<turn|>
                     <- core_identity.py :: CoreIdentityManager

    3. [summary]     Conversation summary (when threshold reached)
                     Inserted as system message context

    4. [reminders]   Active reminders from schedule.db
                     Inserted as <|turn>reminders...<turn|>
                     <- friday_memory_system.py :: ScheduleDatabase

    5. [memories]    Relevant memories ranked by relevance score
                     Inserted as <|turn>memories...<turn|>
                     <- OpenWebUI memory table + curated_memories

  OUTLET (after LLM responds) -- same injection for NEXT message:

    1. [memories]    Fresh retrieval based on latest exchange
                     <- OpenWebUI memory table + curated_memories

    2. [status]      Confirmation message (if show_status valve on)

  SHARED INJECTION HELPER:
    _insert_before_last_user(body, role_name, content)
    Inserts a role message just before the final user message
    in the messages array. Format: <|turn>rolename\ncontent<turn|>

  ORDER list in code: ["datetime", "identity", "summary", "reminders", "memories"]


6. ROLE INJECTION SEQUENCE (Core Identity System)
===================================================

GENERATION (runs daily at 12:30 AM, idle-only):
     1. TaskCoordinator fires core_identity task (daily@00:30,idle)
    2. _core_identity_work() in friday_memory_short_term.py
    3. Lazy-imports CoreIdentityManager from core_identity.py
    4. Calls manager.run_generation() with idle check callback

  DATA GATHERING (three sources, deduplicated):
    a. curated_memories table (FMS long-term)
       -> Incremental since last processed timestamp
    b. OpenWebUI memory table (webui.db)
       -> Cursor-tracked by created_at
    c. Archived monthly databases (memory_data/archives/)
       -> Cursor-paginated, newest first

  BATCH PROCESSING:
    - Chunks of 50 memories
    - Batch 1: Build identity from scratch
    - Batches 2+: Update existing (selectivity-focused)
    - System prompt emphasizes: patterns, high-importance (8-10),
      moments of connection, core constraints, values earned
    - Update mode is conservative: "A single memory is not enough
      to change identity unless it carries extraordinary weight."
    - Progress saved to core_identity_progress.json after each batch
    - Pauses if user becomes active (idle check)

  STORAGE (atomic):
    1. Save to core_identity table in ai_memories.db (version++)
    2. Mark processed memories with core_identity_processed_until
    3. Update tracking cursors for webui/archives
    4. Write friday_core_identity_<uuid>_<model_id>.json backup
    5. Write to OpenWebUI knowledge base

   INJECTION (every inlet call):
     1. Filter.inlet() calls _inject_core_identity_into_context()
     2. Guard: None (guard removed June 28, injects every turn)
     3. Loads identity via manager.get_core_identity_for_injection()
     4. Inserts as "identity" role via _insert_before_last_user()
     5. Format: <|turn>identity\n[Personality]\n...\n<turn|>
     6. Logs to friday_core_identity.log on every attempt:
        - "IDENTITY INJECTED" when identity is found
        - "CORE IDENTITY NOT FOUND" when no identity exists (added June 30)
     7. DIAGNOSTIC NOTE: _inject_core_identity_into_context() catches ALL
        exceptions at logger.debug() level. If the identity log file stays
        empty, the most likely cause is an import failure in core_identity.py
        (e.g., IndentationError) that is silently swallowed.
        Check main log for DEBUG-level messages from the filter, or test
        the import directly: python3.11 -c "from core_identity import CoreIdentityManager"


7. USER_ID AND MODEL_ID NORMALIZATION CHAIN
============================================

  The normalization happens at THREE layers, and the chain works but
  has asymmetries that need attention:

LAYER 1 -- friday_memory_short_term.py :: Filter.inlet()
   ---------------------------------------------------------
   Line 4885-4886:
     model_card_name = self._normalize_name(model_card_name)
     user_id = self._normalize_name(user_id)

  _normalize_name() strips whitespace and lowercases.
  Source: __user__["id"] from OpenWebUI (a UUID like
  9d08cfbb-...), so lowering has no functional effect since
  UUIDs are already lowercase hex.

LAYER 1a -- outlet asymmetry (FIXED June 28):
   ---------------------------------------------------------
   Filter.outlet() now calls _normalize_name() on both user_id and model_id (lines 5390, 5400).

  LAYER 2 -- friday_memory_system.py :: USER_ID_ALIASES
  ---------------------------------------------------------
  Definition (line 67):
    USER_ID_ALIASES = {
        "nate": "9d08cfbb-b8ca-484d-bd37-c5c383c1e5d6",
        "Nate": "9d08cfbb-b8ca-484d-bd37-c5c383c1e5d6",
    }

  Applied in 5 methods:
    store_message()
    get_recent_messages()       -- also runs one-time DB normalization
    search_memories_by_date()
    search_memories()

  Pattern: user_id = USER_ID_ALIASES.get(user_id, user_id)
  The lowered UUID from Layer 1 won't match "nate" or "Nate",
  so it passes through unchanged. But if the raw OpenWebUI
  user_id were literally "Nate" (not a UUID), Layer 1 would
  lowercase it to "nate" which WOULD match the alias key.

  One-time normalization in get_recent_messages() (lines 486-496):
    UPDATE conversations SET user_id = canonical
    WHERE user_id = alias (for each alias)

  LAYER 3 -- model_id LOWERING (in SQL queries):
  ---------------------------------------------------------
  25 occurrences of LOWER(model_id) = ? across
  friday_memory_system.py. All database queries compare
  model_id case-insensitively via SQL LOWER().

  LAYER 4 -- core_identity.py :: _resolve_owu_user_id()
  ---------------------------------------------------------
  A separate third normalization layer. Resolves short names
  ("nate") to full OpenWebUI UUID by querying webui.db's
  user table. Checks UUID format first (dashes, length 36),
  then falls back to database lookup by name or email pattern.

  FULL NORMALIZATION FLOW:
    OpenWebUI __user__["id"]  (UUID string)
      -> Filter.inlet: _normalize_name() (lowercase)
      -> Passes to friday_memory_system.py methods
      -> USER_ID_ALIASES.get() (no match on UUID, passes through)
      -> SQL query: WHERE user_id = ? AND LOWER(model_id) = ?


8. TASK SCHEDULE (ALL BACKGROUND TASKS)
========================================

  REGISTERED BY short_term.py VIA TaskCoordinator:

  TASK                     FREQUENCY       CATEGORY    GATE        STATUS
  ------------------------------------------------------------------------
  summarization            every 2hr       db_heavy    idle        RUNNING (FIXED Jun 27: iterates all users)
  error_logging            every 30min     db_light    none        RUNNING
  date_update              every 1hr       db_light    none        RUNNING
  retry_queue              every 5min      db_light    none        RUNNING
  memory_promotion         every 24hr      db_heavy    none        DISABLED since April 20 (5 consecutive errors)
  memory_linking           daily@02:00     db_heavy    idle        RUNNING
  registry_sync            every 2hr       db_heavy    idle        RUNNING
  nightly_sync             daily@02:30     db_heavy    idle        RUNNING
  core_identity            daily@00:30     llm         idle        RUNNING (enabled, generates identity per user+model pair from OWUI model table)
      FIXED Jun 30: now iterates ALL users and ALL models with short-term
      filter enabled (queries webui.db directly), no hardcoded strings
  model_discovery          disabled        --          --          DISABLED by default
  openwebui_import         every 3hr       db_light    none        RUNNING

  Registered only if this plugin owns maintenance:
  maintenance_mcp          every 6hr       db_heavy    none        RUNNING
  maintenance_24h          daily@05:00     db_heavy    none        RUNNING
  linking_validation       every 6hr       db_heavy    none        RUNNING

  REGISTERED BY mcp_server.py:

  TASK                    FREQUENCY    DESCRIPTION
  -----------------------------------------------------------------
  database_maintenance    every 6hr    Full 13-step maintenance pipeline
  OpenWebUI chat import   every 3hr    Syncs OWUI chat to conversations.db
  module file monitor     every 2s     Hot-reload on code changes
  periodic_maintenance    every 4hr    From FridayMemorySystem._periodic_maintenance_loop

  TASK CONCURRENCY MODEL:
    db_light  -- Free (any number can run)
    db_heavy  -- Per-database mutex (one task per database at a time)
    llm       -- Global mutex (only one LLM call across all tasks)

  MAINTENANCE OWNERSHIP:
    MCP server claims maintenance ownership via TaskCoordinator.
    Claim file with 60s heartbeat, 120s stale threshold.
    Only one process performs database maintenance at a time.

  MAINTENANCE PIPELINE (nightly, 13 steps):
    1.  check_and_rotate_all_databases()
        -> Shards any DB > 3GB or on month boundary
    2.  archive_rotate_to_sharded_structure()
        -> Moves old data to memory_data/archives/
    3.  _upgrade_schemas()
        -> Adds missing columns to existing tables
    4.  _apply_retention_policies()
        -> Cleans schedule (90d) and processing logs (90d)
        -> conversations and curated_memories are NEVER pruned
    5.  _remove_duplicates()
    6.  _optimize_databases()
        -> VACUUM, ANALYZE, reindex
    7.  _collect_statistics()
    8.  _build_tag_registries()
        -> Rebuilds tag_registry.json from curated_memories
    9.  _build_memory_bank_registries()
        -> Rebuilds memory_bank_registry.json
    10. _retroactively_link_memories()
        -> Links unlinked memories to conversations
    11. ltm_maintenance.reformat_memories()
        -> LLM-powered: adds [Tags:] and [Memory Bank:] markers
    12. ltm_maintenance.scan_for_updates()
        -> LLM-powered: contradiction detection between memory pairs
    13. ltm_maintenance.assist_linking()
        -> Text-overlap matcher for unlinked memories

  SHORT-TERM BACKGROUND TASKS (inlet-integrated, not coordinator):

  TASK                  WHEN
  -----------------------------------------------------------------
  Summarization         After every message if threshold reached
                        (_should_summarize_now)
  Memory extraction     After every LLM response (via async queue worker)
  Memory injection      Before every LLM request (in inlet)
  Core identity inject  Every inlet call (guard removed June 28)
                        Logs "CORE IDENTITY NOT FOUND" when no identity
                        exists for user+model pair (added June 30)


9. KNOWN ISSUES AND PHASE 2 PENDING WORK
==========================================

  URGENT (from post-deploy audit May 13, 2026) — ALL RESOLVED:

    1. memory_promotion -- DISABLED since April 20 (HIGH)
       No short-term memories promoted to long-term for 3+ weeks.
       Crashed with 5 consecutive errors and auto-disabled.
       Needs investigation into root cause (likely LLM call failure
       or DB constraint violation).
       STATUS: Still disabled. Not yet investigated.

    2. summarization -- FIXED June 27, 2026
       Was hardcoded to user_id="default" which doesn't exist.
       Now iterates all users via Users.get_users(), matching
       the memory_promotion pattern. Per-user errors are caught
       individually so one bad user doesn't kill the whole run.

    3. model_discovery -- Already fixed (LOW, covered)
       Valve-timing race condition addressed via _register_valve_gated_tasks().

  CODEBASE AUDIT FINDINGS (May 4, 2026) — ALL 16 ITEMS RESOLVED:

    All CRITICAL, HIGH, MODERATE, and MINOR items have been fixed,
    determined to be false alarms, or intentionally left as-is.
    See "RECENTLY COMPLETED" sections for the full list of fixes.

  PLANNED PROJECTS (Plans/ folder):

    A. QUALITY_OF_LIFE_IMPROVEMENTS (approved, locked-in plan, May 1, 2026):
       Phase 1: Verify JSON parsing (diagnostic, 30 min)
       Phase 2: Dynamic tag registry building (1.5 hr) -- PARTIALLY DONE
       Phase 3: Inject tags/banks into memory extraction prompt (1.5 hr)
       Phase 4: Persistent retry queue for failed memories (1.5 hr) -- PARTIALLY DONE
       Phase 5: Enhanced status messages (1 hr)
       Phase 6: Port to PAM upgrade folder (1 hr)
       STATUS: Phases 2 and 4 partially implemented, awaiting rest.

    B. SQLITE_VEC_INTEGRATION (June 14, 2026):
       Replace EmbeddingCache with sqlite-vec VectorCache
       8 steps: WAL mode fix, install sqlite-vec, native float[] column,
       HNSW index, eliminate 10k-item Python vector loop,
       update references, migration script, apply to both systems.

    C. CLICKABLE MEMORY-INJECTION DIALOG (not yet planned):
       Make status messages clickable to show injected memories in a dialog.
       Requires frontend change in fork's StatusItem.svelte + backend confirmation event.

    D. NEW IDEAS (not yet planned):
       - OpenCode support: replace VS Code references with OpenCode throughout.
         PortManager needs OpenCode caller detection. MCP server needs OpenCode
         as a recognized client type. All "vscode" named tools/DBs should work
         for OpenCode sessions. Project history, session save, code context
         should all work with OpenCode workspaces.
       - Error injection system
       - Tag registry (basic)
       - Retry queue (basic)
       - PAM async 0.9.0
       - PAM core identity port

   RECENTLY COMPLETED (June 27-28, 2026):
     - summarization fixed: iterates all users via Users.get_users()
     - maintenance LLM model: qwen-3 -> Gemma4
     - core identity schedule: midnight -> 12:30 AM
     - valve defaults: Gemma4 on llama.cpp endpoint
     - valve_settings.json: absolute path, survives restarts
     - core identity injection: every turn now
     - /identity command: manual generation from chat
     - core identity Error 2: get_db_context -> get_db (fork API mismatch)
     - task_coordinator: 48-hour auto-re-enable
     - memory_promotion dict binding crash: extract memory_id from dict
     - _is_message_in_mcp dead query removed (conversations table has no message_hash)
     - memory_bank_registry: Row.get() -> Row['column'], normalized casing (General=general)
     - inlet/outlet normalization: outlet now normalizes user_id/model_id
     - ConversationFileMonitor: dead first __init__ and orphan docstring removed
     - embeddings_cache.db deleted (old 19MB dead file, zero references)
     - entire May 4 codebase audit cleared (all 16 items resolved or documented)

RECENTLY COMPLETED (June 30, 2026):
      - core identity generation: _core_identity_work() now iterates ALL users
        and ALL models with short-term filter enabled, querying webui.db directly.
        No hardcoded strings, no fallbacks, no reliance on in-memory state.
        Version: 0.0.25 -> 0.0.26
      - identity injection logging: added "CORE IDENTITY NOT FOUND" INFO log
        to friday_core_identity.log when no identity exists for user+model pair
      - PAM upgrade folder: same changes ported, duplicate empty _core_identity_work
        definition removed
      - core_identity.py indentation fix: two IndentationErrors in
        _get_archived_memories() (lines 547, 697) were preventing the entire module
        from importing, silently killing identity injection on every inlet call

   RECENTLY COMPLETED (July 29-30, 2026):
      - Role-aware KV cache: replaced flat --keep N flag with --keep-roles system,identity
        in llama.cpp private fork. Dynamic n_keep calculated from message_spans token
        positions, pinning only system + identity roles during context shift.
        Everything else (datetime, summary, reminders, memories, conversation history)
        is shiftable.
      - New --keep-roles CLI flag: comma-separated list of role names to preserve.
        Falls back to --keep when not specified. Fails loudly to keep_roles_error.log
        if no spans match.
      - Delimiter injection: added system (<|turn>system) and identity (<|turn>identity)
        delimiters to common_chat_params_init_gemma4 so message_spans can identify them.
      - Added COMMON_CHAT_ROLE_IDENTITY to llama.cpp's common_chat_role enum plus
        from_string/to_string mappings.
      - datetime role: new <|turn>datetime block in gemma4_prompt_template.jinja.
        Injected by FMS inlet every turn with seconds-precision current time.
        ORDER list: ["datetime", "identity", "summary", "reminders", "memories"].
      - LLVM intermediate representation (llama.cpp): server rebuild succeeded with
        zero errors across all 7 modified files.
      - Plain text plan saved to /media/nate/Friday/Friday/keep_roles_datetime_plan.txt
      - Summary written to Summaries/SESSION_SUMMARY_20260729.md
      - Version: 0.0.27 -> 0.0.28

   RECENTLY COMPLETED (July 23, 2026) — Timestamp-Aware Context Truncation:
      - llama.cpp router (proxy_request) now truncates by timestamp when context exceeds n_ctx.
        Reads ctx_size + n_keep from model preset, calculates token budget, drops oldest
        non-system messages from the front. Uses per-message timestamp field if present.
      - OpenWebUI fork middleware.py: added 'timestamp' to load_messages_from_db field
        whitelist so timestamps are included in the outgoing LLM payload.
      - Files: llama.cpp/server-models.cpp/h, arg.cpp, server.cpp, OpenWebUI middleware.py
      - Decision doc: Decisions_Folder/LLAMACPP_TIMESTAMP_TRUNCATION.md

   RECENTLY COMPLETED (August 3, 2026) — Appointment Query & Auto-Complete Fixes:
      - Fixed get_upcoming_appointments() lower bound: was using current wall-clock time
        (now_epoch), hiding appointments once their time passed today. Changed to start_of_day
        (midnight) so all of today's appointments remain visible.
      - Added appointment auto-complete to _cleanup_schedule in database_maintenance.py:
        marks overdue appointments as status='completed' with a 24-hour grace period
        mirroring the existing reminder pattern. Appointments more than 24h past their
        scheduled_datetime and still in 'scheduled' status are auto-completed.
      - Files: friday_memory_system.py lines 6033-6036, database_maintenance.py lines 1942-1946
      - Upgrade folder: same changes applied to both files
      - Version: 0.0.28 -> 0.0.29

  RECENTLY COMPLETED (August 6, 2026) — Per-Model Core Identity File Naming:
      - Production core_identity.py: backup files changed from
        friday_core_identity_{user_id}.json (per-user, lossy cache) to
        friday_core_identity_{user_id}_{model_id}.json (per-model, isolated).
        Progress files changed from core_identity_progress_{user_id}.json to
        core_identity_progress_{user_id}_{model_id}.json.
      - Migration runs on startup: old per-user files are read, per-model files
        written from DB data, old files removed. 3 legacy files -> 18 per-model files.
      - load_core_identity() fallback checks per-model file first, then legacy per-user.
      - fms_delete_model_memories.py now deletes the per-model identity backup and
        progress files on disk alongside DB rows.
      - NOTE: Friday_Memory_System_Update/core_identity.py still uses the old
        single-file pattern and needs the same per-model file naming update.
      - Version: 0.0.29
    - Error log dedup
    - aiohttp session cleanup
    - Exception guards on background tasks
    - JSON parsing fallback logging
    - Image database connection cleanup
    - Valve change detection (skipped)


10. ENVIRONMENT VARIABLES
=========================

  NOTE: These env vars are used in the PAM generic version. The production
  FMS files use hardcoded paths derived from FRIDAY_MEMORY_SYSTEM_PATH.
  AI_MEMORY_DATA_DIR and AI_MEMORY_LOG_DIR are not checked in production.

  Used by long-term system (friday_memory_system.py / PAM only):
    AI_MEMORY_DATA_DIR    -- Default: ./memory_data/
    AI_MEMORY_LOG_DIR     -- Default: ./logs/

  Used by MCP server (friday_memory_mcp_server.py):
    MCP_API_KEY           -- API key for HTTP authentication (PAM only)
    (production loads from /media/nate/Friday/Friday/keys/mcpo_api_key.txt)

  Used by short-term system (friday_memory_short_term.py):
    weather_directory     -- Weather cache directory (used in mcp_server)


11. EXTERNAL INTEGRATIONS
==========================

  OpenWebUI Memory Table:
    Short-term system reads/writes OpenWebUI's own memory table
    (in webui.db) as its primary short-term store.

  Conversation File Monitor:
    Watches directories for: ChatGPT, Claude, LM Studio, Ollama,
    Character.ai, Local.ai, text-generation-webui, VS Code,
    OpenAI Playground. Imports conversations automatically.

  LLM Endpoints:
    Short-term memory extraction: http://172.17.0.1:11434/api/chat (Ollama)
    Long-term maintenance LLM:    http://192.168.1.50:8080/v1/chat/completions (Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced)
    Core identity generation:     Configurable, supports ollama + openai_compatible

  Embedding Endpoints:
    Primary:  http://192.168.1.50:1234/v1/embeddings (LM Studio, nomic)
    Fallback: http://localhost:11434/api/embeddings (Ollama, nomic)
    Dimension: 768

  OpenWebUI Databases:
    webui.db (read):  user table, chat table, memory table
    webui.db (write): knowledge base (for core identity output)

  Port Management:
    Primary: 21434, Backups: 21435-21439
    Info file: memory_data/mcp_server_port.json


12. LOG FILES REFERENCE
========================

  /media/nate/Friday/Friday/logs/ (82 entries):
    friday_short_term_memory.log        -- Main short-term memory log
    friday_short_term_inlet_outlet.log  -- Inlet/outlet flow debugging (currently 0 bytes)
    inlet_outlet_flow.log               -- Alternative inlet/outlet logger (6.5K, relationship to above unclear)
    friday_short_term_errors.log        -- LLM and system errors
    friday_core_identity.log            -- Core identity injection events (every attempt logged)
    tool_calls.log                      -- All MCP tool calls with arguments
    tool_call_arg_debug.log             -- Detailed argument debugging
    mcp_server.log                      -- MCP server log
    mcp_server_http_access.log          -- HTTP access log
    brave_search.log                    -- Web search tool
    adaptive_memory_embedding.log       -- Embedding status
    embeddings_completed.log            -- Completed embedding tasks
    friday.log, openwebui.log           -- General logs
    ERRORS_*.log (66 files)             -- Timestamped error dumps

  /media/nate/Friday/Friday/Logs/ (7 entries):
    friday_migration_normalization.log  -- Migration log
    LM_STUDIO_ERROR_ANALYSIS.md         -- Error analysis
    memory_validation_errors.json       -- Validation errors


13. KEY PATHS REFERENCE
========================

  Friday Home:          /media/nate/Friday/Friday/
  Memory Data:          /media/nate/Friday/Friday/memory_data/
  Archives:             /media/nate/Friday/Friday/memory_data/archives/
  Logs:                 /media/nate/Friday/Friday/logs/
  Error Logs:           /media/nate/Friday/Friday/Logs/
  Keys:                 /media/nate/Friday/Friday/keys/
  Summaries:            /media/nate/Friday/Friday/Summaries/
  Decisions:            /media/nate/Friday/Friday/Decisions_Folder/
  Plans:                /media/nate/Friday/Friday/Plans/
  Tests:                /media/nate/Friday/Friday/Tests/
  Upgrade Folder:       /media/nate/Friday/Friday/Friday_Memory_System_Update/ (v0.0.25, three behind prod v0.0.29)
  OpenWebUI DB:         /media/nate/Friday/OpenWebUI/data/webui.db
  OpenWebUI Fork:       /media/nate/Friday/openwbuifork/ (symlink to /media/nate/Games/Openwebuifork/)
  OpenWebUI Stock:      /media/nate/Friday/OpenWebUIstock/

  PAM (persistent-ai-memory):
    Main:              /media/nate/Friday/Friday/persistent-ai-memory/
    Upgrade:           /media/nate/Friday/Friday/persistent-ai-memory-update/
    Tests:             /media/nate/Friday/Friday/persistent-ai-memory/tests/


14. CHANGE LOG
================

  Aug 9, 2026 -- Historical Image Embedding Injection (no version bump)
    Fixed: Follow-up messages in a conversation with images would fail because
    the precomputed embedding pass only scanned the last message for image_url.
    Added a second pass at friday_memory_short_term.py:5593 that scans ALL
    messages in the body for remaining image_url parts and replaces them with
    cached embeddings from image_embeddings SQLite table. The cache is populated
    on the first image-bearing message, so follow-ups are instant cache hits.
    Related: vision server (mmproj-only on separate port) was also configured
    and tested successfully on this date.