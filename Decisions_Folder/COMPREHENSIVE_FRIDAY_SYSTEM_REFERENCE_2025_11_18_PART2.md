# The Friday Memory System - Comprehensive Architecture Reference (CONTINUED)
**Part 4-6: MCP Server, Embedding Details, Tool Catalog**

---

## PART 4: MCP SERVER LAYER - EXPOSING TOOLS

### 4.1 What is MCP?

**MCP** = Model Context Protocol - a standardized way for AI models to request external tools and data

**Why Friday uses it**:
- Allows LM Studio to call Friday Memory System tools
- Allows VS Code extension to access memories
- Standardized protocol (not custom)
- Secure context passing (user_id, model_id)

### 4.2 MCP Server Architecture

**File**: `friday_memory_mcp_server.py` (1,865 lines)  
**Class**: `FridayMemoryMCPServer`  
**Communication**: stdio (standard input/output)  

#### Core Flow

```
LM Studio (or VS Code)
    ↓
    │ "Call tool: create_memory(content='...')"
    ↓ (via MCP protocol over stdio)
    
MCP Server receives request
    ↓
_detect_client_type()
    └─ Who's calling? (LM Studio, VS Code, CLI?)
    ↓
_get_client_tools()
    └─ Return tool list appropriate for this client
    ├─ All clients: memory, schedule, search, weather
    ├─ VS Code: project insights, code context
    └─ SillyTavern: character/roleplay memories
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
    ↓
LM Studio gets response and continues
```

#### Key Methods

```python
class FridayMemoryMCPServer:
    
    def _detect_client_type(self) -> str:
        """Identifies who's calling"""
        # Returns: "vs_code", "lm_studio", "cli", "unknown"
        # Uses environment variables or connection type
    
    def _get_client_tools(self) -> List[Tool]:
        """Returns tools based on client type"""
        # Customizes tool set per client
    
    async def handle_list_tools(self) -> List[Tool]:
        """Called when client asks: 'What tools do you have?'"""
        # Returns MCP Tool definitions
    
    async def handle_call_tool(name: str, arguments: Dict) -> CallToolResult:
        """Called when client requests a tool"""
        return await self._execute_tool(name, arguments)
    
    async def _execute_tool(tool_name: str, args: Dict) -> CallToolResult:
        """Main dispatcher for all tool calls"""
        # Each tool: filter args → call FridayMemorySystem → return result
        # Also: log to MCPToolCallDatabase for reflection
```

### 4.3 Tool Allowlisting (Security)

Each tool has an allowed arguments filter:

```python
if tool_name == "create_memory":
    allowed_args = {
        "content", "memory_type", "importance_level", 
        "tags", "source_conversation_id", "user_id", "model_id"
    }
    # Only pass these fields to create_memory()
    # Reject any other fields (prevents injection)
    
    filtered_args = {k: v for k, v in arguments.items() 
                     if k in allowed_args}
    
    result = await self.memory_system.create_memory(**filtered_args)
```

This prevents attackers from passing malicious fields.

---

## PART 5: EMBEDDING SERVICE - DEEP DIVE

### 5.1 How Embeddings Work

**Embedding** = Converting text to a vector of numbers that capture meaning

```
Input: "I love coffee in the morning"
  ↓
LM Studio Embedding Model
  └─ text-embedding-nomic-embed-text-v1.5
  ↓
Output: [0.234, 0.567, -0.123, ... 0.901]  ← 768 numbers
```

**Why This Matters**:
- Text with similar meaning → similar vectors
- Can calculate cosine similarity (how close two meanings are)
- Enables semantic search (find by meaning, not keywords)

### 5.2 Provider Fallback Chain

```
Try to embed text:
    ↓
Primary: LM Studio (192.168.1.50:1234)
    │
    ├─ HTTP POST to /v1/embeddings
    ├─ Returns 768D vector
    └─ Cache result
    
    If timeout/error:
        ↓
    Fallback 1: Ollama (localhost:11434)
        │
        ├─ HTTP POST to /api/embeddings
        ├─ Returns 768D vector
        └─ Cache result
        
        If timeout/error:
            ↓
        Fallback 2: Text-based search
            │
            └─ No embedding, use SQL LIKE queries
            
        Success! (Lower accuracy but system works)
```

**Key Concept**: System gracefully degrades. Even if embedding fails, text search still works.

### 5.3 Async Embedding (Non-Blocking)

When you create a memory:

```python
async def create_memory(content, importance_level, ...):
    # Step 1: Insert memory immediately
    memory_id = await self.ai_memory_db.create_memory(
        content, importance_level, ...
    )
    
    # Step 2: Start embedding generation in background
    asyncio.create_task(
        self._add_embedding_to_memory(memory_id, content)
    )
    
    # Step 3: Return immediately (don't wait for embedding)
    return {"status": "success", "memory_id": memory_id}
```

**Why This Design**:
- Embedding can take 100-500ms per item
- User doesn't want to wait
- Memory is usable without embedding (just less searchable)
- Embedding happens when system has time

### 5.4 Embedding Caching

Once generated, embeddings are cached:

1. **In-Memory Cache**: Fast access during session
2. **Database BLOB**: Persistent storage
3. **Smart Invalidation**: When embedding model changes, regenerate

```python
# When searching:
query_embedding = await self.embedding_service.generate_embedding(query)
# First check cache
if query in self.embedding_cache:
    return self.embedding_cache[query]

# If not cached, generate and cache
embedding = await self._generate_lm_studio_embedding(query)
self.embedding_cache[query] = embedding
return embedding
```

### 5.5 Vector Search (Cosine Similarity)

How memory search finds relevant results:

```python
async def search_memories(query):
    # Step 1: Generate query embedding
    query_embedding = await self.embedding_service.generate_embedding(query)
    # Result: [0.1, 0.2, -0.3, ... 0.5]  ← 768 numbers
    
    # Step 2: Get all memory embeddings from database
    all_memories = await self.ai_memory_db.get_all_with_embeddings()
    
    # Step 3: Calculate similarity for each memory
    for memory in all_memories:
        memory_embedding = memory.embedding
        # Cosine similarity = dot product / (magnitude1 * magnitude2)
        similarity = np.dot(query_embedding, memory_embedding) / (
            np.linalg.norm(query_embedding) * np.linalg.norm(memory_embedding)
        )
        # Result: similarity score 0.0-1.0
        # 1.0 = identical meaning, 0.0 = completely different
        memory.similarity_score = similarity
    
    # Step 4: Sort by similarity (highest first)
    results = sorted(all_memories, key=lambda m: m.similarity_score, reverse=True)
    
    # Step 5: Apply filters and return top N
    return results[:limit]
```

**Example**:
```
Query: "What do I like?"
Query embedding: [0.234, 0.567, ...]

Memory 1: "I enjoy coffee" → embedding [0.225, 0.571, ...] → similarity: 0.92
Memory 2: "Python programming" → embedding [0.100, 0.200, ...] → similarity: 0.34
Memory 3: "Morning routine" → embedding [0.240, 0.560, ...] → similarity: 0.88

Results (sorted):
  1. "I enjoy coffee" (0.92)
  2. "Morning routine" (0.88)
  3. "Python programming" (0.34)
```

---

## PART 6: TOOL CATALOG - ALL 30+ TOOLS

### 6.1 Memory & Context Tools

#### search_memories()
```python
search_memories(
    query: str,                    # What to search for
    limit: int = 10,              # How many results
    database_filter: str = "all", # Which DB ("ai_memories", "conversations", "schedule", "all")
    min_importance: int = 1,      # Minimum importance level (1-10)
    max_importance: int = 10,     # Maximum importance level
    memory_type: str = None,      # Filter by type ("preference", "skill", "fact", etc.)
    user_id: str = None,          # For multi-user systems
    model_id: str = None          # For multi-model systems
) → {
    "status": "success",
    "results": [
        {
            "memory_id": "uuid",
            "content": "...",
            "similarity": 0.92,
            "importance_level": 8,
            "tags": ["promoted", "important"]
        },
        ...
    ]
}
```

**Use Cases**: Find relevant memories by semantic meaning

---

#### create_memory()
```python
create_memory(
    content: str,                    # The memory text
    memory_type: str = "general",   # Classification
    importance_level: int = 5,      # 1-10 (8-9 for promoted!)
    tags: List[str] = [],           # Keywords
    source_conversation_id: str = None,  # Link to conversation
    user_id: str = None,
    model_id: str = None
) → {
    "status": "success",
    "memory_id": "newly-created-uuid",
    "embedded": False               # Embedding in progress
}
```

**Use Cases**: Store new memories, promote from short-term

---

#### update_memory()
```python
update_memory(
    memory_id: str,                 # Which memory
    content: str = None,            # New content (optional)
    importance_level: int = None,   # New importance (optional)
    tags: List[str] = None          # New tags (optional)
) → {
    "status": "success"
}
```

**Use Cases**: Modify existing memories

---

#### get_recent_context()
```python
get_recent_context(
    limit: int = 10,         # How many messages
    days_back: int = 7,      # From past N days
    session_id: str = None   # Specific session (optional)
) → {
    "status": "success",
    "messages": [
        {
            "message_id": "uuid",
            "role": "user" | "assistant",
            "content": "...",
            "timestamp": "2025-11-18T10:30:00"
        },
        ...
    ]
}
```

**Use Cases**: Get recent conversation history

---

#### store_conversation()
```python
store_conversation(
    content: str,                   # Message text
    role: str,                      # "user", "assistant", "system"
    session_id: str = None,         # Group into session
    metadata: Dict = {}             # Additional context
) → {
    "status": "success",
    "message_id": "newly-stored-uuid"
}
```

**Use Cases**: Store messages from external sources

---

### 6.2 Schedule Management Tools

#### create_appointment()
```python
create_appointment(
    title: str,                             # Event name
    scheduled_datetime: str,                # ISO format
    description: str = None,
    location: str = None,
    recurrence_pattern: str = None,        # "daily", "weekly", "monthly"
    recurrence_count: int = 1,             # How many times
    recurrence_end_date: str = None,
    user_id: str = None
) → {
    "status": "success",
    "appointment_ids": ["uuid1", "uuid2", ...]  # Multiple if recurring
}
```

**Use Cases**: Schedule appointments, recurring events

---

#### create_reminder()
```python
create_reminder(
    content: str,                        # What to remind about
    due_datetime: str,                   # When (ISO format)
    priority_level: int = 5,             # 1-10
    recurrence_pattern: str = None,      # "daily", "weekly", etc.
    recurrence_count: int = 1,
    recurrence_end_date: str = None,
    user_id: str = None
) → {
    "status": "success",
    "reminder_ids": ["uuid1", "uuid2", ...]
}
```

**Use Cases**: Set reminders with recurrence

---

#### get_active_reminders()
```python
get_active_reminders(
    limit: int = 10,
    days_ahead: int = 30,   # Show reminders for next N days
    priority_level: int = None  # Filter by priority (optional)
) → {
    "status": "success",
    "reminders": [
        {
            "reminder_id": "uuid",
            "content": "...",
            "due_datetime": "2025-11-18T15:00:00",
            "priority_level": 8,
            "completed": False
        },
        ...
    ]
}
```

**Use Cases**: Get upcoming reminders

---

#### complete_reminder()
```python
complete_reminder(reminder_id: str) → {
    "status": "success"
}
```

**Use Cases**: Mark reminder as done

---

#### reschedule_reminder()
```python
reschedule_reminder(
    reminder_id: str,
    new_due_datetime: str  # ISO format
) → {
    "status": "success"
}
```

**Use Cases**: Change reminder date/time

---

#### Other Schedule Tools
- `get_reminders()` - Get all reminders (include completed)
- `get_completed_reminders()` - Recently completed
- `delete_reminder()` - Permanently delete
- `cancel_appointment()` - Cancel appointment
- `complete_appointment()` - Mark appointment done
- `get_upcoming_appointments()` - Future appointments

---

### 6.3 System & Reflection Tools

#### get_system_health()
```
Returns:
{
    "status": "healthy",
    "databases": {
        "ai_memories.db": {"size_mb": 15.2, "count": 185, "indexes_ok": true},
        "conversations.db": {"size_mb": 42.5, "count": 3200},
        ...
    },
    "embedding_service": {
        "primary_provider": "lmstudio",
        "primary_endpoint": "http://192.168.1.50:1234/v1/embeddings",
        "status": "available",
        "fallback_provider": "ollama",
        "fallback_status": "available"
    },
    "file_monitor": {
        "watching_directories": 5,
        "last_check": "2025-11-18T10:25:00",
        "files_monitored": 23
    }
}
```

**Use Cases**: Check system status

---

#### get_tool_usage_summary()
```
Returns:
{
    "total_calls": 1247,
    "success_rate": "94.3%",
    "tools": {
        "search_memories": {"calls": 342, "avg_time_ms": 45},
        "create_memory": {"calls": 156, "avg_time_ms": 12},
        ...
    },
    "errors": [
        {"tool": "search_memories", "error": "timeout", "count": 42}
    ]
}
```

**Use Cases**: Analyze tool usage patterns

---

#### reflect_on_tool_usage()
```
AI-generated insights:
{
    "reflection_type": "tool_usage_analysis",
    "content": "You use search_memories most frequently (27% of calls)...",
    "insights": [
        "search_memories is primary tool",
        "Memory creation is 2nd most common",
        "Error rate is low (5.7%)"
    ],
    "recommendations": [
        "Consider auto-promoting frequently searched memories",
        "Error rate acceptable"
    ]
}
```

**Use Cases**: AI self-reflection on behavior

---

#### store_ai_reflection()
```python
store_ai_reflection(
    reflection_type: str,    # "tool_usage_analysis", "memory", "general"
    content: str,           # Detailed reflection
    insights: List[str],    # Bullet points
    recommendations: List[str],
    confidence_level: float = 0.7,  # 0.0-1.0
    source_period_days: int = 7
) → {
    "status": "success",
    "reflection_id": "uuid"
}
```

**Use Cases**: Save AI reflections about system behavior

---

#### get_ai_insights()
```
Returns:
[
    {
        "reflection_id": "uuid",
        "reflection_type": "tool_usage_analysis",
        "content": "...",
        "insights": ["...", "..."],
        "confidence_level": 0.85,
        "created_at": "2025-11-18T08:00:00"
    },
    ...
]
```

**Use Cases**: Retrieve past reflections

---

### 6.4 External Service Tools

#### brave_web_search()
```python
brave_web_search(
    query: str,
    count: int = 10,     # Results
    country: str = "US",
    language: str = "en"
) → {
    "results": [
        {
            "title": "...",
            "url": "...",
            "description": "..."
        },
        ...
    ]
}
```

**Requires**: BRAVE_API_KEY environment variable

---

#### brave_local_search()
```python
brave_local_search(
    query: str,
    location: str = "Motley, MN",
    count: int = 10,
    radius: int = 5000  # meters
) → {
    "results": [
        {
            "name": "...",
            "address": "...",
            "phone": "...",
            "rating": 4.5
        },
        ...
    ]
}
```

**Requires**: BRAVE_API_KEY environment variable

---

#### get_weather_open_meteo()
```python
get_weather_open_meteo(
    latitude: float = None,        # Defaults to Motley, MN
    longitude: float = None,
    override: bool = False,        # Use custom coordinates
    return_changes_only: bool = False  # Only today's changes
) → {
    "location": "Motley, MN",
    "current": {
        "temperature": 34.5,
        "condition": "Partly Cloudy",
        "humidity": 65
    },
    "forecast": [
        {
            "date": "2025-11-18",
            "high": 38,
            "low": 28,
            "condition": "Cloudy"
        },
        ...
    ]
}
```

**Requires**: No API key (uses open-meteo.com)

---

### 6.5 VS Code Specific Tools

#### save_development_session()
Save current VS Code session with context

#### store_project_insight()
Record coding insight/pattern

#### search_project_history()
Search through development sessions

#### link_code_context()
Link chat messages to code

#### get_project_continuity()
Get development context for continuation

---

### 6.6 SillyTavern Specific Tools

#### get_character_context()
Get character-specific memories

#### store_roleplay_memory()
Save roleplay events/interactions

#### search_roleplay_history()
Search through roleplay history

---

## SUMMARY OF PARTS 4-6

✅ **MCP Server**: How Friday exposes tools, client detection, tool allowlisting  
✅ **Embedding Service**: Vector generation, fallback chain, caching, semantic search  
✅ **Tool Catalog**: 30+ tools across memory, schedule, system, external services, and specialized clients  

---

*End of Chunk 4-6. Next: Background Systems, Database Maintenance, Implementation Status, Troubleshooting*
