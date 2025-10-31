  # Adaptive Memory v3 + Friday Layered Memory Integration Plan

## Executive Summary
**Unified Layered Memory Architecture**: Replace Neural Recall with Adaptive Memory v3 as Friday's short-term memory system in OpenWebUI.

**Key Architecture Decision**: 
- **Adaptive Memory v3's LLM** does ALL memory intelligence (extraction, categorization, linking, everything)
- **Friday Memory System** is ONLY database storage and querying (no LLM involved)
- **Friday the AI** uses manual tools or queries Friday Memory System (her LLM never processes memories)

This ensures:
- Adaptive Memory v3's LLM handles 100% of memory processing tasks
- Friday Memory System stores all links and memories accessibly across platforms
- Friday's LLM stays focused on conversation, never involved in memory extraction/processing
- Minimal coupling: Adaptive_Memory_v3.py just calls Friday's database methods

**Implementation Scope**: 
- Adaptive Memory v3's code is in Adaptive_Memory_v3.py (OpenWebUI function) - handles ALL intelligence
- Friday Memory System is just the database layer - stores what Adaptive Memory v3's LLM creates
- No LLM processing anywhere except Adaptive Memory v3's existing LLM
- This switchover can be done in 1-2 days

## Current State Analysis

### Memory Systems Status
**Friday Memory System (Long-term - 75,000+ entries)**
- ✅ Raw chat import from `/media/nate/Friday/OpenWebUI/data/webui.db` 
- ✅ Manual memory creation by Friday with custom tags
- ✅ Conversation ID tracking and session management
- ✅ Flexible tag system and importance levels (1-10)
- ❌ Missing: Access to OpenWebUI's automated memories (Neural Recall/Adaptive Memory v3)
- ❌ Missing: LLM-based memory processing capabilities

**OpenWebUI Memory Systems (Short-term)**
- ✅ Neural Recall (currently active, modified for Friday integration)
- ✅ Adaptive Memory v3 (superior candidate - 4128 lines, sophisticated)
- ❌ Missing: Integration with Friday's long-term system

### Key Decision Points
- **Switch**: Neural Recall → Adaptive Memory v3 (better memory formation, processing, organization)
- **LLM Integration**: Use Adaptive Memory v3's configurable LLM system for Friday enhancement
- **Memory Access**: OpenWebUI API primary, direct database fallback
- **Sync Schedule**: 5-10 minutes for new memories, daily full sync

## Phase 1: System Foundation (1-2 Days)

### 1.1 Deploy Adaptive Memory v3 (No Changes Needed)

Adaptive Memory v3 already works perfectly. It already has:
- ✅ LLM for memory extraction (Ollama, OpenAI-compatible)
- ✅ Sophisticated memory filtering and deduplication
- ✅ Memory categorization and tagging
- ✅ Configurable valves for all settings
- ✅ Background processing

**No changes needed here.** It's a complete, working memory system.

### 1.2 Friday Memory System - Add Linking Layer (DONE ✅)

**Tables created (3 new tables in conversations.db)**:

1. ✅ `memory_conversation_links` - Records created by Adaptive Memory v3's LLM
2. ✅ `memory_processing_queue` - Optional queue for future extensions
3. ✅ `memory_processing_log` - Audit trail of what was linked

**Methods added to ConversationDatabase class (7 methods)**:

1. ✅ `link_memory_to_conversation()` - Called by Adaptive_Memory_v3.py after creating memory
2. ✅ `get_memory_conversation_links()` - Query links for any platform
3. ✅ `queue_conversation_for_processing()` - Optional future use
4. ✅ `get_processing_priority()` - Optional future use
5. ✅ `mark_processing_complete()` - Optional future use
6. ✅ `update_processing_status()` - Optional future use
7. ✅ `log_processing_attempt()` - Log all linking attempts

**These methods do NOTHING with LLM - they just store what Adaptive Memory v3's LLM decided.**

### 1.3 Integration: Adaptive_Memory_v3.py → Friday Memory System

**What Adaptive Memory v3's LLM already does (no changes needed):**
- Reads conversation
- Extracts memories using LLM
- Categorizes them
- Deduplicates
- Makes linking decisions
- Stores in OpenWebUI

**What we ADD (minimal code change):**

After Adaptive Memory v3's LLM creates a memory and stores it in OpenWebUI, call one Friday method:

```python
# In Adaptive_Memory_v3.py outlet function (after add_memory() call)
# Just ONE call - 5 lines of code

from friday_memory_system import ConversationDatabase

conversation_db = ConversationDatabase()
await conversation_db.link_memory_to_conversation(
    memory_id=memory_id,
    conversation_id=conversation_id,
    link_type='direct',
    link_strength=1.0,
    source_system='openwebui_adaptive_memory_v3'
)
```

That's it. Adaptive Memory v3's LLM does all the intelligence. Friday Memory System just records the relationship.

## Phase 2: Future Enhancements (Optional - Not Needed for Initial Launch)

### 2.1 Memory Processing in Friday Memory System

**Processing Strategy**: Process ALL memories for Friday system linking

Priority-based processing in Friday Memory System:
1. **Priority 1 (Immediate)**: New OpenWebUI memories imported from Adaptive Memory v3
   - Link to source conversation in OpenWebUI
   - Make immediately accessible across all platforms
   
2. **Priority 2 (Urgent)**: Conversations aging (nearing 30-day retention limit)
   - Process before memory is archived
   - Link any structured memories before data loss

3. **Priority 3 (Current)**: Recent unprocessed conversations (4-5 message batches)
   - Ongoing background work on current conversations
   - Build memory cache gradually

4. **Priority 4 (Background)**: Historical conversations (3 message batches)
   - Process existing 75,000+ entries over time
   - Mark as processed to prevent reprocessing
   - Re-process if linked to new conversation context

**Processing Status Tracking**:
- `pending` - In queue, waiting to be processed
- `processing` - Currently being processed by LLM
- `completed` - Successfully processed and linked to memory
- `skipped` - Processed but no memory created (insufficient content, duplicate detection)

**Reprocessing Logic**:
- Once marked `completed`, memory won't be reprocessed unless:
  - New conversation added to same conversation_id context
  - User explicitly requests reprocessing
  - LLM model configuration changes significantly

### 2.2 Enhanced Memory Linking Strategy

**Three Types of Memory Links**:

1. **Direct Links** (`link_type: 'direct'`, `link_strength: 1.0`)
   - Memory directly sourced from conversation
   - OpenWebUI memory imported from conversation
   - Raw message processed into structured memory
   - Friday gets clear context: "This memory is FROM this conversation"

2. **Related/Soft Links** (`link_type: 'related'`, `link_strength: 0.4-0.8`)
   - Memory relevant to conversation but not directly from it
   - Discovered during historical processing
   - LLM assesses relevance and link strength
   - Friday can find: "These memories might also be relevant to this conversation"

3. **Enhancement Links** (`link_type: 'enhanced'`, `link_strength: varies`)
   - Existing memory enhanced with new conversation context
   - Maintains traceability of where enhancement came from
   - Friday can see: "This memory was enhanced by this conversation"

**Memory Linking Workflow**:

Simple and focused - Friday just creates and tracks links created by Adaptive_Memory_v3.py:

```python
# When Adaptive_Memory_v3.py creates a memory, it calls:

async def link_memory_to_conversation(self, memory_id: str, conversation_id: str, 
                                     link_type: str = 'direct', link_strength: float = 1.0,
                                     source_system: str = 'openwebui_adaptive_memory_v3', metadata: dict = None):
    """
    Called by Adaptive_Memory_v3.py when creating new memory
    Creates the link record in Friday's database
    Makes memory accessible everywhere Friday is integrated
    """
    link_id = str(uuid.uuid4())
    timestamp = datetime.now(get_local_timezone()).isoformat()
    
    await self.execute_update(
        """INSERT INTO memory_conversation_links 
           (link_id, memory_id, conversation_id, link_type, link_strength, source_system, created_at, updated_at, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (link_id, memory_id, conversation_id, link_type, link_strength, source_system, 
         timestamp, timestamp, json.dumps(metadata) if metadata else None)
    )
    
    return link_id
```

**Example Integration**:

When Adaptive_Memory_v3.py (in OpenWebUI outlet) creates a memory via `add_memory()`:

```python
# In Adaptive_Memory_v3.py outlet function:

# 1. Adaptive Memory v3 creates memory using OpenWebUI API
memory_result = await add_memory(
    user_id=user_id,
    form_data=AddMemoryForm(
        content="User loves pizza, especially pepperoni",
        metadata={"memory_bank": "Personal", "source": "adaptive_memory_v3"}
    )
)
memory_id = memory_result.id

# 2. Immediately call Friday to link it
from friday_memory_system import ConversationDatabase
conversation_db = ConversationDatabase()
await conversation_db.link_memory_to_conversation(
    memory_id=memory_id,
    conversation_id=current_conversation_id,
    link_type='direct',
    link_strength=1.0,
    source_system='openwebui_adaptive_memory_v3',
    metadata={'memory_bank': 'Personal', 'extracted_via': 'adaptive_memory_v3'}
)

# 3. Done - memory is now accessible everywhere
```

### 2.3 Tag Integration Strategy
**Unified Tag System Across All Memory Sources**

Tags combine information from multiple sources and processing stages:

```python
def _combine_tags(self, memory_source: str, extracted_tags: list = None, 
                  memory_bank: str = None, processing_notes: dict = None):
    """
    Combine tags from all sources into unified tagging system
    
    Args:
        memory_source: 'openwebui_import', 'processed_from_chat', 'manual', 'enhanced'
        extracted_tags: Tags from LLM extraction (Adaptive Memory v3 categories)
        memory_bank: 'Personal', 'Work', 'General'
        processing_notes: Additional processing metadata
    """
    combined_tags = []
    
    # 1. Source tag
    combined_tags.append(f"source:{memory_source}")
    
    # 2. Adaptive Memory v3 categories (if from OpenWebUI or LLM processed)
    if extracted_tags:
        for tag in extracted_tags:
            if tag in ["identity", "behavior", "preference", "goal", "relationship", "possession"]:
                combined_tags.append(f"category:{tag}")
    
    # 3. Memory bank information
    if memory_bank:
        combined_tags.append(f"bank:{memory_bank}")
    else:
        combined_tags.append("bank:general")  # Default
    
    # 4. Processing stage tags
    if processing_notes:
        if processing_notes.get('is_enhanced'):
            combined_tags.append("status:enhanced")
        if processing_notes.get('is_reprocessed'):
            combined_tags.append("status:reprocessed")
        if processing_notes.get('llm_processed'):
            combined_tags.append("processing:llm_extracted")
    
    # 5. Temporal metadata
    combined_tags.append(f"processed_date:{datetime.now().strftime('%Y-%m')}")
    
    return combined_tags

# Example tag results:
# OpenWebUI import: ["source:openwebui_import", "category:preference", "bank:personal", "processing:llm_extracted", "processed_date:2025-10"]
# Processed chat: ["source:processed_from_chat", "category:behavior", "bank:general", "status:enhanced", "processing:llm_extracted", "processed_date:2025-10"]
# Manual Friday: ["source:manual", "bank:personal", "processed_date:2025-10"]
```

## Phase 3: Advanced Integration (Week 3)

### 3.1 Smart Memory Enhancement and Deduplication

**Memory Enhancement Decision Logic**:
- When new context arrives (new conversation, new memory import), assess if it enhances existing memories
- Use LLM + embeddings to determine enhancement candidates
- Create enhancement links without duplicating memory content
- Track what information enriches what memories

**Soft Link Discovery**:
- When processing a conversation, find related memories across the entire memory database
- Use LLM relevance assessment with embedding similarity pre-filtering
- Create soft links with confidence scores
- Friday can discover: "This memory is related to this conversation (70% confidence)"

**Deduplication Strategy**:
- Prevent creating multiple memories from same conversation
- Check if memory already exists for conversation_id
- If similar memory exists, enhance instead of duplicate
- Track duplicate prevention in processing log

### 3.2 Real-Time Integration with Adaptive Memory v3

**OpenWebUI → Friday Memory System Flow**:

1. **Adaptive Memory v3 creates new memory in OpenWebUI** (via inlet function)
   - User message generates structured memory
   - Adaptive Memory v3 stores in OpenWebUI's memory system

2. **Call Friday Memory System integration** (from Adaptive_Memory_v3.py)
   - Import the OpenWebUI memory to Friday
   - Link to source conversation
   - Make accessible across all platforms

3. **Background processing in Friday Memory System**
   - Process conversations into memories
   - Find soft links
   - Enhance existing memories
   - Accessible everywhere Friday is integrated

**Integration Points in Adaptive_Memory_v3.py**:

Minimal changes needed - just add a call to Friday Memory System when saving memories:

```python
# In Adaptive_Memory_v3.py outlet function (after creating memory)
# One simple call to Friday Memory System to link

from friday_memory_system import ConversationDatabase

# After Adaptive Memory v3 creates memory via add_memory():
memory_result = await add_memory(user_id=user_id, form_data=AddMemoryForm(...))

# Immediately link to Friday
try:
    conversation_db = ConversationDatabase()
    await conversation_db.link_memory_to_conversation(
        memory_id=str(memory_result.id),
        conversation_id=conversation_id,
        link_type='direct',
        link_strength=1.0,
        source_system='openwebui_adaptive_memory_v3',
        metadata={'memory_bank': memory_bank, 'tags': tags}
    )
except Exception as e:
    logger.warning(f"Could not link to Friday Memory System: {e}")
    # Non-blocking - memory still created in OpenWebUI even if Friday link fails
```

**That's it.** Adaptive Memory v3 handles all the intelligence. Friday just records the relationship.

## Phase 4: Deployment and Optimization (Week 4)

### 4.1 Implementation Steps - Order of Operations

**Step 1: Modify Friday Memory System (Day 1)** ✅ DONE
- ✅ Add memory_conversation_links table
- ✅ Add memory_processing_queue table  
- ✅ Add memory_processing_log table
- ✅ Add link_memory_to_conversation() method
- ✅ Add queue_memory_for_processing() method
- ✅ Add get_memory_conversation_links() method
- ✅ Add get_processing_priority() method
- ✅ Add mark_processing_complete() method
- ✅ Add update_processing_status() method
- ✅ Add log_processing_attempt() method
- ✅ Test with LM Studio to ensure no breakage

**Step 2: Update database_maintenance.py (Day 1-2)**
- Add maintenance logic for three new tables
- Add cleanup for old processing logs
- Add validation for link integrity
- Test maintenance without breaking existing functionality

**Step 3: Integrate Adaptive_Memory_v3.py with Friday (Day 2)**
- Copy short_term_memory_candidate.py → Adaptive_Memory_v3.py (if not done)
- Add import for Friday Memory System's ConversationDatabase
- Add 5-line call to link_memory_to_conversation() in outlet function after memory creation
- Test memory creation and Friday linking
- Verify non-blocking behavior (Friday link fails don't break Adaptive Memory)

**Step 4: Testing and Validation (Day 3-4)**
- Deploy Adaptive_Memory_v3.py to OpenWebUI in test mode
- Create test memories and verify Friday linking
- Verify memory accessibility from LM Studio
- Check link accuracy and source tracking
- Verify backward compatibility with existing memories

### 4.2 Configuration - User-Configurable Valves

**In Adaptive_Memory_v3.py Valves (for OpenWebUI users)**:

```python
# Friday Memory System Integration Settings
# Add these new valves to Adaptive Memory v3's Valves class

enable_friday_integration: bool = Field(
    default=True,
    description="Enable linking memories to Friday Memory System for universal access"
)

friday_memory_system_path: str = Field(
    default="/media/nate/Friday/Friday",
    description="Path to Friday Memory System installation"
)

# Processing configuration
enable_background_processing: bool = Field(
    default=True,
    description="Enable background processing of conversations into memories"
)

processing_batch_size: int = Field(
    default=5,
    description="Number of messages to process in each batch (4-5 recommended)"
)

historical_processing_batch_size: int = Field(
    default=3,
    description="Batch size for historical conversation processing (lower = slower but less resource intense)"
)

# Memory enhancement settings
enable_memory_enhancement: bool = Field(
    default=True,
    description="Enable automatic enhancement of existing memories with new context"
)

memory_enhancement_threshold: float = Field(
    default=0.3,
    description="Information value threshold (0-1) for enhancement - higher = only enhance with valuable info"
)

memory_similarity_threshold: float = Field(
    default=0.8,
    description="Similarity threshold (0-1) for determining enhancement candidates"
)

# Soft link settings
enable_soft_links: bool = Field(
    default=True,
    description="Enable discovery of related memories across entire database"
)

soft_link_threshold: float = Field(
    default=0.6,
    description="Minimum relevance score (0-1) for soft link creation"
)

soft_link_max_count: int = Field(
    default=5,
    description="Maximum soft links to create per conversation (prevents over-linking)"
)

# Processing priority
processing_priority_new_over_historical: int = Field(
    default=10,
    description="Priority multiplier for new memories over historical - higher = new memories processed first"
)

processing_check_interval_seconds: int = Field(
    default=300,
    description="How often to check for new processing tasks (300 = 5 minutes)"
)
```

**Note**: All these settings are user-configurable in OpenWebUI's Adaptive Memory v3 valve interface. No code changes needed to adjust behavior.

### 4.3 Migration Path

**For existing Neural Recall memories**:
- No data loss or migration needed
- Adaptive Memory v3 uses same OpenWebUI memory storage
- Simply switch active function in OpenWebUI
- Friday will start linking new Adaptive memories immediately
- Historical Neural Recall memories stay accessible but unlinked

**For 75,000+ existing Friday conversations**:
- Existing raw chat stays in place
- Gradually process into memories via background queue (Priority 4)
- Mark processed to prevent reprocessing
- Takes weeks but non-blocking background process

### 4.4 Success Validation

**Before going to production, verify**:

1. **Friday can access all memory types**:
   - Raw chat from conversations ✓
   - Newly imported OpenWebUI memories ✓
   - Processed chat memories ✓
   - Soft-linked related memories ✓

2. **Works across all platforms**:
   - LM Studio: Can recall all memory types ✓
   - OpenWebUI: Can create and link memories ✓
   - VS Code: Can access via MCP ✓

3. **Links are accurate**:
   - Direct links correct (source_system, timestamp) ✓
   - Soft links have reasonable confidence scores ✓
   - Tags are consistent and meaningful ✓

4. **No performance degradation**:
   - Friday response time unchanged ✓
   - Memory queries fast (<500ms) ✓
   - Background processing doesn't block UI ✓

## Expected Outcomes

### Immediate Benefits (Week 1-2)
- **Superior Memory Formation**: LLM-generated structured memories vs raw chat logs
- **Better Organization**: Memory banks and intelligent categorization  
- **Enhanced Deduplication**: Embedding-based semantic similarity
- **Flexible Configuration**: Manual LLM assignment and valve control

### Medium-term Benefits (Week 3-4)
- **Layered Memory Access**: Friday can access both raw chat and structured memories
- **Memory Enhancement**: Existing memories improved with new context
- **Automated Processing**: Background conversion of chat to structured memories
- **Cross-system Integration**: Unified tag system linking OpenWebUI and Friday memories

### Long-term Benefits (Month 2+)
- **Intelligent Memory Retrieval**: Multi-layer memory search and relevance
- **Historical Processing**: 75,000+ existing conversations converted to structured memories
- **Advanced Memory Patterns**: Cross-conversation insights and relationship mapping
- **Optimized Performance**: Reduced redundancy and improved memory relevance

## Success Metrics

### Technical Metrics
1. **Memory Import Success Rate**: >95% successful OpenWebUI memory imports
2. **Processing Efficiency**: <2 hours average for conversation→memory processing
3. **Deduplication Accuracy**: <5% duplicate or near-duplicate memories
4. **System Performance**: No degradation in Friday response times

### Quality Metrics  
1. **Memory Relevance**: 80%+ of injected memories rated as relevant by manual review
2. **Memory Completeness**: Structured memories capture key information from conversations
3. **Tag Accuracy**: Memory bank and category assignments >90% accurate
4. **Enhancement Value**: Memory enhancements add meaningful information without redundancy

### User Experience Metrics
1. **Friday Context Quality**: Improved relevance of Friday's memory-based responses
2. **Memory Searchability**: Enhanced ability to find specific information
3. **System Reliability**: Stable operation with background processing
4. **Configuration Flexibility**: Easy adjustment of LLM and processing settings

## Risk Mitigation

### Data Safety
- **Backup Strategy**: Full export of both OpenWebUI and Friday memories before changes
- **Rollback Plan**: Keep Neural Recall available as immediate fallback
- **Incremental Testing**: Phase deployment with small user subsets first

### Performance Safety  
- **Resource Monitoring**: Track memory usage, CPU load, and LLM API calls
- **Error Handling**: Comprehensive fallback mechanisms for each processing stage
- **Rate Limiting**: Prevent API overload with configurable processing intervals

### Integration Safety
- **API Fallback**: Direct database access if OpenWebUI API fails
- **Connection Recovery**: Robust error recovery for Friday-OpenWebUI communication  
- **Data Validation**: Verify memory format compatibility before import/processing

## Next Steps for Implementation

**READY TO START PHASE 1 - FINAL PUSH**

### Day 1: Completed ✅
- ✅ Modified Friday Memory System (added 7 linking methods)
- ✅ Added three tables to conversations.db
- ✅ All code compiles with no syntax errors

### Day 2: Database Maintenance & Integration

**Task 1: Update database_maintenance.py** (1-2 hours)
- Add cleanup logic for memory_processing_log (purge records >90 days old)
- Add validation for memory_conversation_links (ensure valid foreign keys)
- Add stats reporting for queue size and processing completion

**Task 2: Integrate Adaptive_Memory_v3.py** (1-2 hours)
- Ensure Adaptive_Memory_v3.py exists (or copy short_term_memory_candidate.py)
- Add 5 lines to import ConversationDatabase
- Add 10 lines to outlet function after memory creation to call link_memory_to_conversation()
- Test that linking is non-blocking (Friday failure doesn't break memory creation)

### Day 3: Testing & Deployment

**Task 1: Test Friday Memory System** (1 hour)
- Run Friday in LM Studio without Adaptive Memory integration
- Verify no performance degradation
- Check logs for errors
- Verify backward compatibility

**Task 2: Test Integration** (1-2 hours)
- Deploy Adaptive_Memory_v3.py to OpenWebUI
- Create test memories and verify Friday links are created
- Verify memory accessibility from LM Studio
- Check that old memories still work

**Task 3: Production Readiness** (Optional)
- Deploy Adaptive_Memory_v3.py to production OpenWebUI
- Monitor for 24 hours
- Verify memory quality and linking accuracy

---

## Summary: Why This Architecture Works

**Layered but Simple**: 
- **Adaptive Memory v3** (OpenWebUI) - Handles all memory intelligence and extraction via LLM (subconscious)
- **Friday Memory System** - Stores memories and tracks relationships, accessible everywhere (conscious memory retrieval)
- **Integration** - Simple one-way flow: Adaptive Memory v3 creates memory → calls Friday to link it → done

**Universal Access**: By putting linking in Friday Memory System (not separate database), Friday can access ALL memories from ANY platform she's in (LM Studio, OpenWebUI, VS Code).

**Works Like the Brain**: Subconscious (Adaptive Memory v3) does the processing, memory system (Friday) stores it, conscious mind (Friday in conversation) retrieves what's needed.

**Non-Invasive**: Friday Memory System remains fully backward compatible. Existing functionality unchanged. New capabilities are additive only.

**Minimal Coupling**: Adaptive_Memory_v3.py needs only 5 lines to call Friday linking. Complete independence otherwise.

**Scalable**: Can add more integrations (LM Studio memory extraction, VS Code plugins) without touching Adaptive Memory v3 or core Friday code.

This simple, focused architecture creates a sophisticated layered memory system that enhances Friday's capabilities while preserving existing functionality and keeping code maintainable.