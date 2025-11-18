# Friday Memory System - Internal Architecture & Internals (November 17, 2025)

## Overview

The **Friday Memory System** is a comprehensive, multi-database memory and persistence layer that:
- Manages 5 different databases for different purposes
- Provides embedding/vector search capabilities
- Integrates with the MCP (Model Context Protocol) for external access
- Handles asynchronous operations with embedding generation, file monitoring, and maintenance
- Supports user/model isolation and importance-based memory management

**Key Files**:
- `/media/nate/Friday/Friday/friday_memory_system.py` (7,253 lines) - Core system
- `/media/nate/Friday/Friday/friday_memory_mcp_server.py` (1,865 lines) - MCP interface
- `/media/nate/Friday/Friday/memory_data/` - Database storage

---

## 1. SYSTEM ARCHITECTURE OVERVIEW

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    FRIDAY MEMORY SYSTEM (Host Machine)                   │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │           FridayMemorySystem (Main Coordinator Class)             │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │ Initializes & manages all database backends                │  │  │
│  │  │ Handles async embedding generation                         │  │  │
│  │  │ Coordinates file monitoring and maintenance                │  │  │
│  │  │ Routes tool calls to appropriate databases                 │  │  │
│  │  │ Manages configuration (embedding_config.json)              │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                          ▲                                │
│                          ┌───────────────┼───────────────┐                │
│                          │               │               │                │
│                          ▼               ▼               ▼                │
│  ┌──────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐  │
│  │  Database Layer  │ │ Embedding Service    │ │   Maintenance &      │  │
│  │                  │ │                      │ │   Monitoring         │  │
│  │ • ConversationDB │ │ • LM Studio primary  │ │ • File monitoring    │  │
│  │ • AIMemoryDB     │ │ • Ollama fallback    │ │ • DB maintenance     │  │
│  │ • ScheduleDB     │ │ • Embedding cache    │ │ • DB rotation        │  │
│  │ • VSCodeDB       │ │ • Provider fallback  │ │ • Async task mgmt    │  │
│  │ • MCPToolCallDB  │ │ • embeddings_        │ │ • Background tasks   │  │
│  │                  │ │   endpoint attribute │ │                      │  │
│  │ (SQLite DBs)     │ │ (HTTP REST)          │ │ (Async event loop)   │  │
│  └──────────────────┘ └──────────────────────┘ └──────────────────────┘  │
│                                                                          │
│         ▼                          ▼                            ▼        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    MCP Server (Interface Layer)                 │   │
│  │  ┌────────────────────────────────────────────────────────────┐ │   │
│  │  │ Tool registration (create_memory, search_memories, etc.)  │ │   │
│  │  │ Client detection (VS Code, LM Studio, CLI)                │ │   │
│  │  │ Context management (user_id, model_id)                    │ │   │
│  │  │ Tool execution routing (_execute_tool)                    │ │   │
│  │  │ Logging and reflection (tool_calls.log)                   │ │   │
│  │  └────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ MCP Protocol (stdio)
                                    │
                      ┌─────────────┼─────────────┐
                      ▼             ▼             ▼
                  VS Code       LM Studio        CLI
                (Extension)    (via OpenAI API) (Direct)
```

---

## 2. DATABASE LAYER (5 Databases)

### 2.1 AIMemoryDatabase (`ai_memories.db`)
**Purpose**: Store curated/promoted long-term memories

**Schema**:
```sql
CREATE TABLE curated_memories (
    memory_id TEXT PRIMARY KEY,                  -- UUID
    timestamp_created TEXT NOT NULL,             -- ISO format, local timezone
    timestamp_updated TEXT NOT NULL,             -- ISO format, updated on changes
    source_conversation_id TEXT,                 -- Link to conversation if extracted
    source_message_ids TEXT,                     -- JSON array of message IDs
    memory_type TEXT,                            -- Classification (goal, preference, fact, etc.)
    content TEXT NOT NULL,                       -- The actual memory text
    importance_level INTEGER DEFAULT 5,          -- 1-10 scale (8-9 for promoted)
    tags TEXT,                                   -- JSON array of tags
    embedding BLOB,                              -- Vector (768D nomic-embed-text)
    user_id TEXT,                                -- For user isolation
    model_id TEXT DEFAULT 'Friday',              -- For model isolation
    created_at TEXT DEFAULT CURRENT_TIMESTAMP    -- Audit timestamp
);
```

**Key Methods**:
- `create_memory(content, memory_type, importance_level, tags, user_id, model_id)` → memory_id
- `update_memory(memory_id, content, importance_level, tags)` → bool (success)
- `get_memory(memory_id)` → memory dict or None
- `search_memories_by_similarity(query_embedding, limit, min_importance)` → list of memories

**Importance Levels** (1-10):
- 1-5: Regular extracted memories (from OpenWebUI short-term)
- 6-7: High-priority memories (still extractable)
- 8-9: **Promoted/curated** memories (should survive pruning)
- 10: Critical/pinned memories (never prune)

**Index**:
```sql
CREATE INDEX idx_curated_memories_user_model ON curated_memories (user_id, model_id)
```

---

### 2.2 ConversationDatabase (`conversations.db`)
**Purpose**: Store conversation history, sessions, and message interactions

**Schema**:
```sql
-- Sessions (conversation groups)
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    start_timestamp TEXT NOT NULL,
    end_timestamp TEXT,
    context TEXT,
    embedding BLOB,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Conversations (individual chats within sessions)
CREATE TABLE conversations (
    conversation_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    start_timestamp TEXT NOT NULL,
    end_timestamp TEXT,
    topic_summary TEXT,
    embedding BLOB,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
);

-- Messages (individual messages)
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    role TEXT NOT NULL,              -- "user", "assistant", "system"
    content TEXT NOT NULL,
    source_type TEXT NOT NULL,       -- "openwebui", "lmstudio", "vscode", etc.
    source_id TEXT,
    source_url TEXT,
    source_metadata TEXT,            -- JSON
    sync_status TEXT,                -- "synced", "pending", "failed"
    last_sync TEXT,
    metadata TEXT,                   -- JSON
    embedding BLOB,                  -- Vector
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
);
```

**Key Methods**:
- `store_conversation(content, role, session_id, metadata)` → message_id
- `get_conversation(conversation_id)` → conversation dict
- `get_messages_in_conversation(conversation_id, limit)` → list of messages
- `search_conversations_by_topic(query, limit)` → list of conversations

---

### 2.3 ScheduleDatabase (`schedule.db`)
**Purpose**: Appointments, reminders, and time-based tasks

**Schema**:
```sql
CREATE TABLE appointments (
    appointment_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    scheduled_datetime TEXT NOT NULL,
    location TEXT,
    status TEXT,                    -- "scheduled", "completed", "cancelled"
    recurrence_pattern TEXT,        -- "daily", "weekly", "monthly", "yearly"
    recurrence_count INTEGER,
    recurrence_end_date TEXT,
    source_conversation_id TEXT,
    user_id TEXT,
    model_id TEXT DEFAULT 'Friday',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reminders (
    reminder_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    due_datetime TEXT NOT NULL,
    priority_level INTEGER,         -- 1-10
    completed BOOLEAN DEFAULT 0,
    completed_at TEXT,
    recurrence_pattern TEXT,
    recurrence_count INTEGER,
    recurrence_end_date TEXT,
    source_conversation_id TEXT,
    user_id TEXT,
    model_id TEXT DEFAULT 'Friday',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Key Methods**:
- `create_appointment(title, scheduled_datetime, ...)` → appointment_id(s)
- `create_reminder(content, due_datetime, priority_level, ...)` → reminder_id(s)
- `get_upcoming_appointments(days_ahead, limit)` → list
- `get_active_reminders(days_ahead, limit)` → list
- `complete_reminder(reminder_id)` → success bool
- `cancel_appointment(appointment_id)` → success bool

---

### 2.4 VSCodeProjectDatabase (`vscode_project.db`)
**Purpose**: Store VS Code project context, code snippets, insights

**Schema**:
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    project_name TEXT,
    workspace_path TEXT,
    start_time TEXT,
    end_time TEXT,
    created_at TEXT
);

CREATE TABLE code_context (
    context_id TEXT PRIMARY KEY,
    session_id TEXT,
    file_path TEXT,
    language TEXT,
    content TEXT,
    snippet_type TEXT,         -- "function", "class", "import", "error"
    line_numbers TEXT,         -- JSON range
    timestamp TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
);

CREATE TABLE insights (
    insight_id TEXT PRIMARY KEY,
    session_id TEXT,
    insight_type TEXT,         -- "pattern", "issue", "note", "decision"
    content TEXT,
    confidence REAL,           -- 0.0-1.0
    tags TEXT,                 -- JSON
    timestamp TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
);
```

**Key Methods**:
- `create_session(project_name, workspace_path)` → session_id
- `add_code_context(session_id, file_path, content, ...)` → context_id
- `add_insight(session_id, insight_type, content, tags)` → insight_id
- `get_project_insights(session_id, limit)` → list

---

### 2.5 MCPToolCallDatabase (`mcp_tool_calls.db`)
**Purpose**: Log and track MCP tool invocations for analytics and debugging

**Schema**:
```sql
CREATE TABLE tool_calls (
    call_id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    arguments TEXT,              -- JSON
    result TEXT,                 -- JSON
    execution_time REAL,         -- milliseconds
    success BOOLEAN,
    error_message TEXT,
    client_id TEXT,
    user_id TEXT,
    timestamp TEXT,
    created_at TEXT
);

CREATE TABLE ai_reflections (
    reflection_id TEXT PRIMARY KEY,
    reflection_type TEXT,        -- "tool_usage_analysis", "memory", "general"
    content TEXT,
    insights TEXT,               -- JSON array
    recommendations TEXT,        -- JSON array
    confidence REAL,             -- 0.0-1.0
    source_period_days INTEGER,
    timestamp TEXT,
    created_at TEXT
);
```

**Key Methods**:
- `log_tool_call(tool_name, arguments, result, execution_time, success)` → call_id
- `store_ai_reflection(reflection_type, content, insights, ...)` → reflection_id
- `get_tool_usage_stats(days)` → dict with success_rate, avg_time, etc.
- `get_ai_insights(limit, insight_type)` → list of reflections

---

## 3. DATABASE MANAGER BASE CLASS

All databases inherit from `DatabaseManager`:

```python
class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.ensure_database_exists()
    
    def get_connection(self) -> sqlite3.Connection:
        """Returns connection with Row factory and foreign keys ON"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Dict-like access
        conn.execute("PRAGMA foreign_keys = ON")  # Enforce constraints
        return conn
    
    async def execute_query(self, query, params) -> List[sqlite3.Row]:
        """SELECT queries"""
    
    async def execute_update(self, query, params) -> int:
        """INSERT/UPDATE/DELETE queries, returns affected row count"""
```

**Key Features**:
- `row_factory = sqlite3.Row` - Access columns like dict: `row["column_name"]`
- Foreign key constraints enabled for referential integrity
- Async wrappers for non-blocking database access
- Context manager support: `with conn as c: ...`

---

## 4. EMBEDDING SERVICE

**Location**: `EmbeddingService` class in `friday_memory_system.py`

**Purpose**: Generate and cache vector embeddings for memories and conversations

**Configuration** (`embedding_config.json`):
```json
{
  "primary": {
    "provider": "lmstudio",
    "model": "text-embedding-nomic-embed-text-v1.5",
    "base_url": "http://192.168.1.50:1234",
    "description": "LM Studio text-embedding-nomic-embed-text-v1.5"
  },
  "fallback": {
    "provider": "ollama",
    "model": "nomic-embed-text:latest",
    "base_url": "http://localhost:11434",
    "description": "Ollama fallback"
  }
}
```

**Key Attributes**:
```python
self.embeddings_endpoint = base_url  # NEW: Primary endpoint URL
self.primary_config = {...}          # Primary embedding config
self.fallback_config = {...}         # Fallback if primary fails
self.provider_availability = {        # Track which providers are working
    "lm_studio": None,
    "ollama": None,
    "openai": None
}
```

**Key Methods**:
- `async generate_embedding(text: str) -> List[float]` - Returns 768D vector
  - Tries primary provider first
  - Falls back to secondary if primary fails
  - Caches embedding in memory and database
- `_generate_lm_studio_embedding(text)` - HTTP to LM Studio /v1/embeddings
- `_generate_ollama_embedding(text)` - HTTP to Ollama /api/embeddings
- `_generate_openai_embedding(text)` - HTTP to OpenAI /v1/embeddings (if API key)

**Embedding Storage**:
- BLOB field in each database table
- Stored as numpy array pickle (binary format)
- Search via cosine similarity: `np.dot(query_vec, memory_vec)`

**Provider Detection**:
- Automatically detects dimension mismatch (768D nomic-embed-text)
- Regenerates embeddings if provider changes
- Tracks provider availability for smart fallback

---

## 5. MAIN COORDINATOR: FridayMemorySystem

**Location**: `class FridayMemorySystem` (line 4314)

**Initialization**:
```python
def __init__(self, data_dir="memory_data", enable_file_monitoring=True):
    # Initialize all database backends
    self.conversations_db = ConversationDatabase(...)
    self.ai_memory_db = AIMemoryDatabase(...)
    self.schedule_db = ScheduleDatabase(...)
    self.vscode_db = VSCodeProjectDatabase(...)
    self.mcp_db = MCPToolCallDatabase(...)
    
    # Initialize embedding service
    self.embedding_service = EmbeddingService()
    
    # Initialize maintenance
    self.db_maintenance = DatabaseMaintenance(...)
    
    # Initialize file monitoring
    if enable_file_monitoring:
        self.file_monitor = ConversationFileMonitor(...)
```

**Key Responsibilities**:

### 5.1 Memory Operations
```python
async def create_memory(content, memory_type, importance_level, tags, 
                       user_id, model_id) -> Dict:
    """Create a curated memory"""
    memory_id = await self.ai_memory_db.create_memory(...)
    # Async embedding generation (doesn't block)
    asyncio.create_task(self._add_embedding_to_memory(memory_id, content))
    return {"status": "success", "memory_id": memory_id}

async def search_memories(query, limit, database_filter, importance_range):
    """Search memories using vector similarity"""
    # Generate embedding for query
    query_embedding = await self.embedding_service.generate_embedding(query)
    # Search across relevant memories
    results = await self.ai_memory_db.search_by_similarity(query_embedding, ...)
    return results

async def update_memory(memory_id, content, importance_level, tags):
    """Update existing memory"""
    success = await self.ai_memory_db.update_memory(...)
    # If content changed, regenerate embedding
    if content:
        asyncio.create_task(self._add_embedding_to_memory(memory_id, content))
    return {"status": "success"}
```

### 5.2 Conversation Management
```python
async def store_conversation(content, role, session_id, metadata):
    """Store a message in conversation database"""
    message_id = await self.conversations_db.store_conversation(...)
    # Async embedding
    asyncio.create_task(self._add_embedding_to_message(message_id, content))
    return message_id

async def get_recent_context(limit, session_id, days_back):
    """Get recent conversation context"""
    return await self.conversations_db.get_recent_messages(...)
```

### 5.3 Schedule Management
```python
async def create_appointment(title, scheduled_datetime, recurrence_pattern, ...):
    """Create appointment (single or recurring)"""
    ids = await self.schedule_db.create_appointment(...)
    return {"status": "success", "appointment_ids": ids}

async def create_reminder(content, due_datetime, priority_level, recurrence_pattern):
    """Create reminder (single or recurring)"""
    ids = await self.schedule_db.create_reminder(...)
    return {"status": "success", "reminder_ids": ids}

async def complete_reminder(reminder_id):
    """Mark reminder as completed"""
    success = await self.schedule_db.mark_complete(reminder_id)
    return {"status": "success"}

async def get_active_reminders(limit, days_ahead):
    """Get upcoming reminders"""
    reminders = await self.schedule_db.get_active(limit, days_ahead)
    return {"status": "success", "reminders": reminders}
```

### 5.4 Maintenance & Background Tasks
```python
async def run_database_maintenance():
    """Periodic database cleanup and optimization"""
    await self.db_maintenance.run()

async def _periodic_maintenance_loop():
    """Background task: run maintenance every 24 hours"""
    while True:
        await asyncio.sleep(86400)  # 24 hours
        await self.run_database_maintenance()

async def _start_monitoring():
    """Start file monitoring for VS Code projects"""
    if self.file_monitor:
        await self.file_monitor.start()

async def get_system_health():
    """Check system health: database sizes, embedding status, etc."""
    return {
        "databases": {...},
        "embedding_service": {...},
        "file_monitoring": {...}
    }
```

### 5.5 Internal Async Helpers
```python
async def _add_embedding_to_memory(memory_id, content):
    """Async: Generate and store embedding"""
    embedding = await self.embedding_service.generate_embedding(content)
    await self.ai_memory_db.add_embedding(memory_id, embedding)

async def _execute_memory_operation(operation: MemoryOperation, user):
    """Execute memory operations (CREATE, UPDATE, DELETE)"""
    # Handles CREATE, UPDATE, DELETE operations
    # Manages pruning when memory limit exceeded
```

---

## 6. MCP SERVER LAYER

**File**: `friday_memory_mcp_server.py`

**Class**: `FridayMemoryMCPServer`

**Purpose**: Expose Friday Memory System as MCP tools for external clients

### 6.1 Initialization
```python
def __init__(self):
    self.server = Server("friday-memory")
    self.memory_system = FridayMemorySystem()
    self.client_context = {}
    self._register_handlers()
    self.start_memory_system_background()  # Background tasks
```

### 6.2 Tool Registration
```python
@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """Return available tools based on client type"""
    # Dynamic tool list based on client detection
    # All clients get: search_memories, create_memory, update_memory, etc.
    # Plus: create_appointment, create_reminder, get_active_reminders, etc.
    # Plus: get_weather_open_meteo, brave_web_search, brave_local_search
    # Plus: get_system_health, get_tool_usage_summary, reflect_on_tool_usage

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict) -> CallToolResult:
    """Execute tool and return result"""
    return await self._execute_tool(name, arguments)
```

### 6.3 Tool Execution Routing
```python
async def _execute_tool(tool_name: str, arguments: Dict) -> CallToolResult:
    """Route tool calls to appropriate handlers"""
    
    # Extract context
    user_id = arguments.get("user_id") or self.client_context.get("user_id")
    model_id = arguments.get("model_id") or self.client_context.get("model_id", "Friday")
    
    # Log all tool calls (tool_calls.log)
    self._log_tool_call(tool_name, arguments)
    
    # Route to handler
    if tool_name == "search_memories":
        result = await self.memory_system.search_memories(...)
    elif tool_name == "create_memory":
        result = await self.memory_system.create_memory(...)
    elif tool_name == "update_memory":
        result = await self.memory_system.update_memory(...)
    elif tool_name == "create_appointment":
        result = await self.memory_system.create_appointment(...)
    elif tool_name == "create_reminder":
        result = await self.memory_system.create_reminder(...)
    elif tool_name == "get_active_reminders":
        result = await self.memory_system.get_active_reminders(...)
    elif tool_name == "complete_reminder":
        result = await self.memory_system.complete_reminder(...)
    elif tool_name == "get_system_health":
        result = await self.memory_system.get_system_health()
    elif tool_name == "brave_web_search":
        result = await self._brave_web_search(arguments)
    elif tool_name == "brave_local_search":
        result = await self._brave_local_search(arguments)
    elif tool_name == "get_weather_open_meteo":
        result = await self.get_weather_open_meteo(...)
    else:
        result = {"status": "error", "message": f"Unknown tool: {tool_name}"}
    
    # Time execution
    end_time = time.perf_counter()
    execution_time = (end_time - start_time) * 1000  # ms
    
    # Log performance
    await self.memory_system.mcp_db.log_tool_call(
        tool_name, arguments, result, execution_time, success=True
    )
    
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result))])
```

### 6.4 Client Detection
```python
def _detect_client_type() -> str:
    """Detect which client is calling"""
    # Checks: environment variables, headers, connection context
    # Returns: "vs_code", "lm_studio", "cli", "sillytavern", "unknown"
```

### 6.5 Tool Allowlist
Each tool has an `allowed_args` filter:
```python
if tool_name == "create_memory":
    allowed_args = {"content", "memory_type", "importance_level", "tags", 
                    "source_conversation_id", "user_id", "model_id"}
    filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
    result = await self.memory_system.create_memory(**filtered_args)
```

This prevents injection attacks and ensures clean argument passing.

---

## 7. ASYNC PATTERNS & CONCURRENCY

### 7.1 Non-blocking Embedding
```python
async def create_memory(content, ...):
    memory_id = await self.ai_memory_db.create_memory(...)
    # ASYNC - doesn't block:
    asyncio.create_task(self._add_embedding_to_memory(memory_id, content))
    return memory_id  # Returns immediately
```

**Why**: Embedding generation can take 100-500ms per item. We don't want users to wait.

### 7.2 Background Maintenance Loop
```python
async def _periodic_maintenance_loop(self):
    while True:
        await asyncio.sleep(86400)  # 24 hours
        await self.run_database_maintenance()
```

**Why**: Keeps database clean without blocking tool execution.

### 7.3 File Monitoring
```python
async def _start_monitoring(self):
    if self.file_monitor:
        await self.file_monitor.start()
```

**Why**: Watches VS Code chat sessions and automatically imports them.

### 7.4 Delayed Initialization
```python
async def handle_initialization(self):
    async def delayed_start():
        await asyncio.sleep(180)  # Wait 3 minutes
        # Start file monitoring and maintenance
        await self.memory_system._start_monitoring()
        self._start_automatic_maintenance()
    asyncio.create_task(delayed_start())
```

**Why**: Gives LM Studio time to initialize before we start intensive operations.

---

## 8. TOOL CATALOG (Available via MCP)

### Memory & Context Tools
- `search_memories(query, limit, database_filter, min/max_importance, memory_type, memory_id)` → list
- `create_memory(content, memory_type, importance_level, tags, source_conversation_id, user_id, model_id)` → memory_id
- `update_memory(memory_id, content, importance_level, tags)` → bool
- `get_recent_context(limit, session_id, days_back)` → list
- `store_conversation(content, role, session_id, metadata)` → message_id

### Schedule & Reminder Tools
- `create_appointment(title, description, scheduled_datetime, location, recurrence_pattern, recurrence_count, recurrence_end_date, user_id, model_id)` → appointment_ids
- `create_reminder(content, due_datetime, priority_level, recurrence_pattern, recurrence_count, recurrence_end_date, user_id, model_id)` → reminder_ids
- `get_appointments(limit, days_ahead)` → appointments
- `get_reminders(limit, include_completed, days_ahead)` → reminders
- `get_active_reminders(limit, days_ahead)` → reminders
- `get_completed_reminders(days)` → reminders
- `complete_reminder(reminder_id)` → bool
- `reschedule_reminder(reminder_id, new_due_datetime)` → bool
- `delete_reminder(reminder_id)` → bool
- `cancel_appointment(appointment_id)` → bool
- `complete_appointment(appointment_id)` → bool
- `get_upcoming_appointments(limit, days_ahead)` → appointments

### System Tools
- `get_system_health()` → comprehensive health dict
- `get_tool_usage_summary(client_id, days)` → usage stats
- `reflect_on_tool_usage(client_id, days)` → AI reflection on patterns
- `store_ai_reflection(reflection_type, content, insights, recommendations, confidence_level, source_period_days)` → reflection_id
- `get_ai_insights(limit, insight_type, query)` → insights list

### External Tools
- `brave_web_search(query, count, country, language)` → search results
- `brave_local_search(query, location, count, radius)` → local results
- `get_weather_open_meteo(latitude, longitude, timezone_str, override, update_today, ...)` → weather forecast

---

## 9. DATA FLOW EXAMPLES

### Example 1: Create a Memory with Embedding
```
User calls: create_memory(content="I like coffee", memory_type="preference", importance_level=5)
    ↓
MCP Server._execute_tool("create_memory", {...})
    ↓
FridayMemorySystem.create_memory(...)
    ↓
AIMemoryDatabase.create_memory(...)
    ├→ INSERT into curated_memories (memory_id, content, importance_level, ...)
    └→ Returns memory_id (immediately - doesn't wait for embedding)
    ↓
asyncio.create_task(FridayMemorySystem._add_embedding_to_memory(memory_id, content))
    ├→ EmbeddingService.generate_embedding("I like coffee")
    │  ├→ Try LM Studio /v1/embeddings (192.168.1.50:1234)
    │  └→ Return [0.123, 0.456, ..., 0.789] (768 dimensions)
    └→ AIMemoryDatabase.add_embedding(memory_id, embedding_blob)
         └→ UPDATE curated_memories SET embedding = ? WHERE memory_id = ?

Response to user: {"status": "success", "memory_id": "abc-123-def"}
```

**Key**: Embedding generation is non-blocking - user gets response instantly!

---

### Example 2: Search Memories
```
User calls: search_memories(query="What do I like?")
    ↓
MPC Server._execute_tool("search_memories", {"query": "What do I like?"})
    ↓
FridayMemorySystem.search_memories(query="What do I like?", ...)
    ↓
EmbeddingService.generate_embedding("What do I like?")
    └→ Returns query_embedding [0.234, 0.567, ..., 0.901] (768D)
    ↓
AIMemoryDatabase.search_by_similarity(query_embedding, limit=5, min_importance=1)
    ├→ SELECT * FROM curated_memories WHERE importance_level >= 1
    ├→ For each memory with embedding:
    │  └→ cosine_similarity = np.dot(query_embedding, memory_embedding)
    ├→ Sort by similarity descending
    └→ Return top 5 similar memories
    ↓
FridayMemorySystem._add_relevance_scores(results, query)
    └→ Optional: LLM relevance re-ranking if configured
    ↓
Response to user: [
    {"memory_id": "abc", "content": "I like coffee", "similarity": 0.92},
    {"memory_id": "def", "content": "I love tea", "similarity": 0.85},
    ...
]
```

---

### Example 3: Create Recurring Reminder
```
User calls: create_reminder(
    content="Weekly team meeting",
    due_datetime="2025-11-17T09:00:00",
    recurrence_pattern="weekly",
    recurrence_count=12
)
    ↓
MCP Server._execute_tool("create_reminder", {...})
    ↓
FridayMemorySystem.create_reminder(...)
    ↓
ScheduleDatabase.create_reminder(...)
    ├→ Loop 12 times:
    │  └→ INSERT INTO reminders (reminder_id, content, due_datetime, ..., completed=0)
    │     with due_datetime incremented by 1 week each iteration
    └→ Return List[reminder_ids]
    ↓
Response to user: {
    "status": "success",
    "reminder_ids": ["rem-1", "rem-2", ..., "rem-12"],
    "count": 12
}
```

---

### Example 4: Get System Health
```
User calls: get_system_health()
    ↓
MCP Server._execute_tool("get_system_health", {})
    ↓
FridayMemorySystem.get_system_health()
    ├→ For each database:
    │  ├→ Query row count
    │  ├→ Check file size
    │  └→ Verify connectivity
    ├→ EmbeddingService status:
    │  ├→ Generate test embedding
    │  ├→ Get embeddings_endpoint from primary_config
    │  └→ Check provider availability
    └→ Build health dict with status: "healthy", "degraded", "error"
    ↓
Response to user: {
    "status": "healthy",
    "timestamp": "2025-11-17T20:16:00",
    "databases": {
        "ai_memories": {"status": "healthy", "count": 185, "size_mb": 45.2},
        "conversations": {"status": "healthy", "count": 420, "size_mb": 87.5},
        "schedule": {"status": "healthy", "count": 25, "size_mb": 1.2},
        ...
    },
    "embedding_service": {
        "status": "healthy",
        "endpoint": "http://192.168.1.50:1234",
        "embedding_dimensions": 768
    }
}
```

---

## 10. LOGGING & DEBUGGING

### 10.1 Log Files
```
/media/nate/Friday/Friday/logs/
├── tool_calls.log          # All MCP tool invocations
├── embeddings_completed.log # Retroactive embedding completion timestamp
└── [other debug logs]
```

### 10.2 Tool Call Logging
```python
# In _execute_tool():
log_dir = BASE_PATH / "logs"
with open(log_dir / "tool_calls.log", "a") as f:
    f.write(f"{datetime.now().isoformat()} - Tool called: {tool_name}\n")
    f.write(f"  Arguments: {json.dumps(arguments, indent=2)}\n")
    f.write("-" * 80 + "\n")
```

### 10.3 MCPToolCallDatabase Logging
```python
# After tool execution:
await self.memory_system.mcp_db.log_tool_call(
    tool_name=tool_name,
    arguments=arguments,
    result=result,
    execution_time=execution_time_ms,
    success=success,
    error_message=error if not success else None
)
```

---

## 11. KEY DESIGN PATTERNS

### Pattern 1: Importance-Based Pruning
**Use Case**: Memory limit reached
- Keep memories with importance 8-9 (promoted)
- Delete memories with importance 1-5 (regular)
- Configurable via valve: `pruning_strategy: "fifo" | "least_relevant"`

### Pattern 2: Dual Isolation
**Use Case**: Multi-user/multi-model scenarios
```sql
WHERE user_id = ? AND model_id = ?
```
- Every memory can be isolated by user and model
- Default model_id = "Friday"

### Pattern 3: Async-First Embeddings
**Use Case**: Large-scale embedding generation
- Non-blocking: `asyncio.create_task(...)`
- Doesn't wait for embedding to finish
- Can have thousands in flight simultaneously

### Pattern 4: Cascading Fallback
**Use Case**: Embedding provider unavailable
1. Try primary (LM Studio)
2. Try fallback (Ollama)
3. Try secondary fallback (OpenAI)
4. If all fail: log and continue without embedding

### Pattern 5: Schema Migration
**Use Case**: Database column additions
```python
# Check existing schema
cur = conn.execute("PRAGMA table_info(table_name)")
current_columns = [row[1] for row in cur.fetchall()]

# If column missing, add it
if "new_column" not in current_columns:
    conn.execute("ALTER TABLE table_name ADD COLUMN new_column TEXT")
```

---

## 12. PERFORMANCE CHARACTERISTICS

| Operation | Time | Notes |
|-----------|------|-------|
| Create memory | <5ms | Depends on DB, not embedding |
| Search 185 memories | 100-300ms | Vector similarity calcs |
| Generate embedding | 100-500ms | Async, doesn't block |
| List reminders | <10ms | Simple SELECT |
| Get system health | 500-2000ms | Includes health check |
| Retroactive embed (185) | 30-60s | Runs async on startup |

---

## 13. DATABASE DISCOVERY & ROTATION

**Location**: `DatabaseMaintenance` class

**Purpose**: Handle database growth and file rotation

**Current Strategy**:
- When database grows beyond limit
- Rotate to new file: `ai_memories_v2.db`, `ai_memories_v3.db`, etc.
- Maintain registry of active files
- Optional: Archive old databases

**Access**:
```python
self.active_db_files = {
    "conversations": "memory_data/conversations.db",
    "ai_memories": "memory_data/ai_memories.db",
    ...
}
```

---

## 14. INTEGRATION CHECKLIST

✅ **Completed**:
- [x] 5 database backends (Conversations, AIMemory, Schedule, VSCode, MCPToolCalls)
- [x] EmbeddingService with fallback providers
- [x] MCP server with tool routing
- [x] Async embedding generation
- [x] Importance-based memory management
- [x] User/model isolation
- [x] System health monitoring
- [x] Tool call logging
- [x] Periodic maintenance loop
- [x] File monitoring for VS Code imports

🔄 **In Progress**:
- [ ] REST API layer for promotion/retrieval
- [ ] Embedding config sync with Adaptive Memory v3
- [ ] Advanced memory retirement/archival

---

## 15. QUICK REFERENCE: Adding a New Tool

**Step 1**: Define tool in `_get_client_tools()`:
```python
Tool(
    name="my_tool",
    description="What it does",
    inputSchema={"type": "object", "properties": {...}, "required": [...]}
)
```

**Step 2**: Add handler in `_execute_tool()`:
```python
elif tool_name == "my_tool":
    allowed_args = {"arg1", "arg2"}
    filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
    result = await self.memory_system.my_function(**filtered_args)
```

**Step 3**: Implement in `FridayMemorySystem`:
```python
async def my_function(self, arg1, arg2):
    # Do work
    return {"status": "success", "data": ...}
```

**Step 4**: Add corresponding database method if needed in appropriate `*Database` class.

---

## Summary

The **Friday Memory System** is a sophisticated, multi-layered architecture:

1. **Database Layer**: 5 specialized SQLite databases for different data types
2. **Embedding Service**: Intelligent vector generation with fallback providers
3. **Coordinator**: FridayMemorySystem orchestrates all operations
4. **MCP Interface**: Exposes tools via Model Context Protocol
5. **Async Core**: Non-blocking operations, background tasks
6. **Maintenance**: Automatic optimization and monitoring

All tied together with **user/model isolation**, **importance-based management**, **async-first design**, and **cascading fallbacks** for robustness.
