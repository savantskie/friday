# Lazy Remediation Strategy

**Updated**: November 1, 2025

## Overview

Phase 2a implements a **two-tier import system** to keep regular imports fast while still remediating old data:

### Tier 1: Quick Import (Runs Anytime)
- **Function**: `import_openwebui_chat_history()`
- **Purpose**: Import only NEW messages from OpenWebUI
- **Speed**: FAST (seconds to minutes)
- **Deduplication**: Hash-based (SHA256 of chat_id:msg_id:content)
- **Frequency**: Can run multiple times without issues
- **Result**: New messages added with correct isolation format

### Tier 2: Lazy Remediation (Runs During Idle)
- **Function**: `verify_and_remediate_chat_isolation()`
- **Purpose**: Retroactively fix old messages with wrong isolation
- **Speed**: SLOW (minutes to hours depending on database size)
- **Frequency**: Only during idle periods (when system has spare cycles)
- **When to Schedule**: Implement idle-time detector (future work)
- **Result**: Old messages re-aligned to new user+model format

---

## Why Separate?

### Before Phase 2a
```python
# Old code - did BOTH every time:
async def import_openwebui_chat_history():
    # Extract and validate all 139 chats
    # Re-import all messages (slow)
    # Check each message for duplicates (slow)
    # Try to remediate old ones too (very slow)
    # Result: Can't run frequently
```

### After Phase 2a
```python
# New code - separates concerns:
# Tier 1 (Quick):
async def import_openwebui_chat_history():
    # Load existing message hashes (fast)
    # Only check new chat entries (fast)
    # Only import messages not in hash set (fast)
    # Result: Can run every 5 minutes or even constantly

# Tier 2 (Lazy):
async def verify_and_remediate_chat_isolation():
    # Full scan of all imported messages (slow)
    # Check which ones need re-alignment (slow)
    # Move messages to correct buckets (slow)
    # Update links (slow)
    # Result: Runs once daily during idle, or on-demand
```

---

## Example Scenario

### Day 1: Old Import (Before Phase 2a)
```
OpenWebUI chats in webui.db:
  Chat A (Friday): [msg1, msg2, msg3]
  Chat B (Tara):   [msg4, msg5]

Friday DB after import:
  conversation_id="chatA"  # WRONG - no user/model isolation
    └─ message1, message2, message3

  conversation_id="chatB"  # WRONG - no user/model isolation
    └─ message4, message5
```

### Day 2: Phase 2a Deployed
```
Tier 1 runs (Quick Import):
  - Loads hash set of existing messages
  - Sees 5 messages already imported (all have hashes in metadata)
  - Result: 0 new imports (already have them all)

Tier 2 available but NOT scheduled yet:
  - Would fix message1-5 to use {user_uuid}_friday and {user_uuid}_tara
  - But we're not running it yet (no idle scheduler)
```

### Day 3: New Chat as Friday
```
User creates new chat as Friday with 'llama3.1' model:
  [msg6, msg7] in OpenWebUI

Tier 1 runs (Quick Import):
  - Hashes msg6, msg7: not in existing hash set
  - Creates new bucket: {friday_uuid}_llama3.1
  - Imports msg6, msg7 with correct isolation
  - Result: 2 new messages, correct format

Friday DB now:
  conversation_id="chatA"           # Old - wrong format
    └─ message1, message2, message3 # Old - wrong format
  
  conversation_id="chatB"           # Old - wrong format
    └─ message4, message5           # Old - wrong format
  
  conversation_id="{uuid}_llama3.1" # NEW - correct format
    └─ message6, message7
```

### Day 4: Idle Time (Late Night)
```
System detects idle period (3 AM, no active chats)

Tier 2 runs (Lazy Remediation):
  - Scans ALL messages (slow operation)
  - Finds message1-5 in old format
  - For each:
    - Looks up chat_id in metadata
    - Queries OpenWebUI for chat details
    - Extracts user_id and model
    - Creates new bucket: {user_uuid}_{model}
    - Moves message to new bucket
    - Updates all foreign key references
  - Result: message1-5 remediates to correct buckets

Friday DB now:
  conversation_id="{uuid}_friday"       # FIXED
    └─ message1, message2, message3
  
  conversation_id="{uuid}_tara"         # FIXED
    └─ message4, message5
  
  conversation_id="{uuid}_llama3.1"     # Already correct
    └─ message6, message7
```

---

## Implementation Details

### Quick Import (Tier 1)
```python
# Build set of existing message hashes (fast check)
existing_hashes = set()
existing_msgs = await query(
    "SELECT json_extract(metadata, '$.openwebui_message_hash') 
     FROM messages WHERE source_type = 'openwebui'"
)
for msg in existing_msgs:
    if msg_hash:
        existing_hashes.add(msg_hash)

# For each chat in OpenWebUI:
for chat_id, chat_data in chats.items():
    for msg_id, msg_data in chat_data.messages:
        # Create hash: deterministic identifier
        msg_hash = SHA256(f"{chat_id}:{msg_id}:{content}").hex()
        
        # Skip if already imported
        if msg_hash in existing_hashes:
            continue  # Already have this message
        
        # Import with correct isolation format
        conversation_id = f"{user_id}_{model_name}"
        await store_message(
            conversation_id=conversation_id,
            metadata={'openwebui_message_hash': msg_hash, ...}
        )
        existing_hashes.add(msg_hash)
```

### Lazy Remediation (Tier 2)
```python
# Find all old-format messages
old_messages = await query(
    "SELECT * FROM messages 
     WHERE source_type = 'openwebui' 
     AND conversation_id NOT LIKE '%_%'"  # Old format: no underscore
)

# For each old message:
for msg in old_messages:
    chat_id = json_extract(msg.metadata, '$.chat_id')
    
    # Look up original chat in OpenWebUI
    original_chat = openwebui_db.query(f"SELECT user_id, models FROM chat WHERE id = {chat_id}")
    
    # Extract isolation info
    user_id = original_chat.user_id
    model = original_chat.models[0].split('/')[-1]
    new_conversation_id = f"{user_id}_{model}"
    
    # Move message to new bucket
    await db.execute(
        "UPDATE messages SET conversation_id = ? WHERE message_id = ?",
        (new_conversation_id, msg.message_id)
    )
    
    # Update conversation links if exists
    # Update session associations
    # ... update all foreign key references
```

---

## Scheduling Remediation

### When to Run
The remediation function should run when:
1. ✅ System has been idle for N minutes (no active chats)
2. ✅ CPU usage is below threshold
3. ✅ No background tasks running
4. ✅ System is not handling concurrent requests

### Options for Implementation

#### Option A: Event Loop Background Task (Preferred)
```python
async def background_remediation_task():
    while True:
        # Wait for idle condition
        idle_time = check_system_idle_time()
        
        if idle_time > 300:  # 5+ minutes idle
            print("System idle, starting remediation...")
            await memory_system.verify_and_remediate_chat_isolation()
            await asyncio.sleep(3600)  # Don't run more than hourly
        
        await asyncio.sleep(60)  # Check every minute
```

#### Option B: Scheduled Task (Simple)
```python
# Run once per day at 3 AM
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(
    remediation_job,
    'cron',
    hour=3,
    minute=0,
    name='lazy_remediation'
)
scheduler.start()
```

#### Option C: Manual Trigger
```python
# CLI command or admin endpoint
# Allows on-demand remediation if needed
@app.post("/admin/remediate")
async def trigger_remediation():
    stats = await memory_system.verify_and_remediate_chat_isolation()
    return stats
```

---

## Current Status

### ✅ Implemented
- Hash-based deduplication in quick import
- Lazy remediation function created
- Test validates 4,018 messages with isolation format

### ⏳ Pending
- Idle-time detection system
- Scheduler integration (Background task or cron)
- Monitoring/logging for remediation runs
- Dashboard showing remediation progress

### 📊 Metrics to Track
- Import run count vs remediation run count
- Messages remediated per run
- Time taken for each operation
- Hash collision rate (should be ~zero)
- Bucket balance (messages per user+model)

---

## Expected Performance

### Quick Import
- **Database with 10,000 messages**: 5-10 seconds
- **Database with 100,000 messages**: 30-60 seconds
- **Database with 1,000,000 messages**: 3-5 minutes

### Lazy Remediation
- **Database with 10,000 messages**: 1-2 minutes (full scan + update)
- **Database with 100,000 messages**: 10-20 minutes
- **Database with 1,000,000 messages**: 1-2 hours

### Why the difference?
- **Quick import**: Only checks hash set against new data (O(n) where n = new messages only)
- **Lazy remediation**: Full scan + re-alignment + FK updates (O(n) where n = all messages)

---

## Key Insight: Why This Works

The key insight is that **message content is deterministic**. Once created in OpenWebUI, a message's content never changes. Therefore:

1. **Hashing is stable**: `hash(msg) = hash(same_msg)` always
2. **Dedup is foolproof**: If message wasn't imported, hash won't exist
3. **Remediation is safe**: Can re-run anytime, only updates what changed
4. **Idempotent**: Running import 100 times = same result as running it once

This enables us to safely keep both fast imports and lazy remediation without synchronization issues.

---

**Next Steps**: 
- Implement idle-time detection
- Add scheduler integration
- Deploy to production
- Monitor performance metrics
