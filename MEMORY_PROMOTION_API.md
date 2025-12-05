# Memory Promotion API - Short Term to Long Term

**Status:** Implemented and available  
**Location:** `friday_memory_mcp_server.py` (HTTP API endpoints, lines 2187-2290)  
**Purpose:** Enable users to promote memories from OpenWebUI short-term to Friday Memory System long-term storage

---

## API Overview

The promotion API provides a REST endpoint for migrating memories from the short-term memory system (running in OpenWebUI) to the long-term Friday Memory System.

### Endpoint

```
POST /api/memories/promote
```

**Base URL:** `http://127.0.0.1:{PORT}/api/memories/promote`  
**Authentication:** Required (X-API-Key header)

---

## Request Format

### Headers
```
X-API-Key: <mcpo_api_key>
Content-Type: application/json
```

### Body
```json
{
  "content": "Memory content (required)",
  "memory_type": "Optional: memory type or category",
  "tags": ["optional", "tag1", "tag2"],
  "memory_bank": "Optional: Personal|Work|General|Context|Tasks (default: General)",
  "conversation_id": "Optional: UUID of source conversation for linking",
  "source_conversation_id": "Optional: Deprecated, use conversation_id instead"
}
```

### Required Fields
- **content** - The actual memory text to store

### Optional Fields
- **memory_type** - How to classify this memory
- **tags** - Array of custom tags (automatically adds "promoted" tag)
- **memory_bank** - Category for organization (defaults to "General")
- **conversation_id** - Links memory back to the conversation it came from

---

## Response Format

### Success Response (200 OK)
```json
{
  "status": "success",
  "memory_id": "uuid-of-created-memory",
  "importance_level": 8,
  "memory_bank": "Personal",
  "link_id": "uuid-of-conversation-link",
  "message": "Memory promoted to long-term storage and linked to conversation"
}
```

### Error Responses

**400 Bad Request** - Missing required fields
```json
{
  "detail": "Memory content is required"
}
```

**403 Forbidden** - Invalid API key
```json
{
  "detail": "Forbidden: Invalid or missing API key"
}
```

**500 Internal Server Error** - Server error
```json
{
  "detail": "Server error: [error details]"
}
```

---

## How It Works

### Processing Flow

```
1. Client sends POST request with memory content
                    ↓
2. Server verifies API key (X-API-Key header)
                    ↓
3. Parse request body and validate content
                    ↓
4. Add "promoted" tag (automatically)
                    ↓
5. Create memory in long-term storage
   - Set importance_level: 8 (high priority)
   - Set memory_bank: provided or "General"
   - Include all tags + "promoted"
                    ↓
6. Link to source conversation (if conversation_id provided)
   - Creates metadata link with promotion details
   - Stores promoted_at timestamp
   - Tracks promotion_importance: 8
                    ↓
7. Return success response with memory_id and link_id
```

### Key Features

1. **Automatic "promoted" Tag**
   - All promoted memories get tagged with "promoted"
   - Makes it easy to find and filter promoted memories

2. **High Importance by Default**
   - Set to importance_level 8 (1-10 scale)
   - Makes promoted memories surface in searches

3. **Memory Bank Organization**
   - Supports: General, Personal, Work, Context, Tasks
   - Allows organizing promoted memories by context

4. **Conversation Linking**
   - Optionally links promoted memory back to source conversation
   - Stores metadata about promotion (timestamp, tags, importance)
   - Non-blocking: if linking fails, promotion still succeeds

---

## Example Usage

### Using cURL
```bash
curl -X POST http://127.0.0.1:12345/api/memories/promote \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Nate prefers coffee over tea, especially in the morning",
    "memory_type": "preference",
    "tags": ["drinks", "morning"],
    "memory_bank": "Personal",
    "conversation_id": "conv-uuid-123"
  }'
```

### Using Python
```python
import requests
import json

api_key = "your-api-key-here"
endpoint = "http://127.0.0.1:12345/api/memories/promote"

memory_data = {
    "content": "Nate works with Python and JavaScript",
    "memory_type": "skill",
    "tags": ["programming", "work"],
    "memory_bank": "Work",
    "conversation_id": "conv-uuid-456"
}

headers = {
    "X-API-Key": api_key,
    "Content-Type": "application/json"
}

response = requests.post(endpoint, json=memory_data, headers=headers)
result = response.json()

if response.status_code == 200:
    print(f"✅ Memory promoted: {result['memory_id']}")
    print(f"   Importance: {result['importance_level']}")
    print(f"   Bank: {result['memory_bank']}")
else:
    print(f"❌ Error: {result['detail']}")
```

### Using JavaScript/TypeScript
```javascript
const apiKey = "your-api-key-here";
const endpoint = "http://127.0.0.1:12345/api/memories/promote";

const memoryData = {
  content: "Nate has ADHD and has had multiple strokes",
  memory_type: "health",
  tags: ["medical", "personal"],
  memory_bank: "Personal",
  conversation_id: "conv-uuid-789"
};

const response = await fetch(endpoint, {
  method: "POST",
  headers: {
    "X-API-Key": apiKey,
    "Content-Type": "application/json"
  },
  body: JSON.stringify(memoryData)
});

const result = await response.json();

if (response.ok) {
  console.log(`✅ Memory promoted: ${result.memory_id}`);
} else {
  console.error(`❌ Error: ${result.detail}`);
}
```

---

## Cleanup API

There's also a companion cleanup endpoint for managing promoted memories:

### Endpoint

```
DELETE /api/memories/cleanup
```

**Query Parameters:**
- `tag` - Which tag to clean (default: "test", options: "test", "temporary", "promoted")
- `dry_run` - If true, just count without deleting (default: false)

### Example

```bash
# Dry run - see how many promoted memories would be deleted
curl -X DELETE "http://127.0.0.1:12345/api/memories/cleanup?tag=promoted&dry_run=true" \
  -H "X-API-Key: your-api-key-here"

# Actually delete promoted memories
curl -X DELETE "http://127.0.0.1:12345/api/memories/cleanup?tag=promoted&dry_run=false" \
  -H "X-API-Key: your-api-key-here"
```

---

## Where This Fits in the Architecture

```
OpenWebUI (short_term.py)
    ↓
User clicks "Promote this memory"
    ↓
Client makes POST to /api/memories/promote
    ↓
HTTP API (friday_memory_mcp_server.py)
    ↓
Calls friday_memory_system.create_memory()
    ↓
Stores to long-term database (ai_memories.db)
    ↓
Links to source conversation (optional)
    ↓
Returns success response to client
```

---

## API Key Configuration

The API key is stored in:
```
/media/nate/Friday/Friday/keys/mcpo_api_key.txt
```

### Format
Simple text file with just the API key value (no extra formatting)

### Security Notes
- API key should be treated as sensitive
- Keep it secret - don't share in code/logs
- Consider rotating periodically
- Only expose endpoints through HTTPS in production

---

## Integration Points

### For OpenWebUI Short Term Plugin
The `friday_memory_short_term.py` plugin can call this endpoint to promote memories:

```python
# Inside short_term.py
async def promote_memory_to_long_term(self, memory_content):
    """Promote a memory from short-term to long-term storage"""
    
    payload = {
        "content": memory_content,
        "memory_bank": "General",
        "tags": ["user_selected"]
    }
    
    headers = {
        "X-API-Key": self.api_key,
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"http://127.0.0.1:{port}/api/memories/promote",
            json=payload,
            headers=headers
        ) as response:
            if response.status == 200:
                result = await response.json()
                return result["memory_id"]
```

---

## Troubleshooting

### Issue: "Invalid or missing API key"
- Ensure `keys/mcpo_api_key.txt` exists
- Verify the key is correct in your request headers
- Check file permissions

### Issue: "Memory content is required"
- Ensure `content` field is present in request body
- Verify content is not empty string

### Issue: "Failed to link to conversation"
- This is non-blocking - memory is still promoted
- Conversation ID might be invalid
- Check conversation exists in database

### Issue: 500 Server error
- Check Friday Memory System is running
- Verify databases are accessible
- Check server logs for details

---

## Future Enhancements

1. **Batch promotion** - POST multiple memories at once
2. **Selective field update** - Promote and update importance at same time
3. **Bulk cleanup** - DELETE endpoint for cleaning multiple tags
4. **Promotion hooks** - Trigger webhooks when memory promoted
5. **Async processing** - Queue promotions for async processing
6. **Analytics** - Track promotion patterns and statistics

---

## Summary

The Memory Promotion API is a complete system for migrating important short-term memories to long-term storage with:
- ✓ Full linking to source conversations
- ✓ Automatic tagging and importance elevation
- ✓ Category organization (memory banks)
- ✓ Cleanup utilities
- ✓ Comprehensive error handling
- ✓ API key authentication

It bridges the gap between the conversational short-term system and the persistent long-term memory database.
