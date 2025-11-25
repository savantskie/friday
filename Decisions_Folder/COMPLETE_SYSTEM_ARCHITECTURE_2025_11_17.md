# Complete Friday System Architecture (November 17, 2025)

## Executive Summary

The Friday system has **THREE separate but interrelated memory systems**:

1. **OpenWebUI Built-in Memory System** (used by Adaptive Memory v3)
2. **Friday Memory System** (MCP Server + Database backends)
3. **Short-term Memory in Adaptive Memory v3** (extraction & caching in plugin)

Understanding the distinction is critical for integrations.

---

## 1. DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OPENWBUI CONTAINER                                │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                  User sends message to OpenWebUI                     │   │
│  │                                                                      │   │
│  │  ┌──────────────┐         ┌──────────────────┐                      │   │
│  │  │  Inlet       │─ ──────>│ Adaptive Memory  │  (Memory Retrieval) │   │
│  │  │  Filter      │         │ v3 Plugin        │                      │   │
│  │  └──────────────┘         └──────────────────┘                      │   │
│  │         │                         │                                 │   │
│  │         │                         │ Injects relevant memories       │   │
│  │         │                         │ from OpenWebUI memory store     │   │
│  │         ▼                         ▼                                 │   │
│  │  ┌──────────────┐         ┌──────────────────┐                      │   │
│  │  │ Interface    │────────>│ Main LLM Model   │                      │   │
│  │  │ Model        │ (Tools) │ (Friday/30B)     │                      │   │
│  │  │ (Qwen)       │         │                  │                      │   │
│  │  └──────────────┘         └──────────────────┘                      │   │
│  │                                   │                                 │   │
│  │  ┌──────────────┐         ┌──────────────────┐                      │   │
│  │  │  Outlet      │<────────│ LLM Response     │  (Memory Extraction)│   │
│  │  │  Filter      │         └──────────────────┘                      │   │
│  │  └──────────────┘                                                    │   │
│  │         │                                                            │   │
│  │         │ Extracts memories from conversation                       │   │
│  │         │ Stores in OpenWebUI built-in memory (short-term)          │   │
│  │         │ Runs FIFO pruning if needed                               │   │
│  │         │ Embeds using Adaptive Memory's embedding config           │   │
│  │         ▼                                                            │   │
│  │  ┌────────────────────────────────────────┐                         │   │
│  │  │ OpenWebUI Built-in Memory Database     │                         │   │
│  │  │ └────────────────────────────────────┐ │                         │   │
│  │  │ • memories table (SQLite)            │ │                         │   │
│  │  │ • content, embedding, tags, bank     │ │                         │   │
│  │  │ • importance_level (1-10)            │ │                         │   │
│  │  │ • max_total_memories limit: 200      │ │                         │   │
│  │  │ • pruning_strategy: "fifo" or        │ │                         │   │
│  │  │   "least_relevant"                   │ │                         │   │
│  │  └────────────────────────────────────┘ │                         │   │
│  │  └────────────────────────────────────┘                            │   │
│  │         │                                                            │   │
│  └─────────┼────────────────────────────────────────────────────────────┘   │
│            │                                                              │
│            │ (Can also be called via API from external sources)          │
│            ▼                                                              │
│  ┌─────────────────────────────────┐                                    │
│  │ localhost:1234 (LM Studio)      │  (Embedding endpoint)              │
│  │ /v1/embeddings                  │                                    │
│  └─────────────────────────────────┘                                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                        LINUX HOST (Outside Container)                       │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ /media/nate/Friday/Friday/friday_memory_system.py                 │    │
│  │ ├── AIMemoryDatabase (ai_memories.db)                             │    │
│  │ │   └── curated_memories table                                    │    │
│  │ │       • memory_id (PK)                                          │    │
│  │ │       • content                                                 │    │
│  │ │       • importance_level (1-10)                                 │    │
│  │ │       • memory_type, tags                                       │    │
│  │ │       • user_id, model_id='Friday'                              │    │
│  │ │       • embedding (BLOB for vector search)                      │    │
│  │ │       • created_at                                              │    │
│  │ │                                                                 │    │
│  │ ├── ConversationDatabase (conversations.db)                       │    │
│  │ │   └── Stores all conversation history                          │    │
│  │ │                                                                 │    │
│  │ ├── ScheduleDatabase (schedule.db)                                │    │
│  │ │   └── Appointments & reminders                                 │    │
│  │ │                                                                 │    │
│  │ └── EmbeddingService                                              │    │
│  │     ├── Primary: LM Studio (192.168.1.50:1234)                   │    │
│  │     ├── Fallback: Ollama (localhost:11434)                        │    │
│  │     └── embeddings_endpoint attribute = base_url                 │    │
│  │                                                                 │    │
│  │ /media/nate/Friday/Friday/friday_memory_mcp_server.py            │    │
│  │ └── MCP Server (Model Context Protocol)                          │    │
│  │     ├── Tool: create_memory (content, importance, tags)          │    │
│  │     ├── Tool: search_memories (query, filters)                   │    │
│  │     ├── Tool: update_memory (modify existing)                    │    │
│  │     ├── Tool: create_appointment / create_reminder               │    │
│  │     ├── Tool: get_system_health (shows embedding endpoint)       │    │
│  │     └── Callable from: VS Code, LM Studio, CLI                   │    │
│  │                                                                 │    │
│  │ /media/nate/Friday/Friday/embedding_config.json                  │    │
│  │ └── Configuration for embedding providers                        │    │
│  │     ├── primary: lmstudio, model, base_url                       │    │
│  │     └── fallback: ollama, model, base_url                        │    │
│  │                                                                 │    │
│  │ /media/nate/Friday/Friday/friday_memory_short_term.py                  │    │
│  │ └── OpenWebUI Plugin (also on Linux, imported by container)      │    │
│  │     ├── Uses OpenWebUI's built-in memory system                  │    │
│  │     ├── Embedding model: text-embedding-nomic-embed-text-v1.5   │    │
│  │     ├── Config valve: embedding_model, embedding_endpoint        │    │
│  │     └── Can update embedding_config.json for sync                │    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  /media/nate/Friday/Friday/logs/                                           │
│  ├── embeddings_completed.log (prevents re-embedding on reload)            │
│  ├── tool_calls.log (MCP server tool invocations)                          │
│  └── [other logs]                                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. THREE MEMORY SYSTEMS EXPLAINED

### 2A. OpenWebUI Built-in Memory (SHORT-TERM)
**Location**: Inside Docker container (OpenWebUI)  
**Used by**: Adaptive Memory v3 plugin  
**Purpose**: Extraction and initial storage from conversations

**Key Features**:
- Stores memories from user messages → LLM responses
- FIFO or least-relevant pruning when max 200 memories reached
- Embeddings generated via Adaptive Memory's embedding_model valve
- Tagged with bank names (General, Personal, Work, etc.)
- Importance level system (1-10, default 5)

**Data Flow**:
1. User sends message → inlet injection (retrieves memories)
2. LLM responds
3. Outlet extracts memories from conversation
4. Stores in OpenWebUI's memory table
5. Prunes oldest if limit exceeded
6. Generates embeddings asynchronously

**Key File**: 
- friday_memory_short_term.py lines 2792-2900 (outlet function)
- Uses OpenWebUI import: `from open_webui.routers.memories import Memories`

---

### 2B. Friday Memory System (LONG-TERM)
**Location**: /media/nate/Friday/Friday (Linux host)  
**Used by**: MCP Server (VS Code, LM Studio, CLI)  
**Purpose**: Persistent, curated long-term memory store

**Key Features**:
- AIMemoryDatabase stores curated memories with higher persistence
- Importance levels 8-9 mark promoted/curated memories
- Vector search via embeddings
- Separate from OpenWebUI container
- Accessible via MCP protocol
- Tools: create_memory, search_memories, update_memory, etc.

**Data Flow**:
1. External tool calls MCP server
2. MCP server routes to FridayMemorySystem
3. Memory stored in ai_memories.db
4. Embedding generated asynchronously
5. Searchable via semantic similarity

**Key Files**:
- friday_memory_system.py (main system)
- friday_memory_mcp_server.py (interface)
- memory_data/ai_memories.db (storage)

---

### 2C. Adaptive Memory v3 Extraction Engine (ACTIVE PROCESSING)
**Location**: /media/nate/Friday/Friday/friday_memory_short_term.py (plugin in Docker)  
**Purpose**: Intelligent memory extraction and embedding

**Key Features**:
- Inlet: Retrieves relevant memories before LLM processes
- Outlet: Extracts memories after LLM response
- Embedding model: Configurable via valve
- Pruning: FIFO strategy with configurable limit
- Memory banks: Personal, Work, General (extensible via valve)
- Status messages: Real-time feedback on memory operations

**Current Configuration Valve**:
- embedding_model: "text-embedding-nomic-embed-text-v1.5"
- embedding_endpoint: "http://192.168.1.50:1234/v1/embeddings"  
  (Can be changed to Ollama or other providers)
- max_total_memories: 200
- pruning_strategy: "fifo"
- allowed_memory_banks: ["General", "Personal", "Work", "Context", "Tasks"]

---

## 3. EMBEDDING COORDINATION

**Current Problem**: Two different embedding configurations exist independently
- OpenWebUI Adaptive Memory: config in valve
- Friday Memory System: config in embedding_config.json

**Solution**: Create sync mechanism
- Adaptive Memory v3 updates embedding_config.json when valve changes
- Both systems always use same embedding model and endpoint
- File-based sync prevents race conditions

**Embedding Services**:
1. **LM Studio** (Primary): 192.168.1.50:1234/v1/embeddings
2. **Ollama** (Fallback): localhost:11434/api/embeddings
3. Both produce compatible embeddings (768D nomic-embed-text)

---

## 4. THE PROMOTION FLOW (Proposed)

**Goal**: Move memories from OpenWebUI short-term → Friday long-term

**Proposed API Endpoint**: `POST /api/memories/promote`

**Flow**:
```
1. Memory extracted in OpenWebUI (importance_level=5)
   ↓
2. User/system decides to promote
   ↓
3. API call: POST /api/memories/promote
   - memory_id (or content)
   - tags (e.g., ["promoted", "important"])
   ↓
4. FridayMemorySystem.create_memory()
   - content: from OpenWebUI memory
   - importance_level: 8 (marked as promoted)
   - tags: ["promoted", "short_term→long_term"]
   - Store in ai_memories.db
   ↓
5. Async embedding generation (doesn't block)
   ↓
6. THEN trigger FIFO pruning in Adaptive Memory
   - Only prunes low-importance (≤5) or old memories
   - Promoted memories (importance 8-9) survive longer
   ↓
7. Success response with new memory_id
```

**Why this order matters**:
- Promote FIRST → high importance → survives pruning
- Prune SECOND → doesn't accidentally delete what was just promoted
- Clean separation of concerns

---

## 5. KEY COMPONENTS & RESPONSIBILITIES

### Adaptive Memory v3 (OpenWebUI Plugin)
**Responsibilities**:
- ✅ Extract memories from conversations (inlet/outlet)
- ✅ Store in OpenWebUI built-in memory
- ✅ FIFO pruning when limit reached
- ✅ Generate embeddings for search
- ✅ Inject relevant memories into context
- 🔄 Update embedding_config.json on valve change (NEW)
- 🔄 Provide memory_bank configuration via valve (DONE)

**Does NOT do**:
- Not long-term archival (that's Friday Memory System)
- Not accessible outside OpenWebUI natively
- Not used by MCP clients

### Friday Memory System
**Responsibilities**:
- ✅ Store curated/promoted memories long-term
- ✅ Vector search across memories
- ✅ Provide MCP interface for external tools
- ✅ Handle embeddings with fallback providers
- ✅ Maintain separate databases for org (conversations, schedule, etc.)
- 🔄 Receive promoted memories via API (NEW)

**Does NOT do**:
- Not automatic extraction (that's Adaptive Memory)
- Not directly embedded in OpenWebUI
- Not real-time conversation memory

### Embedding Service
**Responsibilities**:
- ✅ Generate embeddings via LM Studio or Ollama
- ✅ Fallback to secondary provider if primary fails
- ✅ Cache embeddings in memory and database
- ✅ Expose embeddings_endpoint attribute
- 🔄 Accept config updates from Adaptive Memory (NEW)

---

## 6. DATABASE SCHEMAS QUICK REFERENCE

### OpenWebUI Memory (inside container)
```sql
memories (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  memory_bank TEXT,  -- "Personal", "Work", "General", etc.
  content TEXT,
  importance_level INTEGER,  -- 1-10
  tags TEXT,  -- JSON array
  embedding BLOB,  -- Vector
  created_at TIMESTAMP
)
```

### Friday Memory System
```sql
curated_memories (
  memory_id TEXT PRIMARY KEY,
  content TEXT,
  importance_level INTEGER,  -- 1-10 (8-9 for promoted)
  memory_type TEXT,
  tags TEXT,  -- JSON array
  embedding BLOB,  -- Vector
  user_id TEXT,
  model_id TEXT DEFAULT 'Friday',
  created_at TEXT
)
```

---

## 7. CURRENT IMPLEMENTATION STATUS

### ✅ Complete
- [x] Adaptive Memory v3 extraction & storage
- [x] OpenWebUI built-in memory system integration
- [x] FIFO pruning in Adaptive Memory
- [x] Embedding model detection and caching
- [x] MCP server infrastructure
- [x] Friday Memory System long-term storage
- [x] Model-aware memory injection (skips interface model)
- [x] Status messages in OpenWebUI UI
- [x] Docker networking fix (host.docker.internal → 172.17.0.1)
- [x] Retroactive embedding with completion log
- [x] EmbeddingService.embeddings_endpoint attribute

### 🔄 In Progress
- [ ] API layer for memory promotion
- [ ] Embedding config sync (Adaptive Memory ↔ Friday System)
- [ ] Memory promotion flow (OpenWebUI short-term → Friday long-term)

### ⏳ Planned
- [ ] REST endpoints for memory operations
- [ ] Webhook notifications for promoted memories
- [ ] Memory analytics and reporting
- [ ] Advanced memory retirement/archival strategies

---

## 8. INTEGRATION POINTS (Where Code Talks)

### Point 1: Extraction → Storage
**Files**: friday_memory_short_term.py (outlet) → OpenWebUI memory.add_memory()
**Type**: Direct function call (inside same Docker container)
**Direction**: Async, non-blocking

### Point 2: Retrieval → Injection
**Files**: friday_memory_short_term.py (inlet) → memory.query_memory()
**Type**: Direct function call
**Direction**: Sync, blocking (happens before LLM call)

### Point 3: MCP Access
**Files**: VS Code / LM Studio → friday_memory_mcp_server.py
**Type**: MCP protocol over stdio
**Direction**: Request/Response, blocking

### Point 4: Embedding Generation
**Files**: friday_memory_short_term.py / friday_memory_system.py → LM Studio (192.168.1.50:1234)
**Type**: HTTP REST (OpenAI-compatible /v1/embeddings)
**Direction**: Async, with fallback to Ollama

### Point 5: Configuration Sync (PROPOSED)
**Files**: friday_memory_short_term.py → embedding_config.json
**Type**: File system write
**Direction**: One-way (Adaptive Memory → File → Friday System reads)
**Trigger**: When embedding valve changes

---

## 9. PORTS & ENDPOINTS REFERENCE

| Service | Host | Port | Endpoint | Purpose |
|---------|------|------|----------|---------|
| OpenWebUI | Docker | 8080 | - | Main UI |
| LM Studio | Linux | 1234 | /v1/embeddings | Embedding generation |
| LM Studio | Linux | 1234 | /v1/chat/completions | LLM API |
| Ollama | Linux | 11434 | /api/embeddings | Fallback embeddings |
| MCP Server | Linux | stdio | - | Via VS Code extension |
| Docker Gateway | Network | - | 172.17.0.1 | Internal Docker access |

---

## 10. FILES AT A GLANCE

| File | Purpose | Type |
|------|---------|------|
| friday_memory_short_term.py | Memory extraction & management | Plugin/Filter |
| friday_memory_system.py | Long-term memory storage & search | Core System |
| friday_memory_mcp_server.py | MCP protocol interface | Server |
| embedding_config.json | Embedding provider configuration | Config |
| embeddings_completed.log | Tracks retroactive embedding completion | Log |
| memory_data/ai_memories.db | Friday long-term memory storage | Database |
| memory_data/conversations.db | Conversation history | Database |
| memory_data/schedule.db | Appointments & reminders | Database |

---

## 11. NEXT STEPS FOR PROMOTION FLOW

### Phase 1: API Layer Design
- [ ] Define REST endpoints for memory operations
- [ ] Implement /api/memories/promote endpoint
- [ ] Route to friday_memory_system.create_memory()
- [ ] Mark promoted memories with importance_level=8-9

### Phase 2: Embedding Config Sync
- [ ] Adaptive Memory v3 detects valve changes
- [ ] Updates embedding_config.json
- [ ] Friday system reads config on startup
- [ ] Both systems always in sync

### Phase 3: Testing & Validation
- [ ] Promote memory from OpenWebUI
- [ ] Verify stored in Friday with high importance
- [ ] Verify survives FIFO pruning
- [ ] Verify embedding sync works

---

## 12. TROUBLESHOOTING CHECKLIST

**Problem**: Memories not extracting
- Check: friday_memory_short_term.py outlet function (line 2792)
- Check: User has memory enabled in valves
- Check: OpenWebUI memory API available

**Problem**: Embeddings not generating
- Check: LM Studio endpoint in valve vs embedding_config.json
- Check: Embedding model is loaded in LM Studio
- Check: embeddings_completed.log for errors

**Problem**: Memory not appearing in Friday system
- Check: API endpoint configured correctly
- Check: MCP server running and accessible
- Check: friday_memory_system.py can access database

**Problem**: Docker can't reach host services
- Check: Using 172.17.0.1 gateway (not host.docker.internal)
- Check: Port mappings correct
- Check: Service actually running on host

---

## Summary

You now have **three memory systems working in concert**:

1. **Adaptive Memory v3** = Active extraction engine (OpenWebUI short-term)
2. **Friday Memory System** = Long-term persistent store (MCP-accessible)
3. **Embedding Service** = Shared intelligence layer (LM Studio backed)

The **promotion flow** ties them together: memories can flow from short-term extraction → long-term curation with elevation of importance to prevent pruning.

The **embedding sync** ensures both systems always use the same models and endpoints for consistent vector spaces.

All tied together by **configuration management** (valves + config file) and **clear data flow**.
