# Memory Promotion System - Corrected Requirements & Architecture

**Status:** Requirements document for implementation  
**Date:** December 4, 2025  
**Purpose:** Define correct behavior for memory promotion from short-term to long-term storage

---

## Current Issues with Promotion API

The current `/api/memories/promote` endpoint has these problems:

1. **Conversation ID is optional** - Should be MANDATORY
2. **No automatic cleanup** - Promoted short-term memories are not deleted
3. **No auto-promotion rules** - Memories aren't automatically promoted after 90 days or at 3K limit
4. **Cleanup API exists** - DELETE endpoint for long-term memories should NOT exist
5. **Missing linking requirement** - Both systems need to know which conversation they're part of

---

## Required Architecture Changes

### 1. Conversation ID Requirement

**Current State:**
- OpenWebUI passes messages in `body["messages"]` array
- No explicit conversation_id in the request
- Short-term system has access to user_id but not conversation tracking

**What's Available in OpenWebUI:**
```python
# In inlet/outlet, we have access to:
body = {
    "messages": [...],      # Full message history
    "model": "...",         # Model name
    "stream": True/False,   # Streaming indicator
    "user": {...}          # User info from __user__ parameter
}

# Missing: conversation_id or session_id
# We need to DERIVE or GENERATE this
```

**Solution - Multiple Approaches:**

Option A: **OpenWebUI native conversation tracking**
- OpenWebUI may have a conversation_id in the WebUI layer
- Need to check if it can be passed through the plugin interface
- Would require OpenWebUI modification/extension

Option B: **Generate from message history hash** (Recommended for now)
- Create a stable conversation_id from session context
- Hash the first message in the conversation
- Tie to user_id + timestamp of conversation start

Option C: **Use timestamp-based sessions**
- Start new conversation_id when no messages received for X minutes
- Track active sessions per user
- Simple but prone to session fragmentation

**RECOMMENDATION: Hybrid approach**
- Store session state in short_term.py per user
- Track "current conversation" based on message flow
- When new session detected (gap > 30min or explicit reset), create new conversation_id
- Format: `conv_{user_id}_{start_timestamp}`

### 2. Mandatory Conversation ID in Promotion

**Current Code (WRONG):**
```python
conversation_id = body.get("conversation_id") or body.get("source_conversation_id")  # Optional!
```

**Required Code:**
```python
# Conversation ID MUST be provided
if not conversation_id or not conversation_id.strip():
    raise HTTPException(
        status_code=400, 
        detail="conversation_id is REQUIRED for memory promotion. Cannot promote memory without conversation context."
    )
```

**Updated Promotion Endpoint:**
```json
POST /api/memories/promote
{
  "content": "Memory content (required)",
  "conversation_id": "conv_user123_1733350800 (REQUIRED - format: conv_{user_id}_{start_timestamp})",
  "memory_type": "Optional: memory type",
  "tags": ["optional"],
  "memory_bank": "Optional: Personal|Work|General|Context|Tasks"
}
```

### 3. Automatic Short-Term Memory Cleanup

**After Successful Promotion:**
- Short-term memory entry should be DELETED
- Only long-term copy remains
- This prevents duplicate storage and confusion

**Current Flow:**
```
User promotes memory
  ↓
Memory stored in long-term database
  ↓
Short-term memory still exists (WRONG!)
```

**Required Flow:**
```
User promotes memory
  ↓
Memory stored in long-term database ✓
  ↓
Short-term memory deleted ✓
  ↓
Only long-term memory exists
```

**Implementation:**
```python
# In promote_memory endpoint, after successful long-term creation:
try:
    # Get the short-term memory ID (if provided)
    short_term_memory_id = body.get("short_term_memory_id")
    
    if short_term_memory_id:
        # Delete from short-term storage
        await delete_short_term_memory(short_term_memory_id, user_id)
        logger.info(f"✅ Deleted short-term memory {short_term_memory_id} after promotion")
except Exception as e:
    logger.warning(f"Could not delete short-term memory (non-blocking): {e}")
    # Don't fail promotion if cleanup fails - the long-term copy exists
```

### 4. Auto-Promotion Rules

**Requirements:**
- Memories automatically promoted after 90 days
- OR when short-term storage reaches 3,000 memories per user
- OR when memory_bank fill ratio reaches threshold

**NOT Deletion - Promotion:**
- These memories should move to long-term, NOT be deleted
- They should be searchable in both systems during transition
- After promotion, only accessible through long-term system

**Implementation Location:** `friday_memory_short_term.py`

```python
class Filter:
    class Valves(BaseModel):
        # ... existing valves ...
        
        # Auto-promotion configuration
        enable_auto_promotion: bool = Field(
            default=True,
            description="Automatically promote memories to long-term storage"
        )
        
        auto_promotion_age_days: int = Field(
            default=90,
            description="Promote memories older than N days to long-term"
        )
        
        auto_promotion_max_short_term_memories: int = Field(
            default=3000,
            description="Maximum short-term memories per user before promoting oldest"
        )
        
        auto_promotion_batch_size: int = Field(
            default=100,
            description="Number of memories to promote in each batch"
        )
        
        auto_promotion_api_endpoint: str = Field(
            default="http://127.0.0.1:12345/api/memories/promote",
            description="Endpoint to call for automatic promotions"
        )
        
        auto_promotion_api_key: str = Field(
            default=None,
            description="API key for automatic promotions (from mcpo_api_key.txt)"
        )
```

**Background Task:**
```python
async def _auto_promotion_loop(self):
    """
    Background task that periodically:
    1. Identifies memories older than auto_promotion_age_days
    2. OR checks if short-term storage exceeds auto_promotion_max_short_term_memories
    3. Promotes qualifying memories to long-term
    4. Deletes from short-term after successful promotion
    """
    while True:
        try:
            if not self.valves.enable_auto_promotion:
                await asyncio.sleep(3600)  # Check every hour
                continue
            
            # For each user, check if promotion needed
            for user_id in self.get_active_user_ids():
                # Count short-term memories
                short_term_count = await self.count_short_term_memories(user_id)
                
                # Check conditions
                promote_due_to_count = short_term_count >= self.valves.auto_promotion_max_short_term_memories
                
                # Get memories older than threshold
                old_memories = await self.get_memories_older_than_days(
                    user_id, 
                    self.valves.auto_promotion_age_days
                )
                promote_due_to_age = len(old_memories) > 0
                
                # If either condition met, start promotion
                if promote_due_to_count or promote_due_to_age:
                    await self._promote_batch_of_memories(
                        user_id,
                        old_memories if promote_due_to_age else None,
                        batch_size=self.valves.auto_promotion_batch_size
                    )
            
            # Run every 6 hours
            await asyncio.sleep(21600)
            
        except Exception as e:
            logger.error(f"Error in auto-promotion loop: {e}")
            await asyncio.sleep(3600)  # Retry after 1 hour

async def _promote_batch_of_memories(self, user_id: str, memories=None, batch_size: int = 100):
    """Promote a batch of memories to long-term"""
    memories_to_promote = memories or []
    
    promoted_count = 0
    for memory in memories_to_promote[:batch_size]:
        try:
            # Call promotion API
            payload = {
                "content": memory["content"],
                "conversation_id": memory.get("conversation_id"),
                "tags": memory.get("tags", []) + ["auto_promoted"],
                "memory_bank": memory.get("memory_bank", "General"),
                "memory_type": memory.get("memory_type"),
                "short_term_memory_id": memory["id"]  # For cleanup
            }
            
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.valves.auto_promotion_api_endpoint,
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        promoted_count += 1
                        logger.info(f"✅ Auto-promoted memory {memory['id']}")
                    else:
                        logger.warning(f"Failed to auto-promote memory {memory['id']}: {response.status}")
        
        except Exception as e:
            logger.error(f"Error auto-promoting memory {memory.get('id')}: {e}")
    
    logger.info(f"✅ Auto-promoted {promoted_count}/{len(memories_to_promote)} memories for user {user_id}")
```

### 5. Memory Linking by Conversation & Date

**Current State:**
- `source_conversation_id` field exists in create_memory
- Linking to conversations via `link_memory_to_conversation()` exists
- BUT: conversation_id is optional and often NULL

**Required Changes:**

**A. In create_memory (friday_memory_system.py):**
```python
async def create_memory(self, content: str, memory_type: str = None,
                       importance_level: int = 5, tags: List[str] = None,
                       conversation_id: str = None,  # RENAME from source_conversation_id
                       memory_bank: str = "General",
                       user_id: str = None, model_id: str = None) -> Dict:
    """
    Create a curated memory.
    
    IMPORTANT: conversation_id should be provided to enable:
    - Linking memory to source conversation
    - Cross-referencing across the conversation
    - Finding all memories from a specific conversation
    """
    
    # Validate conversation_id is provided
    if not conversation_id:
        logger.warning(
            f"Creating memory without conversation_id - "
            f"memory will not be linked to conversation context. "
            f"This may reduce searchability and context."
        )
    
    memory_id = await self.ai_memory_db.create_memory(
        content, memory_type, importance_level, tags, 
        conversation_id=conversation_id,  # RENAMED
        memory_bank=memory_bank, 
        user_id=user_id, 
        model_id=model_id
    )
    
    # Automatically link to conversation if provided
    if conversation_id:
        try:
            await self.link_memory_to_conversation(
                memory_id=memory_id,
                conversation_id=conversation_id,
                link_type="created_during_conversation",
                link_strength=1.0,
                metadata={
                    "memory_bank": memory_bank,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "promotion_source": "short_term" if tags and "promoted" in tags else "manual"
                }
            )
        except Exception as e:
            logger.warning(f"Could not link memory {memory_id} to conversation: {e}")
```

**B. Querying by Conversation:**
```python
async def get_memories_by_conversation(self, conversation_id: str, user_id: str = None) -> List[Dict]:
    """
    Retrieve all memories created during a specific conversation.
    
    Uses:
    - Conversation links in memory_links table
    - Filters by conversation_id and optionally user_id
    - Returns memories in chronological order
    """
    query = """
        SELECT DISTINCT m.* FROM curated_memories m
        JOIN memory_links ml ON m.id = ml.memory_id
        WHERE ml.conversation_id = ?
        ORDER BY m.created_at DESC
    """
    
    params = [conversation_id]
    if user_id:
        query = query.replace("WHERE", "WHERE m.user_id = ? AND")
        params.insert(0, user_id)
    
    results = await self.ai_memory_db.execute_query(query, tuple(params))
    return [dict(row) for row in results]

async def get_memories_by_date_range(self, start_date: str, end_date: str, 
                                     conversation_id: str = None,
                                     user_id: str = None) -> List[Dict]:
    """
    Retrieve memories created within a date range.
    
    Optionally filtered by:
    - conversation_id: memories from a specific conversation
    - user_id: memories for a specific user
    """
    query = """
        SELECT * FROM curated_memories
        WHERE created_at BETWEEN ? AND ?
    """
    params = [start_date, end_date]
    
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    
    if conversation_id:
        query = f"""
            {query.replace('WHERE created_at', 
            'WHERE m.id IN (SELECT memory_id FROM memory_links WHERE conversation_id = ?) AND created_at')}
        """
        params.insert(0, conversation_id)
    
    query += " ORDER BY created_at DESC"
    results = await self.ai_memory_db.execute_query(query, tuple(params))
    return [dict(row) for row in results]
```

---

## Conversation ID Strategy for OpenWebUI

### Current Limitation
OpenWebUI doesn't provide a native conversation_id in the plugin interface. We need to generate one.

### Recommended Implementation

**1. Session Tracking in short_term.py:**
```python
class Filter:
    def __init__(self):
        # ... existing init ...
        
        # Track active conversations per user
        self._active_conversations: Dict[str, Dict[str, Any]] = {}
        # Format: {user_id: {"current_id": "conv_...", "start_time": ..., "last_message_time": ...}}
```

**2. Generate or Get Conversation ID:**
```python
def _get_or_create_conversation_id(self, user_id: str, messages: List[Dict]) -> str:
    """
    Get the current conversation ID or create a new one.
    
    Logic:
    - If no active conversation for this user, create new one
    - If conversation has been idle > 30 minutes, start new one
    - Otherwise, use existing conversation_id
    """
    
    now = time.time()
    SESSION_TIMEOUT = 30 * 60  # 30 minutes
    
    if user_id not in self._active_conversations:
        # Create new conversation
        conv_id = f"conv_{user_id}_{int(now)}"
        self._active_conversations[user_id] = {
            "current_id": conv_id,
            "start_time": now,
            "last_message_time": now,
            "message_count": 0
        }
        logger.info(f"🆕 Created new conversation: {conv_id}")
        return conv_id
    
    # Check if conversation has timed out
    conv_data = self._active_conversations[user_id]
    if now - conv_data["last_message_time"] > SESSION_TIMEOUT:
        # Start new conversation
        conv_id = f"conv_{user_id}_{int(now)}"
        self._active_conversations[user_id] = {
            "current_id": conv_id,
            "start_time": now,
            "last_message_time": now,
            "message_count": 0
        }
        logger.info(f"🔄 Session timeout - created new conversation: {conv_id}")
        return conv_id
    
    # Update last message time and return current conversation
    conv_data["last_message_time"] = now
    conv_data["message_count"] += len(messages) if messages else 0
    return conv_data["current_id"]
```

**3. Store in Memory Metadata:**
```python
# When creating memories in _process_user_memories:
conversation_id = self._get_or_create_conversation_id(user_id, body.get("messages", []))

# Store with every memory:
memory_metadata = {
    "conversation_id": conversation_id,
    "user_id": user_id,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "promoted_from_short_term": False
}

# Pass to create_memory:
await friday_memory_system.create_memory(
    content=content,
    conversation_id=conversation_id,  # Now mandatory!
    memory_bank=memory_bank,
    user_id=user_id,
    model_id=self.valves.llm_model_name
)
```

---

## Updated Promotion Endpoint Spec

### Endpoint
```
POST /api/memories/promote
```

### Request (Updated)
```json
{
  "content": "Memory content to promote (required)",
  "conversation_id": "conv_user123_1733350800 (REQUIRED)",
  "short_term_memory_id": "Optional: ID in short-term storage for cleanup",
  "memory_type": "Optional: memory type or category",
  "tags": ["Optional", "tags"],
  "memory_bank": "Optional: Personal|Work|General|Context|Tasks (default: General)"
}
```

### Response (Updated)
```json
{
  "status": "success",
  "memory_id": "uuid-of-created-memory",
  "conversation_id": "conv_user123_1733350800",
  "importance_level": 8,
  "memory_bank": "Personal",
  "short_term_memory_deleted": true,
  "link_id": "uuid-of-conversation-link",
  "message": "Memory promoted to long-term storage, linked to conversation, and removed from short-term"
}
```

### Changes Made
1. ✅ conversation_id is now REQUIRED (not optional)
2. ✅ Accepts short_term_memory_id for automatic cleanup
3. ✅ Automatically links to conversation
4. ✅ Confirms deletion of short-term copy
5. ✅ NO DELETE endpoint for long-term memories

---

## Implementation Checklist

### Phase 1: Conversation ID Generation (Priority 1)
- [ ] Add `_active_conversations` tracking to Filter.__init__()
- [ ] Implement `_get_or_create_conversation_id()` method
- [ ] Modify inlet() to generate conversation_id for all memories
- [ ] Update create_memory() calls to always pass conversation_id
- [ ] Test conversation boundaries (30-minute timeout)

### Phase 2: Update Memory Linking (Priority 1)
- [ ] Rename parameter from `source_conversation_id` to `conversation_id` in create_memory()
- [ ] Auto-link memories to conversation during creation
- [ ] Implement `get_memories_by_conversation()` query
- [ ] Implement `get_memories_by_date_range()` query

### Phase 3: Update Promotion API (Priority 2)
- [ ] Make conversation_id REQUIRED in promote_memory endpoint
- [ ] Add short_term_memory_id parameter
- [ ] Implement automatic short-term cleanup after promotion
- [ ] Update response to confirm all actions
- [ ] Remove/disable DELETE endpoint for long-term memories

### Phase 4: Auto-Promotion Rules (Priority 2)
- [ ] Add auto-promotion valves to Filter.Valves
- [ ] Implement `_auto_promotion_loop()` background task
- [ ] Implement `_promote_batch_of_memories()` method
- [ ] Add memory counting and aging queries
- [ ] Test promotion triggers (90 days, 3K limit)

### Phase 5: Documentation Updates (Priority 3)
- [ ] Update MEMORY_PROMOTION_API.md with new spec
- [ ] Create auto-promotion documentation
- [ ] Document conversation ID generation strategy
- [ ] Create migration guide for existing memories

---

## Success Criteria

1. ✅ All memories have a valid conversation_id
2. ✅ Conversation_id is REQUIRED for promotion
3. ✅ Promoted memories are automatically deleted from short-term
4. ✅ Old memories auto-promote after 90 days OR at 3K limit
5. ✅ Memories are linked by conversation AND date
6. ✅ Can query all memories from specific conversation
7. ✅ Can query all memories from date range
8. ✅ NO API endpoint to delete long-term memories
9. ✅ All memories always searchable (in long-term if promoted)

---

## Migration Considerations

**For Existing Memories:**
1. Identify memories without conversation_id
2. Generate retroactive conversation IDs based on created_at timestamp + user_id
3. Optionally link them to inferred conversations
4. Add warning that pre-migration memories may have incomplete conversation context

---

## Notes

- **Conversation_id format:** `conv_{user_id}_{unix_timestamp}` ensures uniqueness and sortability
- **30-minute timeout:** Can be made configurable via valves if needed
- **Auto-promotion:** Non-blocking, errors don't interrupt service
- **Linking:** Both ways enabled (memory→conversation, conversation→memory)
- **Search:** Both systems fully integrated for seamless search experience
