# Valve Persistence Solution - Friday Short Term Memory

## Problem Statement
OpenWebUI's Save button for valve settings accepts the HTTP POST request (200 OK) but doesn't actually persist the settings to its config storage. This means:
- User sets `max_total_memories=3000`
- Clicks Save
- OpenWebUI accepts the change (HTTP 200)
- Settings work for the current session (in-memory)
- **But on restart, they revert to defaults (200)**

## Root Cause
OpenWebUI appears to have a bug or design issue where the valve configuration isn't being written to persistent storage, or the plugin isn't loading it from storage even if it exists.

## Solution Implemented
A **two-part workaround** that provides persistent valve settings independent of OpenWebUI's storage:

### 1. **Persistent JSON File Storage**
- Location: `/media/nate/Friday/Friday/valve_settings.json`
- Format: JSON containing all current valve settings
- Mounted on OpenWebUI container so it persists across restarts

### 2. **Automatic Load & Save Mechanism**

#### At Startup (`__init__`)
1. **First priority**: Load from persisted JSON file (if exists)
2. **Second priority**: Try to load from OpenWebUI config
3. All loaded settings are saved back to file as backup

#### During Message Processing (`inlet`)
1. Check if OpenWebUI injected config (with new user settings)
2. If yes: Apply new settings AND save to file immediately
3. If no: Fall back to persisted settings from file
4. Log all valve status so user can verify they're active

### 3. **Code Changes**

#### New Methods Added
```python
def _load_persisted_valve_settings(self) -> Optional[Dict[str, Any]]:
    """Load valve settings from /media/nate/Friday/Friday/valve_settings.json"""
    
def _save_persisted_valve_settings(self, valves: 'Filter.Valves') -> bool:
    """Save current valve settings to valve_settings.json"""
```

#### Updated `__init__` Method
- Now loads persisted settings as highest startup priority
- Falls back through: persisted file → OpenWebUI config → defaults
- Automatically saves any loaded settings

#### Updated `inlet` Method
- Saves OpenWebUI-injected settings to file immediately
- Falls back to persisted settings if OpenWebUI doesn't inject
- Provides clear logging so user knows which source was used

## Usage

### Setting Valves
1. Go to function settings in OpenWebUI
2. Adjust any valve values (e.g., `max_total_memories=3000`)
3. Click Save
4. Plugin will:
   - Accept the setting from OpenWebUI
   - Immediately save it to `/media/nate/Friday/Friday/valve_settings.json`
   - Use it for all future messages

### Verifying Settings
Check the logs (in OpenWebUI or via terminal) for:
```
📋 VALVE STATUS - max_total_memories=3000, pruning_strategy=fifo, ...
```

If you see `max_total_memories=3000`, your settings are active.

### Persistence Across Restarts
1. When you restart OpenWebUI, the plugin starts up
2. Loads settings from `valve_settings.json` first
3. Your `max_total_memories=3000` setting is restored automatically
4. No need to reconfigure after restart

### Manual Adjustment (Advanced)
You can directly edit `/media/nate/Friday/Friday/valve_settings.json`:
```json
{
  "max_total_memories": 3000,
  "pruning_strategy": "fifo",
  "top_n_memories": 4,
  "vector_similarity_threshold": 0.75,
  ...
}
```
Just restart the plugin or send a message to reload.

## Benefits

✅ **Survives Restarts** - Settings persist even if OpenWebUI is restarted  
✅ **Backup Mechanism** - Settings saved to file as insurance  
✅ **Clear Logging** - Always know which valve source is being used  
✅ **Fallback Chain** - Tries OpenWebUI first, falls back to file if needed  
✅ **No Manual Intervention** - Happens automatically on message send  
✅ **Mounted Directory** - File is in directory OpenWebUI can access  

## Technical Details

### Load Priority (Startup)
1. Persisted file `/media/nate/Friday/Friday/valve_settings.json`
2. OpenWebUI injected config (`self.config['valves']`)
3. Hardcoded defaults in `Valves` class

### Save Timing
- **On startup**: After loading from any source
- **On first message**: If OpenWebUI injected config
- **Automatic fallback**: If OpenWebUI doesn't inject but file exists

### File Location
The file persists in the mounted volume:
```bash
docker run -v /media/nate/Friday/Friday:/media/nate/Friday/Friday ...
```

So it's automatically preserved across container restarts.

## Troubleshooting

### Settings still reverting?
Check the inlet logs:
```
⚠️ OpenWebUI did NOT inject valve config (self.config['valves'] is None/missing). Using current valves.
✓ Fell back to persisted valve settings from file
📋 VALVE STATUS - max_total_memories=3000, ...
```

If you see `max_total_memories=3000` in the VALVE STATUS line, the settings are working.

### File not being created?
- Check permissions on `/media/nate/Friday/Friday/`
- Ensure OpenWebUI container has write access to the directory
- Check logs for: `✓ Persisted valve settings to /media/nate/Friday/Friday/valve_settings.json`

### Reverting to defaults
Delete the file:
```bash
rm /media/nate/Friday/Friday/valve_settings.json
```
On next restart, plugin will use OpenWebUI defaults.

## Next Steps (Investigation)

If you want to investigate the OpenWebUI bug further:
1. Check OpenWebUI's database where plugin configs should be stored
2. Verify the valve save endpoint is actually writing to storage
3. Check if plugin config loader is being called at startup

This workaround ensures your settings work correctly regardless of OpenWebUI's config persistence issues.
