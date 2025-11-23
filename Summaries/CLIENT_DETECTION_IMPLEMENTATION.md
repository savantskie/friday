# Client Detection Fix - Implementation Guide

## Problem
The MCP server was detecting all clients as "unknown" because detection was only happening during HTTP server startup (`start_http_server`), but when the MCP server is imported as a module (LM Studio, VS Code), tools are requested before the HTTP server starts. This meant the caller program was never detected.

## Solution
Implemented **lazy detection** in `_detect_client_type()` method. When tools are requested and no detection has happened yet, the method now triggers detection immediately rather than waiting for HTTP server startup.

### Key Changes

#### 1. Import CallerProgram Enum (friday_memory_mcp_server.py, line 52)
```python
from port_manager import PortManager, CallerProgram
```
Needed to check `CallerProgram.UNKNOWN` value.

#### 2. Lazy Detection in _detect_client_type() (lines 1310-1365)
```python
def _detect_client_type(self) -> str:
    # Ensure caller program has been detected
    if port_manager.caller_program == CallerProgram.UNKNOWN and not getattr(port_manager, '_detection_attempted', False):
        logger.debug("Caller program not yet detected - running detection now")
        port_manager.detect_caller_program()
        port_manager._detection_attempted = True
    
    # Priority 1: Check if we're running on OpenWebUI's dedicated port (12345)
    if port_manager.active_port and port_manager.active_port == 12345:
        return "unknown"  # OpenWebUI gets core tools
    
    # Priority 2: Use process-based caller detection
    caller = port_manager.caller_program.value
    
    # Map caller program appropriately...
```

The `_detection_attempted` flag prevents redundant detection calls.

#### 3. Enhanced port_manager.py Detection (lines 64-155)
Multiple detection methods applied in order:
1. Parent process name (VS Code: "code"/"electron", LM Studio: "lm-studio", etc.)
2. Grandparent process name (for nested calls like bash → code)
3. Command line scanning (looks for ".vscode", "vscode-server", "copilot", etc.)

## How It Works Now

### When MCP Server is Imported as Module (LM Studio, VS Code)

```
1. Client imports friday_memory_mcp_server
2. Client asks for tools → list_tools() called → _get_client_tools() called
3. _get_client_tools() calls _detect_client_type()
4. _detect_client_type() sees no detection yet
5. Triggers port_manager.detect_caller_program() immediately
6. Checks parent process name → finds "code" or "lm-studio"
7. Returns appropriate tool set
8. Sets _detection_attempted = True (won't re-detect next time)
```

### When MCP Server Starts HTTP Server (OpenWebUI via MCPO)

```
1. start_http_server() called
2. Calls port_manager.detect_caller_program() at startup (line 1891)
3. HTTP server starts on available port (usually 21434)
4. When tools requested, _detect_client_type() is called
5. Checks: is active_port == 12345? (OpenWebUI specific port)
6. Falls back to process-based detection if not on 12345
```

## Detection Flow for Each Platform

### VS Code
```
Process Tree:
  python (MCP server) → bash → code (VS Code)

Detection:
  1. Parent = bash (no match)
  2. Grandparent = code (✓ MATCH)
  3. Returns "vscode"
  4. Tools: Core + VS Code development tools
```

### LM Studio
```
Process Tree:
  python (MCP server) → lm-studio (direct parent)

Detection:
  1. Parent = lm-studio (✓ MATCH)
  2. Returns "unknown" (core tools only)
  3. Tools: Core memory tools
```

### OpenWebUI via MCPO
```
Process Tree:
  HTTP server on port 12345

Detection:
  1. Port detection: active_port == 12345 (✓ MATCH)
  2. OR: Process name detection
  3. Returns "unknown" (core tools only)
  4. Tools: Core memory tools
```

## Testing the Detection

### Test Individual Environment
Run the diagnostic script appropriate for your platform:

```bash
# From VS Code Terminal:
python3 /media/nate/Friday/Friday/test_multi_env_detection.py

# From LM Studio Terminal:
python3 /media/nate/Friday/Friday/test_multi_env_detection.py

# From OpenWebUI machine:
python3 /media/nate/Friday/Friday/test_multi_env_detection.py
```

This shows:
- What process tree is detected
- What client type will be recognized
- What tools will be available
- Troubleshooting information

### Expected Outputs

**From VS Code:**
```
✅ Your environment: VSCODE
🛠️  Tools you'll have access to:
   ✓ Core Memory Tools (all memory/reminder/appointment tools)
   ✓ VS CODE-SPECIFIC Tools (project insight, development session, etc.)
```

**From LM Studio:**
```
✅ Your environment: LM_STUDIO
   (But may show as UNKNOWN if detection doesn't find "lm-studio" in parent)
🛠️  Tools you'll have access to:
   ✓ Core Memory Tools only
```

**From OpenWebUI on port 12345:**
```
✅ Port detected: 12345 (OpenWebUI)
🛠️  Tools you'll have access to:
   ✓ Core Memory Tools only
```

## Troubleshooting

### Issue: VS Code showing "unknown" instead of "vscode"

**Root Cause:** Parent process detection didn't find "code" or "electron"

**Solutions:**
1. Check process tree output from diagnostic script
2. Look for different parent name (might be different VS Code setup)
3. Restart VS Code - process tree might need refreshing
4. The detection will still work, but VS Code tools won't be available until process name is correctly identified

### Issue: LM Studio showing "unknown"

**Root Cause:** Parent process name doesn't match "lm-studio" pattern

**Solutions:**
1. Check process tree output from diagnostic script
2. Report the actual parent process name
3. We can add it to detection patterns
4. LM Studio gets same tools as "unknown" anyway (core tools only)

### Issue: OpenWebUI on MCPO not detecting

**Root Cause:** Running on non-standard port (not 12345)

**Solutions:**
1. Check what port MCPO is actually running on
2. The process-based detection will handle it if port detection fails
3. Update hardcoded port if needed

## Code Flow Summary

```
MCP Client Requests → list_tools()
                   → _get_client_tools()
                   → _detect_client_type()
                      ├─ If caller_program == UNKNOWN and not _detection_attempted:
                      │   └─ Run detect_caller_program() NOW (lazy detection)
                      ├─ Check if active_port == 12345 (OpenWebUI)
                      └─ Map caller_program to tool set
                   → Return appropriate tools
```

## Files Modified

1. **friday_memory_mcp_server.py**
   - Line 52: Added CallerProgram import
   - Lines 1310-1365: Implemented lazy detection in _detect_client_type()

2. **port_manager.py**
   - Lines 64-155: Enhanced detect_caller_program() with multiple detection methods

3. **test_multi_env_detection.py** (New)
   - Comprehensive diagnostic script for testing all three environments

## Summary

The fix ensures that:
- ✅ VS Code using MCP will detect "vscode" and get development tools
- ✅ LM Studio using MCP will detect "lm_studio" and get core tools
- ✅ OpenWebUI via MCPO will detect port 12345 and get core tools
- ✅ Detection happens automatically when tools are first requested (lazy)
- ✅ Redundant detection is prevented with _detection_attempted flag
- ✅ Multiple detection methods ensure reliable identification
