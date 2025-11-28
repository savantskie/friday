# OAuth Proxy Setup Instructions

## Completed Steps ✓

1. ✓ Generated secure OAuth client_secret
2. ✓ Created [oauth_config.json](oauth_config.json) with configuration
3. ✓ Created [requirements_oauth.txt](requirements_oauth.txt) with dependencies
4. ✓ Implemented [oauth_mcpo_proxy.py](oauth_mcpo_proxy.py) OAuth proxy server
5. ✓ Installed Python dependencies
6. ✓ Made oauth_mcpo_proxy.py executable
7. ✓ Created systemd service file at `/etc/systemd/system/oauth-mcpo-proxy.service`

## Remaining Steps

### Step 1: Update Caddy Configuration

You need to add OAuth proxy routes to your Caddy configuration. The exact location of your Caddy config file may vary.

**Find your Caddy config:**
```bash
# Common locations:
ls /etc/caddy/Caddyfile
ls ~/.config/caddy/Caddyfile
ls /etc/caddy/conf.d/
```

**Add these routes** to your `fridayonline.bounceme.net` block:

```
fridayonline.bounceme.net {
    # Existing MCPO endpoint (for OpenWebUI) - keep this unchanged
    reverse_proxy /mcpo/* localhost:12345

    # New OAuth endpoints (for Claude Desktop)
    reverse_proxy /oauth/* localhost:8888

    # MCP endpoint with OAuth (for Claude Desktop)
    reverse_proxy /mcp/* localhost:8888
}
```

**Reload Caddy:**
```bash
sudo systemctl reload caddy
# OR
sudo caddy reload --config /path/to/Caddyfile
```

### Step 2: Enable and Start OAuth Proxy Service

```bash
# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable oauth-mcpo-proxy

# Start the service
sudo systemctl start oauth-mcpo-proxy

# Check status
sudo systemctl status oauth-mcpo-proxy

# View logs
sudo journalctl -u oauth-mcpo-proxy -f
```

### Step 3: Test OAuth Proxy Locally

Before configuring Claude Desktop, test the OAuth flow in your browser:

**1. Test health endpoint:**
```bash
curl http://localhost:8888/health
```

Should return:
```json
{
  "status": "healthy",
  "service": "oauth-mcpo-proxy",
  "timestamp": "2025-11-27T..."
}
```

**2. Test authorization endpoint:**

Open in browser:
```
http://localhost:8888/oauth/authorize?client_id=friday-memory-claude-desktop&response_type=code
```

You should see an authorization code displayed.

**3. Test token endpoint:**
```bash
# Copy the authorization code from step 2, then:
curl -X POST http://localhost:8888/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code=YOUR_AUTH_CODE_HERE" \
  -d "client_id=friday-memory-claude-desktop" \
  -d "client_secret=t5rNBHPZEG5qAjHvYDbrCIjwtJrqFpIPoxfTEyGoTdw"
```

Should return access_token and refresh_token.

### Step 4: Configure Claude Desktop

1. Open Claude Desktop app
2. Go to **Settings > Connectors**
3. Click **Add Connector** or **Add Remote MCP Server**
4. Enter the following information:

   **Server Configuration:**
   - Server URL: `https://fridayonline.bounceme.net/mcp`

   **OAuth Configuration:**
   - Authorization URL: `https://fridayonline.bounceme.net/oauth/authorize`
   - Token URL: `https://fridayonline.bounceme.net/oauth/token`
   - Client ID: `friday-memory-claude-desktop`
   - Client Secret: `t5rNBHPZEG5qAjHvYDbrCIjwtJrqFpIPoxfTEyGoTdw`

5. Save the connector
6. Complete the OAuth authorization flow when prompted

### Step 5: Test Claude Desktop Integration

1. Start a new conversation in Claude Desktop
2. Try using a memory tool:
   - "What reminders do I have?"
   - "Search my memories for [topic]"
   - "What's the weather?"

3. Verify the tools work correctly

### Step 6: Configure Claude Mobile (Optional)

Same configuration as Claude Desktop:
1. Open Claude mobile app
2. Go to Settings > Connectors
3. Add the same connector configuration as above

## Architecture Diagram

```
┌─────────────────────┐
│  Claude Desktop     │
│    or Mobile        │
└──────────┬──────────┘
           │ OAuth 2.0
           │
┌──────────▼──────────┐
│  OAuth Proxy        │
│  (port 8888)        │
│  - Validates OAuth  │
│  - Adds Bearer Token│
└──────────┬──────────┘
           │ Bearer Token
           │
┌──────────▼──────────┐
│  MCPO Server        │
│  (port 12345)       │
│  - Validates Bearer │
│  - Proxies to MCP   │
└──────────┬──────────┘
           │ stdio
           │
┌──────────▼──────────┐
│  friday_memory_     │
│  mcp_server.py      │
└─────────────────────┘
```

## Port Allocation

- **Port 8888**: OAuth proxy (new)
- **Port 12345**: MCPO (existing, unchanged)
- **Port 21435**: MCP server stdio (existing, unchanged)

## Tools Available in Claude Desktop

Claude Desktop will have access to **core tools only** (same as OpenWebUI):

✓ Memory operations (search, create, update)
✓ Reminders and appointments
✓ Conversation context
✓ System health
✓ Weather and web search
✓ AI self-reflection tools

✗ VS Code-specific tools (not included)

## Security Notes

- **OAuth client_secret**: Stored in [oauth_config.json](oauth_config.json)
- **MCPO bearer token**: Read from `/media/nate/Friday/Friday/keys/mcpo_api_key.txt`
- **Access token expiry**: 1 hour
- **Refresh token expiry**: 7 days
- **All communication**: Over HTTPS (via Caddy)

## Troubleshooting

### OAuth proxy won't start

Check logs:
```bash
sudo journalctl -u oauth-mcpo-proxy -n 50
```

Common issues:
- Port 8888 already in use
- Missing dependencies
- Config file not found

### Claude Desktop can't connect

1. Check Caddy is proxying correctly:
```bash
curl https://fridayonline.bounceme.net/oauth/authorize?client_id=friday-memory-claude-desktop&response_type=code
```

2. Check OAuth proxy is running:
```bash
sudo systemctl status oauth-mcpo-proxy
```

3. Check OAuth proxy logs:
```bash
sudo journalctl -u oauth-mcpo-proxy -f
```

### Tools not working

1. Verify MCPO is still running:
```bash
# Check if MCPO process is running
ps aux | grep mcpo
```

2. Test MCPO directly:
```bash
# Get bearer token
BEARER_TOKEN=$(cat /media/nate/Friday/Friday/keys/mcpo_api_key.txt)

# Test MCPO endpoint
curl -H "Authorization: Bearer $BEARER_TOKEN" \
  http://localhost:12345/mcpo/health
```

3. Check OAuth proxy can reach MCPO:
```bash
# Check OAuth proxy logs for errors
sudo journalctl -u oauth-mcpo-proxy -n 100 | grep error
```

## Files Created

1. [/media/nate/Friday/Friday/oauth_config.json](oauth_config.json) - OAuth configuration
2. [/media/nate/Friday/Friday/oauth_mcpo_proxy.py](oauth_mcpo_proxy.py) - OAuth proxy server
3. [/media/nate/Friday/Friday/requirements_oauth.txt](requirements_oauth.txt) - Python dependencies
4. `/etc/systemd/system/oauth-mcpo-proxy.service` - Systemd service file

## No Changes Needed

- ✓ `friday_memory_mcp_server.py` - Works as-is
- ✓ `openwebuifridayMCP.sh` - Unchanged
- ✓ OpenWebUI - Continues using MCPO directly
- ✓ VS Code / Claude Code - Uses local stdio

## Next Steps After Setup

Once everything is working:

1. Test from Claude Desktop
2. Test from Claude mobile
3. Verify OpenWebUI still works (unchanged)
4. Verify Claude Code still works (local stdio, unchanged)
5. Optional: Set up monitoring/alerts for OAuth proxy service

## Support

If you encounter issues, check:
1. OAuth proxy logs: `sudo journalctl -u oauth-mcpo-proxy`
2. Caddy logs: `sudo journalctl -u caddy`
3. MCPO logs (if running as service)
4. MCP server logs in `/media/nate/Friday/Friday/Logs`
