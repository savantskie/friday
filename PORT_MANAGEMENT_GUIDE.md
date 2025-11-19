# MCP Server Port Management System

## Overview

The Friday Memory MCP Server now features intelligent port management that:
- **Automatically detects the calling program** (VS Code, LM Studio, Ollama, OpenWebUI, etc.)
- **Falls back to backup ports** if the primary port is unavailable
- **Still works correctly on any assigned port** (clients can discover which port)
- **Cleans up gracefully** when shutting down

## Problem It Solves

Previously, the MCP server would crash if port 21434 was already in use by another instance. This commonly happened when:
- Running MCP server in VS Code while LM Studio was also using it
- Multiple instances started accidentally
- Server crashed but didn't release the port

Now the server automatically:
1. Tries to bind to primary port (21434)
2. Falls back to backup ports (21435-21439) if needed
3. Detects which program called it (VS Code, LM Studio, etc.)
4. Saves port info for clients to discover
5. Works seamlessly on any assigned port

## How It Works

### 1. Port Detection Flow

```
MCP Server Start
    ↓
Detect Caller Program (detect_caller_program)
    - Checks parent process name
    - Checks Python command line
    - Returns: VSCODE, LM_STUDIO, OLLAMA, OPENWEBUI, or UNKNOWN
    ↓
Find Available Port (find_available_port)
    - Try primary port (21434)
    - If unavailable, try backups (21435, 21436, 21437, 21438, 21439)
    - Return first available
    ↓
Save Port Info (save_port_info)
    - Writes to memory_data/mcp_server_port.json
    - Contains: active port, caller, process ID, timestamp
    ↓
Start HTTP Server on Found Port
```

### 2. Port Info File

When the server starts, it creates `memory_data/mcp_server_port.json`:

```json
{
  "active_port": 21435,
  "primary_port": 21434,
  "caller_program": "lm_studio",
  "process_id": 12345,
  "timestamp": "2025-11-18T13:52:31.460339",
  "http_url": "http://127.0.0.1:21435",
  "status": "active"
}
```

This allows clients to discover which port the server is actually listening on.

### 3. Client Discovery

Clients can read `memory_data/mcp_server_port.json` to find the active port:

```python
from port_manager import PortManager

# Discover which port the server is on
active_port = PortManager.get_active_port("/path/to/memory_data")
# Returns: 21435 (if server is on backup port)
```

## New Endpoints

The HTTP API now includes diagnostics endpoints:

### GET /api/health
Health check with server info:
```json
{
  "status": "healthy",
  "server": "friday-memory",
  "port": 21435,
  "primary_port": 21434,
  "caller_program": "lm_studio",
  "process_id": 12345,
  "http_url": "http://127.0.0.1:21435",
  "process_name": "python3",
  "memory_usage_mb": 45.2
}
```

### GET /api/diagnostics
Full diagnostics showing all port and caller info:
```json
{
  "server_info": {
    "active_port": 21435,
    "primary_port": 21434,
    "backup_ports": [21435, 21436, 21437, 21438, 21439],
    "http_url": "http://127.0.0.1:21435",
    "caller_program": "lm_studio"
  },
  "process_info": { ... },
  "message": "MCP server successfully detected caller program and bound to available port"
}
```

## Supported Caller Programs

The system detects:
- **VS Code** (Pylance, VS Code Extensions)
- **LM Studio** (Local LLM interface)
- **Ollama** (Container orchestration)
- **OpenWebUI** (Web interface)
- **Unknown** (Other callers, still works)

Detection uses two strategies:
1. **Parent process name** - checks if parent is `code`, `lm-studio`, `ollama`, etc.
2. **Command line arguments** - searches Python command line for program names

## Port Assignment Strategy

```
Primary Port:   21434
Backup Ports:   21435, 21436, 21437, 21438, 21439
Max Instances:  6 concurrent MCP servers
```

The system will find the first available port in this range. If all 6 are in use, it raises an error with a clear message.

## Troubleshooting

### Server Still Fails to Start

If you see "No available ports found", check for stale processes:

```bash
# Check what's using the port range
lsof -i :21434-21439

# Or with netstat
netstat -tlnp | grep -E "21434|21435|21436|21437|21438|21439"

# Kill stale process if needed
kill -9 <PID>
```

### Finding Which Port the Server Is On

Read the port info file:

```bash
cat /media/nate/Friday/Friday/memory_data/mcp_server_port.json
```

Or query the health endpoint once you know it's running.

### Multiple Instances Running

You can now run multiple MCP server instances (one per program). Each will:
- Detect its caller program
- Find its own available port
- Save its own port info (or create separate files if needed)

## Configuration

To customize port ranges, edit `port_manager.py`:

```python
class PortManager:
    PRIMARY_PORT = 21434           # Change this
    BACKUP_PORTS = [21435, ...]    # Change this
    PORT_INFO_FILENAME = "..."     # Change filename
```

## Technical Details

### Port Availability Check

Uses raw socket binding to check if port is available:

```python
def is_port_available(self, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result != 0  # Non-zero = port available
```

This is more reliable than checking /proc because it accounts for the SO_REUSEADDR socket option and actual binding state.

### Caller Detection

Uses `psutil` to inspect the process tree:

```python
process = psutil.Process(os.getpid())
parent = process.parent()
# Check parent name and command line
```

This works across platforms (Windows, Linux, macOS) and detects even GUI applications that spawn Python processes.

### Graceful Shutdown

On server exit:
- Port info file is deleted (via `cleanup_port_info()`)
- Port is released back to OS
- If other instances exist, they continue running independently

## Testing

Run the port manager test:

```bash
cd /media/nate/Friday/Friday
python3 test_port_manager.py
```

This will:
1. Initialize the port manager
2. Show available and in-use ports
3. Find an available port
4. Save and verify port info
5. Show process details

## Dependencies

Added to `requirements.txt`:
- `psutil>=5.9.0` - Process and system monitoring

Install with:
```bash
pip install psutil
```

## Future Enhancements

Possible improvements:
1. **Per-program port reservation** - Always use same port for each program
2. **Port locking** - Prevent port stealing by multiple instances
3. **Web UI port display** - Show active port in web dashboard
4. **Auto-reconnect** - Clients auto-discover new port if server restarts
5. **Port history** - Log which ports were used and when
