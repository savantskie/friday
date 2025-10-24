  # Adaptive Memory v3 + Friday Integration Plan

## Executive Summary
Replace Neural Recall with Adaptive Memory v3 as Friday's short-term memory system while maintaining Friday Memory System integration for long-term storage.

## Phase 1: Core Integration (Immediate)

### 1.1 Add Friday Storage Configuration
```python
# Add to Valves class
enable_friday_storage: bool = Field(
    default=True,
    description="Enable transfer of old memories to Friday Memory System before deletion"
)
friday_retention_days: int = Field(
    default=30,
    description="Days to retain memories before transferring to Friday"
)
friday_mcp_url: str = Field(
    default="http://localhost:8000",
    description="Friday Memory System MCP server URL"
)
```

### 1.2 Friday Storage Function
```python
async def _store_to_friday(self, memory_content: str, memory_bank: str, tags: list):
    """Store memory to Friday Memory System before deletion"""
    try:
        friday_tags = tags + [f"openwebui_archive", f"memory_bank_{memory_bank.lower()}", "30day_retention"]
        # Implementation similar to Neural Recall's Friday integration
        # Use aiohttp to call Friday MCP server
        pass
    except Exception as e:
        logger.error(f"Failed to store memory to Friday: {e}")
```

### 1.3 Memory Pruning Enhancement
```python
async def _prune_old_memories_with_friday_storage(self, user_id: str):
    """Enhanced pruning that stores to Friday before deletion"""
    # Get memories older than retention period
    # Store each to Friday with proper metadata
    # Then delete from OpenWebUI
    pass
```

## Phase 2: Advanced Features (Short-term)

### 2.1 Memory Bank-aware Friday Storage
- Store Personal/Work/General memories with appropriate Friday tags
- Use memory bank information to set Friday importance levels
- Personal memories → importance 7-8
- Work memories → importance 6-7  
- General memories → importance 5-6

### 2.2 Summarization Integration
- Store summarized memories to Friday instead of individual memories
- Include cluster information in Friday metadata
- Maintain traceability from original memories to summaries

### 2.3 Enhanced Background Tasks
```python
async def _friday_sync_task(self):
    """Background task for Friday synchronization"""
    # Check for memories ready for Friday transfer
    # Batch transfer operations for efficiency
    # Verify successful transfers before deletion
    pass
```

## Phase 3: Advanced Integration (Long-term)

### 3.1 Bidirectional Memory Flow
- Query Friday for relevant long-term memories during context retrieval
- Include Friday memories in relevance scoring
- Seamless short-term + long-term memory injection

### 3.2 Memory Migration Tool
```python
async def migrate_neural_recall_to_adaptive():
    """One-time migration from Neural Recall to Adaptive Memory v3"""
    # Export existing Neural Recall memories
    # Convert to Adaptive Memory format with proper categorization
    # Import with Friday storage enabled
    pass
```

### 3.3 Friday Memory Enhancement
- Enhance Friday to accept structured memory data
- Support memory banks and categorization
- Import Adaptive Memory's LLM-generated memory formation

## Implementation Steps

### Step 1: Backup and Prepare
1. Backup existing Neural Recall memories
2. Test Adaptive Memory v3 in isolated environment
3. Verify Friday Memory System compatibility

### Step 2: Core Integration
1. Add Friday-specific valves to Adaptive Memory v3
2. Implement Friday storage functions
3. Add Friday storage to memory pruning logic
4. Test basic integration

### Step 3: Enhanced Features  
1. Implement memory bank-aware Friday storage
2. Add summarization → Friday integration
3. Create background Friday sync task
4. Performance testing and optimization

### Step 4: Migration and Deployment
1. Create migration tool for existing memories
2. Deploy in production with gradual rollout
3. Monitor performance and error rates
4. Fine-tune configuration based on usage

## Configuration Recommendations

### Production Settings
```python
# Memory Management
max_total_memories: 150  # Reduced for 30-day retention
recent_messages_n: 5
related_memories_n: 3
top_n_memories: 3

# Performance Optimizations  
use_llm_for_relevance: False  # Rely on vector similarity
vector_similarity_threshold: 0.7
llm_skip_relevance_threshold: 0.93
cache_ttl_seconds: 86400

# Friday Integration
enable_friday_storage: True
friday_retention_days: 30
friday_mcp_url: "http://localhost:8000"

# Summarization
summarization_interval: 7200  # 2 hours
summarization_min_cluster_size: 3
summarization_min_memory_age_days: 7
```

## Expected Benefits

### 1. Memory Quality Improvements
- **50-70% better memory formation** vs raw chat logs
- **Reduced noise** through intelligent categorization
- **Better context relevance** through embedding-based retrieval

### 2. Performance Gains
- **30-40% faster retrieval** through vector similarity pre-filtering
- **Reduced LLM calls** via smart caching and thresholds
- **Background processing** prevents UI blocking

### 3. Friday Integration Benefits
- **Seamless 30-day retention flow** maintained
- **Enhanced metadata** for better Friday memory organization
- **Structured memory transfer** vs raw chat logs

## Risk Mitigation

### 1. Migration Risks
- **Backup strategy**: Full export of existing memories
- **Rollback plan**: Keep Neural Recall as fallback
- **Gradual migration**: Test with subset of users first

### 2. Performance Risks
- **Resource monitoring**: Track embedding model memory usage
- **Error handling**: Comprehensive fallback mechanisms
- **Rate limiting**: Prevent LLM API overload

### 3. Friday Integration Risks
- **Connection handling**: Robust error recovery for Friday API
- **Data validation**: Ensure Friday compatibility before transfer
- **Duplicate prevention**: Avoid storing same memory twice

## Timeline

- **Week 1**: Core integration implementation
- **Week 2**: Testing and Friday storage validation  
- **Week 3**: Enhanced features and background tasks
- **Week 4**: Migration tool and production deployment

## Success Metrics

1. **Memory Formation Quality**: Manual review of 100 memories vs Neural Recall
2. **Performance**: Response time improvements and error rate reduction
3. **Friday Integration**: Successful 30-day retention flow with zero data loss
4. **User Experience**: Improved memory relevance in conversations