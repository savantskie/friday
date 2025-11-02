# OpenWebUI Chat Isolation & Remediation Service

## Overview

Fixed a critical issue where imported OpenWebUI chats were NOT being properly isolated by user and model. This document explains the problem, the solution, and how to use the remediation service.

## The Problem

**Original Code (BROKEN):**
```python
cursor.execute('SELECT id, name FROM chat')  # ❌ Missing user_id and model
chats = {row[0]: row[1] for row in cursor.fetchall()}

# Later, messages were linked using only chat_id:
conversation_id = str(chat_id)  # ❌ Single bucket for ALL users and models
```

**Impact:**
- User A's chat with Friday model → stored in bucket "chat_uuid"
- User B's chat with Friday model → stored in SAME bucket "chat_uuid" if same chat
- User A's chat with Tara model → mixed with Friday
- **Result:** Complete breakdown of per-user, per-model isolation

## The Solution

### 1. Enhanced Import Function

**New Code (FIXED):**
```python
# Extract full chat info including user_id and model
cursor.execute('SELECT id, user_id, title, chat FROM chat')
for chat_id, user_id, title, chat_json in cursor.fetchall():
    chat_data = json.loads(chat_json)
    models = chat_data.get('models', [])
    primary_model = models[0] if models else 'default'
    model_name = primary_model.split('/')[-1]  # Extract "friday" from "openai/friday"
    
    # Proper isolation key
    conversation_id = f"{user_id}_{model_name}"  # ✅ User + Model
```

**Benefits:**
- ✅ Each user gets separate memory buckets
- ✅ Each model gets separate buckets per user
- ✅ Metadata preserved with user_id, model, and original chat_id
- ✅ Full deduplication preserved

### 2. Remediation Service

**New Method:** `verify_and_remediate_chat_isolation()`

This service:
1. Reads OpenWebUI's webui.db to get correct user_id and model for each chat
2. Queries all imported messages in Friday Memory System
3. Checks if each message has the correct isolation format
4. Retroactively fixes any messages with incorrect conversation_id
5. Returns detailed statistics

**Key Features:**
- ✅ Idempotent (safe to run multiple times)
- ✅ Detailed statistics on what was fixed
- ✅ Error handling and reporting
- ✅ Preserves original metadata
- ✅ Tracks remediation history

## Database Impact

### Before Remediation
```
Message A:
  conversation_id: "4902c4b3-c616-4942-b9d3-29f9f71ba9af"  ❌ Just chat UUID
  metadata: {"chat_id": "4902c4b3...", "user_id": "alice_xyz", "model": "friday"}

Message B (different user, same chat UUID):
  conversation_id: "4902c4b3-c616-4942-b9d3-29f9f71ba9af"  ❌ SAME bucket!
  metadata: {"chat_id": "4902c4b3...", "user_id": "bob_abc", "model": "friday"}

Result: Both users' memories mixed in one bucket ❌
```

### After Remediation
```
Message A:
  conversation_id: "alice_xyz_friday"  ✅ User + Model
  metadata: {
    "chat_id": "4902c4b3...",
    "user_id": "alice_xyz",
    "model": "friday",
    "remediated_at": "2025-11-01T10:30:00...",
    "previous_conversation_id": "4902c4b3..."
  }

Message B:
  conversation_id: "bob_abc_friday"  ✅ Different bucket!
  metadata: {
    "chat_id": "4902c4b3...",
    "user_id": "bob_abc",
    "model": "friday",
    "remediated_at": "2025-11-01T10:30:00...",
    "previous_conversation_id": "4902c4b3..."
  }

Result: Each user has isolated memories ✅
```

## Isolation Format

### Conversation ID Format
```
"{user_id}_{model_name}"
```

**Examples:**
- `alice_xyz_friday` - Alice talking with Friday model
- `alice_xyz_tara` - Alice talking with Tara model
- `bob_abc_friday` - Bob talking with Friday model
- `bob_abc_jessica` - Bob talking with Jessica model

**Where it comes from:**
- `user_id`: From OpenWebUI `chat.user_id` column
- `model_name`: Extracted from chat JSON `history.models[0]` with path splitting

## Usage

### Run the Import (Fresh)
```python
# Direct import with proper isolation
await memory_system.import_openwebui_chat_history()
```

### Run Verification & Remediation
```python
# Check and fix any existing imported chats
stats = await memory_system.verify_and_remediate_chat_isolation()

print(f"Already isolated: {stats['already_isolated']}")
print(f"Remediated: {stats['remediations']}")
print(f"Errors: {stats['errors']}")
```

### Test Script
```bash
python3 test_chat_isolation_service.py
```

This script:
1. Imports fresh chat history
2. Runs remediation
3. Queries to verify isolation buckets
4. Shows sample messages from each bucket

## Statistics Structure

The remediation service returns:
```python
{
    'total_messages': int,           # Total OpenWebUI messages in Friday Memory System
    'already_isolated': int,         # Messages already in correct format
    'missing_isolation': int,        # Messages that needed fixing
    'remediations': int,             # Successfully updated
    'errors': int,                   # Failed to update
    'details': [                     # Array of individual results
        {
            'message_id': str,
            'previous_conv_id': str,
            'new_conv_id': str,
            'user_id': str,
            'model': str,
            'status': 'remediated'  # or 'error'/'issue'
        }
    ]
}
```

## Integration with Phase 2

### Real-time (Adaptive_Memory_v3)
- Captures `body['model']` on every request ✅
- Uses `conversation_id = f"{user_id}_{model}"` ✅
- New memories are properly isolated ✅

### Imported History (Friday Memory System)
- **Before:** Watchdog import mixed all users/models ❌
- **After:** Fixed import uses proper isolation ✅
- **Retroactive Fix:** Remediation service fixes existing chats ✅

### Result
Per-user, per-model isolation is now consistent across:
- ✅ Real-time conversations (Adaptive_Memory_v3)
- ✅ Imported chat history (Fixed import)
- ✅ Existing retroactively imported chats (Remediation service)

## Metadata Preserved

All remediation tracks the original data:
```python
metadata = {
    'source': 'openwebui_import',           # Source system
    'chat_id': str(chat_id),                # Original OpenWebUI chat ID
    'chat_title': str(chat_title),          # Chat title
    'user_id': str(user_id),                # User UUID from OpenWebUI
    'model': model_name,                    # Model name (short form)
    'full_model': primary_model,            # Full model path
    'role': role,                           # 'user' or 'assistant'
    'created_at': timestamp,                # Original timestamp
    'message_id_in_chat': str(msg_id),      # Message ID from OpenWebUI
    'remediated_at': ISO_datetime,          # When remediation happened (if updated)
    'previous_conversation_id': old_conv_id # What it was before (if updated)
}
```

## Error Handling

Errors are collected and reported but don't stop the remediation:

```python
# Error cases:
- 'No chat_id in metadata' → Imported with missing OpenWebUI metadata
- 'Chat not found in OpenWebUI' → Chat deleted from OpenWebUI since import
- 'Update failed: ...' → Database constraint or connection error
```

These are tracked in `stats['details']` and logged for debugging.

## Next Steps

1. **Run remediation on existing data:**
   ```bash
   python3 test_chat_isolation_service.py
   ```

2. **Verify isolation in the database:**
   ```sql
   SELECT DISTINCT conversation_id, COUNT(*) as message_count
   FROM messages WHERE source_type = 'openwebui'
   GROUP BY conversation_id
   ORDER BY conversation_id;
   ```

3. **Proceed with Phase 2c:** Live testing with real OpenWebUI usage

## Files Modified

- `friday_memory_system.py`:
  - **Line 4477-4555:** Fixed `import_openwebui_chat_history()` 
  - **Line 4557-4728:** New `verify_and_remediate_chat_isolation()` method

## Files Added

- `test_chat_isolation_service.py`: Test and verification script

## Backward Compatibility

✅ **Fully backward compatible:**
- Existing Friday Memory System schema unchanged
- Only changes conversation_id format (logical, not schema)
- Metadata preservation ensures traceability
- All operations are reversible (metadata stores previous state)
