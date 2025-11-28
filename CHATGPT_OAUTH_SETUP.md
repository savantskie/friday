# ChatGPT Developer Mode OAuth Setup

Your ChatGPT has its own separate OAuth credentials! This keeps Claude Desktop and ChatGPT memories separate so you can track which AI created what.

## ChatGPT OAuth Credentials

```
Client ID:     friday-memory-chatgpt
Client Secret: XpOHqE-4KxnFuwcqNKsYL3qO_g3lvNBvtCM3j3E3LNE
```

## Configure ChatGPT Developer Mode

### Step 1: Enable Developer Mode

1. Go to **ChatGPT Settings**
2. Navigate to **Connectors** → **Advanced**
3. Toggle **Developer Mode** ON

### Step 2: Add Friday Memory Connector

1. Go to **Settings** → **Connectors** → **Create**
2. Select **Remote MCP Server** or **Custom Connector**
3. Fill in the following details:

| Field | Value |
|-------|-------|
| **Name** | Friday Memory (or any name you prefer) |
| **Server URL** | `https://fridayonline.bounceme.net/mcp` |
| **Authentication Type** | OAuth |
| **Authorization URL** | `https://fridayonline.bounceme.net/oauth/authorize` |
| **Token URL** | `https://fridayonline.bounceme.net/oauth/token` |
| **Client ID** | `friday-memory-chatgpt` |
| **Client Secret** | `XpOHqE-4KxnFuwcqNKsYL3qO_g3lvNBvtCM3j3E3LNE` |

### Step 3: Save and Authorize

1. Click **Save** or **Create**
2. You'll be redirected to authorize
3. Click **Allow** or **Authorize**
4. Return to ChatGPT

### Step 4: Use in Developer Mode

1. Start a new conversation
2. Click the **Plus** (+) menu at the bottom
3. Select **Developer Mode**
4. Choose **Friday Memory** connector
5. Use your memory tools!

## Testing ChatGPT Integration

Try these prompts in Developer Mode:

- "Using the Friday Memory connector, what reminders do I have?"
- "Search my memories for important decisions"
- "Create a reminder for tomorrow at 10am"
- "What's the weather today?"

## Credential Comparison

### Claude Desktop
- **Client ID:** `friday-memory-claude-desktop`
- **Client Secret:** `t5rNBHPZEG5qAjHvYDbrCIjwtJrqFpIPoxfTEyGoTdw`
- **Platform:** Desktop & Mobile
- **Setup:** Settings > Connectors

### ChatGPT Developer Mode
- **Client ID:** `friday-memory-chatgpt`  ✓ Separate credentials!
- **Client Secret:** `XpOHqE-4KxnFuwcqNKsYL3qO_g3lvNBvtCM3j3E3LNE`
- **Platform:** Web only (currently)
- **Setup:** Settings > Connectors > Advanced > Developer Mode

## Benefits of Separate OAuth Clients

✅ **Tracking:** Each AI has its own client ID, making it easy to track which AI created what memory
✅ **Audit Trail:** OAuth logs show which AI (Claude vs ChatGPT) is making tool calls
✅ **Security:** Can revoke access for one client without affecting the other
✅ **Granular Control:** Can set different permissions for each client in the future

## Troubleshooting

### "Connection Failed"
- Check that the OAuth proxy is running: `sudo systemctl status oauth-mcpo-proxy`
- Verify both clients are in the config: Check `oauth_config.json`

### "Invalid Credentials"
- Double-check that you copied the ChatGPT credentials (NOT the Claude Desktop ones!)
- Make sure there are no extra spaces or typos
- Copy-paste directly from this file to avoid mistakes

### "Unauthorized"
- Try removing and re-adding the connector
- Make sure you're using the ChatGPT client credentials

## How It Works

```
ChatGPT (Developer Mode)
    ↓ OAuth 2.0 with client_id: friday-memory-chatgpt
https://fridayonline.bounceme.net/oauth/*  (Caddy reverse proxy)
    ↓
localhost:8888  (OAuth Proxy - validates ChatGPT credentials)
    ↓ Bearer token
MCPO (port 12345)
    ↓
Friday Memory MCP Server
    ↓ (Logs which client made the request)
Memory System Databases
```

## Next Steps

1. ✓ OAuth proxy supports both Claude Desktop and ChatGPT
2. ✓ ChatGPT has its own OAuth credentials
3. Configure ChatGPT Developer Mode (follow steps above)
4. Test with memory tools
5. Watch the logs to see which client is being used!

## Status

✅ OAuth proxy updated with multi-client support
✅ Claude Desktop client: `friday-memory-claude-desktop`
✅ ChatGPT client: `friday-memory-chatgpt`
✅ Both clients tested and working
✅ Memory system will track which AI created each memory

---

**Enjoy using Friday Memory with both Claude Desktop and ChatGPT!**

**Updated:** November 27, 2025
**OAuth Proxy Version:** 1.0.1 (Multi-client support)
