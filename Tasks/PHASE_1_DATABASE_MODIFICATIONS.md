# Phase 1: Database Modifications and Code Changes

## Task Status: IN PROGRESS

**Objective**: Add memory-conversation linking capability to Friday Memory System to support Adaptive Memory v3 integration.

---

## Part A: Database Tables (Use DB Browser)

### Database: `memory_data/conversations.db`

Add the following three tables to this database:

#### Table 1: `memory_conversation_links`

**Purpose**: Track relationships between memories (from any source) and conversations

**SQL**:
```sql
CREATE TABLE memory_conversation_links (
    link_id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    link_type TEXT DEFAULT 'direct',
    link_strength REAL DEFAULT 1.0,
    source_system TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,
    FOREIGN KEY (memory_id) REFERENCES curated_memories (memory_id),
    FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
);

CREATE INDEX idx_memory_links_memory ON memory_conversation_links(memory_id);
CREATE INDEX idx_memory_links_conversation ON memory_conversation_links(conversation_id);
CREATE INDEX idx_memory_links_source ON memory_conversation_links(source_system);
```

**Columns**:
- `link_id`: Unique identifier (UUID)
- `memory_id`: Foreign key to curated_memories.memory_id
- `conversation_id`: Foreign key to conversations.conversation_id
- `link_type`: 'direct' (from conversation), 'related' (soft link), 'enhanced' (enhanced by conversation)
- `link_strength`: 0.0-1.0 confidence/strength score
- `source_system`: 'openwebui_import', 'processed_from_chat', 'manual', 'enhanced'
- `created_at`: When link created
- `updated_at`: When link last modified
- `metadata`: JSON with processing info, tags, etc.

---

#### Table 2: `memory_processing_queue`

**Purpose**: Track which conversations need memory processing and prevent duplicate work

**SQL**:
```sql
CREATE TABLE memory_processing_queue (
    queue_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL UNIQUE,
    processing_status TEXT DEFAULT 'pending',
    processing_type TEXT,
    message_count INTEGER DEFAULT 0,
    last_processed_message_id TEXT,
    processing_priority INTEGER DEFAULT 5,
    marked_processed BOOLEAN DEFAULT FALSE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
);

CREATE INDEX idx_processing_queue_status ON memory_processing_queue(processing_status);
CREATE INDEX idx_processing_queue_priority ON memory_processing_queue(processing_priority DESC);
CREATE INDEX idx_processing_queue_type ON memory_processing_queue(processing_type);
CREATE INDEX idx_processing_queue_marked ON memory_processing_queue(marked_processed);
```

**Columns**:
- `queue_id`: Unique identifier (UUID)
- `conversation_id`: Foreign key to conversations.conversation_id (UNIQUE - one entry per conversation)
- `processing_status`: 'pending', 'processing', 'completed', 'skipped'
- `processing_type`: 'new_openwebui', 'recent_chat', 'aging_chat', 'historical_chat'
- `message_count`: Number of messages in conversation
- `last_processed_message_id`: Last message processed (for resuming)
- `processing_priority`: 1-10 (higher = more urgent)
- `marked_processed`: Prevents reprocessing unless linked to new conversation
- `created_at`: When queued
- `updated_at`: Last status update

---

#### Table 3: `memory_processing_log`

**Purpose**: Audit trail of all memory processing attempts and outcomes

**SQL**:
```sql
CREATE TABLE memory_processing_log (
    log_id TEXT PRIMARY KEY,
    conversation_id TEXT,
    memory_id TEXT,
    processing_type TEXT,
    status TEXT,
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id),
    FOREIGN KEY (memory_id) REFERENCES curated_memories (memory_id)
);

CREATE INDEX idx_processing_log_conversation ON memory_processing_log(conversation_id);
CREATE INDEX idx_processing_log_memory ON memory_processing_log(memory_id);
CREATE INDEX idx_processing_log_status ON memory_processing_log(status);
CREATE INDEX idx_processing_log_date ON memory_processing_log(created_at);
```

**Columns**:
- `log_id`: Unique identifier (UUID)
- `conversation_id`: Which conversation was processed
- `memory_id`: Which memory was created/enhanced
- `processing_type`: Type of processing attempted
- `status`: 'success', 'failed', 'skipped'
- `reason`: Why success/failure/skip (for debugging)
- `created_at`: When logged

---

## Part B: Code Changes in `friday_memory_system.py`

### Task B.1: Add Methods to `ConversationDatabase` Class

**Location**: Add these methods to the `ConversationDatabase` class (around line 110)

**Methods to Add**:

1. `async def link_memory_to_conversation()` - Create memory-conversation links
2. `async def get_memory_conversation_links()` - Retrieve links for a memory or conversation
3. `async def queue_conversation_for_processing()` - Add conversation to processing queue
4. `async def get_processing_priority()` - Determine what to process next
5. `async def mark_processing_complete()` - Mark conversation as processed
6. `async def update_processing_status()` - Update queue status
7. `async def log_processing_attempt()` - Log all processing attempts

**Method Signatures**:

```python
async def link_memory_to_conversation(self, memory_id: str, conversation_id: str, 
                                     link_type: str = 'direct', link_strength: float = 1.0,
                                     source_system: str = 'processed_from_chat', metadata: dict = None) -> str:
    """Link a memory to a conversation. Returns link_id."""
    pass

async def get_memory_conversation_links(self, memory_id: str = None, conversation_id: str = None,
                                       link_type: str = None) -> List[Dict]:
    """Get links for a specific memory or conversation or both."""
    pass

async def queue_conversation_for_processing(self, conversation_id: str, 
                                           processing_type: str, priority: int = 5) -> str:
    """Queue a conversation for memory processing. Returns queue_id."""
    pass

async def get_processing_priority(self) -> dict:
    """Get next conversation to process based on priority."""
    pass

async def mark_processing_complete(self, queue_id: str, memory_id: str = None) -> bool:
    """Mark conversation as processed."""
    pass

async def update_processing_status(self, queue_id: str, status: str, reason: str = None) -> bool:
    """Update processing status (pending/processing/completed/skipped)."""
    pass

async def log_processing_attempt(self, conversation_id: str, processing_type: str,
                                status: str, memory_id: str = None, reason: str = None) -> str:
    """Log a processing attempt. Returns log_id."""
    pass
```

---

### Task B.2: Add `MemoryLLMProcessor` Class to `AIMemoryDatabase` Class

**Location**: Add this class to `friday_memory_system.py` (after `AIMemoryDatabase` class definition, around line 500)

**Purpose**: Handle LLM-based memory processing using Adaptive Memory v3's LLM configuration

**Class Structure**:

```python
class MemoryLLMProcessor:
    """
    Handles LLM-based memory extraction and enhancement for Friday Memory System.
    Uses configuration from Adaptive Memory v3 to maintain consistency.
    """
    
    def __init__(self, llm_config: dict):
        """Initialize with LLM configuration from Adaptive Memory v3"""
        self.provider_type = llm_config.get("provider_type", "ollama")
        self.model_name = llm_config.get("model_name", "llama3:latest")
        self.api_endpoint = llm_config.get("api_endpoint", "http://host.docker.internal:11434/api/chat")
        self.api_key = llm_config.get("api_key")
        # Store Adaptive Memory v3's processing prompts
        self.memory_identification_prompt = llm_config.get("memory_identification_prompt")
        self.memory_relevance_prompt = llm_config.get("memory_relevance_prompt")
        pass
    
    async def process_conversation_to_memory(self, conversation_messages: List[Dict]) -> dict:
        """
        Process conversation messages into structured memory.
        Returns: {
            'content': str,
            'category': str,  # identity, behavior, preference, goal, relationship, possession
            'importance': int,  # 1-10
            'tags': List[str],
            'memory_bank': str  # Personal, Work, General
        }
        """
        pass
    
    async def assess_memory_enhancement(self, existing_memory: dict, new_context: str) -> dict:
        """
        Determine if memory should be enhanced with new context.
        Returns: {
            'should_enhance': bool,
            'enhancement_type': str,  # 'append', 'merge', 'supplement'
            'confidence': float,  # 0.0-1.0
            'information_value': float  # 0.0-1.0 how much new info adds
        }
        """
        pass
    
    async def enhance_memory_with_context(self, memory_id: str, new_context: str) -> str:
        """
        Enhance existing memory with new information.
        Returns: enhanced content
        """
        pass
    
    async def find_related_memories(self, memory_content: str, threshold: float = 0.7) -> List[Dict]:
        """
        Find related memories for soft linking.
        Returns: List of {'memory_id': str, 'relevance_score': float, 'reason': str}
        """
        pass
    
    async def extract_key_information(self, messages: List[Dict]) -> str:
        """Extract key information from messages for comparison."""
        pass
```

---

## Part C: Integration Points

### Where These Will Be Called

These new database tables and methods will be called by:

1. **Adaptive_Memory_v3.py** - When creating new memories in OpenWebUI
   - Call `link_memory_to_conversation()` after memory creation
   - Call `queue_conversation_for_processing()` for batch processing

2. **Friday Memory System (in LM Studio, etc.)** - Background processing
   - Call `get_processing_priority()` to find what to work on next
   - Call `process_conversation_to_memory()` using LLMProcessor
   - Call `link_memory_to_conversation()` when memory is created
   - Call `mark_processing_complete()` when done
   - Call `log_processing_attempt()` for audit trail

3. **Memory Queries from Any Platform**
   - Call `get_memory_conversation_links()` to find memories related to a conversation
   - Makes memories accessible from LM Studio, OpenWebUI, VS Code

---

## Summary of Database Tasks

**Using DB Browser, add these three tables to `memory_data/conversations.db`:**

1. ✅ `memory_conversation_links` - Links memories to conversations
2. ✅ `memory_processing_queue` - Tracks processing status
3. ✅ `memory_processing_log` - Audit trail

**Then implement these code changes:**

1. ✅ Add linking methods to `ConversationDatabase` class
2. ✅ Add `MemoryLLMProcessor` class to handle LLM processing

---

## Testing Before Moving to Phase 2

Before proceeding:
- [ ] All three tables created in DB Browser
- [ ] Tables have correct columns and indices
- [ ] Code compiles without errors
- [ ] Friday Memory System still works in LM Studio (backward compatible)
- [ ] No errors in logs

**Status**: Ready for DB Browser table creation