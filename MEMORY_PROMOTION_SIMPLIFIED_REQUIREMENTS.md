# Memory Promotion System - Simplified Requirements (Using Existing Infrastructure)

**Status:** Corrected requirements based on existing implementation  
**Date:** December 4, 2025  
**Key Finding:** Friday Memory System already handles conversation tracking with user_id and model_id. Short-term system needs to reference these existing IDs.

---

## What Already Exists in Friday Memory System

### 1. Conversations with Full Tracking
**Location:** `ConversationDatabase` in `friday_memory_system.py`

**Current Schema:**
```sql
CREATE TABLE conversations (
    conversation_id TEXT PRIMARY KEY,        -- UUID, auto-generated
    session_id TEXT NOT NULL,                -- Groups related conversations
    start_timestamp TEXT NOT NULL,           -- When conversation started
    end_timestamp TEXT,                      -- When conversation ended (optional)
    topic_summary TEXT,                      -- AI-generated summary
    user_id TEXT,                            -- Which user this conversation belongs to
    model_id TEXT,                           -- Which model was used
    embedding BLOB,                          -- Conversation summary embedding
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

**Already Doing:**
- ✅ Auto-generating `conversation_id` (UUID)
- ✅ Tracking `user_id` for each conversation
- ✅ Tracking `model_id` for each conversation
- ✅ Storing start and end timestamps
- ✅ Generating topic summaries

### 2. Messages Linked to Conversations
```sql
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,          -- Links to conversation
    timestamp TEXT NOT NULL,
    role TEXT NOT NULL,                     -- "user" or "assistant"
    content TEXT NOT NULL,
    source_type TEXT NOT NULL,              -- "ollama", "lmstudio", etc.
    user_id TEXT,                           -- Which user
    model_id TEXT,                          -- Which model
    ...
    FOREIGN KEY (conversation_id) REFERENCES conversations
)
```

### 3. Memory-Conversation Linking
```sql
CREATE TABLE memory_conversation_links (
    link_id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,          -- Links memory to conversation
    link_type TEXT NOT NULL,                -- "direct", "related", "enhanced"
    link_strength REAL DEFAULT 1.0,         -- Confidence 0.0-1.0
    source_system TEXT,                     -- "openwebui_promotion", "processed_from_chat"
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations
)
```

### 4. Memory Promotion Already Implemented
**Location:** `_promote_old_memories_loop()` in `friday_memory_short_term.py`

**Current Features:**
- ✅ Runs on configurable interval: `memory_promotion_interval` (currently 86400 seconds)
- ✅ Promotes memories older than threshold: `memory_promotion_age_threshold_days` (currently 90 days)
- ✅ Creates memories in Friday system with promotion metadata
- ✅ Cleans up promoted memories from short-term (if `clean_promoted_memories` is True)
- ✅ Tracks promoted memories with "promoted" and "archived" tags

---

## What's Actually Missing (The Real Problem)

### 1. Short-Term Memories Don't Have Conversation Context
**Problem:**
- Short-term memories are extracted from chat but don't know which conversation they came from
- When promoted to long-term, they use generic `source_conversation_id=f"openwebui_user_{user_id}"` 
- This makes it impossible to:
  - Query "what memories were created during THIS specific conversation?"
  - Link memory back to the actual conversation it came from
  - Track memory creation context across conversation boundaries

**Current Code (Line 2617):**
```python
# This doesn't use the actual conversation context!
result = await memory_system.create_memory(
    content=memory_content,
    importance_level=5,
    memory_type="archived",
    source_conversation_id=f"openwebui_user_{user_id}",  # ❌ Generic, not conversation-specific
    tags=["promoted", "archived"],
    wait_for_embedding=True
)
```

### 2. Short-Term System Doesn't Know Conversation IDs
**Problem:**
- OpenWebUI short-term plugin doesn't have access to Friday's `conversation_id`
- Each time a memory is extracted in short_term.py, we don't know which Friday conversation it belongs to
- We're tracking the memory but losing the conversation context

### 3. Model_id Flow is Incomplete
**Problem:**
- When a model creates a memory, we should track which model it was
- Friday system has `model_id` on conversations and messages
- Short-term memories should also reference the model that created them

---

## Solution: Use Existing Infrastructure Properly

### Phase 1: Get Conversation ID in Short-Term Plugin

**Approach:**
1. Get `conversation_id` from the body when available (check OpenWebUI fields)
2. Generate one using user_id + timestamp if not provided
3. Store it with every short-term memory

**In `inlet()` function, extract conversation_id:**
```python
async def inlet(self, body: Dict[str, Any], __event_emitter__=None, __user__=None):
    # ... existing code ...
    
    # NEW: Get or generate conversation_id
    # Try to get from OpenWebUI body (check various possible field names)
    conversation_id = (
        body.get("conversation_id") or 
        body.get("chat_id") or 
        body.get("session_id") or 
        self._get_or_generate_conversation_id(__user__)  # Fallback
    )
    
    # Store in body for use throughout inlet/outlet
    body["_friday_conversation_id"] = conversation_id
    body["_friday_user_id"] = user_id
    body["_friday_model_id"] = self.valves.llm_model_name
```

**Helper function:**
```python
def _get_or_generate_conversation_id(self, __user__):
    """
    Get or generate a stable conversation_id for this user.
    Uses a session timeout approach to determine conversation boundaries.
    """
    import time
    
    user_id = __user__.get("id", "unknown")
    current_time = time.time()
    SESSION_TIMEOUT = 30 * 60  # 30 minutes
    
    if not hasattr(self, "_user_sessions"):
        self._user_sessions = {}
    
    if user_id not in self._user_sessions:
        # Create new session
        conv_id = f"conv_{user_id}_{int(current_time)}"
        self._user_sessions[user_id] = {
            "conversation_id": conv_id,
            "last_activity": current_time,
            "message_count": 0
        }
        logger.debug(f"Created new conversation session: {conv_id}")
        return conv_id
    
    session = self._user_sessions[user_id]
    
    # Check if session expired
    if current_time - session["last_activity"] > SESSION_TIMEOUT:
        # Start new conversation
        conv_id = f"conv_{user_id}_{int(current_time)}"
        self._user_sessions[user_id] = {
            "conversation_id": conv_id,
            "last_activity": current_time,
            "message_count": 0
        }
        logger.debug(f"Session expired, created new: {conv_id}")
        return conv_id
    
    # Update last activity and return current conversation
    session["last_activity"] = current_time
    session["message_count"] += 1
    return session["conversation_id"]
```

### Phase 2: Store Conversation ID in Short-Term Memories

**When extracting memories, include conversation context:**

```python
# In _process_user_memories():

conversation_id = body.get("_friday_conversation_id", "unknown")
user_id = __user__.get("id")
model_id = self.valves.llm_model_name

# Store metadata with memory
memory_metadata = {
    "conversation_id": conversation_id,
    "user_id": user_id,
    "model_id": model_id,
    "created_in_short_term": True,
    "created_at": datetime.now(timezone.utc).isoformat()
}

# When creating memory (pseudo-code)
await store_memory(
    content=memory_content,
    user_id=user_id,
    model_id=model_id,
    metadata=memory_metadata
)
```

### Phase 3: Promote with Full Context

**Update promotion loop to use actual conversation context:**

```python
# In _promote_old_memories_loop():

for mem in old_memories:
    # EXISTING: Extract content and metadata
    memory_content = mem.get("memory", "")
    
    # NEW: Get the conversation_id from memory metadata
    conversation_id = mem.get("metadata", {}).get("conversation_id") or f"openwebui_user_{user_id}"
    model_id = mem.get("metadata", {}).get("model_id") or "unknown"
    
    # UPDATED: Use actual conversation context
    result = await memory_system.create_memory(
        content=memory_content,
        importance_level=5,
        memory_type="archived",
        conversation_id=conversation_id,  # ✅ USE ACTUAL CONVERSATION ID
        tags=["promoted", "archived"],
        user_id=user_id,                  # ✅ PASS USER ID
        model_id=model_id,                # ✅ PASS MODEL ID
        wait_for_embedding=True
    )
    
    # Link to conversation in Friday system
    if result.get("status") == "success":
        memory_id = result.get("memory_id")
        try:
            await memory_system.link_memory_to_conversation(
                memory_id=memory_id,
                conversation_id=conversation_id,
                link_type="promoted_from_short_term",
                source_system="openwebui_promotion",
                metadata={
                    "promoted_at": datetime.now(timezone.utc).isoformat(),
                    "user_id": user_id,
                    "model_id": model_id
                }
            )
        except Exception as e:
            logger.warning(f"Could not link promoted memory: {e}")
    
    # NOW: Delete from short-term after successful promotion
    if self.valves.clean_promoted_memories:
        try:
            await delete_short_term_memory(mem["id"], user_id)
            logger.info(f"Deleted short-term memory {mem['id']} after promotion")
        except Exception as e:
            logger.warning(f"Could not delete short-term memory: {e}")
```

---

## Implementation Checklist

### Priority 1: Integration with Existing Systems
- [ ] Modify `inlet()` to extract or generate `conversation_id`
- [ ] Add `_get_or_generate_conversation_id()` helper
- [ ] Store conversation_id in body as `_friday_conversation_id`
- [ ] Modify memory extraction to include conversation_id metadata
- [ ] Test conversation boundary detection (30-minute timeout)

### Priority 2: Update Promotion Loop
- [ ] Modify `_promote_old_memories_loop()` to extract conversation_id from memory metadata
- [ ] Pass `user_id` and `model_id` to `create_memory()`
- [ ] Pass `conversation_id` instead of generic string
- [ ] Call `link_memory_to_conversation()` after promotion
- [ ] Ensure cleanup happens AFTER successful promotion and linking
- [ ] Add logging for promotion success/failure with full context

### Priority 3: Validation & Testing
- [ ] Verify promoted memories show correct conversation_id in Friday system
- [ ] Verify memories are linked to correct conversations
- [ ] Test that memory queries by conversation_id work
- [ ] Test user_id and model_id are preserved in promoted memories
- [ ] Test cleanup actually deletes short-term copies

---

## Key Benefits of This Approach

1. **Uses Existing Infrastructure**
   - No new database schema changes needed
   - Friday system already has all the tracking (user_id, model_id, conversation_id)
   - Memory-conversation links already exist

2. **Preserves Full Context**
   - Every memory knows which conversation it came from
   - Every memory knows which user created it
   - Every memory knows which model created it
   - Complete audit trail maintained

3. **Enables Rich Queries**
   - Query all memories from specific conversation
   - Query all memories for specific user across all conversations
   - Query all memories created by specific model
   - Date-based queries within conversation context

4. **Clean Memory Lifecycle**
   - Short-term → Long-term promotion with full context
   - Automatic cleanup of short-term after promotion
   - No data loss or context loss during migration
   - Always searchable and retrievable

5. **Respects User/Model Isolation**
   - Different users have separate conversations
   - Different models have separate conversation traces
   - model_id filtering works throughout the system

---

## Valves Already Configured

These already exist in `friday_memory_short_term.py` Valves:

```python
enable_memory_promotion: bool = Field(default=True)
memory_promotion_interval: int = Field(default=86400)  # 1 day in seconds
memory_promotion_age_threshold_days: int = Field(default=90)
clean_promoted_memories: bool = Field(default=True)
max_total_memories: int = Field(default=200)  # Max per user before pruning
```

**No new valves needed** - the promotion behavior is fully configurable.

---

## Data Flow After Changes

```
User sends message in OpenWebUI
    ↓
inlet() captures conversation_id (or generates)
    ↓
Store in body._friday_conversation_id
    ↓
Memory extracted with conversation context
    ↓
Short-term memory created with:
    - conversation_id
    - user_id  
    - model_id
    ↓
[90 days pass or max memories reached]
    ↓
_promote_old_memories_loop() triggers
    ↓
Promotion API called with:
    - conversation_id ✓
    - user_id ✓
    - model_id ✓
    - Full metadata preserved ✓
    ↓
Memory created in Friday system
    ↓
Linked to conversation via memory_conversation_links ✓
    ↓
Short-term memory deleted ✓
    ↓
Result: Complete context preserved, only long-term exists
```

---

## Summary

**What Friday System Already Does:**
- ✅ Stores conversations with unique IDs
- ✅ Tracks user_id and model_id on conversations
- ✅ Provides conversation-memory linking
- ✅ Supports memory promotion with intervals and age thresholds
- ✅ Cleans up promoted memories on request

**What Short-Term System Needs to Do:**
1. Extract or generate conversation_id in inlet()
2. Include conversation_id in memory metadata
3. Pass conversation_id to promotion API
4. Call link_memory_to_conversation() after promotion
5. Ensure cleanup happens after successful promotion

**No reimplementation needed** - just use the existing infrastructure properly and consistently.
