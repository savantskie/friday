# Caddy Configuration Cleanup - Direct MCP Server Proxying
**Date:** November 28, 2025  
**Status:** ✅ COMPLETE AND DEPLOYED  

## Changes Made to Caddy Configuration

### File: `/media/nate/Friday/Friday/caddy/Caddyfile`

#### Removed Old MCPO Routing
- **Deleted:** `/mcpo*` routes that were forwarding to `192.168.1.50:12345` (MCPO port)
- **Reason:** MCPO intermediary layer no longer needed; OAuth proxy now routes directly to MCP Server

#### Consolidated OAuth + MCP Handlers
- **Before:** Separate preflight handlers for `/oauth*` and `/mcp*`
- **After:** Combined preflight handler for both `/oauth*` and `/mcp*` routes
- **Result:** Both route to `localhost:8888` (OAuth proxy) which validates JWT and forwards to MCP Server

#### Disabled AnythingLLM Route
- **Changed:** `/mcp-anythingllm*` route commented out (not currently in use)
- **Reason:** Service not running; can be re-enabled if needed

## Architecture After Changes

### Simplified Request Flow
```
External Client (Claude.ai or Browser)
        ↓
    Caddy (HTTPS frontend)
        ↓
    Route matches /oauth* or /mcp*
        ↓
    OAuth Proxy (localhost:8888)
        ↓
    OAuth Validates JWT token
        ↓
    Proxy to MCP Server (127.0.0.1:21436)
        ↓
    MCP Server validates X-API-Key
        ↓
    Return response to client
```

## Verification

### Configuration Validation
```bash
✓ caddy validate --config /media/nate/Friday/Friday/caddy/Caddyfile
  Result: Valid configuration
```

### Service Status
```bash
✓ Caddy running on ports 80 (HTTP redirect) and 443 (HTTPS)
✓ TLS certificate loaded for fridayonline.bounceme.net
✓ Config watching enabled (auto-reload on changes)
```

### Endpoint Testing
```bash
✓ OAuth endpoint: https://fridayonline.bounceme.net/oauth/authorize
  Status: 422 (expected - missing client_id parameter)

✓ MCP endpoint: https://fridayonline.bounceme.net/mcp/
  Status: 401 (expected - invalid bearer token)
  Confirms: Routes correctly to OAuth proxy → validates JWT
```

## Configuration Details

### CORS Headers (Applied to both OAuth and MCP)
- Origin: `https://fridayonline.bounceme.net`
- Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
- Credentials: true

### Static Assets Routing (for OpenWebUI)
- `/_app/*` → `127.0.0.1:3000`
- `/assets/*` → `127.0.0.1:3000`
- `/build/*` → `127.0.0.1:3000`

### LM Studio Proxy
- `/lmstudio*` → `192.168.1.50:1234`

### OpenID Configuration
- `/.well-known/*` → `localhost:8888` (OAuth proxy for discovery)

### Claude.ai JWT Bearer Token Support
- Requests with `Authorization: Bearer eyJ*` automatically routed to OAuth proxy

## Testing Status
- ✅ Caddy configuration valid
- ✅ Service running and listening
- ✅ OAuth routing working
- ✅ MCP routing working
- ✅ HTTPS/TLS functioning
- ⏳ **NEXT:** Test Claude Desktop connection with actual MCP calls

## How to Restart Caddy
```bash
# Kill old process and restart with launch script
pkill -f "caddy run"
bash /media/nate/Friday/Friday/fridaycaddylaunch.sh &
```

## Monitoring
Watch Caddy logs for routing issues:
```bash
# The launch script logs to stdout, so check process output
ps aux | grep caddy
```

## Rollback
The old Caddyfile is preserved as `Caddyfile.2025-08-21.locked` if needed.
