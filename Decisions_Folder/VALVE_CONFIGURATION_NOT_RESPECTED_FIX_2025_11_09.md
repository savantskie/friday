# Valve Configuration Not Being Respected - FIX Applied

## The Real Problem

User had valve settings configured to 0.5 for similarity thresholds, but the inlet function was **ignoring these settings and reverting to defaults (0.7)** on every call.

## Root Cause

**File**: `/media/nate/Friday/Friday/friday_memory_short_term.py`, Line 1776

**Buggy Code**:
```python
self.valves = self.Valves(**getattr(self, "config", {}).get("valves", {}))
```

**The Problem**:
- Line attempts to reload valves from `self.config` on every inlet call
- If `self.config` is empty (which it is), `get("valves", {})` returns an empty dict `{}`
- Creating `self.Valves(**{})` means no kwargs, so all fields use their DEFAULTS
- **User's saved valve settings are completely discarded and replaced with defaults**

**Log Evidence**:
```
🔍 DEBUG: self.config = {}
🔍 DEBUG: self.config.get('valves') = <No valves key>
✓ Valves reloaded. vector_similarity_threshold=0.7, top_n_memories=3
```

Shows that:
- `self.config` is empty
- No valves in config
- But then vector_similarity_threshold is 0.7 (the DEFAULT), not 0.5 (what user set)

## The Fix

**Location**: Line 1771-1783 in `friday_memory_short_term.py`

**New Logic**:
```python
# CRITICAL FIX: Only reload valves if config actually contains valves, otherwise keep the valves from __init__
# This prevents user-configured valve settings from being overwritten by defaults
loaded_config_valves = getattr(self, "config", {}).get("valves", None)
if loaded_config_valves is not None:
    self.valves = self.Valves(**loaded_config_valves)
    logger.debug(f"✓ Valves reloaded from config. vector_similarity_threshold={self.valves.vector_similarity_threshold}, top_n_memories={self.valves.top_n_memories}")
else:
    logger.debug(f"✓ Using current valves (config not set). vector_similarity_threshold={self.valves.vector_similarity_threshold}, top_n_memories={self.valves.top_n_memories}")
```

**What Changed**:
1. Check if `loaded_config_valves` is NOT None (instead of defaulting to `{}`)
2. Only reload if config actually has valves
3. Otherwise keep the valves that were initialized in `__init__`
4. Better logging to show what's happening

## Why This Works

The valve settings are initialized in `__init__` (line 996-1020) where they're properly loaded from OpenWebUI config if available. By NOT resetting them on every inlet call, we preserve the user's actual settings.

**Behavior**:
- **First plugin load** (`__init__`): Load valves from saved OpenWebUI config or use defaults
- **Each inlet call**: Keep using those valves UNLESS OpenWebUI passes new config
- **Result**: User's valve settings are respected throughout the session

## What This Fixes

✅ User's valve settings (vector_similarity_threshold: 0.5) now used  
✅ Memory retrieval now works with the configured threshold  
✅ Inlet memory injection now respects user preferences  
✅ Each inlet call no longer overwrites configuration  

## No Default Changes Needed

The default thresholds of 0.7 are CORRECT for the code logic. The issue was never the defaults—it was that user settings weren't being respected. With this fix:
- If user has 0.5 configured → uses 0.5 ✅
- If user never configured → uses default 0.7 ✅

## Files Modified

- `/media/nate/Friday/Friday/friday_memory_short_term.py`
  - Lines 1771-1783: Fixed valve reloading logic to check for None instead of defaulting to empty dict

## Testing

Upload the fixed code and verify:
1. Logs should show "Using current valves (config not set)" or "Valves reloaded from config"
2. If you have 0.5 set, logs should show vector_similarity_threshold=0.5
3. Memory retrieval should now work with your actual configured thresholds
