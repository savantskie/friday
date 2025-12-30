# Friday Tag Registry System

## Overview
Building a self-organizing tag system for Friday's memory system. Tags are embedded inline within memories, and a maintenance system automatically builds/updates a searchable tag registry.

## Current Memory Format
Memories are stored with inline tags like this:
```
[Tags: behavior, misc] User forgot an appointment on the 17th [Memory Bank: General]
```

## System Architecture

### Components
1. **Tag Registry (JSON file)**
   - Stored in two locations:
     - Docker container (short-term system)
     - Main Friday folder (long-term system)
   - Both systems can access independently

2. **MCP Search Tool**
   - Allows Friday to query available tags
   - Returns structured tag data with variations and counts

3. **Maintenance System**
   - Runs every 3 hours
   - Parses all memories (current DB + archives) for tags
   - Updates tag registry JSON files
   - Handles syncing between both locations

### Tag Normalization
- Tags are normalized by splitting on delimiters (underscores, hyphens, spaces)
- Variations are grouped under a canonical form
- Canonical form = most frequently used variation
- If usage patterns shift, canonical form automatically updates

### JSON Structure Example
{
  "conversation_analysis": {
    "canonical": "conversation_analysis",
    "variations": ["conversation_analysis", "conversation-analysis", "Conversation_Analysis"],
    "word_components": ["conversation", "analysis"],
    "usage_count": 15
  },
  "behavior": {
    "canonical": "behavior",
    "variations": ["behavior", "behaviour"],
    "word_components": ["behavior"],
    "usage_count": 12
  }
}

## Implementation Order
1. **MCP Search Tool** - First priority
   - Read-only access to tag registry JSON
   - Returns structured tag list showing canonical forms and variations
   
2. **Maintenance System Updates** - Second priority
   - Add tag parsing logic to existing 3-hour maintenance passes
   - Extract tags using regex: `\[Tags: ([^\]]+)\]`
   - Build/update JSON registry with normalization logic
   - Sync between both storage locations

## Key Design Decisions
- **No write-side processing**: Tags are not parsed when memories are created
- **Include everything**: All tags Friday has ever used are tracked (no filtering)
- **Usage-driven canonical forms**: Most-used variation becomes the default
- **Full history parsing**: Registry built from current DB + all archives
- **Simple MCP tool**: Tool just reads JSON, no parsing or updates

## Technical Details
- Language: Python
- Database: SQLite (in both OpenWebUI and Friday's memory system)
- Storage: JSON files for tag registry
- Parsing: Regex for inline tag extraction
- Search: Archives are searchable, tags from archived memories included in registry
- Maintenance: Scheduled tasks every 3 hours for updates