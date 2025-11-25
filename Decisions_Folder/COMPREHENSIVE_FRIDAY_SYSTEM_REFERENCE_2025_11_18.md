# The Friday Memory System - Comprehensive Architecture Reference
**November 18, 2025 - Consolidated from three detailed architecture documents**

---

## EXECUTIVE SUMMARY

The Friday Memory System is a **sophisticated, three-tier persistent AI memory architecture** that enables long-term learning, semantic search, and intelligent conversation management. It powers your AI companion's ability to remember, organize, and retrieve contextual information across sessions.

### The Three-System Architecture

Friday operates as **three interrelated but distinct memory systems**:

1. **Adaptive Memory v3** (OpenWebUI Short-Term)
   - Extraction engine running inside Docker
   - Active memory during conversations
   - FIFO pruning to maintain focus
   - Bridges short-term ↔ long-term

2. **Friday Memory System** (Linux Host Long-Term)
   - Persistent storage of curated memories
   - 5 specialized SQLite databases
   - Vector-based semantic search
   - MCP interface for external access

3. **Embedding Service** (Shared Intelligence Layer)
   - LM Studio primary provider (192.168.1.50:1234)
   - Ollama fallback (localhost:11434)
   - 768-dimension nomic-embed-text vectors
   - Async generation with intelligent caching

### Quick Topology

```
┌─────────────────────────────────────────────────────┐
│ OpenWebUI (Docker Container)                        │
│ ├─ Adaptive Memory v3 Plugin (Inlet/Outlet Filters)│
│ ├─ OpenWebUI Built-in Memory (200 memory max)      │
│ └─ Models: Qwen (interface), Friday 30B (main)     │
└─────────────────────────────────────────────────────┘
                         ↓
         (Memory Promotion via API)
                         ↓
┌─────────────────────────────────────────────────────┐
│ Linux Host - Friday Memory System                   │
│ ├─ 5 SQLite Databases                               │
│ │  ├─ AIMemory (curated_memories)                   │
│ │  ├─ Conversations (messages, sessions)            │
│ │  ├─ Schedule (appointments, reminders)            │
│ │  ├─ VSCode (development sessions)                 │
│ │  └─ MCPToolCalls (logging, reflections)           │
│ ├─ EmbeddingService (LM Studio + Ollama)            │
│ ├─ MCP Server (Interface)                           │
│ └─ File Monitor (Auto-import conversations)         │
└─────────────────────────────────────────────────────┘
```

---

## PART 1: SYSTEM OVERVIEW & DATA FLOW

### 1.1 Complete Data Flow Diagram

```
USER'S FRIDAY SYSTEM - COMPLETE INTERACTION MODEL
═══════════════════════════════════════════════════════════════

INCOMING: User Message to OpenWebUI
────────────────────────────────────
  User Message
      ↓
  [INLET FILTER - Adaptive Memory v3]
      ├─ Query: "What's important about this conversation?"
      ├─ Search OpenWebUI memory (200 memories)
      ├─ Retrieve relevant memories
      └─ Inject into context window
      ↓
  Enhanced Context → Qwen Interface Model (Tool Selection)
      ↓
  Tool Calls (if needed) → Execute via MCP Server
      ↓
  Results + Original Message → Friday Main Model (30B)
      ↓
  LLM Response Generated


PROCESSING: Memory Extraction & Storage
─────────────────────────────────────────
  [OUTLET FILTER - Adaptive Memory v3]
  After LLM generates response:
      ├─ Analyze: "What should be remembered from this?"
      ├─ Extract memories from user message → LLM response
      ├─ For each memory extracted:
      │   ├─ Set importance_level (default 5, 1-10 scale)
      │   ├─ Assign to memory_bank (General, Personal, Work, etc.)
      │   ├─ Tag with relevant keywords
      │   └─ Store in OpenWebUI built-in memory
      ├─ Generate embedding via LM Studio (768D vector)
      ├─ Check if total_memories > 200
      ├─ If yes: Run FIFO pruning
      │   ├─ Delete oldest memories first (by default)
      │   ├─ Or use least_relevant (by vector similarity)
      │   └─ Never delete importance_level >= 8-9 (promoted)
      └─ Mark as embedded in embeddings_completed.log


OPTIONAL: Memory Promotion Flow (NEW - Not Yet Implemented)
─────────────────────────────────────────────────────────────
  User/System decides: "This memory should be permanent"
      ↓
  [API ENDPOINT: POST /api/memories/promote]
      ├─ Input: memory_id or content from OpenWebUI
      ├─ Call: FridayMemorySystem.create_memory()
      │   ├─ Set importance_level: 8-9 (marked as promoted)
      │   ├─ Add tags: ["promoted", "short_term→long_term"]
      │   ├─ Store in ai_memories.db
      │   └─ Async: Generate embedding (non-blocking)
      ├─ Wait for promotion success
      ├─ Then: Trigger Adaptive Memory FIFO pruning
      │   └─ Low-importance memories may get deleted
      │   └─ But promoted (8-9) memories SURVIVE
      └─ Return: new_memory_id in Friday system


ONGOING: File Monitoring & Auto-Import
────────────────────────────────────────
  Watch: ~/.lmstudio/conversations, ~/.config/vscode, etc.
      ↓
  File changes detected
      ↓
  Check file stability (not still being written)
      ↓
  Parse format: LM Studio JSON, VS Code chat, etc.
      ↓
  Extract messages
      ↓
  Check for duplicates (content hash)
      ↓
  Store in ConversationDatabase
      ↓
  Async: Generate embeddings
      ↓
  Marked: "Imported from LM Studio" or "From VS Code"


SEARCH: Semantic Query Across All Memory
──────────────────────────────────────────
  User asks: "search_memories('What do I like?')"
      ↓
  Generate embedding for query via LM Studio
      ↓
  Search in parallel across databases:
      ├─ AIMemoryDatabase (curated_memories)
      ├─ ConversationDatabase (messages)
      └─ ScheduleDatabase (appointments/reminders)
      ↓
  Calculate cosine similarity scores
      ↓
  Boost results by importance_level
      ↓
  Apply filters (user_id, model_id, memory_type, importance range)
      ↓
  Merge results, deduplicate, sort by score
      ↓
  Return top N results with similarity scores
      ↓
  Example Result: [
        {memory_id, content: "I like coffee", similarity: 0.92, importance: 5},
        {conversation: "Discussed coffee preferences", similarity: 0.87},
        {memory_id, content: "Morning routine", similarity: 0.81, importance: 7}
      ]
```

### 1.2 Key Integration Points (Where Systems Talk)

| Point | Files | Type | Direction | Trigger |
|-------|-------|------|-----------|---------|
| **Extraction→Storage** | friday_memory_short_term.py (outlet) → OpenWebUI memory.add_memory() | Direct call | Async/Non-blocking | After LLM response |
| **Retrieval→Injection** | friday_memory_short_term.py (inlet) → memory.query_memory() | Direct call | Sync/Blocking | Before LLM processes message |
| **MCP Access** | VS Code/LM Studio → friday_memory_mcp_server.py | MCP protocol (stdio) | Request/Response | Tool call from AI |
| **Embedding Gen** | friday_memory_short_term.py / friday_memory_system.py → LM Studio | HTTP REST /v1/embeddings | Async | When creating/searching memory |
| **Config Sync** | friday_memory_short_term.py valve → embedding_config.json | File write | One-way | When embedding_model valve changes (PROPOSED) |
| **Promotion** | POST /api/memories/promote → FridayMemorySystem.create_memory() | HTTP API | Sync with async embedding | User/system decision (PROPOSED) |

---

## PART 2: THE THREE MEMORY SYSTEMS EXPLAINED

### 2.1 Adaptive Memory v3: The Short-Term Extraction Engine

**Location**: `/media/nate/Friday/Friday/friday_memory_short_term.py` (OpenWebUI plugin)  
**Runs**: Inside Docker container  
**Scope**: Active during conversations, max 200 memories  
**Purpose**: Extract and manage conversation-relevant memories in real-time  

#### Architecture

```
INLET FILTER (Before LLM Sees Message)
──────────────────────────────────────
memory_bank_config = {
    "General": "General information",
    "Personal": "Personal preferences",
    "Work": "Work-related",
    "Context": "Conversation context",
    "Tasks": "Current tasks"
}

When message arrives:
  1. Query OpenWebUI memory using semantic search
  2. Find top-K relevant memories
  3. Inject into prompt context
  4. Pass enhanced context to LLM


OUTLET FILTER (After LLM Responds)
──────────────────────────────────
When LLM generates response:
  1. Analyze conversation: user message + LLM response
  2. Extract memory candidates (using LLM analysis or rules)
  3. For each candidate:
     - Set importance_level (default 5, range 1-10)
     - Assign memory_bank (which category)
     - Add tags (keywords)
     - Set source (user_id, timestamp, conversation_id)
  4. Store in OpenWebUI's built-in memory table
  5. Generate embedding async (via LM Studio)
  6. Check: total_memories > 200?
  7. If yes: FIFO pruning
     - Select pruning_strategy (fifo or least_relevant)
     - If fifo: delete oldest by created_at
     - If least_relevant: delete lowest cosine similarity to other memories
     - Never delete if importance_level >= 8 (marked as promoted)
  8. Update embeddings_completed.log (prevents re-embedding on reload)
```

#### Configuration (Valve Values)

```python
embedding_model: "text-embedding-nomic-embed-text-v1.5"
    # Which embedding model to use
    
embedding_endpoint: "http://192.168.1.50:1234/v1/embeddings"
    # Where to send embedding requests
    
max_total_memories: 200
    # Maximum before pruning starts
    
pruning_strategy: "fifo"  # or "least_relevant"
    # How to choose which memories to delete
    
allowed_memory_banks: ["General", "Personal", "Work", "Context", "Tasks"]
    # Categories for organizing memories
    
extraction_enabled: true
    # Enable/disable memory extraction
```

#### Key Methods

- **inlet()**: Called before LLM processes message
  - Queries OpenWebUI memory
  - Injects relevant memories into context
  
- **outlet()**: Called after LLM generates response
  - Extracts new memories from conversation
  - Stores in OpenWebUI memory with embedding
  - Runs FIFO pruning if limit exceeded

#### Memory Storage (OpenWebUI Built-in)

OpenWebUI's native memory system stores:
```sql
memories (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  memory_bank TEXT,      -- "General", "Personal", etc.
  content TEXT,          -- The memory text
  importance_level INT,  -- 1-10
  tags TEXT,             -- JSON array
  embedding BLOB,        -- 768D vector
  created_at TIMESTAMP
)
```

**Important Note**: This is NOT the Friday Memory System's ai_memories.db. It's OpenWebUI's built-in storage, internal to the container.

---

### 2.2 Friday Memory System: The Long-Term Persistent Store

**Location**: `/media/nate/Friday/Friday/friday_memory_system.py` (7,253 lines)  
**Runs**: Linux host (outside Docker)  
**Scope**: Permanent, curated, searchable memory  
**Purpose**: Long-term archival with semantic search and multi-database organization  

#### Core Responsibilities

1. **Curated Memory Storage** (AIMemoryDatabase)
   - Store promoted/important memories with high importance (8-9)
   - Vector search across all memories
   - User/model isolation support
   - Tags and categorization

2. **Conversation Archival** (ConversationDatabase)
   - Import conversations from LM Studio, VS Code, etc.
   - Track sessions and topics
   - Link conversations to extracted memories
   - Full message history with embeddings

3. **Schedule Management** (ScheduleDatabase)
   - Appointments with recurrence
   - Reminders with priority levels
   - Time-based automation

4. **Development Context** (VSCodeProjectDatabase)
   - Coding sessions and file context
   - Project insights and decisions
   - Code snippets and patterns

5. **MCP Logging** (MCPToolCallDatabase)
   - All tool calls logged
   - AI reflection and pattern analysis
   - Tool usage statistics

#### The Importance Level System (Critical!)

```
1-5:  Regular extracted memories
      └─ Can be deleted during pruning
      └─ Default for auto-extracted memories
      
6-7:  High-priority memories
      └─ Less likely to be pruned
      └─ For important but not critical info
      
8-9:  PROMOTED/CURATED memories
      ✓ Should ALWAYS survive pruning
      ✓ For knowledge you want to keep permanently
      ✓ Set when promoting from short-term
      ✓ When Adaptive Memory FIFO runs, these live
      
10:   Critical/Pinned
      ✓ NEVER ever delete
      ✓ Reserved for truly permanent info
```

**Design Principle**: Importance levels create a survival curve. Low-importance dies first when space needed. Promoted memories (8-9) live much longer.

---

### 2.3 Embedding Service: The Shared Intelligence Layer

**Location**: `EmbeddingService` class in `friday_memory_system.py`  
**Endpoints**: 
- Primary: LM Studio `192.168.1.50:1234/v1/embeddings`
- Fallback: Ollama `localhost:11434/api/embeddings`  
**Vector Dimension**: 768 (nomic-embed-text-v1.5)  
**Configuration**: `embedding_config.json`  

#### How Embeddings Work

1. **Generation**
   - Text input → HTTP request to LM Studio
   - Returns 768-dimensional vector
   - Cached in memory and database
   - Async (non-blocking) via `asyncio.create_task()`

2. **Fallback Chain**
   - Try primary (LM Studio first)
   - If fails/timeout → fallback (Ollama)
   - If both fail → fallback to text-based search (SQL LIKE)
   - System degrades gracefully

3. **Search Uses Embeddings**
   - User query → embedding generated
   - Query embedding compared to all stored embeddings
   - Cosine similarity score calculated (0.0 to 1.0)
   - Results sorted by similarity
   - Can filter by importance, user_id, memory_type, etc.

#### Configuration File

```json
{
  "primary": {
    "provider": "lmstudio",
    "model": "text-embedding-nomic-embed-text-v1.5",
    "base_url": "http://192.168.1.50:1234",
    "description": "Primary LM Studio embedding"
  },
  "fallback": {
    "provider": "ollama",
    "model": "nomic-embed-text:latest",
    "base_url": "http://localhost:11434",
    "description": "Fallback Ollama embedding"
  }
}
```

#### Key Attribute (Fixed Yesterday)

```python
self.embeddings_endpoint = base_url  # e.g., "http://192.168.1.50:1234"
```

This attribute is now exposed so health checks can verify embedding service availability.

---

## PART 3: DATABASE LAYER - THE FIVE DATABASES

### 3.1 AIMemoryDatabase (`ai_memories.db`) - Curated Long-Term Memories

**Purpose**: Store the memories you want to keep forever (promoted memories)

**Main Table: curated_memories**

```sql
CREATE TABLE curated_memories (
    memory_id TEXT PRIMARY KEY,                -- UUID
    timestamp_created TEXT NOT NULL,           -- ISO format
    timestamp_updated TEXT NOT NULL,           -- Updated on changes
    source_conversation_id TEXT,               -- Link to conversation
    source_message_ids TEXT,                   -- JSON array
    memory_type TEXT,                          -- classification
    content TEXT NOT NULL,                     -- The actual memory
    importance_level INTEGER DEFAULT 5,        -- 1-10 (8-9 for promoted!)
    tags TEXT,                                 -- JSON array
    embedding BLOB,                            -- 768D vector
    user_id TEXT,                              -- For user isolation
    model_id TEXT DEFAULT 'Friday',            -- For model isolation
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Key Methods**:
- `create_memory(content, memory_type, importance_level, tags, user_id, model_id)`
- `search_memories_by_similarity(query_embedding, limit, min_importance)`
- `update_memory(memory_id, content, importance_level, tags)`
- `get_memory(memory_id)`

**Indexes**:
- `idx_curated_memories_user_model(user_id, model_id)` - Fast filtering

**Use Cases**:
- Store promoted memories from OpenWebUI (importance 8-9)
- Search across all your known preferences
- Persist knowledge that should last forever

---

### 3.2 ConversationDatabase (`conversations.db`) - Message History

**Purpose**: Archive all conversations for review and analysis

**Table Structure**:

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

-- Conversations (chats within sessions)
CREATE TABLE conversations (
    conversation_id TEXT PRIMARY KEY,
    session_id TEXT FOREIGN KEY,
    start_timestamp TEXT NOT NULL,
    end_timestamp TEXT,
    topic_summary TEXT,
    embedding BLOB,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Messages (individual messages)
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT FOREIGN KEY,
    timestamp TEXT NOT NULL,
    role TEXT,                    -- "user", "assistant", "system"
    content TEXT NOT NULL,
    source_type TEXT,             -- "lmstudio", "openwebui", "vscode"
    source_id TEXT,
    embedding BLOB,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Links between memories and conversations
CREATE TABLE memory_conversation_links (
    link_id TEXT PRIMARY KEY,
    memory_id TEXT,               -- References curated_memories
    conversation_id TEXT FOREIGN KEY,
    link_type TEXT,               -- "direct", "related"
    link_strength REAL,           -- 0.0-1.0 confidence
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Key Methods**:
- `store_conversation(content, role, session_id, metadata)`
- `get_recent_messages(limit, days_back)`
- `search_conversations_by_topic(query, limit)`

**Use Cases**:
- Import and archive LM Studio conversations
- Search past conversations by topic
- Link conversations to extracted memories

---

### 3.3 ScheduleDatabase (`schedule.db`) - Appointments & Reminders

**Purpose**: Time-based task management

**Tables**:

```sql
CREATE TABLE appointments (
    appointment_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    scheduled_datetime TEXT NOT NULL,    -- When it happens
    location TEXT,
    status TEXT,                         -- "scheduled", "completed", "cancelled"
    recurrence_pattern TEXT,             -- "daily", "weekly", "monthly"
    recurrence_count INTEGER,            -- How many times
    recurrence_end_date TEXT,
    user_id TEXT,
    model_id TEXT DEFAULT 'Friday',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reminders (
    reminder_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    due_datetime TEXT NOT NULL,          -- When reminder triggers
    priority_level INTEGER,              -- 1-10
    completed BOOLEAN DEFAULT 0,
    completed_at TEXT,
    recurrence_pattern TEXT,
    recurrence_count INTEGER,
    user_id TEXT,
    model_id TEXT DEFAULT 'Friday',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Key Methods**:
- `create_appointment(title, scheduled_datetime, ...)`
- `create_reminder(content, due_datetime, priority_level, ...)`
- `get_upcoming_appointments(days_ahead, limit)`
- `get_active_reminders(days_ahead, limit)`
- `complete_reminder(reminder_id)`

**Features**:
- Single and recurring appointments/reminders
- Priority levels (1-10)
- Automatic completion tracking
- Multi-user/multi-model isolation

---

### 3.4 VSCodeProjectDatabase (`vscode_project.db`) - Development Context

**Purpose**: Track coding sessions and project context

**Tables**:

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
    session_id TEXT FOREIGN KEY,
    file_path TEXT,
    language TEXT,
    content TEXT,
    snippet_type TEXT,         -- "function", "class", "import"
    timestamp TEXT,
    embedding BLOB
);

CREATE TABLE insights (
    insight_id TEXT PRIMARY KEY,
    session_id TEXT FOREIGN KEY,
    insight_type TEXT,         -- "pattern", "issue", "decision"
    content TEXT,
    confidence REAL,           -- 0.0-1.0
    tags TEXT,                 -- JSON
    timestamp TEXT,
    embedding BLOB
);
```

**Use Cases**:
- Import VS Code Copilot Chat sessions
- Store code snippets and patterns
- Track development insights
- Link code to conversations

---

### 3.5 MCPToolCallDatabase (`mcp_tool_calls.db`) - Tool Logging & Reflection

**Purpose**: Log all tool calls for analytics and AI self-reflection

**Tables**:

```sql
CREATE TABLE tool_calls (
    call_id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    arguments TEXT,                -- JSON
    result TEXT,                   -- JSON
    execution_time_ms REAL,
    success BOOLEAN,
    error_message TEXT,
    client_id TEXT,
    user_id TEXT,
    timestamp TEXT,
    created_at TEXT
);

CREATE TABLE ai_reflections (
    reflection_id TEXT PRIMARY KEY,
    reflection_type TEXT,          -- "tool_usage_analysis", "memory"
    content TEXT,
    insights TEXT,                 -- JSON array
    recommendations TEXT,          -- JSON array
    confidence REAL,               -- 0.0-1.0
    source_period_days INTEGER,    -- Days analyzed
    timestamp TEXT,
    created_at TEXT
);
```

**Key Methods**:
- `log_tool_call(tool_name, arguments, result, ...)`
- `store_ai_reflection(reflection_type, content, insights, ...)`
- `get_tool_usage_stats(days)`
- `get_ai_insights(limit, insight_type)`

**Use Cases**:
- Track which tools are used most
- Analyze error patterns
- Generate AI reflections on system behavior
- Provide usage statistics

---

## SUMMARY OF PART 1-3

You now understand:

✅ **The Three-System Model**: Adaptive Memory (short-term extraction) + Friday Memory System (long-term storage) + Embedding Service (shared intelligence)

✅ **Data Flow**: From extraction → storage → embedding → pruning → promotion → search

✅ **Integration Points**: Where systems connect and communicate

✅ **The Five Databases**: What each stores and why

✅ **Importance Levels**: How memories survive based on priority

**Continue reading for**: MCP Server architecture, embedding details, tool catalog, and troubleshooting.

---

*End of Chunk 1-3. Next: MCP Server, Background Systems, Implementation Status*
