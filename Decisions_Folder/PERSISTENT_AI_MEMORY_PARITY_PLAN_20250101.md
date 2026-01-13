# Persistent AI Memory Feature Parity Plan
**Created**: January 1, 2026  
**Goal**: Align persistent-ai-memory with Friday Memory System functionality while maintaining generic design

---

## EXECUTIVE SUMMARY

The Friday Memory System has evolved significantly beyond persistent-ai-memory. This plan details all missing features and required architectural changes to achieve feature parity while keeping persistent-ai-memory generic for public use (no hardcoded paths, user IDs, or Friday-specific logic).

### Key Principle
- **Friday Memory System**: Purpose-built, Friday-specific (hardcoded paths, "Nate" user, OpenWebUI integration with short-term memory)
- **persistent-ai-memory Core**: Generic, self-contained long-term memory system (configurable settings, neutral user/model handling)
- **persistent-ai-memory Short-Term**: Optional OpenWebUI integration (separate from core, can be ported to other systems)

When porting features, we **extract the generic logic** from the long-term system and add configuration where needed.

### Architecture Clarification
**persistent-ai-memory does NOT require short-term memory to function.** Instead:
- **persistent-ai-memory core** = Standalone long-term memory system (conversations, AI memories, schedule, project tracking)
- **persistent-ai-memory short-term** = Optional OpenWebUI function (integrates with core via MCP server)
- Users can use persistent-ai-memory with OR without the short-term integration
- Users can use short-term independently in OpenWebUI and manually export memories, or via MCP connection to long-term system

---

## PART 1: FEATURE COMPARISON

### 1.1 CORE DATABASE LAYERS

#### ✅ Existing in persistent-ai-memory
- ConversationDatabase (basic version)
- AIMemoryDatabase (basic version)
- ScheduleDatabase (basic version)
- MCPToolCallDatabase
- VSCodeProjectDatabase (basic version)
- EmbeddingService

#### ❌ Missing/Incomplete Features in persistent-ai-memory

**A. ConversationDatabase Enhancements**
- [ ] Message linking to memories (memory-conversation junction table)
- [ ] Processing queue for conversation-based memory extraction
- [ ] Conversation processing status tracking
- [ ] Chat isolation support (character/model/user specific memory threads)

**B. AIMemoryDatabase Enhancements**
- [ ] Memory bank categorization (Personal, Work, General, etc.)
- [ ] Tag registry system for normalized memory tagging
- [ ] Structured tag management with canonical forms and variations
- [ ] Memory source tracking (direct, openwebui_promotion, mcp_external, etc.)
- [ ] Importance-weighted search

**C. Schedule Database Enhancements**
- [ ] Recurring appointment support (daily, weekly, monthly, yearly)
- [ ] Appointment modification history tracking
- [ ] Better reminder status management
- [ ] Appointment cancellation vs. deletion

**D. Overall Database**
- [ ] Database cleanup/archival mechanics (old conversations, expired reminders)
- [ ] Conversation validation and error tracking
- [ ] Archive database for historical records
- [ ] Better schema migrations

---

### 1.2 SHORT-TERM MEMORY SYSTEM (OPTIONAL OPENWEBUI INTEGRATION)

**IMPORTANT**: Short-term memory is NOT a core dependency of persistent-ai-memory. It's an optional OpenWebUI integration that complements the long-term system.

**persistent-ai-memory can function completely standalone without short-term memory.**

#### What Short-Term Memory Does (in OpenWebUI context)
- Intelligent memory extraction from user messages during conversations
- Multi-layered filtering pipeline (blacklist/whitelist, deduplication)
- Memory categorization (identity, preference, behavior, relationship, goal, possession)
- Memory relevance scoring (vector-based + optional LLM-based)
- Memory injection into conversation context
- Memory bank organization (Personal, Work, General)
- Background summarization and pruning tasks
- Valve-based (configurable) behavior control

#### How It Integrates With persistent-ai-memory
1. **OpenWebUI Setup**: User adds short-term memory function to OpenWebUI instance
2. **During Chat**: Short-term system extracts and manages in-conversation memories
3. **Optional MCP Connection**: Can push memories to long-term persistent-ai-memory via MCP server
4. **Standalone Use**: Can also work in OpenWebUI without MCP connection (manual export)

#### Current Implementation
- **File in Friday System**: `friday_memory_short_term.py` (~8800 lines)
- **Usage**: Imported as OpenWebUI function in function editor
- **Configuration**: Controlled via "valves" (user-configurable settings)

#### For persistent-ai-memory
- Will create generic version: `persistent_ai_memory_short_term.py`
- Keep it separate from core package
- Provide as optional module for OpenWebUI users
- Document integration steps separately in OpenWebUI integration guide
- **Timeline**: After core parity is achieved

---

### 1.3 CONVERSATION FILE MONITORING

#### Current State in persistent-ai-memory-upgrade
- Basic file monitoring exists
- Supports: LM Studio, Ollama, text files, JSON formats
- Some format parsers present

#### Missing Functionality
- [ ] More robust parsing for additional chat platforms
- [ ] Deduplication system (avoid importing same conversation twice)
- [ ] Better Ollama database extraction
- [ ] OpenWebUI database direct integration
- [ ] Character AI conversation parsing
- [ ] Text Generation WebUI support
- [ ] Sillytavern format parsing
- [ ] Claude conversation export parsing

#### File Formats Supported in Friday (need to ensure in persistent-ai-memory)
1. ✅ LM Studio JSON
2. ✅ Ollama database extraction
3. ✅ Character.AI JSON export
4. ✅ Text Gen WebUI format
5. ❓ OpenWebUI database (native format)
6. ✅ Simple JSON arrays
7. ❓ Markdown conversations
8. ❓ JSONL format
9. ❓ Claude export format

---

### 1.4 EMBEDDING SERVICE

#### Current State
- Both have basic embedding service
- Both support: Ollama, LM Studio, OpenAI

#### Missing in persistent-ai-memory
- [ ] Better fallback mechanisms
- [ ] Retry logic for failed embeddings
- [ ] Batch embedding support
- [ ] Caching for identical texts
- [ ] Provider detection/testing

---

### 1.5 MCP SERVER INTEGRATION

#### Current State in persistent-ai-memory
- Basic MCP server structure exists
- Tools are defined but incomplete

#### Friday Memory System Has
- Comprehensive tool definitions for all database operations
- Client-specific context management
- Better error handling and validation
- Tool usage logging and statistics
- AI reflection on tool usage
- Performance optimizations
- Support for search, creation, update, deletion across all memory types
- Weather, web search, and local search integration
- Health check and system monitoring tools

#### MCP Tools Currently Missing/Incomplete in persistent-ai-memory
**Memory Operations**:
- [ ] Advanced search_memories with all filters (memory_bank, tags, importance, type)
- [ ] update_memory with full parameter support
- [ ] delete_memory
- [ ] Memory promotion (moving between banks/archives)
- [ ] Memory archival operations

**Memory Bank Operations**:
- [ ] list_available_memory_banks
- [ ] get_memory_bank_stats

**Tag Management**:
- [ ] list_available_tags
- [ ] get_tag_variations/canonicalization

**Conversation Operations**:
- [ ] link_memory_to_conversation
- [ ] get_conversation_memories
- [ ] search_conversations

**Schedule Operations**:
- [ ] Full CRUD for reminders and appointments
- [ ] Recurring appointment support
- [ ] Auto-complete overdue reminders
- [ ] get_upcoming_appointments
- [ ] get_active_reminders
- [ ] reschedule_reminder
- [ ] cancel_appointment

**Project/Development Operations**:
- [ ] save_development_session
- [ ] store_project_insight
- [ ] search_project_history
- [ ] get_project_continuity

**System Operations**:
- [ ] get_system_health
- [ ] get_tool_information (usage + documentation)
- [ ] reflect_on_tool_usage
- [ ] store_ai_reflection
- [ ] Export tool calls for training datasets

**External Integration**:
- [ ] brave_web_search
- [ ] brave_local_search
- [ ] get_weather_open_meteo

**Maintenance Operations**:
- [ ] trigger_database_maintenance
- [ ] get_current_time

#### Need to Port
- [ ] Complete tool definitions with proper input schemas
- [ ] Client detection and context management
- [ ] Better example payloads in tool schemas
- [ ] Performance metrics and statistics
- [ ] Rate limiting and error recovery
- [ ] Streaming responses where applicable
- [ ] Tool call logging to MCP database
- [ ] AI reflection generation on tool patterns

---

### 1.6 DATABASE MAINTENANCE

#### Current State
- Both have database_maintenance.py
- Friday version is more mature

#### Missing in persistent-ai-memory-upgrade
- [ ] Automatic archival of old conversations
- [ ] Better optimization algorithms
- [ ] Health check improvements
- [ ] Repair mechanisms for corrupted databases
- [ ] Better error recovery

---

## PART 2: ARCHITECTURAL CHANGES NEEDED

### 2.1 Path Configuration
**Current**: persistent-ai-memory-upgrade uses `settings.py` ✅  
**Action**: Ensure ALL hardcoded paths are removed and use settings consistently

**Files to Update**:
- `ai_memory_core.py` - Remove any hardcoded paths
- `ai_memory_short_term.py` (new) - Use settings for logs, data directories
- `ai-memory-mcp_server.py` - Use settings for all paths

### 2.2 User/Model ID Handling
**Current in Friday**: Defaults to "Nate" for user, "Eddie" for model  
**Action in persistent-ai-memory**: Make these optional, default to generic values

**Change**:
```python
# Friday version (specific)
user_id = "Nate"
model_id = "Eddie"

# persistent-ai-memory version (generic)
user_id: Optional[str] = None  # Client determines
model_id: Optional[str] = None  # Client determines
```

### 2.3 Memory Bank System
**Add to persistent-ai-memory**:
- Default memory banks: "General", "Personal", "Work"
- Configurable via settings
- Tag registry system (like Friday has)
- Memory categorization by bank

### 2.4 Chat Isolation
**Friday Feature**: Memories can be isolated by (user_id, model_id, character_name)  
**persistent-ai-memory**: Needs this for multi-user scenarios

**Implementation**:
- Add isolation tracking to conversation queries
- Ensure memory retrieval respects isolation
- Make it optional/configurable

---

## PART 3: IMPLEMENTATION PHASES

### PHASE 1: Database Schema Enhancements (Week 1)
**Priority**: HIGH - Foundation for everything else

1. Add memory bank table and system
2. Add tag registry tables
3. Add memory-conversation junction table
4. Add processing queue for conversations
5. Create archive tables
6. Update schema migration logic

**Files Modified**:
- `ai_memory_core.py` - AIMemoryDatabase class

### PHASE 2: Conversation Database Enhancements (Week 1-2)
**Priority**: HIGH

1. Add message linking to memories
2. Add processing queue for conversation-based memory extraction
3. Add conversation processing status tracking
4. Implement chat isolation support (character/model/user specific memory threads)

**Files Modified**:
- `ai_memory_core.py` - ConversationDatabase class

### PHASE 3: Enhanced File Monitoring (Week 2)
**Priority**: MEDIUM

1. Add missing format parsers
2. Improve deduplication logic
3. Add better error handling
4. Create format detection improvements
5. Improve Ollama database extraction
6. Add OpenWebUI webui.db integration

**Files Modified**:
- `ai_memory_core.py` - ConversationFileMonitor class

### PHASE 4: Database Maintenance & Health (Week 2-3)
**Priority**: MEDIUM

1. Enhance database maintenance routines
2. Add better archival logic
3. Improve health checks
4. Add error recovery

**Files Modified**:
- `database_maintenance.py`
- `ai_memory_core.py` - Health check methods

### PHASE 5: MCP Server Functional Parity (Week 3)
**Priority**: HIGH - Critical infrastructure

1. Add all missing MCP tools from Friday's server
2. Tool parameter validation and error handling
3. Client context management and isolation
4. Tool usage statistics and logging
5. Better tool documentation and examples
6. Response formatting and error messages
7. Streaming support where applicable
8. Rate limiting and performance optimizations

**Missing Tools/Features to Add**:
- Enhanced memory search with all filtering options
- Memory promotion/archival operations
- Chat isolation-aware queries
- Memory bank management tools
- Tag registry operations
- Conversation linking operations
- Schedule management completeness
- Project/development tracking
- AI reflection and insight operations
- Web search and local search capabilities
- Weather integration
- Tool call logging and statistics
- Health check and system monitoring

**Files Modified**:
- `ai-memory-mcp_server.py` (major updates)
- `settings.py` (ensure all MCP configuration is present)

### PHASE 6: Testing & Documentation (Week 3-4)
**Priority**: MEDIUM

1. Create comprehensive test suite
2. Write integration tests
3. Document all new features
4. Create setup guides for different platforms

**Files Created**:
- `tests/test_memory_banks.py`
- `tests/test_chat_isolation.py`
- `docs/MEMORY_BANKS_GUIDE.md`
- `docs/OPENWEBUI_INTEGRATION_GUIDE.md`

### PHASE 7: Short-Term Memory System (AFTER CORE PARITY)
**Priority**: LOWER - Only after persistent-ai-memory core is complete

1. Copy Friday's `friday_memory_short_term.py`
2. Create generic version: `persistent_ai_memory_short_term.py`
3. Remove all hardcoded paths and Friday-specific logic
4. Make all configuration use settings from short-term module or environment
5. Test OpenWebUI integration
6. Document setup and configuration
7. Provide import instructions for OpenWebUI function editor

**Files Created**:
- `persistent_ai_memory_short_term.py` (new)
- `docs/SHORT_TERM_MEMORY_SETUP.md`

---

## PART 4: GENERICIZATION CHECKLIST

### When Porting from Friday → persistent-ai-memory

**❌ DO NOT COPY**:
- Hardcoded paths like `/media/nate/Friday/Friday`
- User ID "Nate" as default
- Model ID "Eddie" (or any Friday-specific names)
- OpenWebUI instance URLs
- Hardcoded local coordinates (weather)
- Friday-specific prompts/messages
- Friday system branding

**✅ DO COPY**:
- Algorithm implementations
- Database schemas
- Logic and business rules
- Error handling patterns
- Feature architecture
- Performance optimizations

**⚙️ MAKE CONFIGURABLE**:
- All paths → use settings.py
- All user IDs → optional parameters
- All model names → optional parameters
- All URLs → environment variables in .env
- All prompts → settings or importable constants
- All timeouts/thresholds → settings with sensible defaults

---

## PART 5: CONFIGURATION EXAMPLES

### New Settings to Add (settings.py)

```python
# Short-term memory configuration
enable_short_term_memory: bool = Field(default=True)
short_term_max_memories: int = Field(default=200)
short_term_pruning_strategy: str = Field(default="fifo")  # or "least_relevant"

# Memory banks
allowed_memory_banks: List[str] = Field(
    default=["General", "Personal", "Work"]
)
default_memory_bank: str = Field(default="General")

# Extraction & filtering
min_memory_length: int = Field(default=8)
vector_similarity_threshold: float = Field(default=0.7)
embedding_similarity_threshold: float = Field(default=0.97)

# Summarization
enable_summarization: bool = Field(default=True)
summarization_interval_seconds: int = Field(default=7200)
summarization_strategy: str = Field(default="hybrid")  # embeddings, tags, hybrid

# Chat isolation
enable_chat_isolation: bool = Field(default=True)
```

---

## PART 6: TESTING STRATEGY

### Unit Tests
- Memory bank operations
- Tag normalization
- Short-term memory extraction
- Deduplication logic
- Embedding generation

### Integration Tests
- End-to-end short-term memory workflow
- File monitoring and import
- Memory retrieval across memory banks
- Schedule management

### Platform Tests
- OpenWebUI integration
- LM Studio integration
- Ollama integration

---

## TIMELINE ESTIMATE

**For Core Parity (Phases 1-6):**
- **Phase 1**: 3-4 days
- **Phase 2**: 3-4 days
- **Phase 3**: 2-3 days
- **Phase 4**: 2-3 days
- **Phase 5 (MCP Server)**: 4-5 days (critical infrastructure, many tools)
- **Phase 6**: 3-4 days

**Core Parity Subtotal**: ~2.5-3.5 weeks

**Short-Term Memory System (Phase 7 - AFTER core parity):**
- **Phase 7**: 3-5 days (copy, genericize, test, document)

**Total**: ~3-4 weeks for full core parity + optional short-term system

---

## DECISION POINTS

1. **Should short-term memory be a separate module or integrated into ai_memory_core.py?**
   - Recommend: Separate file for clarity, but importable from main

2. **How to handle OpenWebUI function code?**
   - Recommend: Provide both `ai_memory_short_term.py` AND copy-paste instructions for OpenWebUI function editor

3. **Should memory extraction be optional?**
   - Recommend: Yes - make it a valve setting, disabled by default (safer for public)

4. **How to handle multi-user scenarios?**
   - Recommend: Full support through chat isolation feature, configurable

---

## NEXT STEPS

1. Nate reviews and approves this plan
2. Begin Phase 1 (database schema)
3. Create feature branch in persistent-ai-memory-upgrade
4. Port features incrementally with testing
5. When complete, merge to persistent-ai-memory main repo

---

## NOTES

- This plan maintains the generic nature of persistent-ai-memory
- All Friday-specific logic is extracted to be user/model/LLM-agnostic
- **Short-term memory is OPTIONAL** - persistent-ai-memory works fully without it
- Short-term system is a separate module for OpenWebUI users or can be adopted elsewhere
- MCP server integration is critical for full feature parity
- Memory banks and tag system improve organization significantly
- Full backward compatibility maintained for existing features
- OpenWebUI's webui.db is SQLite - can be directly queried and monitored
- Short-term system will be documented in separate OpenWebUI integration guide
- Users can port short-term to other systems if desired (beyond scope of this plan)
