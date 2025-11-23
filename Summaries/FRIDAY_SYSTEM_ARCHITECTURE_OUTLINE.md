# Friday Memory System & MCP Server - Complete Architecture Outline

## Overview
Friday is a persistent AI memory system that serves as the backend for your AI companion. It combines multiple databases, an MCP (Model Context Protocol) server, and intelligent file monitoring to create a comprehensive memory system for AI assistants. The system is designed to work with LM Studio, OpenWebUI, and other compatible platforms.

---

## Part 1: Core Architecture

### 1.1 System Components

The system consists of three main layers:

```
┌─────────────────────────────────────────────────────────┐
│         MCP Server Layer (MCP Interface)                │
│   - Exposes tools to AI clients (LM Studio, OpenWebUI)  │
│   - Handles authentication and client context           │
│   - Manages tool calls and responses                    │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│      Friday Memory System (Business Logic)              │
│   - Semantic search with embeddings                     │
│   - Memory management (create, read, update)            │
│   - Schedule management (appointments, reminders)       │
│   - File monitoring for conversation imports            │
│   - AI self-reflection and insights                    │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│      Database Layer (SQLite Databases)                  │
│   - Conversations DB (conversations.db)                 │
│   - AI Memories DB (ai_memories.db)                     │
│   - Schedule DB (schedule.db)                           │
│   - VS Code Projects DB (vscode_project.db)             │
│   - MCP Tool Calls DB (mcp_tool_calls.db)               │
└─────────────────────────────────────────────────────────┘
```

---

## Part 2: Database Schema

### 2.1 ConversationDatabase (`conversations.db`)

**Purpose**: Stores all conversation messages, sessions, and chat history

**Tables**:

1. **sessions**
   - session_id (PRIMARY KEY, UUID)
   - start_timestamp (ISO format, local timezone)
   - end_timestamp (ISO format, nullable)
   - context (string, session metadata)
   - embedding (binary, semantic embedding)
   - created_at (timestamp)
   - **Purpose**: Groups related conversations into sessions

2. **conversations**
   - conversation_id (PRIMARY KEY, UUID)
   - session_id (FOREIGN KEY)
   - start_timestamp (ISO format)
   - end_timestamp (ISO format, nullable)
   - topic_summary (string, auto-generated)
   - embedding (binary)
   - created_at (timestamp)
   - **Purpose**: Groups messages into logical conversations

3. **messages**
   - message_id (PRIMARY KEY, UUID)
   - conversation_id (FOREIGN KEY)
   - timestamp (ISO format, local timezone)
   - role ('user', 'assistant', 'system')
   - content (TEXT, the actual message)
   - source_type (string: 'lmstudio', 'openwebui', 'vscode', etc.)
   - source_id (optional ID from source system)
   - source_url (optional)
   - source_metadata (JSON, additional context)
   - sync_status (tracking for multi-system sync)
   - last_sync (timestamp)
   - metadata (JSON, flexible metadata)
   - embedding (binary, semantic embedding)
   - created_at (timestamp)
   - **Purpose**: Individual messages with full tracking

4. **source_tracking**
   - source_id (PRIMARY KEY)
   - source_type ('lmstudio', 'openwebui', 'vscode', 'sillytavern', etc.)
   - source_name (human-readable name)
   - source_path (file path or URL)
   - last_check (when we last checked this source)
   - last_sync (last successful import)
   - status ('active', 'inactive', 'error')
   - error_count (for retry logic)
   - created_at (timestamp)
   - **Purpose**: Tracks which applications we're monitoring

5. **conversation_relationships**
   - relationship_id (PRIMARY KEY)
   - source_conversation_id (FOREIGN KEY)
   - related_conversation_id (FOREIGN KEY)
   - relationship_type ('continuation', 'related', 'alternative')
   - metadata (JSON)
   - created_at (timestamp)
   - **Purpose**: Links conversations across different sources

6. **memory_conversation_links**
   - link_id (PRIMARY KEY)
   - memory_id (UUID, references curated_memories)
   - conversation_id (FOREIGN KEY)
   - link_type ('direct', 'related', 'enhanced')
   - link_strength (float 0.0-1.0, confidence)
   - source_system (how the link was created)
   - created_at (timestamp)
   - updated_at (timestamp)
   - metadata (JSON)
   - **Purpose**: Bridges between conversations and AI memories

7. **memory_processing_queue** & **memory_processing_log**
   - Track which conversations need memory extraction
   - Audit trail of processing attempts
   - Handles memory enhancement pipeline

### 2.2 AIMemoryDatabase (`ai_memories.db`)

**Purpose**: Stores curated AI memories (insights, preferences, learned information)

**Tables**:

1. **curated_memories**
   - memory_id (PRIMARY KEY, UUID)
   - timestamp_created (ISO format)
   - timestamp_updated (ISO format)
   - source_conversation_id (optional reference)
   - source_message_ids (JSON array)
   - memory_type ('preference', 'skill', 'fact', 'relationship', 'project', 'general')
   - content (TEXT, the actual memory)
   - importance_level (1-10 integer)
   - tags (JSON array, for categorization)
   - embedding (binary, semantic embedding)
   - user_id (for user separation in multi-user scenarios)
   - model_id (for model-specific memories)
   - created_at (timestamp)
   - **Purpose**: Persistent learned information about users and topics

### 2.3 ScheduleDatabase (`schedule.db`)

**Purpose**: Manages appointments and reminders

**Tables**:

1. **appointments**
   - appointment_id (PRIMARY KEY, UUID)
   - timestamp_created (ISO format)
   - scheduled_datetime (ISO format, when appointment occurs)
   - title (string)
   - description (text)
   - location (string)
   - status ('scheduled', 'cancelled', 'completed')
   - cancelled_at (timestamp, if cancelled)
   - completed_at (timestamp, if completed)
   - source_conversation_id (optional)
   - embedding (binary)
   - created_at (timestamp)
   - user_id, model_id (for separation)
   - **Purpose**: One-time or recurring appointments

2. **reminders**
   - reminder_id (PRIMARY KEY, UUID)
   - timestamp_created (ISO format)
   - due_datetime (ISO format, when reminder triggers)
   - content (string, what to remind about)
   - priority_level (1-10 integer)
   - completed (0/1 boolean)
   - completed_at (timestamp, if completed)
   - source_conversation_id (optional)
   - embedding (binary)
   - created_at (timestamp)
   - user_id, model_id (for separation)
   - **Purpose**: Reminders with optional recurrence

### 2.4 VSCodeProjectDatabase (`vscode_project.db`)

**Purpose**: Tracks VS Code development sessions and code context

**Tables**:

1. **project_sessions**
   - session_id (PRIMARY KEY)
   - start_timestamp, end_timestamp (ISO format)
   - workspace_path (string)
   - active_files (JSON array of file paths)
   - git_branch (current git branch)
   - git_commit_hash (current commit)
   - session_summary (text)
   - embedding (binary)
   - created_at (timestamp)

2. **development_conversations**
   - conversation_id (PRIMARY KEY)
   - session_id (FOREIGN KEY)
   - timestamp (ISO format)
   - chat_context_id (VS Code chat ID)
   - conversation_content (text)
   - decisions_made (text summary)
   - code_changes (JSON of file changes)
   - embedding (binary)
   - created_at (timestamp)

3. **project_insights**
   - insight_id (PRIMARY KEY)
   - timestamp_created, timestamp_updated
   - insight_type ('architecture', 'bug_fix', 'refactor', 'feature')
   - content (text)
   - related_files (JSON array)
   - source_conversation_id (optional)
   - importance_level (1-10)
   - embedding (binary)

4. **code_context**
   - context_id (PRIMARY KEY)
   - timestamp (ISO format)
   - file_path (string)
   - function_name (string)
   - description (text)
   - purpose (text)
   - related_insights (JSON)
   - embedding (binary)

### 2.5 MCPToolCallDatabase (`mcp_tool_calls.db`)

**Purpose**: Logs MCP tool calls for AI self-reflection

**Tables**:

1. **tool_calls**
   - call_id (PRIMARY KEY)
   - timestamp (ISO format)
   - client_id (who called the tool)
   - tool_name (which tool was called)
   - parameters (JSON of arguments)
   - execution_time_ms (float)
   - status ('success', 'error', 'timeout')
   - result (JSON or text)
   - error_message (if error)
   - embedding (binary)
   - created_at (timestamp)

2. **usage_patterns**
   - Stores identified patterns in tool usage
   - Used for AI self-reflection

3. **ai_reflections**
   - reflection_id (PRIMARY KEY)
   - timestamp_created (ISO format)
   - reflection_type ('tool_usage_analysis', 'memory', 'general')
   - content (detailed reflection text)
   - insights (JSON array)
   - recommendations (JSON array)
   - confidence_level (0.0-1.0)
   - source_period_days (how many days analyzed)
   - embedding (binary)

---

## Part 3: File Monitoring System

### 3.1 Conversation File Monitor

**Location**: `ConversationFileMonitor` class in `friday_memory_system.py`

**Purpose**: Automatically detects and imports conversations from various chat applications

**Key Features**:

1. **Multi-Source Support**:
   - LM Studio conversations
   - VS Code Copilot Chat sessions
   - ChatGPT exports
   - Claude desktop
   - Character.ai
   - Local.ai
   - Ollama SQLite databases
   - text-generation-webui

2. **File Stability Checking**:
   - Prevents importing incomplete/partially-written files
   - Waits for file size to stabilize before processing
   - Default threshold: 3 consecutive checks with 0.5s interval

3. **Duplicate Prevention**:
   - Content hash-based deduplication
   - Timestamp + content matching
   - Per-source message tracking
   - Prevents duplicate imports across multiple sources

4. **Format Parsers**:
   - **LM Studio**: Complex `versions` structure with current selection
   - **VS Code**: JSON chat sessions with request/response pairs
   - **ChatGPT**: `mapping` structure with node graph
   - **Claude**: Simple `messages` array format
   - **JSON/JSONL**: Flexible parsers for generic formats
   - **Markdown**: Pattern-based extraction

### 3.2 Watch Directories

**Default locations by platform**:

```
Windows:
  - ~/.lmstudio/conversations
  - %APPDATA%/LM Studio/conversations
  - OpenWebUI conversation exports
  - VS Code workspaceStorage/*/chatSessions

Linux:
  - ~/.lmstudio/conversations
  - ~/.config/lm-studio/conversations
  - ~/.local/share/ollama/db.sqlite
  - ~/.config/vscode/workspaceStorage/*/chatSessions

macOS:
  - ~/Library/Application Support/LM Studio/conversations
  - ~/.config/lm-studio/conversations
  - ~/Library/Application Support/Ollama/db.sqlite
```

---

## Part 4: Embedding & Search System

### 4.1 Embedding Service

**Location**: `EmbeddingService` class in `friday_memory_system.py`

**Purpose**: Generate semantic embeddings for all content

**Features**:

1. **Primary & Fallback Configuration**:
   ```
   Primary: LM Studio (local, unlimited usage)
   Fallback 1: OpenAI (if LM Studio unavailable)
   Fallback 2: Ollama (local, free)
   Fallback 3: Text-based search (no embedding)
   ```

2. **Smart Caching**:
   - Caches embeddings in database
   - Skip re-embedding existing content
   - Preserves historical embeddings

3. **Configuration** (`embedding_config.json`):
   ```json
   {
     "primary": {
       "provider": "lm-studio",
       "model": "embedding-model-name",
       "api_endpoint": "http://localhost:1234",
       "dimension": 384
     },
     "fallback": {
       "provider": "openai",
       "model": "text-embedding-3-small",
       "api_key": "${OPENAI_API_KEY}"
     }
   }
   ```

### 4.2 Semantic Search

**Location**: `search_memories()` in `FridayMemorySystem`

**Process**:

1. Generate embedding for search query
2. Calculate cosine similarity with all stored embeddings
3. Apply importance-level boost (±10%)
4. Apply database filters (user_id, model_id, memory_type, importance)
5. Return top N results sorted by similarity

**Search Databases**:
- Conversations (messages)
- AI Memories (curated_memories)
- Schedule (appointments, reminders)
- All combined with deduplication

**Fallback**: Text-based search using SQL LIKE when embeddings unavailable

---

## Part 5: MCP Server Implementation

### 5.1 Server Structure

**File**: `friday_memory_mcp_server.py`

**Class**: `FridayMemoryMCPServer`

**Core Methods**:

1. **`_register_handlers()`**
   - Registers two main handlers:
   - `handle_list_tools()`: Returns available tools based on client type
   - `handle_call_tool()`: Executes tool and returns result

2. **`_detect_client_type()`**
   - Identifies client connecting to server
   - Currently supports: "unknown" (placeholder for expansion)
   - Future: LM Studio, VS Code, SillyTavern detection

3. **`_get_client_tools()`**
   - Returns tools based on client type:
   - Common tools: memory search, reminders, appointments, weather, search
   - VS Code tools: project tracking, code context
   - SillyTavern tools: character context, roleplay memories

4. **`_execute_tool()`**
   - Main dispatcher for all tool calls
   - Logs execution for AI self-reflection
   - Handles tool-specific argument filtering
   - Returns formatted responses

### 5.2 Available Tools

**Common Tools** (all clients):

```
Memory Operations:
  - search_memories: Semantic search across all databases
  - create_memory: Create curated memory entry
  - update_memory: Update existing memory
  - get_recent_context: Get recent conversation history
  - store_conversation: Save conversation message

Schedule Management:
  - create_appointment: Create appointment (with recurrence support)
  - create_reminder: Create reminder (with recurrence support)
  - get_appointments: Get upcoming appointments
  - get_reminders: Get active reminders
  - complete_reminder: Mark reminder as done
  - reschedule_reminder: Change reminder date/time
  - cancel_appointment: Cancel appointment
  - delete_reminder: Delete reminder

System Tools:
  - get_system_health: Database stats and health
  - get_tool_usage_summary: Tool call statistics
  - reflect_on_tool_usage: AI analysis of usage patterns
  - get_ai_insights: Get stored reflections
  - store_ai_reflection: Save reflection/insight
  - get_current_time: Get server time

External Services:
  - brave_web_search: Web search (requires API key)
  - brave_local_search: Local business search
  - get_weather_open_meteo: Weather forecast (no API key)
```

**VS Code Specific Tools**:

```
  - save_development_session: Save VS Code session
  - store_project_insight: Record coding insight
  - search_project_history: Search development history
  - link_code_context: Link chat to code
  - get_project_continuity: Get development context
```

**SillyTavern Specific Tools**:

```
  - get_character_context: Get character memory
  - store_roleplay_memory: Save roleplay event
  - search_roleplay_history: Search roleplay interactions
```

### 5.3 Tool Call Flow

```
Client sends tool request
         ↓
MCP Server receives call
         ↓
_execute_tool() dispatcher
         ↓
Tool-specific handler
         ↓
Filter arguments (security)
         ↓
Call FridayMemorySystem method
         ↓
Generate embedding (async)
         ↓
Store in appropriate database
         ↓
Log tool call (async)
         ↓
Format response
         ↓
Return to client
```

---

## Part 6: Background Maintenance

### 6.1 Database Maintenance

**Location**: `database_maintenance.py`

**Tasks**:

1. **Optimization**:
   - VACUUM (defragment)
   - ANALYZE (update statistics)
   - PRAGMA optimization_pragma

2. **Cleanup**:
   - Remove duplicate entries
   - Delete orphaned records
   - Clean invalid entries

3. **Schema Evolution**:
   - Add missing columns
   - Migrate old schemas
   - Update table structures

4. **Rotation** (for large databases):
   - When database grows > threshold (default 100MB)
   - Create `database_YYYY-MM.db` archive
   - Start fresh main database
   - Maintains searchability across sharded DBs

### 6.2 Background Tasks

**Initialization Flow**:

```
MCP Server starts
         ↓ (wait 3 minutes)
Start file monitoring
         ↓
Start automatic maintenance loop
         ↓
Run maintenance every 3 hours
         ↓
Monitor files for changes
         ↓
Import new conversations automatically
         ↓
Generate embeddings for new content
         ↓
Extract AI memories from conversations
```

**File Monitoring Loop**:

```
Watch configured directories
         ↓ (on file change detected)
Check file stability
         ↓ (once file stops growing)
Read file content
         ↓
Detect format (LM Studio, VS Code, etc.)
         ↓
Parse messages
         ↓
Check for duplicates
         ↓
Store new messages
         ↓
Queue for embedding generation
```

---

## Part 7: AI Self-Reflection System

### 7.1 Purpose

Enables the AI to analyze its own tool usage patterns and learn from them

### 7.2 Reflected Information

```
Tool Usage Analysis:
  - Most used tools (frequency analysis)
  - Tool success rates
  - Error patterns
  - Execution time metrics
  - Client activity breakdown

Generated Insights:
  - Reliability patterns
  - Performance bottlenecks
  - Tool effectiveness
  - Usage trends

Recommendations:
  - Tools to optimize
  - Potential improvements
  - Configuration suggestions
```

### 7.3 Methods

- **`reflect_on_tool_usage()`**: Analyzes usage patterns
- **`get_ai_insights()`**: Retrieves stored reflections
- **`store_ai_reflection()`**: Saves analysis results

---

## Part 8: Data Flow Examples

### 8.1 Storing a Conversation

```
User sends message in LM Studio
         ↓
File monitor detects update to .json file
         ↓
Checks file stability (waits if still writing)
         ↓
Reads and parses LM Studio format
         ↓
Extracts user message
         ↓
Checks duplicate hash (content-based)
         ↓
Calls store_message()
         ↓
Creates message_id, conversation_id, session_id if needed
         ↓
Stores in messages table with timestamp
         ↓
Async: generates embedding
         ↓
Async: links to any relevant memories
         ↓
Returns message_id to file monitor
```

### 8.2 Semantic Search

```
Client calls search_memories("tell me about preferences")
         ↓
Generate embedding for query
         ↓
Search conversations database
   - Query embedding vs message embeddings
   - Calculate cosine similarity
   - Keep only > 0.3 similarity
         ↓
Search AI memories database
   - Apply user_id filter if provided
   - Apply memory_type filter if provided
   - Apply importance_level range if provided
         ↓
Search schedule database
   - Query appointments and reminders
   - Calculate similarity
         ↓
Merge results from all databases
         ↓
Boost importance-level results (±10%)
         ↓
Sort by similarity score descending
         ↓
Return top N results
```

### 8.3 Creating a Reminder with Recurrence

```
Client calls create_reminder(
  content="Take breaks",
  due_datetime="2025-08-03T14:00:00Z",
  recurrence_pattern="daily",
  recurrence_count=7
)
         ↓
Parse start datetime
         ↓
Loop 7 times:
  - Generate reminder_id
  - Calculate next occurrence (daily delta)
  - Insert reminder row
  - Increment datetime
         ↓
Return [reminder_id_1, reminder_id_2, ..., reminder_id_7]
         ↓
Async: Generate embeddings for each
         ↓
Async: Store in database
```

---

## Part 9: API Endpoint Examples

### 9.1 MCP Server Communication

**Note**: MCP uses stdio (standard input/output) for communication, not HTTP.

**Example Tool Call**:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search_memories",
    "arguments": {
      "query": "what are my preferences",
      "limit": 5,
      "database_filter": "all",
      "min_importance": 5
    }
  },
  "id": 1
}
```

**Expected Response**:

```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "success",
    "query": "what are my preferences",
    "results": [
      {
        "type": "ai_memory",
        "similarity_score": 0.87,
        "data": {
          "memory_id": "UUID...",
          "content": "User prefers detailed technical explanations",
          "importance_level": 8,
          "tags": ["preference", "technical"],
          "timestamp_created": "2025-08-01T10:30:00+00:00"
        }
      }
    ],
    "count": 1
  },
  "id": 1
}
```

### 9.2 Weather Endpoint

```json
{
  "name": "get_weather_open_meteo",
  "arguments": {
    "override": false,
    "update_today": true,
    "return_changes_only": false,
    "force_refresh": false
  }
}
```

Returns: Current weather for Motley, MN with hourly and daily forecast

---

## Part 10: User & Model Separation

### 10.1 Multi-User/Multi-Model Support

All memory operations support:

```
user_id: Optional string to separate user memories
model_id: Optional string to separate model-specific memories
```

**Example**:

```
create_memory(
  content="...",
  user_id="nate@friday.local",
  model_id="claude-3-sonnet"
)
```

**Search Filtering**:

```
search_memories(
  query="...",
  user_id="nate@friday.local",
  model_id="claude-3-sonnet"
)
```

Returns only memories for that specific user+model combination

---

## Part 11: Error Handling & Resilience

### 11.1 Database Resilience

- **Connection pooling**: Uses sqlite3 row factories for dict-like access
- **Foreign key constraints**: Enabled to maintain referential integrity
- **PRAGMA settings**: Optimized for reliability
- **Schema migration**: Automatic schema updates on startup

### 11.2 File Monitoring Resilience

- **File stability checking**: Prevents reading incomplete files
- **Duplicate detection**: Multiple methods (hash, timestamp, content)
- **Format error recovery**: Can recover from partially corrupted JSON
- **Graceful degradation**: Falls back to text search if embeddings fail

### 11.3 Tool Call Resilience

- **Error logging**: All errors captured for AI reflection
- **Timeout handling**: Tools return error if they take too long
- **Parameter validation**: Arguments filtered before tool execution
- **Logging**: Comprehensive logging for debugging

---

## Part 12: Configuration

### 12.1 Key Configuration Files

**`embedding_config.json`**:
```json
{
  "primary": {
    "provider": "lm-studio",
    "model": "model-name",
    "api_endpoint": "http://localhost:1234"
  },
  "fallback": { ... }
}
```

**Environment Variables**:

```
BRAVE_API_KEY: For web/local search
OPENAI_API_KEY: Fallback embedding provider
FRIDAY_DEFAULT_MODEL: Default model_id
weather_directory: Where to cache weather data
```

### 12.2 Watch Directories

**Custom directories** can be added via:

```python
memory_system.file_monitor.add_watch_directory("/custom/path")
```

**Default directories** are automatically discovered based on installed applications

---

## Part 13: Performance Characteristics

### 13.1 Response Times

- **Memory search**: 50-200ms (depends on database size)
- **Create memory**: 5-20ms (+ async embedding generation)
- **Store message**: 1-5ms (+ async embedding generation)
- **Get reminders**: 10-50ms

### 13.2 Storage

- **Per message**: ~200-2000 bytes + 1536-byte embedding (if using vector DB)
- **Per memory**: ~500-5000 bytes + embedding
- **Database overhead**: ~10-20% depending on usage patterns

### 13.3 Scalability

- **Sharded databases**: Automatic archival when database grows > 100MB
- **Parallel queries**: Multiple memory databases queried in parallel
- **Index optimization**: Automatic ANALYZE updates statistics

---

## Part 14: Security Considerations

### 14.1 Data Isolation

- **User separation**: user_id field prevents cross-user memory leakage
- **Model separation**: model_id prevents sharing between AI models
- **Tool filtering**: Client type determines available tools

### 14.2 Authentication

- **MCP Protocol**: Built-in authentication at protocol level
- **API Keys**: Stored in environment or files with restricted access
- **Tool call logging**: All access tracked for audit trail

### 14.3 Data Privacy

- **Local storage**: All data stored locally by default
- **No cloud sync**: Unless explicitly configured
- **Encryption**: Not implemented by default (can be added)

---

## Part 15: Integration Points

### 15.1 LM Studio Integration

- Watches `~/.lmstudio/conversations` for new chats
- Imports conversation JSON format
- Can use LM Studio as embedding provider
- Tool calls via MCP protocol

### 15.2 VS Code Integration

- Monitors Copilot Chat sessions in workspaceStorage
- Tracks development sessions
- Stores code context and insights
- Integrates with chat interface

### 15.3 Ollama Integration

- Monitors Ollama SQLite database directly
- Imports conversations from database
- Can use Ollama for embeddings (fallback)
- Supports multiple local models

### 15.4 OpenWebUI Integration

- Can import conversation history
- Supports model-specific memory separation
- Integrates with custom tools

---

## Part 16: Extension Points

### 16.1 Adding New Chat Sources

1. Add format parser method: `_parse_new_format()`
2. Add importer method: `_import_new_app_conversation()`
3. Add to watch directories
4. Add to file detection logic

### 16.2 Adding New Tools

1. Create async method in `FridayMemorySystem`
2. Add `Tool` definition in `_get_client_tools()`
3. Add handler in `_execute_tool()`
4. Add parameter validation

### 16.3 Custom Embeddings Provider

1. Subclass `EmbeddingService`
2. Implement `generate_embedding()` method
3. Update `embedding_config.json`
4. Test with `search_memories()`

---

## Part 17: Troubleshooting Guide

### 17.1 Common Issues

**Embeddings not generating**:
- Check `embedding_config.json` - verify LM Studio endpoint
- Check `get_system_health()` for embedding service status
- Review logs in `/media/nate/Friday/Friday/Logs/`

**File monitoring not importing**:
- Check watch directories exist
- Verify file format is recognized
- Check file isn't being constantly written to
- Review `db_debug_log.txt` for details

**Duplicate messages**:
- Check `content_hash` in message metadata
- Verify file stability threshold isn't too low
- Check for clock skew in timestamps

**Search returning no results**:
- Verify embeddings exist for content
- Check min/max importance filters
- Try text-based search as fallback
- Verify user_id/model_id filters

---

## Part 18: Key Statistics

- **Number of tables**: 20+ across all databases
- **Number of MCP tools**: 30+
- **Supported chat sources**: 8+
- **Max database size before rotation**: 100MB
- **Embedding dimension**: 384-1536 (configurable)
- **Search similarity threshold**: 0.3 (configurable)
- **Background maintenance interval**: 3 hours
- **File stability checks**: 3 (0.5s intervals)

---

## Conclusion

The Friday Memory System is a comprehensive, modular architecture designed to:

1. **Capture** conversations from multiple sources automatically
2. **Organize** information with semantic embeddings and traditional databases
3. **Retrieve** relevant information via semantic search and filtering
4. **Reflect** on AI tool usage for continuous learning
5. **Scale** through database sharding and parallel queries
6. **Integrate** with multiple AI platforms via MCP protocol

The system is designed for extensibility, allowing new chat sources, tools, and embedding providers to be added without modifying core logic.

