# Claude Web (PWA) OAuth MCP Integration - Current Status

**Date**: November 28, 2025
**Status**: In Progress - Plan Mode Active
**User**: Using claude.ai web via PWA (NOT Claude Desktop)
**Goal**: Connect claude.ai web to Friday Memory MCP server via OAuth

## Critical Context Discovery

**IMPORTANT**: User is using **claude.ai web interface via PWA**, NOT Claude Desktop app. This was clarified late in the conversation and changes nothing about the approach - OAuth is the correct method for claude.ai web/mobile access.

## Current Situation

### What's Working ✓
- OAuth proxy server running on port 8888
- OAuth authorization flow completes successfully
- Token generation and validation working
- Caddy routing `/oauth/*` and `/mcp/*` to OAuth proxy
- OpenWebUI continues working normally at base URL with `/mcpo` path

### What's Broken ✗
- Claude.ai web hitting root `/` path and getting 404s
- OAuth proxy only handles `/mcp/{path:path}` (requires non-empty path)
- When claude.ai tries to connect to `/mcp`, the path parameter is empty string
- Connection fails before MCP protocol can initialize

### Root Cause
The OAuth proxy's `/mcp/{path:path}` handler doesn't properly handle the case when `path` is empty. Claude.ai needs to hit `/mcp` (base endpoint) to initialize the MCP connection, but the current implementation doesn't proxy this correctly to MCPO.

## Architecture

### Current Setup
```
Claude.ai Web (PWA)
    ↓ OAuth 2.0 Authorization (✓ WORKING)
    ↓ https://fridayonline.bounceme.net/oauth/authorize
    ↓
OAuth Proxy (port 8888)
    ↓ Validates OAuth token (✓ WORKING)
    ↓ Adds MCPO bearer token
    ✗ /mcp endpoint not handling empty path properly
    ↓
MCPO Server (port 12345)
    ↓ Validates bearer token
    ↓ stdio protocol
    ↓
friday_memory_mcp_server.py
```

### URL Paths
- **OpenWebUI**: `https://fridayonline.bounceme.net/` (web interface)
- **OpenWebUI MCP**: `https://fridayonline.bounceme.net/mcpo` (direct bearer token, unchanged)
- **Claude.ai OAuth**: `https://fridayonline.bounceme.net/oauth/*` (working)
- **Claude.ai MCP**: `https://fridayonline.bounceme.net/mcp` (broken - 404s)

## The Plan

### Solution Overview
Fix the OAuth proxy to handle both:
1. `/mcp` - base endpoint (currently broken)
2. `/mcp/something` - sub-paths (currently working)

Plus implement SQLite token storage for persistence across restarts.

### Step 1: Fix MCP Root Handler
Add dedicated `/mcp` endpoint handler in OAuth proxy (before the `/mcp/{path:path}` handler):

```python
@app.api_route("/mcp", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_mcp_root(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Proxy MCP root endpoint to MCPO backend"""
    target_url = MCPO_BACKEND  # http://localhost:12345/mcpo
    # Same proxy logic as proxy_to_mcpo
```

Also update existing `/mcp/{path:path}` handler to handle empty paths:
```python
if path:
    target_url = f"{MCPO_BACKEND}/{path}"
else:
    target_url = MCPO_BACKEND
```

### Step 2: Implement SQLite Token Storage
Replace in-memory dictionaries with SQLite database:
- Create tables: `authorization_codes`, `access_tokens`, `refresh_tokens`
- Add async database helper functions
- Update all endpoints to use database instead of dicts
- Update cleanup task to delete from database
- Tokens persist across OAuth proxy restarts

### Step 3: Update Dependencies
Add `aiosqlite>=0.21.0` to `requirements_oauth.txt`

### Step 4: Restart and Test
```bash
sudo systemctl restart oauth-mcpo-proxy
```

Test claude.ai connection via Settings > Connectors

## Files Involved

### To Modify
1. `/media/nate/Friday/Friday/oauth_mcpo_proxy.py`
   - Add `/mcp` root handler (line ~350, before existing handler)
   - Update `/mcp/{path:path}` to handle empty paths (line ~363)
   - Add SQLite imports and database path
   - Replace in-memory dicts with SQLite operations
   - Update all token operations throughout file

2. `/media/nate/Friday/Friday/requirements_oauth.txt`
   - Add: `aiosqlite>=0.21.0`

### No Changes Needed
- Caddy configuration (already routes `/mcp*` correctly)
- MCPO configuration (unchanged)
- friday_memory_mcp_server.py (unchanged)
- OpenWebUI integration (unchanged)

## User Constraints

- **Base URL reserved for OpenWebUI**: `https://fridayonline.bounceme.net/` serves OpenWebUI only
- **Cannot route root paths to OAuth proxy**: Would break OpenWebUI
- **Must maintain separate paths**: `/mcpo` for OpenWebUI, `/mcp` for claude.ai
- **User preference**: Frustrated with multiple URL paths, but OAuth is required by claude.ai

## Key User Quotes

> "I wish they'd just fucking use a standard api key like every other mcp server so I can use what I already have in mcpo set up. This multiple pages bullshit is pissing me off especially since the damned system Claude.ai has checks the damned base url."

> "i'm not using Claude desktop. I'm using claude web via pwa...."

## Configuration

### OAuth Config
**File**: `/media/nate/Friday/Friday/oauth_config.json`
```json
{
  "clients": {
    "claude-desktop": {
      "client_id": "friday-memory-claude-desktop",
      "client_secret": "t5rNBHPZEG5qAjHvYDbrCIjwtJrqFpIPoxfTEyGoTdw",
      "name": "Claude Desktop & Mobile"
    },
    "chatgpt": {
      "client_id": "friday-memory-chatgpt",
      "client_secret": "XpOHqE-4KxnFuwcqNKsYL3qO_g3lvNBvtCM3j3E3LNE",
      "name": "ChatGPT Developer Mode"
    }
  },
  "authorization_endpoint": "https://fridayonline.bounceme.net/oauth/authorize",
  "token_endpoint": "https://fridayonline.bounceme.net/oauth/token",
  "mcpo_backend": "http://localhost:12345/mcpo",
  "mcpo_bearer_token_file": "/media/nate/Friday/Friday/keys/mcpo_api_key.txt",
  "token_expiry_seconds": 3600,
  "refresh_token_expiry_seconds": 604800
}
```

### Claude.ai Connector Settings
**Settings > Connectors > Friday Memory System**:
- Server URL: `https://fridayonline.bounceme.net/mcp`
- Authorization URL: `https://fridayonline.bounceme.net/oauth/authorize`
- Token URL: `https://fridayonline.bounceme.net/oauth/token`
- Client ID: `friday-memory-claude-desktop`
- Client Secret: `t5rNBHPZEG5qAjHvYDbrCIjwtJrqFpIPoxfTEyGoTdw`

## Logs Showing Issue

From OAuth proxy logs (`sudo journalctl -u oauth-mcpo-proxy`):
```
INFO: Generated authorization code for client friday-memory-claude-desktop
INFO: 209.212.33.59:0 - "GET /oauth/authorize?client_id=friday-memory-claude-desktop&response_type=code HTTP/1.1" 200 OK
INFO: 34.162.136.91:0 - "POST / HTTP/1.1" 404 Not Found  # ← Claude.ai hitting root
INFO: 34.162.136.91:0 - "GET / HTTP/1.1" 404 Not Found   # ← Claude.ai hitting root
```

IP `34.162.136.91` is Claude's infrastructure trying to connect.

## Previous Work Session

From earlier in the conversation (before oauth issue):
- Added friday-memory MCP server to Claude Code (~/.claude.json) - working
- Fixed schema validation (removed `anyOf` constraint) - working
- Changed archival maintenance from 3 hours to 6 hours - completed
- Changed retention from 30 days to 90 days - completed
- Created `.claude.md` instructions file - completed

## Plan File Location

Active plan: `/home/nate/.claude/plans/delightful-singing-lollipop.md`

Contains detailed implementation steps for:
1. Fixing OAuth proxy MCP handler
2. Implementing SQLite token storage
3. Updating dependencies

## Next Steps (When Resuming)

1. Exit plan mode and begin implementation
2. Modify `oauth_mcpo_proxy.py`:
   - Add `/mcp` root handler
   - Update `/mcp/{path:path}` handler
   - Implement SQLite token storage
3. Update `requirements_oauth.txt`
4. Install dependencies: `pip3 install aiosqlite>=0.21.0`
5. Restart OAuth proxy: `sudo systemctl restart oauth-mcpo-proxy`
6. Test connection from claude.ai Settings > Connectors
7. Verify tools appear in claude.ai

## Open Questions

None - plan is clear and ready to implement.

## Related Documentation

- `/media/nate/Friday/Friday/Summaries/CLAUDE_DESKTOP_OAUTH_SETUP_2025_11_27.md` - Previous OAuth setup summary (slightly outdated, references "Claude Desktop" but user is actually using claude.ai web)
- `/media/nate/Friday/Friday/OAUTH_SETUP_INSTRUCTIONS.md` - OAuth setup guide
- `/media/nate/Friday/Friday/keys/claude_desktop_oauth_credentials.txt` - Credentials reference

## Why This Approach

- OAuth is **required** by claude.ai for remote MCP servers
- Cannot use base URL (reserved for OpenWebUI)
- `/mcp` path keeps claude.ai separate from OpenWebUI's `/mcpo` path
- SQLite token storage provides persistence and better UX
- Minimal changes required - just fixing path handling

## Architecture After Fix

```
OpenWebUI → /mcpo → MCPO (bearer token) → MCP Server ✓ (unchanged)

Claude.ai Web → /mcp → OAuth Proxy → /mcpo → MCPO (bearer token) → MCP Server ✓ (will work after fix)
```

Both paths reach the same Friday Memory MCP server, just with different authentication.
