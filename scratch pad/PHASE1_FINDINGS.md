# Phase 1 Investigation - COMPLETE

**Status**: Research complete. Ready for Phase 2.  
**Database state**: Empty - no data currently in FMS databases  
**Architecture mismatch**: Code expects columns that don't exist

---

## Summary of Findings

### 1. OpenWebUI Database Structure (webui.db)
**Location**: `/media/nate/Friday/OpenWebUI/data/webui.db`

**Chat Table Schema** (where OpenWebUI stores conversations):
```
id             VARCHAR(255) - Primary key (chat ID)
user_id        VARCHAR(255) - User who owns this chat
title          TEXT         - Chat title
chat           JSON         - Message history (JSON)
meta           JSON         - Metadata
created_at     DATETIME     - Creation timestamp
updated_at     DATETIME     - Last update
pinned         BOOLEAN      - Pin status
share_id       VARCHAR(255) - Share ID
archived       INTEGER      - Archive status
folder_id      TEXT         - Folder reference
```

**Key Finding**: OpenWebUI stores `user_id` with each chat. Chat ID is the canonical identifier.

---

### 2. FMS Database Structure (conversations.db)
**Location**: `/media/nate/Friday/Friday/data/memory/Memories/conversations.db`

**Current state**: 
- `sessions` table: 0 rows
- `conversations` table: 0 rows  
- `messages` table: 0 rows
- **NO `conversation_relationships` table** (defined in code but not created in DB)

**Table Schemas**:

#### conversations table:
```
conversation_id      TEXT - Primary key
session_id           TEXT - Links to sessions table
start_timestamp      TEXT
end_timestamp        TEXT
topic_summary        TEXT
embedding            BLOB
created_at           TEXT
```
**MISSING**: user_id, model_id columns

#### messages table:
```
message_id           TEXT - Primary key
conversation_id      TEXT - Links to conversations table
timestamp            TEXT
role                 TEXT
content              TEXT
metadata             TEXT  
embedding            BLOB
created_at           TEXT
```
**MISSING**: user_id, model_id, session_id columns (wait, session_id should be here!)

#### sessions table:
```
session_id           TEXT - Primary key
start_timestamp      TEXT
end_timestamp        TEXT
context              TEXT
embedding            BLOB
created_at           TEXT
```
**MISSING**: user_id, model_id columns

---

### 3. AI Memories Database (ai_memories.db)
**Location**: `/media/nate/Friday/Friday/data/memory/Memories/ai_memories.db`

**Current state**: 
- `curated_memories` table: 3 rows (actual memories stored here!)

**Table Schema**:
```
memory_id            TEXT - Primary key
timestamp_created    TEXT
timestamp_updated    TEXT
source_conversation_id TEXT
source_message_ids   TEXT
memory_type          TEXT
content              TEXT - Actual memory content
importance_level     INTEGER
tags                 TEXT
embedding            BLOB
created_at           TEXT
```
**MISSING**: user_id, model_id columns

---

## Critical Finding: Code vs Database Mismatch

### The Code Expects (friday_memory_system.py in UPDATE folder):
- All store_message() calls require `user_id` and `model_id`
- All operations validate: `if not user_id or not model_id: return error`
- Messages should be stored with user/model context
- Should populate conversation_relationships table

### The Database Actually Has:
- NO user_id or model_id columns in ANY table
- NO conversation_relationships table at all
- All conversation/message tables are EMPTY (0 rows)
- Only ai_memories.db has data (3 memories)

### Production vs Update Folder:
- **Production folder** (friday_memory_system.py): Original code, probably doesn't enforce user_id/model_id
- **UPDATE folder** (Friday_Memory_System_Update/): New code with strict user_id/model_id requirements

---

## Why Everything Is Empty

1. **Importers (Issue #1)**: Don't pass user_id/model_id → store_message() returns error dict → nothing gets stored
2. **OpenWebUI (Issue #3)**: Doesn't call store_conversation/store_message() → nothing recorded from live chats
3. **Database schema mismatch**: Tables defined in code but not with user_id/model_id columns

**Result**: 
- FMS conversation/message tables never populated
- Only memories get stored (via ai_memories.db)
- conversation_relationships never used (table doesn't exist)

---

## What We Need To Do

### Option A: Add missing columns (DATA MIGRATION APPROACH)
1. Add user_id/model_id columns to all FMS tables
2. Create conversation_relationships table
3. Migrate existing data (though it's empty, so easy)
4. Fix importers to populate proper data
5. Implement conversation matching across systems

### Option B: Redesign linking (ARCHITECTURE APPROACH)
1. Link memories via ai_memories.db (where actual data lives)
2. Track conversation context in ai_memories metadata
3. Skip the unused conversation/message tables
4. Use memory_conversation_links table (already working)

**Recommendation**: Option A - properly implement the designed system but fix the schema mismatch first

---

## Data Currently In System

✓ **3 memories in ai_memories.db** - Can be examined
✓ **Web UI chats in webui.db** - Many conversations with user_id context
✗ **0 conversations in FMS conversations.db** - Completely empty
✗ **0 messages in FMS messages.db** - Completely empty
✗ **No conversation_relationships** - Table doesn't exist

---

## Next Steps (Phase 2)

1. **Schema Update**: Add user_id/model_id columns to conversations, messages, sessions tables
2. **Create Table**: Add conversation_relationships table in FMS DB
3. **Implement Matching**: Build logic to match OpenWebUI chats with FMS conversations
4. **Fix Importers**: Update all importers to extract from webui.db and pass user_id/model_id
5. **Verify**: Test that data flows properly with user/model isolation

---

## Files To Create/Modify (in UPDATE folder)

**Critical**:
- `Friday_Memory_System_Update/friday_memory_system.py` - Schema fixes + matching logic
- `Friday_Memory_System_Update/database_maintenance.py` - Migration helpers

**Important**:
- All importers in update folder to use webui.db matching

**Reference** (don't modify):
- Production folder stays untouched
- webui.db stays read-only (OpenWebUI's database)
