  # Adaptive Memory v3 + Friday Layered Memory Integration Plan

## Executive Summary
**Unified Layered Memory Architecture**: Replace Neural Recall with Adaptive Memory v3 as Friday's short-term memory system, while creating a sophisticated multi-layer memory integration that enhances Friday's long-term memory capabilities through intelligent processing and cross-system memory linking. Adaptive Memory v3's code is in the Adaptive_Memory_v3.py file. This is the code that we will be augmenting for this system. All changes to Adaptive Memory v3 should be done in this file: Adaptive_Memory_v3.py. This switch over may be done in hours, or days. Hopefully not weeks.

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

## Phase 1: System Foundation (Week 1)

### 1.1 Deploy Adaptive Memory v3
**Replace Neural Recall with Adaptive Memory v3 in OpenWebUI**
- Configure Adaptive Memory v3 valves for production use
- Set LLM provider (manual configuration - not hardcoded)
- Enable memory banks (Personal/Work/General)
- Test memory formation, categorization, and deduplication

**Production Configuration:**
```python
# Memory Management
max_total_memories: 150  # 30-day retention optimization
recent_messages_n: 5
related_memories_n: 3
top_n_memories: 3

# Performance Settings
use_llm_for_relevance: # Per Nate, if the system already relies on LLM for this, do not touch.
#The system already has around 65 valves that can be customized, these valves already manage behavior. Most settings that seem hardcoded? Are not. they are just the default values.
```

### 1.2 Friday Memory System Enhancement
**Add OpenWebUI Memory Import Capability**
```python
# New database tables in Friday Memory System, but if it makes sense to do so, let's make a new database that tracks what memories are tied to which conversations.
CREATE TABLE openwebui_memory_links (
    id TEXT PRIMARY KEY,
    friday_memory_id TEXT,           -- Links to curated_memories.memory_id
    openwebui_memory_id TEXT,        -- From OpenWebUI memories
    conversation_id TEXT,            -- Groups related memories
    relationship_type TEXT,          -- 'imported_openwebui', 'processed_from_chat', 'enhanced'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,                   -- JSON: tags, memory_bank, processing_info
    FOREIGN KEY (friday_memory_id) REFERENCES curated_memories (memory_id),
    FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
);

CREATE TABLE memory_processing_queue (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    message_count INTEGER DEFAULT 0,
    last_processed_message_id TEXT,
    processing_status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed'
    processing_priority INTEGER DEFAULT 5,    -- 1-10 priority
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
);
```

**Add OpenWebUI Memory Import Function**
```python
async def import_openwebui_memories(self):
    """Import automated memories from OpenWebUI via API"""
    from open_webui.routers.memories import query_memory, QueryMemoryForm
    from open_webui.models.users import Users
    
    users = Users.get_users()
    imported_count = 0
    
    for user in users:
        result = await query_memory(
            user_id=user.id,
            form_data=QueryMemoryForm(query="", k=1000)  # Get all memories
        )
        
        if result and result.memories:
            for memory in result.memories:
                success = await self._import_openwebui_memory(memory, user.id)
                if success:
                    imported_count += 1
    
    logger.info(f"Imported {imported_count} OpenWebUI memories")
    return imported_count
```

### 1.3 LLM Integration Enhancement
**Integrate Adaptive Memory v3's LLM System into Friday**
```python
# Add to Friday Memory System, and let Adaptive Memory's valves influence how the LLM choses memories or updates memories within the Friday Memory System.
class FridayLLMProcessor:
    def __init__(self, llm_config):
        self.provider_type = llm_config.get("provider_type", "ollama")
        self.model_name = llm_config.get("model_name", "llama3:latest")
        self.api_endpoint = llm_config.get("api_endpoint", "http://host.docker.internal:11434/api/chat")
        self.api_key = llm_config.get("api_key")
    
    async def process_conversations_to_memories(self, conversation_messages):
        """Use Adaptive Memory v3's memory extraction logic"""
        # Leverage Adaptive Memory v3's memory identification prompt
        # Process chat into structured memories with categories and tags
        pass
    
    async def enhance_existing_memory(self, existing_memory, new_context):
        """Enhance existing memory with new information"""
        # Check for similarity/duplication
        # Append or enhance rather than duplicate
        pass
```

## Phase 2: Memory Processing Pipeline (Week 2)

### 2.1 Background Memory Processing
**Priority-Based Processing System**
```python
async def get_processing_priority(self):
    """Determine what memories to process next"""
    
    # Priority 1: New OpenWebUI memories (import immediately)
    new_openwebui = await self._check_new_openwebui_memories()
    if new_openwebui:
        return ("openwebui_import", new_openwebui, priority=1)
    
    # Priority 2: Conversations nearing 30-day mark (urgent processing)
    aging_conversations = await self._get_aging_conversations(days_until_archive=3)
    if aging_conversations:
        return ("aging_chat", aging_conversations, priority=2)
    
    # Priority 3: Recent unprocessed conversations (4-5 message batches)
    recent_unprocessed = await self._get_recent_unprocessed_conversations(batch_size=5)
    if recent_unprocessed:
        return ("recent_chat", recent_unprocessed, priority=3)
    
    # Priority 4: Historical chat processing (background, low priority)
    historical_batch = await self._get_historical_unprocessed(batch_size=3)
    if historical_batch:
        return ("historical_chat", historical_batch, priority=4)
    
    return None

async def process_memory_queue(self):
    """Main processing loop with priority handling"""
    while True:
        task = await self.get_processing_priority()
        
        if task:
            task_type, data, priority = task
            await self._process_memory_task(task_type, data, priority)
        else:
            await asyncio.sleep(300)  # Wait 5 minutes if no tasks
```

### 2.2 Enhanced Memory Linking
**Conversation-Based Memory Enhancement**
```python
async def _process_conversation_to_memory(self, conversation_id: str):
    """Convert chat conversation into structured memory with linking"""
    
    # Get conversation messages
    messages = await self.get_conversation_messages(conversation_id)
    
    # Check if conversation already has curated memories
    existing_memories = await self._get_conversation_memories(conversation_id)
    
    if existing_memories:
        # Enhancement mode: check if new processing would add value
        should_enhance = await self._should_enhance_memory(existing_memories, messages)
        if should_enhance:
            enhanced_memory = await self._enhance_existing_memory(existing_memories[0], messages)
            return enhanced_memory
        else:
            logger.info(f"Conversation {conversation_id} already has sufficient curated memory")
            return None
    else:
        # New processing: create structured memory from chat
        processed_memory = await self.llm_processor.process_conversations_to_memories(messages)
        
        # Create curated memory with enhanced metadata
        memory_id = await self.create_memory(
            content=processed_memory['content'],
            memory_type=processed_memory['category'],  # identity, behavior, preference, goal, relationship, possession
            importance_level=processed_memory['importance'],
            tags=self._combine_tags(processed_memory['adaptive_tags'], processed_memory['friday_tags']),
            source_conversation_id=conversation_id
        )
        
        # Record the processing in linking table
        await self._record_memory_processing(conversation_id, memory_id, "processed_from_chat")
        
        return memory_id
```

### 2.3 Tag Integration Strategy
**Unified Tag System**
```python
def _combine_tags(self, adaptive_tags, friday_tags=None):
    """Combine Adaptive Memory v3 and Friday tag systems"""
    combined_tags = []
    
    # Add Adaptive Memory v3 categories with prefix
    for tag in adaptive_tags:
        if tag in ["identity", "behavior", "preference", "goal", "relationship", "possession"]:
            combined_tags.append(f"adaptive:{tag}")
    
    # Add memory bank information
    if "memory_bank" in adaptive_tags:
        combined_tags.append(f"adaptive:bank_{adaptive_tags['memory_bank'].lower()}")
    
    # Add Friday's custom tags (if any)
    if friday_tags:
        combined_tags.extend(friday_tags)
    
    # Add processing metadata
    combined_tags.append("conversation_processed")
    combined_tags.append(f"processed_date:{datetime.now().strftime('%Y-%m')}")
    
    return combined_tags

# Example tag result:
# ["adaptive:preference", "adaptive:bank_personal", "friday_custom_tag", "conversation_processed", "processed_date:2025-10"]
```

## Phase 3: Advanced Integration (Week 3)

### 3.1 Memory Deduplication and Enhancement
**Smart Memory Management**
```python
async def _should_enhance_memory(self, existing_memories, new_messages):
    """Determine if new conversation content should enhance existing memory"""
    
    for memory in existing_memories:
        # Extract key information from new messages
        new_info = await self.llm_processor.extract_key_information(new_messages)
        
        # Check semantic similarity with existing memory
        similarity = await self._calculate_memory_similarity(memory['content'], new_info)
        
        if similarity > 0.8:  # High similarity - potential enhancement
            # Check if new information adds substantial value
            added_value = await self.llm_processor.assess_information_value(memory['content'], new_info)
            
            if added_value > 0.3:  # Threshold for worthwhile enhancement
                return True
    
    return False

async def _enhance_existing_memory(self, base_memory, new_context):
    """Enhance existing memory with new context without duplication"""
    
    enhanced_content = await self.llm_processor.enhance_memory_content(
        existing_content=base_memory['content'],
        new_context=new_context,
        enhancement_type="append_new_insights"
    )
    
    # Update the memory with enhanced content
    success = await self.update_memory(
        memory_id=base_memory['memory_id'],
        content=enhanced_content,
        tags=self._merge_tags(base_memory['tags'], ["enhanced", f"enhanced_date:{datetime.now().isoformat()}"])
    )
    
    return success
```

### 3.2 Monitoring and Sync System
**Real-time OpenWebUI Memory Monitoring**
```python
async def monitor_openwebui_memories(self):
    """Monitor OpenWebUI for new memories and import them"""
    
    last_check = await self._get_last_import_timestamp()
    
    while True:
        try:
            # Check for new memories since last import
            new_memories = await self._get_openwebui_memories_since(last_check)
            
            if new_memories:
                logger.info(f"Found {len(new_memories)} new OpenWebUI memories")
                
                for memory in new_memories:
                    await self._import_openwebui_memory(memory)
                
                await self._update_last_import_timestamp()
            
            # Wait 5 minutes before next check
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"Error monitoring OpenWebUI memories: {e}")
            await asyncio.sleep(600)  # Wait 10 minutes on error
```

## Phase 4: Deployment and Optimization (Week 4)

### 4.1 Migration and Testing
**No Migration Needed**
- Neural Recall and Adaptive Memory v3 use the same OpenWebUI memory storage
- Simply switch the active function in OpenWebUI
- Friday will start importing Adaptive Memory v3's superior memories automatically

**Testing Protocol**
1. Deploy Adaptive Memory v3 in test mode
2. Compare memory quality with Neural Recall over 48-hour period
3. Test Friday import functionality with new memories
4. Verify memory enhancement and deduplication logic
5. Performance testing with background processing

### 4.2 Production Configuration
**Adaptive Memory v3 Production Settings**
```python
# Optimized for Friday integration
llm_provider_type: "ollama"  # User configurable
llm_model_name: "llama3:latest"  # User configurable  
llm_api_endpoint_url: "http://host.docker.internal:11434/api/chat"

# Memory formation settings
filter_trivia: true
enable_json_stripping: true
enable_fallback_regex: true
enable_short_preference_shortcut: true

# Performance optimization
use_llm_for_relevance: false  # Use vector similarity for speed
vector_similarity_threshold: 0.7
llm_skip_relevance_threshold: 0.93

# Background processing
enable_summarization_task: true
summarization_interval: 7200  # 2 hours
enable_error_logging_task: true
error_logging_interval: 1800   # 30 minutes
```

**Friday Memory System Integration Settings**
```python
# OpenWebUI integration
openwebui_import_interval: 300      # 5 minutes
openwebui_full_sync_interval: 86400 # Daily
openwebui_api_fallback_enabled: true

# Memory processing
conversation_processing_batch_size: 5
historical_processing_batch_size: 3
memory_enhancement_threshold: 0.3   # When to enhance vs create new
memory_similarity_threshold: 0.8    # Deduplication threshold

# LLM processing
enable_llm_memory_processing: true
llm_processing_priority: ["openwebui_import", "aging_chat", "recent_chat", "historical_chat"]
```

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

1. **Immediate**: Deploy Adaptive Memory v3 to replace Neural Recall
2. **Day 1**: Implement OpenWebUI memory import in Friday Memory System
3. **Day 2**: Add LLM processing capabilities using Adaptive Memory v3's system
4. **Day 3**: Create memory linking and processing queue tables
5. **Day 4**: Implement background processing with priority system
6. **Week 2**: Add memory enhancement and deduplication logic
7. **Week 3**: Deploy monitoring and real-time sync
8. **Week 4**: Performance optimization and production deployment

This plan creates a sophisticated layered memory architecture that enhances Friday's capabilities while preserving existing functionality and providing a clear upgrade path.