# Friday Memory System - Complete Architecture Documentation

**Last Updated:** December 4, 2025  
**Status:** Comprehensive overview of all system components, connections, and data flows

---

## Executive Summary

The Friday Memory System is a multi-layered, distributed architecture designed to provide persistent, intelligent memory capabilities across multiple interfaces (OpenWebUI, LM Studio, Ollama, VS Code). The system has **three main components** running in different environments with different purposes:

| Component | Location | Environment | Purpose | Primary Network |
|-----------|----------|-------------|---------|-----------------|
| **friday_memory_system.py** | `/media/nate/Friday/Friday/` | Host machine | Core database engine + embeddings | Local machine network (192.168.1.50) |
| **friday_memory_short_term.py** | OpenWebUI plugin | Docker container | Chat memory extraction/injection | Docker network (172.17.0.1 gateway) |
| **friday_memory_mcp_server.py** | `/media/nate/Friday/Friday/` | Host machine | MCP interface for VS Code/tools | Local machine network (stdio/HTTP) |

---

## Network Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        HOST MACHINE                             │
│                    (192.168.1.50 network)                       │
│                                                                 │
│  ┌──────────────────────┐    ┌──────────────────────┐           │
│  │   LM Studio          │    │   Ollama             │           │
│  │   Port: 1234         │    │   Port: 11434        │           │
│  │   Embeddings:        │    │   Chat Models:       │           │
│  │   /v1/embeddings     │    │   /api/chat          │           │
│  │   /v1/models         │    │   /api/embeddings    │           │
│  └──────────────────────┘    │   /api/tags          │           │
│           ▲                   └──────────────────────┘           │
│           │                            ▲                        │
│           │                            │                        │
│  ┌────────┴────────────────────────────┴──────────────────┐     │
│  │  friday_memory_system.py (HOST)                        │     │
│  │  ─────────────────────────────────────────────────     │     │
│  │  • Core database engine                              │     │
│  │  • EmbeddingService (tries LM Studio, falls back)  │     │
│  │  • Conversation/Memory/Schedule DBs                 │     │
│  │  • Direct HTTP to 192.168.1.50:1234 & :11434      │     │
│  │                                                      │     │
│  │  embedding_config.json:                            │     │
│  │    primary: LM Studio @ 192.168.1.50:1234         │     │
│  │    fallback: Ollama @ localhost:11434             │     │
│  └──────┬───────────────────────────────────────────────┘     │
│         │                                                      │
│         │ (via stdin/stdio)                                   │
│  ┌──────┴───────────────────────────────────────────────┐     │
│  │  friday_memory_mcp_server.py (HOST)                 │     │
│  │  ─────────────────────────────────────────────────  │     │
│  │  • MCP Server interface (stdio-based)              │     │
│  │  • Port detection (OpenWebUI=12345, other=stdio)  │     │
│  │  • Bridges external tools to memory system         │     │
│  │  • Used by: VS Code, LM Studio UI                 │     │
│  │                                                     │     │
│  │  Flows requests through:                          │     │
│  │    → friday_memory_system.py → LM Studio/Ollama   │     │
│  └────────────────────────────────────────────────────┘     │
│                                                                 │
│                                                                 │
│                    CADDY REVERSE PROXY                          │
│                    Port: 443 (HTTPS)                            │
│                    Domain: fridayonline.bounceme.net            │
│                    ─────────────────────────                    │
│                    Routes available:                            │
│                    • /mcpo   → 192.168.1.50:12345  ✓ Working   │
│                    • /lmstudio → 192.168.1.50:1234 ✓ Configured│
│                    • /ollama → NOT CONFIGURED ✗                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS Port 443
                              │
        ┌─────────────────────┴──────────────────────┐
        │                                             │
┌───────────────────┐                   ┌────────────────────────┐
│  DOCKER CONTAINER │                   │  EXTERNAL CLIENTS      │
│  (OpenWebUI)      │                   │  (Web Browsers, etc)   │
│                   │                   │                        │
│  127.0.0.1:3000   │                   │  fridayonline.         │
│                   │                   │  bounceme.net          │
│  ┌───────────────┐│                   └────────────────────────┘
│  │ friday_memory_││
│  │ short_term.py││
│  │               ││   Uses host gateway: 172.17.0.1
│  │ Connects to:  ││   ├─ 172.17.0.1:1234    (LM Studio embeddings)
│  │ • Ollama      ││   └─ 172.17.0.1:11434   (Ollama for chat)
│  │ • LM Studio   ││
│  │ • Friday DB   ││   Should NOT use HTTPS (same machine)
│  └───────────────┘│
│                   │
└───────────────────┘
```

---

## Detailed Component Breakdown

### 1. **friday_memory_system.py** (Host Machine)

**Location:** `/media/nate/Friday/Friday/friday_memory_system.py`  
**Runs on:** Host machine  
**Port:** None (library/service, not a server)  
**Used by:** MCP Server, Short Term plugin, standalone scripts

**Key Responsibilities:**
- **Database Management:** SQLite databases for conversations, memories, schedules, AI insights, etc.
- **Embedding Service:** Converts text to embeddings for semantic search
- **Memory Operations:** Store, retrieve, search, update memories across all databases
- **File Monitoring:** Watches for Ollama/LM Studio conversation files and imports them

**Embedding Service Flow:**
```
Text to embed
    ↓
EmbeddingService.generate_embedding()
    ↓
Primary Provider (LM Studio @ 192.168.1.50:1234/v1/embeddings)
    ↓ [if fails]
Fallback Provider (Ollama @ localhost:11434/api/embeddings)
    ↓ [if both fail]
Return empty list (semantic search unavailable)
```

**Configuration File:** `embedding_config.json`
```json
{
  "primary": {
    "provider": "lmstudio",
    "model": "text-embedding-nomic-embed-text-v1.5",
    "base_url": "http://192.168.1.50:1234/v1/embeddings"
  },
  "fallback": {
    "provider": "ollama",
    "model": "nomic-embed-text:latest",
    "base_url": "http://localhost:11434/api/embeddings"
  }
}
```

**Connection Details:**
- ✓ Uses **direct HTTP** to LM Studio (port 1234) - no HTTPS needed
- ✓ Uses **direct HTTP** to Ollama (port 11434) - no HTTPS needed
- ✓ Both are on the same physical machine - HTTPS adds unnecessary overhead
- ✓ LM Studio preferred because it's specifically running an embedding model
- ✓ Ollama is fallback for embeddings (though it's a general LLM server)

---

### 2. **friday_memory_short_term.py** (OpenWebUI Plugin)

**Location:** Loaded as a plugin in OpenWebUI  
**Runs in:** Docker container (127.0.0.1:3000 mapped from container)  
**Container Network:** Docker network with gateway 172.17.0.1  
**Used by:** Chat interface in OpenWebUI

**Key Responsibilities:**
- Extract memories from user messages during chat
- Retrieve relevant memories from the database
- Inject memories into LLM prompts for context
- Manage memory deduplication and pruning

**How it connects to host services:**

```
Short Term Plugin (inside Docker container)
    ↓
Uses gateway IP: 172.17.0.1
    ├─ 172.17.0.1:1234 → LM Studio embeddings (for embedding messages)
    ├─ 172.17.0.1:11434 → Ollama chat (for LLM relevance scoring)
    └─ (Friday Memory DB accessed directly - shared filesystem)
```

**Configuration (from Valves/settings):**
```python
llm_api_endpoint_url: "http://172.17.0.1:11434/api/chat"
embedding_api_endpoint_url: "http://192.168.1.50:1234/v1/embeddings"
```

**Why 172.17.0.1?**
- Docker containers cannot use `localhost` to reach host services
- `172.17.0.1` is the Docker host gateway on Linux
- Container can reach host's port 11434 via this gateway
- Container can reach LM Studio embeddings (though config shows hardcoded IP)

**Important Note:** The short_term.py uses `172.17.0.1` for Ollama but `192.168.1.50` for LM Studio embeddings. This seems inconsistent but both work because they're on the same physical machine that hosts both services.

---

### 3. **friday_memory_mcp_server.py** (Host Machine)

**Location:** `/media/nate/Friday/Friday/friday_memory_mcp_server.py`  
**Runs on:** Host machine  
**Communication:** stdio-based (MCP protocol)  
**Port for OpenWebUI:** Port 12345 (when called via Caddy/OpenWebUI integration)  
**Used by:** VS Code, LM Studio, Ollama UIs, OpenWebUI via MCPO

**Key Responsibilities:**
- Expose Friday Memory System as MCP tools
- Route requests from external clients to memory system
- Provide client-specific tool sets based on caller identification
- Handle embeddings in background for created reminders

**Client Detection Logic:**
```python
def _identify_caller():
    # Priority 1: Check if running on port 12345 (OpenWebUI/MCPO)
    if port == 12345:
        return "openwebui"
    
    # Priority 2: Check parent process name
    if parent_process == "LM Studio":
        return "lm_studio"
    elif parent_process == "Ollama":
        return "ollama"
    elif parent_process == "code" or "code-server":
        return "vscode"
    
    return "unknown"
```

**How it connects to Friday Memory System:**
- Imports `FridayMemorySystem` directly (same machine, same Python process)
- Calls methods like `store_memory()`, `search_memories()`, etc.
- Delegates embedding generation to `friday_memory_system.py`

---

## Data Flow Diagrams

### Flow 1: User Sends Message in OpenWebUI

```
User types message in OpenWebUI
    ↓
OpenWebUI frontend (browser)
    ↓
OpenWebUI backend (127.0.0.1:3000)
    ↓
Loads chat model (Ollama via 172.17.0.1:11434)
    ↓
Calls friday_memory_short_term.py plugin
    ↓ (runs inside container, Docker network)
    ├─ Generate embedding for message
    │   └─ HTTP POST to 192.168.1.50:1234/v1/embeddings
    │       ↓
    │       LM Studio (host)
    │
    ├─ Search relevant memories
    │   └─ Query Friday Memory DB (shared)
    │       ↓
    │       friday_memory_system.py (host)
    │
    ├─ Call LLM to score relevance
    │   └─ HTTP POST to 172.17.0.1:11434/api/chat
    │       ↓
    │       Ollama (host, via Docker gateway)
    │
    ├─ Inject memories into prompt
    │   └─ Modify system prompt with relevant memories
    │
    └─ Send prompt to LLM
        └─ HTTP POST to 172.17.0.1:11434/api/chat
            ↓
            Ollama generates response
    ↓
Response returned to user
```

### Flow 2: VS Code Uses Friday Memory via MCP

```
VS Code
    ↓
Invokes MCP command (e.g., "search_memories")
    ↓
stdio connection to friday_memory_mcp_server.py
    ↓
MCP Server identifies caller as "vscode"
    ↓
Calls friday_memory_system.search_memories()
    ↓
Friday Memory System may need embeddings
    ├─ Generate embedding for search query
    │   └─ HTTP POST to 192.168.1.50:1234/v1/embeddings
    │       ↓
    │       LM Studio
    │
    ├─ Query memory databases
    │   └─ SQLite queries
    │
    └─ Return results
    ↓
MCP Server formats response
    ↓
stdio back to VS Code
```

### Flow 3: External Browser Accesses Friday via Caddy

```
Browser: https://fridayonline.bounceme.net/mcpo
    ↓
Caddy reverse proxy (HTTPS)
    ↓
Routes /mcpo → 192.168.1.50:12345
    ↓
HTTP connection to OpenWebUI/MCPO endpoint
    ↓
Can access Friday Memory tools
    ✓ WORKS because MCP server is running and port 12345 is exposed
```

```
Browser: https://fridayonline.bounceme.net/ollama (NOT CONFIGURED)
    ↓
Caddy reverse proxy (HTTPS)
    ↓
❌ No route for /ollama
    ↓
404 Not Found
```

---

## Why LM Studio (port 1234) is Necessary

**LM Studio serves embeddings specifically:**

1. **Primary Embedding Provider**
   - Configured in `embedding_config.json` as the primary provider
   - Dedicated embedding model loaded and running
   - Better quality embeddings than general LLM

2. **Used by:**
   - `friday_memory_system.py` for all semantic search operations
   - `friday_memory_short_term.py` for memory relevance scoring
   - Any memory search operation across all components

3. **Why not Ollama for embeddings?**
   - Ollama is a general LLM server primarily for chat models
   - Can run embedding models too, but not optimized for it
   - LM Studio provides dedicated, faster embeddings
   - LM Studio is fallback if needed

4. **Why HTTP is fine (not HTTPS):**
   - Both are on the same physical machine (192.168.1.50)
   - Direct local network communication
   - HTTPS adds latency and complexity with no security benefit
   - Only exposed via HTTPS to external clients through `/lmstudio` path in Caddy (which proxies back to HTTP internally)

---

## Why Ollama (port 11434) is NOT in Caddyfile

**Ollama is used locally only:**

1. **Used for:**
   - Chat model inference in OpenWebUI
   - Chat/text completion in `friday_memory_short_term.py`
   - Optional fallback for embeddings

2. **Why not exposed through Caddy:**
   - It's primarily accessed locally through OpenWebUI (127.0.0.1:3000)
   - The short_term plugin connects directly via Docker gateway (172.17.0.1:11434)
   - No external clients need direct access to Ollama API
   - OpenWebUI itself handles the chat model interaction

3. **Could it be added?**
   - Technically yes, but unnecessary right now
   - Would create: `https://fridayonline.bounceme.net/ollama`
   - Would proxy to `127.0.0.1:11434` internally
   - Use case: If you wanted external clients to call Ollama directly (likely not needed)

---

## IP Address Reference

| Service | Host IP | Docker IP | Port | Purpose |
|---------|---------|-----------|------|---------|
| **LM Studio** | 192.168.1.50 | 172.17.0.1 | 1234 | Embeddings (primary) |
| **Ollama** | 127.0.0.1 or localhost | 172.17.0.1 | 11434 | Chat models + embeddings (fallback) |
| **OpenWebUI** | 127.0.0.1 | 127.0.0.1 (mapped) | 3000 | Web interface |
| **Friday MCP Server** | N/A (stdio) | N/A (stdio) | N/A | MCP interface |
| **Caddy Reverse Proxy** | 0.0.0.0 | N/A | 443 | HTTPS endpoint |

**Why 192.168.1.50 for LM Studio?**
- This is Nate's host machine on the local network
- Used by short_term plugin and by `friday_memory_system.py` on host
- Reachable from Docker via Docker gateway translation

**Why 127.0.0.1 vs 172.17.0.1?**
- Short_term plugin (in Docker) must use `172.17.0.1` to reach host services
- `localhost` (127.0.0.1) inside a container refers to the container itself, not the host
- Docker automatically translates `172.17.0.1` to the host

---

## Configuration Issues & Inconsistencies

### Issue 1: Hardcoded IPs
- `friday_memory_system.py` uses `192.168.1.50` for LM Studio embeddings
- `friday_memory_short_term.py` uses `192.168.1.50` for embeddings but `172.17.0.1` for Ollama chat
- This works because they're the same physical machine, but it's not resilient

### Issue 2: Docker Gateway Awareness
- `172.17.0.1` works on Linux but may not work on all Docker setups
- Windows Docker uses `host.docker.internal` instead
- Code in "short term candidates" shows comments about this

### Issue 3: No HTTPS Between Local Services
- LM Studio and Ollama are not exposed via HTTPS internally
- Caddy routes `/lmstudio` to the internal HTTP endpoint
- This is correct (no need for HTTPS locally)
- But it's worth noting that external HTTPS masks internal HTTP

---

## Recommendation: Why NOT to Add Ollama to Caddyfile

**Current State:** Ollama works fine, no issues

**Why not expose it through HTTPS:**
1. **No external clients need it** - OpenWebUI uses it internally
2. **Unnecessary complexity** - Adds another route to manage
3. **Security not needed locally** - Internal services don't need encryption
4. **Performance overhead** - HTTPS adds latency for local calls
5. **Inconsistent architecture** - If exposed, should be for a specific use case

**If you later want to expose Ollama:**
- Define your use case (e.g., "remote clients need to call Ollama directly")
- Then add the route to Caddyfile
- Configure proper authentication/authorization
- Update documentation to explain why

---

## Testing the Architecture

### Test 1: Verify LM Studio Embeddings Work
```bash
# From host
curl -X POST http://192.168.1.50:1234/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "text-embedding-nomic-embed-text-v1.5", "input": "test"}'
```

### Test 2: Verify Ollama Works
```bash
# From host
curl -X POST http://localhost:11434/api/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "nomic-embed-text:latest", "prompt": "test"}'
```

### Test 3: Verify Short Term Plugin Access
```bash
# From Docker container
curl -X POST http://172.17.0.1:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3:latest", "prompt": "hello"}'
```

### Test 4: Verify MCP Server Works
```bash
# Via VS Code or command line
mcp invoke friday_memory_mcp_server.py "search_memories" \
  --arg "query" "test" \
  --arg "user_id" "default"
```

---

## Future Architecture Improvements

### 1. Service Discovery
- Don't hardcode IPs - use service discovery (Consul, etcd)
- Allows dynamic reconfiguration

### 2. Unified Embedding Provider
- Currently: LM Studio primary, Ollama fallback
- Future: Abstract provider interface that supports multiple backends

### 3. Docker Compose
- Orchestrate all services (LM Studio, Ollama, OpenWebUI, Friday MCP)
- Eliminate hardcoded IPs with service names

### 4. Comprehensive Logging
- Track which embedding provider was used
- Log fallback events
- Monitor provider health

### 5. Configuration Management
- Centralize all connection strings
- Support environment variables
- Configuration UI in OpenWebUI

---

## Summary Table

| Component | Runs On | Network | Connects To | Purpose |
|-----------|---------|---------|-------------|---------|
| friday_memory_system.py | Host | Local/HTTP | LM Studio (1234), Ollama (11434) | Core memory engine |
| friday_memory_short_term.py | Docker | Docker Net | Ollama (172.17.0.1:11434), LM Studio (192.168.1.50:1234) | Memory injection in chat |
| friday_memory_mcp_server.py | Host | stdio/HTTPS | friday_memory_system.py (direct) | MCP interface for tools |
| Caddy | Host | HTTPS (443) | Internal HTTP endpoints | HTTPS reverse proxy |
| LM Studio | Host | HTTP (1234) | EmbeddingService requests | Embeddings only |
| Ollama | Host | HTTP (11434) | Chat/Embedding requests | Chat models + fallback embeddings |

---

## Conclusion

The Friday Memory System architecture is well-designed with:
- ✓ Clear separation of concerns (core engine, chat plugin, MCP interface)
- ✓ Appropriate use of HTTP for local services (no unnecessary HTTPS)
- ✓ Intelligent fallback for embeddings (LM Studio → Ollama)
- ✓ Support for multiple interfaces (OpenWebUI, VS Code, MCP clients)

**Current status:** Working as intended. LM Studio is necessary and properly configured. Ollama does not need to be in Caddyfile because it's accessed locally through OpenWebUI.
