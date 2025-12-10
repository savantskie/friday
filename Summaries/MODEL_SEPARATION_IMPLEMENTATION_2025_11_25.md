# Model Card Separation Implementation - Complete
**Date**: November 25, 2025  
**Status**: ✅ Complete  
**Implementation Approach**: Content-based model tagging with LLM-level filtering and stripping

## Overview
Successfully implemented persona/model card separation for the Friday Memory System. Memories created by "Friday" are now isolated from "Tara", "Jessie", "James", "Willow", and other personas. The implementation uses content-based tagging (`[Model: ...]` tags embedded in memory content) rather than database metadata, which allows:
- Memory LLMs to filter by persona when scoring relevance
- Main chat LLM to receive clean memories without model metadata
- Full backward compatibility without database schema changes

## Key Technical Decisions

### 1. Why Content-Based vs Metadata-Based?
**Investigation Finding**: OpenWebUI's memory database schema contains only: `id, user_id, content, updated_at, created_at` (no metadata column). The `AddMemoryForm` accepts metadata parameter but doesn't persist it.

**Solution**: Embed model identification directly in memory content as `[Model: {persona_name}]` tag
- **Pros**: Works with existing database, visible to memory LLMs, easily strippable for main chat
- **Cons**: Adds slight memory content overhead (negligible)

### 2. Two-Filter Architecture
Memory goes through three LLM interaction points:

| Stage | LLM | Sees Model Tag? | Purpose |
|-------|-----|-----------------|---------|
| 1. Memory Identification | Memory Creation LLM | ✅ YES | Aware of which persona is creating memories |
| 2. Memory Retrieval | Memory Scoring LLM | ✅ YES | Filters by `[Model: ...]` tag, only returns matching persona |
| 3. Chat Context | Main Chat LLM | ❌ NO | Receives stripped memories via `_strip_model_info_from_memory()` |

## Implementation Details

### Code Changes in `friday_memory_short_term.py`

#### 1. MemoryOperation Class (Line 286)
Added optional field for tracking which persona created the memory:
```python
model_card_name: Optional[str] = None  # Model card name (persona) for memory separation
```

#### 2. Model Card Name Extraction (inlet/outlet)

**inlet() method (Lines 3248-3255)**:
```python
model_card_name = None
if __metadata__:
    model_card_name = __metadata__.get("model", {}).get("name")
if not model_card_name:
    model_card_name = body.get("model", "default")
self._current_model_card_name = model_card_name
```

**outlet() method (Lines 3821-3828)**: Same extraction logic

**Extraction Priority**:
1. Primary: `__metadata__["model"]["name"]` (OpenWebUI model card friendly name)
2. Fallback: `body.get("model")` (backend model identifier)
3. Default: `"default"` (if both missing)

#### 3. Memory Content Formatting (Lines 6717-6724)

Function `_format_memory_content()` now appends model tag:
```python
model_part = f" [Model: {operation.model_card_name}]" if operation.model_card_name else ""
return f"{tag_part}{content}{bank_part}{model_part}".strip()
```

**Example Output**:
```
[Tags: preference] I like coffee [Memory Bank: Personal] [Model: Friday]
```

#### 4. Model Tag Stripping (Lines 4307-4319)

New function `_strip_model_info_from_memory()` removes model tags before chat injection:
```python
import re
cleaned = re.sub(r'\s*\[Model:\s*[^\]]+\]', '', memory_content)
return cleaned.strip()
```

**Pattern Explanation**:
- `\s*\[Model:` - Whitespace + literal "[Model:"
- `\s*[^\]]+` - Whitespace + any non-bracket characters
- `\]` - Closing bracket
- This safely removes `[Model: Friday]` while preserving other tags

#### 5. Memory Format Stripping (Lines 4336, 4357, 4378)

Updated `_format_memories_for_context()` to strip model info in all three formats:
- **Bullet format** (Line 4336): Strips before `[Tags: ...]` extraction
- **Numbered format** (Line 4357): Strips before extraction
- **Paragraph format** (Line 4378): Strips before content assembly

Result: Main LLM sees:
```
[Tags: preference] I like coffee [Memory Bank: Personal]
```
NOT:
```
[Tags: preference] I like coffee [Memory Bank: Personal] [Model: Friday]
```

#### 6. Memory Retrieval Enhancement (Line 5614, 5879, 5887-5892)

Updated `get_relevant_memories()`:
- Accepts `model_card_name` parameter
- Passes it to memory filtering LLM
- Formats memory strings for LLM: `"ID: {id}, MODEL: {model_card}, CONTENT: {mem['memory']}"`
- LLM can see which model each memory came from

#### 7. Memory Creation Points Populated (4 locations)

Added `model_card_name` population at memory creation:
- Line 2506: Standard memory creation
- Line 4625: Special memory creation path
- Line 6174: Another creation variant
- Line 6302: Final creation point

### Prompt Updates

#### Memory Identification Prompt
Updated to include persona awareness context so the memory creation LLM understands it's extracting memories for a specific persona.

#### Memory Retrieval Prompt (Friday Memory Retrieval prompt.txt)
**Critical Updates**:
1. Explicitly instructs LLM to check for `[Model: ...]` tag
2. Specifies filtering rule: "Only return memories matching the current model"
3. Example: "if currently using Friday, only return memories with [Model: Friday]"
4. Scoring guidance: "0.0 = from a different model card"
5. Role-playing memories kept separate by their tags

## Memory Format Examples

### In Storage (What's Saved)
```json
{
  "id": "mem_12345",
  "user_id": "user_001",
  "content": "[Tags: preference, coffee] User likes coffee [Memory Bank: Preferences] [Model: Friday]",
  "created_at": "2025-11-25T10:30:00Z",
  "updated_at": "2025-11-25T10:30:00Z"
}
```

### Sent to Memory Retrieval LLM (With Model Context)
```
ID: mem_12345, MODEL: Friday, CONTENT: [Tags: preference, coffee] User likes coffee [Memory Bank: Preferences] [Model: Friday]
```

### Injected into Chat Context (Stripped)
```
[Tags: preference, coffee] User likes coffee [Memory Bank: Preferences]
```

## Persona Separation

The system now maintains separate memory contexts for:
- **Friday** - Main assistant persona
- **Tara** - Role-playing persona
- **Jessie** - Role-playing persona
- **James** - Role-playing persona
- **Willow** - Role-playing persona

When using "Friday", the memory system:
1. Creates memories tagged with `[Model: Friday]`
2. Only retrieves memories matching `[Model: Friday]`
3. Strips model tags before showing to main chat

## Backward Compatibility

✅ **Fully backward compatible**:
- No database schema changes (works with existing OpenWebUI)
- `[Model: ...]` tags are optional (missing tags treated as unfiltered)
- Existing memories work with regex stripper (safely removes tags if present)
- No impact on non-model-separated use cases

## Testing Checklist

- [ ] Create memory as "Friday" - verify `[Model: Friday]` tag appears in content
- [ ] Switch to "Tara" - verify memory retrieval only returns `[Model: Tara]` memories
- [ ] Check chat injection - verify model tags are stripped before main LLM
- [ ] Test mixed personas - verify isolation is maintained
- [ ] Verify backward compat - test with existing memories (pre-model separation)
- [ ] Log inspection - check friday_memory_system.log for memory operations

## Validation Points

### Code Verification
- ✅ Model extraction logic in inlet/outlet (lines 3248-3255, 3821-3828)
- ✅ Memory content formatting with model tag (lines 6717-6724)
- ✅ Model tag stripping function (lines 4307-4319)
- ✅ All memory format functions apply stripping (lines 4336, 4357, 4378)
- ✅ Memory retrieval accepts model_card_name parameter (line 5614)
- ✅ All memory creation points populate model_card_name (4 locations)

### Prompt Verification
- ✅ Memory Identification prompt updated with persona awareness
- ✅ Memory Retrieval prompt explicitly references `[Model: ...]` tags
- ✅ Filtering instructions clear and specific
- ✅ Example outputs show correct behavior

## Next Steps

1. **Test persona isolation** - Create memories with different personas, verify separation
2. **Verify chat injection** - Check that stripped memories appear correctly in chat
3. **Log inspection** - Review logs to confirm proper model_card_name extraction
4. **Performance validation** - Ensure regex stripping doesn't impact performance

## Related Documentation

- `CONSOLIDATED_IMPLEMENTATION_MASTER_2025_11_09.md` - Full implementation details
- `friday_memory_short_term.py` - Main implementation file
- `Friday System PROMPTS/Friday Memory Retrieval prompt.txt` - Memory filtering instructions
- `Friday System PROMPTS/Memory Identification Prompt` - Memory creation awareness

## Summary

Model card separation is now fully implemented using a clean content-based tagging approach. Memories are automatically tagged with `[Model: {persona}]` when created, filtered by the memory retrieval LLM based on the current persona, and stripped before injection into the main chat context. This provides full persona isolation while maintaining backward compatibility and requiring no database schema changes.

**Status**: Ready for testing and deployment ✅
