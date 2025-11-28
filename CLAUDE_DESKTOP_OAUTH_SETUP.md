# Configure Claude Desktop with Friday Memory OAuth

Your OAuth proxy is now running and ready for Claude Desktop to connect! Follow these steps to set up the connector in Claude Desktop (and Claude Mobile).

## OAuth Credentials

Keep these credentials safe - you'll need them to configure Claude Desktop:

```
Client ID:     friday-memory-claude-desktop
Client Secret: t5rNBHPZEG5qAjHvYDbrCIjwtJrqFpIPoxfTEyGoTdw
```

## Claude Desktop Configuration

### Step 1: Open Claude Desktop Settings

1. Launch Claude Desktop app
2. Click the **Settings** icon (gear icon in the top-right corner)

### Step 2: Add Remote MCP Server Connector

1. Go to **Settings > Connectors** or **Settings > Remote MCP Servers**
2. Click **Add Connector** or **Add Remote Server**
3. Select **Custom OAuth** as the server type

### Step 3: Enter OAuth Configuration

Fill in the following fields:

| Field | Value |
|-------|-------|
| **Server Name** | Friday Memory (or any name you prefer) |
| **Server URL** | `https://fridayonline.bounceme.net/mcp` |
| **Authorization URL** | `https://fridayonline.bounceme.net/oauth/authorize` |
| **Token URL** | `https://fridayonline.bounceme.net/oauth/token` |
| **Client ID** | `friday-memory-claude-desktop` |
| **Client Secret** | `t5rNBHPZEG5qAjHvYDbrCIjwtJrqFpIPoxfTEyGoTdw` |

### Step 4: Save and Authorize

1. Click **Save** or **Connect**
2. You'll be redirected to the authorization page
3. Click **Authorize** or **Allow** to grant access
4. You should see a success message
5. Return to Claude Desktop

### Step 5: Start Using Memory Tools

In a new chat, you should now be able to use Friday Memory tools:

- "Search my memories for [topic]"
- "What reminders do I have?"
- "Create a reminder for [task]"
- "What's the weather?"
- "Search the web for [query]"

## Claude Mobile Configuration

The same configuration works for Claude Mobile! Simply repeat the steps above in the Claude Mobile app Settings > Connectors.

## Available Tools

Claude Desktop will have access to the **core tools** (same as OpenWebUI):

✓ **Memory Operations**
- Search memories
- Create new memories
- Update existing memories
- Get recent context

✓ **Schedule Management**
- Create reminders
- Create appointments
- Get active reminders
- Complete reminders
- Reschedule items

✓ **Utilities**
- Check weather
- Web search
- Local business search
- System health
- AI self-reflection

✗ **VS Code Tools** (Not included)
- These are only for Claude Code in VS Code

## Testing the Connection

### Test 1: Simple Query

Try this in Claude Desktop:
```
What time is it right now?
```

This should return the current time from the memory system.

### Test 2: Memory Search

```
Search my memories for important decisions
```

### Test 3: Reminder Creation

```
Create a reminder for me to review the project tomorrow at 10am
```

## Troubleshooting

### "Connection Failed" Error

**Check:**
1. Is the OAuth proxy running?
   ```bash
   sudo systemctl status oauth-mcpo-proxy
   ```

2. Is MCPO running?
   ```bash
   ps aux | grep mcpo
   ```

3. Can you reach the OAuth endpoints?
   ```bash
   curl https://fridayonline.bounceme.net/oauth/authorize?client_id=friday-memory-claude-desktop
   ```

### "Unauthorized" or "Invalid Token" Error

1. Check that your credentials are exactly correct (copy-paste to avoid typos)
2. Try removing and re-adding the connector
3. Check the OAuth proxy logs:
   ```bash
   sudo journalctl -u oauth-mcpo-proxy -f
   ```

### Tools Not Showing Up

1. Verify the connection is active in Settings > Connectors
2. Try starting a new chat conversation
3. Check that the server URL is correctly set to `https://fridayonline.bounceme.net/mcp`

## Architecture

```
Claude Desktop / Mobile
    ↓ (OAuth 2.0)
https://fridayonline.bounceme.net/oauth/*  (Caddy reverse proxy)
    ↓
localhost:8888  (OAuth proxy server)
    ↓ (Bearer token)
MCPO (port 12345)
    ↓
Friday Memory MCP Server
    ↓
Memory System Databases
```

## Security

- All communication uses HTTPS (via Caddy)
- OAuth tokens expire after 1 hour
- Bearer tokens are never exposed to the client
- MCPO API key is only used server-side

## Next Steps

1. ✅ OAuth proxy is running and tested
2. ✅ Caddy routes are configured
3. Configure Claude Desktop (follow steps above)
4. Test with simple queries
5. Enjoy using Friday Memory from Claude Desktop and Mobile!

## Support

If you encounter issues:

1. Check the OAuth proxy logs:
   ```bash
   sudo journalctl -u oauth-mcpo-proxy -n 50
   ```

2. Check the MCPO/MCP logs (if available)

3. Verify all services are running:
   ```bash
   sudo systemctl status oauth-mcpo-proxy
   ps aux | grep mcpo
   ps aux | grep caddy
   ```

4. Test endpoints locally:
   ```bash
   curl http://localhost:8888/health
   curl http://localhost:8888/oauth/authorize?client_id=friday-memory-claude-desktop
   ```

---

**Status:** ✅ Ready for Claude Desktop connection
**Last Updated:** November 27, 2025
**OAuth Proxy Version:** 1.0.0
