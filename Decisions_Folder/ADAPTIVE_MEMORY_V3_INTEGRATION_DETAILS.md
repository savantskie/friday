# Adaptive Memory v3 Integration with Friday Memory System - Detailed Design

## Core Principle
**Don't break Adaptive Memory v3's intelligence. Enhance its context access.**

Adaptive Memory v3's LLM is powerful and sophisticated. We're not replacing it. We're:
1. Giving it better context (access to long-term memories)
2. Letting it promote memories to long-term storage
3. Tracking the lineage of memories (short-term → long-term)

---

## Architecture: Three Memory Layers

### Layer 1: Short-Term Memory (OpenWebUI's existing system)
- **Where**: OpenWebUI's memory system
- **What**: Raw memories Adaptive Memory v3 creates during conversations
- **How long**: Until consolidated/promoted
- **Lifespan**: Session-based, auto-purged by OpenWebUI

### Layer 2: Long-Term Memory (Friday Memory System)
- **Where**: Friday Memory System's `curated_memories` table
- **What**: Promoted memories from short-term + manually created by Friday
- **How long**: 1 year retention
- **Source tracking**: Tagged with `source_system: 'openwebui_adaptive_memory_v3'` and `source_conversation_id`

### Layer 3: Conversation Context (Friday Memory System)
- **Where**: Friday Memory System's `memory_conversation_links` table
- **What**: Links between memories and conversations
- **Purpose**: Allows finding memories related to any conversation
- **Use**: Adaptive Memory v3 can search for context

---

## How Adaptive Memory v3 Uses Friday Memory System

### During INLET (Before LLM Response)

**Current flow** (no change):
```
User message → Retrieve relevant short-term memories → Inject into context → LLM
```

**Enhanced flow** (Adaptive Memory v3 calls Friday):
```
User message → Retrieve relevant short-term memories from OpenWebUI
           → If not enough context, search Friday long-term memories for similar context
           → Inject both layers into context → LLM
```

**Implementation**:
```python
# In Adaptive Memory v3's inlet function

# 1. Get short-term memories (current behavior - unchanged)
short_term_memories = await self.get_relevant_memories(user_message, user_id)

# 2. If short-term is sparse, augment with long-term context
if len(short_term_memories) < threshold:
    long_term_memories = await friday_system.search_long_term_for_context(
        user_message=user_message,
        user_id=user_id,
        threshold=0.6
    )
    # Augment short-term with long-term context
    all_memories = short_term_memories + long_term_memories
else:
    all_memories = short_term_memories

# 3. Inject all memories into context (current behavior)
self._inject_memories_into_context(body, all_memories)
```

**Key point**: This is ADDITIVE. If long-term search fails, we just use short-term. No breaking changes.

---

### During OUTLET (After LLM Response - Memory Creation)

**Current flow** (Adaptive Memory v3 alone):
```
User message + LLM response → Extract memories → Save to OpenWebUI
```

**Enhanced flow** (Adaptive Memory v3 uses Friday for lineage):
```
User message + LLM response → Extract memories → Save to OpenWebUI
                           → Call Friday to link and track lineage
```

**Implementation**:
```python
# In Adaptive Memory v3's outlet function

# 1. Adaptive Memory v3 creates memory in OpenWebUI (unchanged)
memory_result = await add_memory(
    user_id=user_id,
    form_data=AddMemoryForm(
        content="User loves pizza",
        metadata={"memory_bank": "Personal"}
    )
)
memory_id = str(memory_result.id)

# 2. Link to Friday for future reference (NEW)
await friday_system.link_memory_to_conversation(
    memory_id=memory_id,
    conversation_id=current_conversation_id,
    link_type='direct',
    link_strength=1.0,
    source_system='openwebui_adaptive_memory_v3',
    metadata={'memory_bank': 'Personal', 'promoted_to_long_term': False}
)

# 3. That's it - memory is tracked for future searches
```

---

### During CONSOLIDATION (Memory Promotion - Short-term → Long-term)

**This is where it gets interesting.**

Adaptive Memory v3 periodically consolidates short-term memories into long-term (when memory limit reached, or on schedule).

**Current flow**:
```
Short-term memory → User decides to keep → Update OpenWebUI memory
```

**Enhanced flow** (uses Friday + tracks lineage):
```
Short-term memory → Adaptive Memory v3 decides to promote
                 → Save to Friday long-term with lineage tracking
                 → Update metadata to show promotion
                 → Link to original conversation
```

**Implementation**:
```python
# New function in Adaptive Memory v3: _promote_to_long_term()

async def _promote_to_long_term(self, short_term_memory_id: str, user_id: str):
    """
    Promote a short-term memory to long-term storage (Friday Memory System)
    This creates a permanent record while keeping OpenWebUI memory active
    """
    try:
        # 1. Get the short-term memory from OpenWebUI
        short_term_memory = await query_memory(
            user_id=user_id,
            form_data=QueryMemoryForm(query=short_term_memory_id, k=1)
        )
        
        if not short_term_memory or not short_term_memory.memories:
            return
        
        mem = short_term_memory.memories[0]
        
        # 2. Create long-term version in Friday Memory System
        long_term_memory_id = await friday_system.create_memory(
            content=mem.content,
            memory_type=mem.metadata.get('category', 'general'),
            importance_level=mem.metadata.get('importance_level', 5),
            tags=mem.metadata.get('tags', []),
            source_conversation_id=mem.metadata.get('source_conversation_id')
        )
        
        # 3. Track the promotion relationship
        await friday_system.link_memory_to_conversation(
            memory_id=long_term_memory_id,
            conversation_id=mem.metadata.get('source_conversation_id'),
            link_type='promoted',
            source_system='openwebui_adaptive_memory_v3',
            metadata={
                'promoted_from_short_term': short_term_memory_id,
                'promoted_at': datetime.now().isoformat(),
                'memory_bank': mem.metadata.get('memory_bank', 'General')
            }
        )
        
        # 4. Log the promotion
        await friday_system.log_processing_attempt(
            conversation_id=mem.metadata.get('source_conversation_id'),
            processing_type='memory_promotion',
            status='success',
            memory_id=long_term_memory_id,
            reason=f'Promoted from short-term ({short_term_memory_id}) to long-term'
        )
        
        # 5. Update OpenWebUI memory metadata to show it was promoted
        new_metadata = mem.metadata.copy()
        new_metadata['promoted_to_long_term'] = True
        new_metadata['long_term_memory_id'] = long_term_memory_id
        
        await delete_memory_by_id(user_id=user_id, memory_id=short_term_memory_id)
        await add_memory(
            user_id=user_id,
            form_data=AddMemoryForm(
                content=mem.content,
                metadata=new_metadata
            )
        )
        
        logger.info(f"Promoted short-term memory {short_term_memory_id} → {long_term_memory_id}")
        
    except Exception as e:
        logger.error(f"Error promoting memory to long-term: {e}")
        # Non-blocking - promotion failure doesn't break anything
```

---

## Human-Like Memory Function

This design creates human-like memory behavior:

### How Human Memory Works:
1. **Immediate recall**: "Wait, what did we just talk about?" (short-term memory)
2. **Related recall**: "This reminds me of something from years ago" (long-term search)
3. **Memory consolidation**: "I should remember this" (moving to long-term storage)
4. **Lineage**: "I remember because of that conversation with..."

### How Adaptive Memory v3 Now Works:
1. **Immediate recall**: Gets short-term memories from OpenWebUI
2. **Related recall**: If short-term sparse, searches Friday for similar context
3. **Memory consolidation**: Periodically promotes short-term to long-term Friday storage
4. **Lineage tracking**: Every memory links back to source conversation

---

## Key Design Decisions

### 1. Non-Blocking Failures
If Friday Memory System call fails:
- ✅ Memory still created in OpenWebUI
- ✅ Short-term memory works normally
- ✅ Just loses the long-term linking/context
- ✅ No user-visible impact

### 2. Metadata Tracking
Every promoted memory has metadata showing:
- `source_system: 'openwebui_adaptive_memory_v3'` - Where it came from
- `source_conversation_id` - Which conversation generated it
- `promoted_from_short_term` - Which short-term ID it came from
- `promoted_at` - When promotion happened
- `memory_bank` - Which bank it belongs to

### 3. Search Strategy
When searching long-term for context:
- Use embedding similarity (fast first pass)
- If multiple results, use LLM relevance scoring (slower but accurate)
- Return top N results with confidence scores
- Optional: Return both semantic matches AND keyword matches

### 4. Intelligence Preservation
Adaptive Memory v3's LLM logic is UNTOUCHED:
- ✅ Memory extraction logic unchanged
- ✅ Filtering and deduplication unchanged
- ✅ Categorization unchanged
- ✅ Tag assignment unchanged
- We just give it BETTER CONTEXT and LONG-TERM STORAGE

---

## Function Calls Summary

### From Adaptive Memory v3 to Friday Memory System:

**Inlet (adding context)**:
```python
# NEW - optional search for long-term context
await friday_system.get_memories(
    limit=5,
    memory_type=relevant_category  # Filter by type
)
```

**Outlet (after creating memory)**:
```python
# NEW - link short-term memory to conversation
await friday_system.link_memory_to_conversation(
    memory_id=memory_id,
    conversation_id=current_conversation_id,
    link_type='direct',
    source_system='openwebui_adaptive_memory_v3'
)

# NEW - log what was processed
await friday_system.log_processing_attempt(
    conversation_id=current_conversation_id,
    processing_type='short_term_memory_created',
    status='success',
    memory_id=memory_id,
    reason='Created by Adaptive Memory v3 extraction'
)
```

**Consolidation (promoting to long-term)**:
```python
# NEW - create in long-term
long_term_id = await friday_system.create_memory(
    content=memory_content,
    memory_type=category,
    importance_level=importance,
    tags=tags,
    source_conversation_id=conv_id
)

# NEW - track the relationship
await friday_system.link_memory_to_conversation(
    memory_id=long_term_id,
    conversation_id=conv_id,
    link_type='promoted',
    source_system='openwebui_adaptive_memory_v3',
    metadata={'promoted_from_short_term': short_term_id}
)

# NEW - log the promotion
await friday_system.log_processing_attempt(
    conversation_id=conv_id,
    processing_type='memory_promotion',
    status='success',
    memory_id=long_term_id,
    reason=f'Promoted from short-term memory'
)
```

---

## Implementation Order

1. **Easy**: Add linking after memory creation (just append call)
2. **Medium**: Add long-term search to inlet function (search if short-term sparse)
3. **Advanced**: Add consolidation/promotion logic (when OpenWebUI consolidates memories)

We can do #1 and #2 now, leave #3 for later when you want memory consolidation.

---

## Does This Make Sense?

Key points to confirm:
- ✅ Adaptive Memory v3's LLM intelligence is NOT changed
- ✅ We're just giving it better context (long-term search)
- ✅ We're tracking lineage (promoted_from_short_term, source_conversation_id)
- ✅ Human-like behavior: immediate recall + related recall + consolidation
- ✅ All failures are non-blocking
- ✅ No breaking changes to existing functionality

Ready to code it up?
