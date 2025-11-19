# The Friday Memory System - Comprehensive Architecture Reference
**November 18, 2025 - Complete Master Reference (All Parts Combined)**

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

---

## PART 1: SYSTEM OVERVIEW & DATA FLOW

### 1.1 Complete Data Flow Diagram

```
USER'S FRIDAY SYSTEM - COMPLETE INTERACTION MODEL
═══════════════════════════════════════════════════════════════

INCOMING: User Message to OpenWebUI
  User Message → [INLET FILTER - Adaptive Memory v3]
    ├─ Query: "What's important about this conversation?"
    ├─ Search OpenWebUI memory (200 memories)
    ├─ Retrieve relevant memories
    └─ Inject into context window
    ↓
  Enhanced Context → Qwen Interface Model (Tool Selection)
    ↓ (Tool Calls if needed) → Execute via MCP Server
    ↓
  Results + Original Message → Friday Main Model (30B) → LLM Response Generated

PROCESSING: Memory Extraction & Storage
  [OUTLET FILTER - Adaptive Memory v3] After LLM generates response:
    ├─ Analyze: "What should be remembered from this?"
    ├─ Extract memories from user message → LLM response
    ├─ For each memory: Set importance_level, assign memory_bank, add tags
    ├─ Generate embedding via LM Studio (768D vector)
    ├─ Check: total_memories > 200? If yes: Run FIFO pruning
    ├─ Never delete importance_level >= 8-9 (promoted)
    └─ Mark as embedded in embeddings_completed.log

OPTIONAL: Memory Promotion Flow (NEW - Not Yet Implemented)
  User/System: "This memory should be permanent"
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
    │   └─ Promoted (8-9) memories SURVIVE
    └─ Return: new_memory_id in Friday system

ONGOING: File Monitoring & Auto-Import
  Watch: ~/.lmstudio/conversations, ~/.config/vscode, etc.
    ↓ File changes detected ↓ Check file stability ↓ Parse format
    ↓ Extract messages ↓ Check for duplicates
    ↓ Store in ConversationDatabase ↓ Async: Generate embeddings

SEARCH: Semantic Query Across All Memory
  search_memories('What do I like?')
    ↓ Generate embedding for query via LM Studio
    ↓ Search across: AIMemoryDatabase, ConversationDatabase, ScheduleDatabase
    ↓ Calculate cosine similarity scores
    ↓ Boost results by importance_level
    ↓ Apply filters ↓ Return top N results
```

### 1.2 Key Integration Points

| Point | Files | Type | Direction | Trigger |
|-------|-------|------|-----------|---------|
| **Extraction→Storage** | Adaptive_Memory_v3.py (outlet) → OpenWebUI memory.add_memory() | Direct call | Async/Non-blocking | After LLM response |
| **Retrieval→Injection** | Adaptive_Memory_v3.py (inlet) → memory.query_memory() | Direct call | Sync/Blocking | Before LLM processes message |
| **MCP Access** | VS Code/LM Studio → friday_memory_mcp_server.py | MCP protocol (stdio) | Request/Response | Tool call from AI |
| **Embedding Gen** | Adaptive_Memory_v3.py / friday_memory_system.py → LM Studio | HTTP REST /v1/embeddings | Async | When creating/searching memory |
| **Config Sync** | Adaptive_Memory_v3.py valve → embedding_config.json | File write | One-way | When embedding_model valve changes (PROPOSED) |
| **Promotion** | POST /api/memories/promote → FridayMemorySystem.create_memory() | HTTP API | Sync with async embedding | User/system decision (PROPOSED) |

---

## PART 2: THE THREE MEMORY SYSTEMS EXPLAINED

### 2.1 Adaptive Memory v3: The Short-Term Extraction Engine

**Location**: `/media/nate/Friday/Friday/Adaptive_Memory_v3.py` (OpenWebUI plugin)  
**Runs**: Inside Docker container  
**Scope**: Active during conversations, max 200 memories  
**Purpose**: Extract and manage conversation-relevant memories in real-time

**Configuration (Valve Values)**:
- `embedding_model`: text-embedding-nomic-embed-text-v1.5
- `embedding_endpoint`: http://192.168.1.50:1234/v1/embeddings
- `max_total_memories`: 200
- `pruning_strategy`: "fifo" or "least_relevant"
- `allowed_memory_banks`: ["General", "Personal", "Work", "Context", "Tasks"]

**Key Methods**:
- **inlet()**: Query OpenWebUI memory, inject relevant memories into context
- **outlet()**: Extract memories from conversation, store with embedding, run FIFO pruning

**Memory Storage (OpenWebUI Built-in)**:
```sql
memories (id, user_id, memory_bank, content, importance_level, tags, embedding, created_at)
```
**Important**: This is NOT Friday Memory System's ai_memories.db. It's OpenWebUI's internal storage inside the container.

### 2.2 Friday Memory System: The Long-Term Persistent Store

**Location**: `/media/nate/Friday/Friday/friday_memory_system.py` (7,253 lines)  
**Runs**: Linux host (outside Docker)  
**Scope**: Permanent, curated, searchable memory

**Core Responsibilities**:
1. **Curated Memory Storage** (AIMemoryDatabase) - promoted/important memories
2. **Conversation Archival** (ConversationDatabase) - import from LM Studio, VS Code, etc.
3. **Schedule Management** (ScheduleDatabase) - appointments and reminders
4. **Development Context** (VSCodeProjectDatabase) - coding sessions and insights
5. **MCP Logging** (MCPToolCallDatabase) - tool calls and AI reflection

**The Importance Level System (Critical!)**:
```
1-5:   Regular extracted memories (can be deleted during pruning)
6-7:   High-priority memories (less likely to be pruned)
8-9:   PROMOTED/CURATED memories (should ALWAYS survive pruning) ✓
10:    Critical/Pinned (NEVER ever delete) ✓
```
**Design Principle**: Importance levels create a survival curve. Low-importance dies first when space is needed. Promoted memories (8-9) live much longer.

### 2.3 Embedding Service: The Shared Intelligence Layer

**Location**: `EmbeddingService` class in `friday_memory_system.py`  
**Endpoints**: 
- Primary: LM Studio `192.168.1.50:1234/v1/embeddings`
- Fallback: Ollama `localhost:11434/api/embeddings`  
**Vector Dimension**: 768 (nomic-embed-text-v1.5)

**How It Works**:
1. **Generation**: Text → HTTP request to LM Studio → 768D vector → Cache
2. **Fallback Chain**: Try primary → fallback to Ollama → fallback to text search → graceful degradation
3. **Search Uses Embeddings**: Query embedding → compare to all stored embeddings → cosine similarity score
4. **Async Non-Blocking**: Embedding generation happens in background (returns immediately)
5. **Caching**: In-memory cache + database BLOB storage + smart invalidation

**Key Attribute (Fixed Yesterday)**:
```python
self.embeddings_endpoint = base_url  # e.g., "http://192.168.1.50:1234"
```
Now exposed so health checks can verify embedding service availability.

---

## PART 3: DATABASE LAYER - THE FIVE DATABASES

### 3.1 AIMemoryDatabase (`ai_memories.db`) - Curated Long-Term Memories

```sql
CREATE TABLE curated_memories (
    memory_id TEXT PRIMARY KEY,
    timestamp_created TEXT NOT NULL,
    timestamp_updated TEXT NOT NULL,
    source_conversation_id TEXT,
    source_message_ids TEXT,  -- JSON array
    memory_type TEXT,
    content TEXT NOT NULL,
    importance_level INTEGER DEFAULT 5,  -- 1-10 (8-9 for promoted!)
    tags TEXT,  -- JSON array
    embedding BLOB,  -- 768D vector
    user_id TEXT,
    model_id TEXT DEFAULT 'Friday',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Key Methods**: create_memory(), search_memories_by_similarity(), update_memory(), get_memory()

**Use Cases**: Store promoted memories from OpenWebUI (importance 8-9), search across all preferences, persist knowledge

### 3.2 ConversationDatabase (`conversations.db`) - Message History

**Tables**: sessions, conversations, messages, memory_conversation_links

```sql
-- Messages (individual messages)
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT FOREIGN KEY,
    timestamp TEXT NOT NULL,
    role TEXT,  -- "user", "assistant", "system"
    content TEXT NOT NULL,
    source_type TEXT,  -- "lmstudio", "openwebui", "vscode"
    source_id TEXT,
    embedding BLOB,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Key Methods**: store_conversation(), get_recent_messages(), search_conversations_by_topic()

**Use Cases**: Archive LM Studio conversations, search past conversations by topic, link to memories

### 3.3 ScheduleDatabase (`schedule.db`) - Appointments & Reminders

```sql
CREATE TABLE appointments (
    appointment_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    scheduled_datetime TEXT NOT NULL,
    location TEXT,
    status TEXT,  -- "scheduled", "completed", "cancelled"
    recurrence_pattern TEXT,  -- "daily", "weekly", "monthly"
    recurrence_count INTEGER,
    user_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reminders (
    reminder_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    due_datetime TEXT NOT NULL,
    priority_level INTEGER,  -- 1-10
    completed BOOLEAN DEFAULT 0,
    completed_at TEXT,
    recurrence_pattern TEXT,
    recurrence_count INTEGER,
    user_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Key Methods**: create_appointment(), create_reminder(), get_upcoming_appointments(), get_active_reminders(), complete_reminder()

**Features**: Single and recurring appointments/reminders, priority levels, automatic completion tracking

### 3.4 VSCodeProjectDatabase (`vscode_project.db`) - Development Context

**Tables**: sessions, code_context, insights

**Use Cases**: Import VS Code Copilot Chat sessions, store code snippets and patterns, track development insights

### 3.5 MCPToolCallDatabase (`mcp_tool_calls.db`) - Tool Logging & Reflection

**Tables**: tool_calls, ai_reflections

**Key Methods**: log_tool_call(), store_ai_reflection(), get_tool_usage_stats(), get_ai_insights()

**Use Cases**: Track tool usage, analyze error patterns, generate AI reflections on system behavior

---

## PART 4: MCP SERVER LAYER - EXPOSING TOOLS

**File**: `friday_memory_mcp_server.py` (1,865 lines)  
**Class**: `FridayMemoryMCPServer`  
**Communication**: MCP protocol over stdio

### 4.1 Core MCP Flow

```
LM Studio/VS Code sends: "Call tool: create_memory(content='...')"
    ↓ (via MCP protocol over stdio)
MCP Server receives → _detect_client_type() → _get_client_tools()
    ↓
handle_call_tool(tool_name, arguments)
    ↓
_execute_tool(tool_name, arguments)
    ├─ Filter arguments (security: only allow expected fields)
    ├─ Call FridayMemorySystem method
    ├─ Async: Generate embeddings (non-blocking)
    ├─ Async: Log tool call
    └─ Format response
    ↓
Return JSON result to caller
```

### 4.2 Tool Allowlisting (Security)

Each tool filters arguments to prevent injection attacks:
```python
if tool_name == "create_memory":
    allowed_args = {"content", "memory_type", "importance_level", "tags", ...}
    filtered_args = {k: v for k, v in arguments.items() if k in allowed_args}
    result = await self.memory_system.create_memory(**filtered_args)
```

---

## PART 5: EMBEDDING SERVICE - DEEP DIVE

### 5.1 How Embeddings Work

**Embedding** = Converting text to numbers that capture meaning

```
Input: "I love coffee in the morning"
  ↓ LM Studio Embedding Model (text-embedding-nomic-embed-text-v1.5)
  ↓
Output: [0.234, 0.567, -0.123, ... 0.901]  ← 768 numbers
```

**Why**: Text with similar meaning → similar vectors → enables semantic search

### 5.2 Provider Fallback Chain

```
Try Primary: LM Studio (192.168.1.50:1234)
    ├─ HTTP POST to /v1/embeddings
    ├─ Fast, local, unlimited
    └─ If timeout/error:
        ↓
    Try Fallback 1: Ollama (localhost:11434)
        ├─ HTTP POST to /api/embeddings
        ├─ Local, free, slower
        └─ If timeout/error:
            ↓
        Fallback 2: Text-based search (SQL LIKE)
            └─ No embedding, system still works (lower accuracy)
```
**System degrades gracefully** - never fully breaks.

### 5.3 Vector Search (Cosine Similarity)

```python
async def search_memories(query):
    # 1. Generate query embedding (768D vector)
    query_embedding = await embedding_service.generate_embedding(query)
    
    # 2. Get all memory embeddings from database
    all_memories = await ai_memory_db.get_all_with_embeddings()
    
    # 3. Calculate cosine similarity for each memory
    #    similarity = dot_product / (magnitude1 * magnitude2)
    #    Result: 0.0-1.0 (1.0 = identical, 0.0 = completely different)
    
    # 4. Sort by similarity (highest first)
    results = sorted(all_memories, key=lambda m: m.similarity_score, reverse=True)
    
    # 5. Return top N results with filters applied
    return results[:limit]
```

**Example**:
```
Query: "What do I like?"
Memory 1: "I enjoy coffee" → similarity: 0.92
Memory 2: "Morning routine" → similarity: 0.88
Memory 3: "Python programming" → similarity: 0.34
```

---

## PART 6: TOOL CATALOG - ALL 30+ TOOLS

### 6.1 Memory & Context Tools

**search_memories()** - Find relevant memories by semantic meaning (query, limit, database_filter, importance range)

**create_memory()** - Store new memories, promote from short-term (content, memory_type, importance_level=5, tags, user_id, model_id)
- For promotion: use importance_level=8-9 with tags=["promoted"]

**update_memory()** - Modify existing memories (memory_id, content, importance_level, tags)

**get_recent_context()** - Get recent conversation history (limit, days_back, session_id)

**store_conversation()** - Store messages from external sources (content, role, session_id, metadata)

### 6.2 Schedule Management Tools

**create_appointment()** - Schedule appointments with recurrence (title, scheduled_datetime, recurrence_pattern, recurrence_count)

**create_reminder()** - Create reminders with recurrence (content, due_datetime, priority_level, recurrence_pattern)

**get_active_reminders()** - Get upcoming reminders (limit, days_ahead)

**complete_reminder()** - Mark reminder as done (reminder_id)

**reschedule_reminder()** - Change reminder date/time (reminder_id, new_due_datetime)

**Other**: get_reminders(), get_completed_reminders(), delete_reminder(), cancel_appointment(), complete_appointment(), get_upcoming_appointments()

### 6.3 System & Reflection Tools

**get_system_health()** - Check system status (database sizes, embedding service status, file monitor status)

**get_tool_usage_summary()** - Analyze tool usage patterns (total calls, success rate, per-tool stats, errors)

**reflect_on_tool_usage()** - AI-generated insights about system behavior (reflections on usage patterns)

**store_ai_reflection()** - Save AI reflections about system behavior (reflection_type, content, insights, recommendations)

**get_ai_insights()** - Retrieve past reflections (limit, insight_type)

### 6.4 External Service Tools

**brave_web_search()** - Web search (query, count, country, language) - Requires BRAVE_API_KEY

**brave_local_search()** - Local business search (query, location, count, radius) - Requires BRAVE_API_KEY

**get_weather_open_meteo()** - Weather forecast (latitude, longitude, override) - No API key required

### 6.5 VS Code Specific Tools

save_development_session(), store_project_insight(), search_project_history(), link_code_context(), get_project_continuity()

### 6.6 SillyTavern Specific Tools

get_character_context(), store_roleplay_memory(), search_roleplay_history()

---

## PART 7: BACKGROUND SYSTEMS & MAINTENANCE

### 7.1 File Monitoring System

**Purpose**: Automatically discover and import conversations from external sources

**Watch Directories**:
- ~/.lmstudio/conversations
- ~/.config/vscode/workspaceStorage/*/chatSessions
- ~/.local/share/ollama/db.sqlite

**Process Loop** (every 0.5 seconds):
1. Check watch directories for file changes
2. Check file stability (wait for file to stop growing)
3. Parse format (LM Studio JSON, VS Code chat JSON, Ollama SQLite, etc.)
4. Extract messages
5. Check for duplicates (content hash)
6. Store in ConversationDatabase
7. Async: Generate embeddings

**Key Features**: Stability checking, duplicate detection, multi-format support, graceful error handling, async embeddings

### 7.2 Database Maintenance

**File**: `database_maintenance.py`

**Maintenance Tasks** (every 24 hours):
1. **VACUUM** - Defragmentation, reclaim deleted space
2. **ANALYZE** - Query optimization, update statistics
3. **Foreign Key Check** - Detect orphaned records
4. **Duplicate Detection** - Find and remove duplicates
5. **Stale Record Cleanup** - Remove old low-importance memories
6. **Database Rotation** - Archive when database > 100MB
7. **Index Rebuilding** - Optimize indexes

**What Gets Cleaned Up**:
- Low-importance memories (1-3) > 90 days old (kept if importance 8-10)
- Old messages < 30 days (kept if linked to memory)
- Failed tool calls > 30 days old (always kept for analysis)
- Duplicate messages (keep first, delete others)
- Orphaned records (foreign key violations)

### 7.3 Retroactive Embedding (Completion Tracking)

**File**: `embeddings_completed.log`

**Purpose**: Prevent re-embedding all 185+ memories every time code reloads

**How It Works**:
```
First time code loads:
  ├─ embeddings_completed.log doesn't exist?
  │   └─ Run FULL retroactive embedding (30-60 minutes)
  │   └─ Loop through all 185 memories, generate embeddings
  │   └─ Write timestamp to log when complete
  └─ Log exists and is recent (< 24 hours)?
      └─ Skip full retroactive, only embed NEW memories
      └─ Much faster!

Next time code loads:
  ├─ Log exists and < 24 hours old?
  │   └─ Skip full retroactive
  └─ Log exists but > 24 hours old?
      └─ Run full retroactive (refresh embeddings)
```

**Benefits**: First run: complete embeddings, reloads: skip expensive re-embedding, auto-refresh every 24 hours, fallback regeneration if log corrupted

---

## PART 8: CURRENT IMPLEMENTATION STATUS

### 8.1 What's Complete & Working ✅

- [x] Adaptive Memory v3 Extraction (inlet/outlet filters)
- [x] OpenWebUI Memory Storage (200-memory limit with FIFO pruning)
- [x] Embedding Generation (LM Studio primary + Ollama fallback)
- [x] Friday Memory System (5 databases fully operational)
- [x] MCP Server Interface (30+ tools exposed via MCP protocol)
- [x] Semantic Search (vector-based similarity search)
- [x] Schedule Management (appointments and reminders with recurrence)
- [x] File Monitoring (auto-import from LM Studio, VS Code, Ollama)
- [x] Database Maintenance (automatic optimization and cleanup)
- [x] Retroactive Embedding (completion log prevents re-embedding waste)
- [x] EmbeddingService.embeddings_endpoint (attribute now exposed - FIX FROM YESTERDAY)
- [x] Docker Networking (using 172.17.0.1 gateway - FIX FROM YESTERDAY)
- [x] Health Check (system health reporting working - FIX FROM YESTERDAY)

### 8.2 What's In Progress 🔄

- [ ] **API Layer for Memory Promotion**: `POST /api/memories/promote` endpoint (PLANNED)
  - Wrapper around create_memory() with importance_level=8-9
  - Integrate with Adaptive Memory pruning (PROMOTE before PRUNE)
  - Status: Design phase, not yet implemented

- [ ] **Embedding Config Sync**: Keep Adaptive Memory valve ↔ embedding_config.json in sync (PLANNED)
  - Detect when embedding_model valve changes
  - Update embedding_config.json automatically
  - Status: Design phase, not yet implemented

### 8.3 What's Planned ⏳

- [ ] REST API endpoints for memory operations
- [ ] Webhook notifications for promoted memories
- [ ] Memory analytics and reporting dashboard
- [ ] Advanced memory retirement strategies
- [ ] Multi-user mode improvements
- [ ] Encryption at rest (optional)
- [ ] Cloud sync (optional)

---

## PART 9: KEY LESSONS & DESIGN PRINCIPLES

### 9.1 Why Importance Levels Matter

**Problem**: Need to keep some memories forever while pruning others

**Solution**: Importance-level survival curve creates natural hierarchy

```
1-5:   Deleted first (FIFO pruning) - auto-extracted memories
6-7:   Deleted less often - important but not critical
8-9:   Survive indefinitely - PROMOTED memories ✓
10:    NEVER deleted - critical/pinned knowledge ✓
```
**Why This Works**: Low-importance dies first when space needed. High-importance lives long. Promoted memories (8-9) become permanent. Aligns with human priority thinking.

### 9.2 Why Non-Blocking Embeddings Matter

**Problem**: Embedding generation takes 100-500ms per item

**Solution**: Async embedding with immediate return

```
Sync (Bad):           Async (Good):
create_memory()       create_memory()
  ↓                     ↓
Generate embedding    Store memory, return immediately ✓
(wait 500ms) ← SLOW     ↓
Return to user        Background: generate embedding later
                      (non-blocking)
                      ← FAST
```
**Trade-off**: Memory is usable without embedding (searchable by text), embedding adds later for full semantic search.

### 9.3 Why Three Memory Systems?

**Problem**: Need both short-term and long-term, but they have different needs

**Solution**: Separate systems with intentional promotion flow

```
OpenWebUI (Short-Term):          Friday System (Long-Term):
- Active, focused, fast          - Permanent, organized, searchable
- 200-memory limit               - Unlimited (technically)
- FIFO pruning                   - Curated, importance-based
- Real-time extraction           - MCP accessible
- Embedded in conversation       - Historical record
                ↓ (Promotion)
            Importance: 5 → 8-9
                ↓
            Survives longer, becomes permanent
```
**Why Separate?**:
- Different operational requirements
- Different update frequencies (real-time vs archival)
- Different access patterns (active vs historical)
- Clear data flow (extraction → promotion → archival)

### 9.4 Why Embedding Fallback Chain?

**Problem**: Embedding service could fail or be unavailable

**Solution**: Smart fallback chain with graceful degradation

```
Primary: LM Studio (fast, local, unlimited)
  ├─ Optimal for production
  ├─ If fails/timeout:
Fallback: Ollama (local, free)
  ├─ Always available
  ├─ Slower than LM Studio
  ├─ If fails/timeout:
Fallback: Text-based search (SQL LIKE)
  ├─ No embedding needed
  ├─ Lower accuracy
  └─ System still works!
```
**Why This Works**: Primary is optimal, fallback is always available (local), system never fully breaks, admin can detect and fix primary issue.

### 9.5 Why File Monitoring?

**Problem**: Conversations exist in many places (LM Studio, VS Code, etc.)

**Solution**: Auto-import via file monitoring

**Benefits**:
1. No manual export needed - just use LM Studio normally, Friday auto-archives
2. Multi-source aggregation - conversations from everywhere in one searchable database
3. Historical record - every conversation backed up, searchable by topic, forever findable

### 9.6 Why MCP Protocol?

**Problem**: Need multiple clients to access Friday memories

**Solution**: Standard MCP protocol

**Benefits**:
- Works with LM Studio, VS Code, CLI
- No custom protocol needed
- Standardized security model
- Easy to add new clients

### 9.7 Core Design Principle: Progressive Elaboration

**Concept**: Information flow from simple to permanent

```
Stage 1: EXTRACT
  └─ OpenWebUI outlet extracts memory (importance 5)
  └─ Short-term storage (max 200)
  └─ FIFO pruning deletes oldest

Stage 2: PROMOTE
  └─ User/system decides "keep this forever"
  └─ API calls promote (importance 8-9)
  └─ Moved to Friday long-term
  └─ Survives indefinitely

Stage 3: ARCHIVE
  └─ Memory lives permanently in ai_memories.db
  └─ Searchable by semantic similarity
  └─ Cross-referenced by many queries
  └─ Part of permanent knowledge

Result: Natural flow from ephemeral → curated → permanent
```

---

## PART 10: WHERE WE ARE & WHAT'S NEXT

### 10.1 Current State (November 18, 2025)

**Infrastructure**: All core systems operational
- 5 databases working
- Embedding service with fallback
- File monitoring importing conversations
- MCP server exposing 30+ tools
- Three recent fixes deployed (embeddings_endpoint, Docker URLs, embedding log)

**Architecture Documentation**: Complete
- Comprehensive reference created (this document)
- All systems documented at structural level
- Data flows explained
- Integration points identified

**Blocking Issue for Next Phase**:
- Need definitive code understanding before building API layer
- Current docs are structural, not line-by-line code patterns
- Affects: Design of REST endpoint, integration with pruning, error handling

### 10.2 Immediate Next Steps

**Phase 1: Finalize Architecture Understanding**
- [ ] Do full deep-read of friday_memory_system.py (7,253 lines)
  - Every line, every function, every error handler
  - Document exact async patterns used
  - Find exact create_memory() signature and behavior

- [ ] Do full deep-read of friday_memory_mcp_server.py (1,865 lines)
  - How tool routing works exactly
  - Error handling patterns
  - Response formatting

- [ ] Result: Definitive code reference (line-by-line)

**Phase 2: Design API Layer**
- [ ] Define `POST /api/memories/promote` endpoint
  - Where does it live? (Friday system? Separate FastAPI app?)
  - Input: memory_id or content
  - Output: new memory_id in Friday system
  - Error handling: what can go wrong?

- [ ] Design integration with pruning
  - Call sequence: promote THEN prune
  - Make sure promoted memories (8-9) don't get deleted
  - Coordinate Adaptive Memory valve config

**Phase 3: Implement API Layer**
- [ ] Create API endpoint code
- [ ] Test with manual memory promotion
- [ ] Verify promoted memories survive FIFO pruning
- [ ] Document endpoint in API docs

**Phase 4: Implement Embedding Config Sync**
- [ ] Detect Adaptive Memory valve changes
- [ ] Update embedding_config.json safely
- [ ] Both systems always in sync
- [ ] Handle errors gracefully

### 10.3 Success Criteria

**API Layer Success**:
- ✅ Memory can be promoted from OpenWebUI → Friday
- ✅ Promoted memory has importance_level 8-9
- ✅ Promoted memory survives FIFO pruning
- ✅ New memory_id returned to caller

**Embedding Sync Success**:
- ✅ Change Adaptive Memory embedding_model valve
- ✅ embedding_config.json updates automatically
- ✅ Both systems use same embedding model/endpoint
- ✅ No race conditions on file update

---

## COMPREHENSIVE REFERENCE SUMMARY

### What You Now Know

✅ Complete System Architecture (three systems, five databases, async patterns)  
✅ Data Flows (extraction → storage → embedding → pruning → promotion → search)  
✅ Integration Points (how systems talk to each other)  
✅ Tool Catalog (30+ tools and what they do)  
✅ Background Systems (file monitoring, maintenance, embedding)  
✅ Design Principles (why each design choice exists)  
✅ Implementation Status (what's done, what's planned)  
✅ Next Steps (clear path to API layer implementation)

### Key Files to Know

| File | Lines | Purpose |
|------|-------|---------|
| `friday_memory_system.py` | 7,253 | Core Friday Memory System (all databases, embedding service, coordinator) |
| `friday_memory_mcp_server.py` | 1,865 | MCP interface (tool registration, routing, execution) |
| `Adaptive_Memory_v3.py` | ~3,500 | OpenWebUI plugin (inlet/outlet filters, pruning, embedding) |
| `embedding_config.json` | Small | Embedding provider configuration |
| `embeddings_completed.log` | Log | Tracks retroactive embedding completion |
| `database_maintenance.py` | ~500 | Database optimization and cleanup |

### Files for Deep-Read (Next Phase)

Priority order:
1. `friday_memory_system.py` - Understand create_memory(), search_memories(), async patterns
2. `friday_memory_mcp_server.py` - Understand _execute_tool(), argument filtering
3. `Adaptive_Memory_v3.py` - Understand FIFO/least_relevant pruning, importance filtering

---

## CLOSING NOTES

The Friday Memory System is a **thoughtfully designed, multi-layered architecture** that solves real problems:

1. **Problem**: Conversations are ephemeral, lost after session ends
   **Solution**: Automatic file monitoring and archival

2. **Problem**: Too much information, can't remember everything
   **Solution**: Importance-level filtering and FIFO pruning

3. **Problem**: Need fast short-term focus but long-term persistence
   **Solution**: Three-system design (short-term + long-term + promotion flow)

4. **Problem**: Embedding service might fail
   **Solution**: Fallback chain with graceful degradation

5. **Problem**: Multiple clients need memory access
   **Solution**: Standard MCP protocol

6. **Problem**: Memory creation is expensive (embedding)
   **Solution**: Non-blocking async design

Each design choice exists for a reason. Each system serves a purpose. Together, they create an AI companion that truly learns and remembers.

---

**This comprehensive reference is your definitive guide to Friday's architecture.**

*For implementation details and exact code patterns, proceed to full deep-read of friday_memory_system.py and friday_memory_mcp_server.py (separate session recommended for clarity).*
