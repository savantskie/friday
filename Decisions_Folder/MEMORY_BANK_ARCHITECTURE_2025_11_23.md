# Memory Bank Architecture Decision
**November 23, 2025 - Unified Long-Term Memory Design**

## Problem Statement

How should Friday Memory System handle memory categorization when promoting memories from OpenWebUI short-term to long-term storage? Should `memory_bank` be:

A) Just metadata about origin (deprecated after storage)
B) A persistent organizational layer supporting future AI-enrichment

## Decision: Option B - Persistent Organizational Layer

**Rationale**: Memory evolution mirrors human cognition. Short-term memory (OpenWebUI) extracts immediate facts. Long-term memory (Friday) builds deeper structures and connections. The secondary layer of enrichment (future LLM) discovers relationships between memories that weren't obvious at creation time.

### The Three-Layer Memory Model

```
LAYER 1: Extraction (OpenWebUI - Adaptive Memory v3)
  ├─ Role: Real-time memory capture from conversations
  ├─ Data: content, importance_level, tags
  ├─ Storage: OpenWebUI short-term (200-max FIFO)
  └─ Purpose: Active conversation context

LAYER 2: Organization (Friday - Long-term with categories)
  ├─ Role: Persistent curation with semantic organization
  ├─ Data: content, importance_level, tags, memory_bank
  ├─ Storage: ai_memories.db (permanent)
  ├─ memory_bank: "Personal", "Work", "Tasks", "Context", "General"
  └─ Purpose: Organized retrieval, category-based queries

LAYER 3: Enrichment (Future LLM - Relationship Discovery)
  ├─ Role: Semantic analysis across memories
  ├─ Process: "What events connect these memories?"
  ├─ Queries: Group by memory_bank, find cross-bank relationships
  ├─ Output: Link memories by discovered relationships
  └─ Result: "Memory 5 (Work) relates to Memory 12 (Personal) via shared timeline"
```

### Why memory_bank Must Persist

1. **Category Anchoring**: Organization persists across all layers
2. **Query Foundation**: "Show me all Work memories related to Project X"
3. **Enrichment Input**: LLM layer uses categories as semantic anchors
4. **Future-Proofing**: Enables advanced features without data migration

### How It Works End-to-End

```
User Message in OpenWebUI
  ↓
Adaptive Memory Extraction (Outlet)
  ├─ Assigned memory_bank: "Personal"
  ├─ Store in OpenWebUI short-term
  └─ Importance: 5

User/System: "Promote to long-term"
  ↓
POST /api/memories/promote
  ├─ Provide: content, memory_bank, conversation_id
  ├─ Call: FridayMemorySystem.create_memory()
  │   ├─ Store with memory_bank: "Personal"
  │   ├─ Set importance_level: 8 (promoted)
  │   ├─ Return: memory_id
  │   └─ Background: Generate embedding
  ├─ Call: link_memory_to_conversation()
  │   ├─ Create link with source_conversation_id
  │   ├─ Include metadata: memory_bank, promotion_source
  │   └─ link_type: "promoted_from_short_term"
  └─ Return: memory_id to caller

Result in Friday Memory System
  ├─ curated_memories.memory_bank = "Personal" (persists)
  ├─ memory_conversation_links entry (for provenance)
  ├─ Embedding generated (for semantic search)
  └─ Ready for enrichment layer

Future: Secondary LLM Analysis
  ├─ Query: "Find patterns across memory_banks"
  ├─ Process: Semantic similarity + category analysis
  ├─ Output: "Memory 5 (Personal) and 23 (Work) connected via 'team collaboration'"
  └─ Result: New links created automatically
```

## Implementation Details

### Database Schema Change
```sql
-- Current schema already has these fields:
ALTER TABLE curated_memories 
ADD COLUMN IF NOT EXISTS memory_bank TEXT DEFAULT 'General'

-- Index for efficient category queries:
CREATE INDEX IF NOT EXISTS idx_curated_memories_bank
ON curated_memories (memory_bank, importance_level)
```

### Method Signature Enhancement

**Before**:
```python
async def create_memory(
    self,
    content: str,
    memory_type: str = None,
    importance_level: int = 5,
    tags: List[str] = None,
    source_conversation_id: str = None,
    user_id: str = "",
    model_id: str = "",
) -> str:
```

**After**:
```python
async def create_memory(
    self,
    content: str,
    memory_type: str = None,
    importance_level: int = 5,
    tags: List[str] = None,
    source_conversation_id: str = None,
    memory_bank: str = "General",  # NEW: organizational category
    user_id: str = "",
    model_id: str = "",
) -> str:
```

### Promotion Endpoint Enhancement

**Request**:
```json
{
    "content": "Memory content (required)",
    "memory_type": "Optional: type of memory",
    "tags": ["optional", "tag", "list"],
    "memory_bank": "Personal",
    "conversation_id": "source_conversation_id"
}
```

**Flow**:
1. Create memory with memory_bank preserved
2. Link memory to conversation with metadata including memory_bank
3. Return with confirmation

## Allowed Memory Banks

Defined in Adaptive Memory v3 valves:
```python
allowed_memory_banks = ["General", "Personal", "Work", "Context", "Tasks"]
```

Same values used in Friday Memory System for consistency.

## Data Flow Example

### Scenario: Promoting a Personal Project Memory

**Step 1: Create in OpenWebUI**
```
Memory: "Learned Rust programming today, got async/await working"
Assigned: memory_bank = "Personal"
Stored in: OpenWebUI short-term (5-day retention)
```

**Step 2: Promote to Friday**
```python
# API call from OpenWebUI or external system
POST /api/memories/promote
{
    "content": "Learned Rust programming today, got async/await working",
    "memory_type": "skill_acquisition",
    "memory_bank": "Personal",
    "tags": ["rust", "programming", "learning"],
    "conversation_id": "conv_uuid_12345"
}

# Friday System processes:
# 1. Creates memory_id in curated_memories with memory_bank="Personal"
# 2. Sets importance_level=8 (promoted)
# 3. Links to conversation via memory_conversation_links with metadata
# 4. Generates embedding asynchronously
# 5. Returns memory_id to caller
```

**Step 3: Future Enrichment Query**
```
Secondary LLM analysis:
"Find memories that share skill-building themes across categories"

Result might discover:
- Memory 42 (Work): "Team adopted async patterns"
- Recognized connection: Rust async/await learning bridges to team technology adoption
- Automatically creates relationship link
```

## Integration Points

### 1. POST /api/memories/promote Endpoint
- Accept memory_bank parameter
- Validate against allowed_memory_banks
- Pass to create_memory()
- Include in link metadata

### 2. FridayMemorySystem.create_memory()
- Add memory_bank parameter (default: "General")
- Store in curated_memories table
- Include in returned memory data

### 3. Memory Conversation Linking
- Call link_memory_to_conversation() with metadata including memory_bank
- Link metadata includes: source_system, memory_bank, promotion_context
- Enables future queries by category relationships

### 4. Adaptive Memory v3 Promotion
- Already assigns memory_bank during extraction
- Promotion preserves the bank assignment
- No changes needed in Adaptive Memory extraction logic

## Future Extensibility

### Phase A: Basic Promotion (This Session)
- ✅ memory_bank persists with promoted memories
- ✅ Conversation linking captures context
- ✅ Tests verify both work correctly

### Phase B: Category-Based Search (Next Phase)
- [ ] Add search endpoint: `GET /api/memories?memory_bank=Personal`
- [ ] Implement category filtering in semantic search
- [ ] Show memory_bank in search results

### Phase C: Relationship Discovery (Future Project)
- [ ] Secondary LLM analyzes memory clusters by bank
- [ ] Detects cross-bank semantic relationships
- [ ] Automatically creates memory_conversation_links for discovered relationships
- [ ] UI shows "This memory is related to..." suggestions

### Phase D: Memory Analytics (Later)
- [ ] Track memory_bank usage patterns
- [ ] Identify gaps in certain categories
- [ ] Suggest memory extraction in underrepresented areas

## Design Principles Upheld

1. **Layered Complexity**: Each layer adds sophistication without breaking previous layers
2. **Human Cognition Alignment**: Mimics how human memory organizes information
3. **Future-Proofing**: Enables AI-assisted enrichment without data restructuring
4. **Non-Destructive**: All additions are additive, no breaking changes
5. **Semantic Foundation**: Builds on LM Studio embeddings for deep relationship discovery

## Success Criteria

✅ **Immediate** (This Session)
- [ ] memory_bank column added to curated_memories
- [ ] create_memory() accepts and stores memory_bank
- [ ] Promotion endpoint accepts memory_bank parameter
- [ ] Conversation linking includes memory_bank in metadata
- [ ] All tests pass without failures
- [ ] Backward compatibility: existing memories default to "General"

✅ **Short-term** (Next Session)
- [ ] Category-based search queries work
- [ ] Can filter memories by memory_bank
- [ ] Linking metadata used in advanced queries

✅ **Long-term** (Future Project)
- [ ] Secondary LLM layer implemented
- [ ] Cross-bank relationship discovery working
- [ ] Automatic link creation from enrichment

## Backward Compatibility

- Existing memories (before this change) will have memory_bank = "General" (default)
- No data loss or restructuring needed
- Queries without memory_bank filter work as before
- Optional parameter in all APIs

## Files to Modify

1. `/media/nate/Friday/Friday/friday_memory_system.py`
   - Add memory_bank column to table creation
   - Add memory_bank parameter to create_memory()
   - Update insert statement

2. `/media/nate/Friday/Friday/friday_memory_mcp_server.py`
   - Update promote endpoint to accept memory_bank
   - Call link_memory_to_conversation with metadata
   - Add memory_bank to create_memory allowed_args

3. `/media/nate/Friday/Friday/Tests/test_promote_endpoint.py`
   - Test promotion with different memory_banks
   - Verify memory_bank persists
   - Verify linking includes memory_bank metadata

## References

- Architecture Design: `COMPLETE_SYSTEM_ARCHITECTURE_2025_11_17.md`
- API Implementation: `API_LAYER_IMPLEMENTATION_2025_11_18.md`
- Link Infrastructure: `COMPREHENSIVE_IMPLEMENTATION_FINDINGS_2025_11_09.md`

---

## Conclusion

By treating memory_bank as a persistent organizational layer rather than just origin metadata, we create a foundation for intelligent memory enrichment. The three-layer model (extraction → organization → enrichment) aligns with human cognition and enables future AI systems to discover meaningful patterns that weren't obvious at memory creation time.

This decision embodies the principle: **Start with the simple architecture you need, but design it to support the complex system you'll eventually want.**
