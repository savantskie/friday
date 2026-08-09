FMS SYSTEM MAP AUDIT REPORT
============================
Date: June 30, 2026
Scope: All FMS files vs System Map at FMS_Complete_System_Map.md
Method: Parallel audit of code content, file paths, and log files

================================================================================
SUMMARY
================================================================================
Total discrepancies found: 14 (2 HIGH, 5 MODERATE, 7 LOW)

================================================================================
HIGH SEVERITY
================================================================================

1. MISSING HTTP ENDPOINTS (documented but not in code)
   Map Section 2 lists: POST /api/memories/promote and DELETE /api/memories/cleanup
   Neither endpoint exists in friday_memory_mcp_server.py. They were either never
   implemented or removed. The map says they exist.

2. ENVIRONMENT VARIABLES DOCUMENTED BUT UNUSED
   Map Section 10 says:
   - AI_MEMORY_DATA_DIR (used by long-term system) — NOT checked anywhere in live FMS files
   - AI_MEMORY_LOG_DIR (used by long-term system) — NOT checked anywhere in live FMS files
   - MCP_API_KEY (used by MCP server) — NOT checked. MCP server reads from
     /media/nate/Friday/Friday/keys/mcpo_api_key.txt instead.
   These env vars only exist in the PAM upgrade folder, not in production.

3. get_system_health AND get_error_summary SKIP user_id/model_id
   Map says "ALL tools require user_id + model_id." But in mcp_server.py lines 2057-2060,
   these two tools call memory_system methods without passing user_id or model_id.

================================================================================
MODERATE SEVERITY
================================================================================

4. MEMORY_LINKING SCHEDULE WRONG IN MAP
   Map Section 8 (line 612): "memory_linking every 5hr"
   Actual code (line 2485): "daily@02:00,idle"
   Wrong frequency (5hr vs daily) AND map omits idle gate.

5. MISSING TASKS FROM SECTION 8 SHORT_TERM TABLE
   7 tasks registered by friday_memory_short_term.py lines 2483-2494 are NOT listed
   in Section 8's short_term task table:
   - retry_queue (interval:5m, db_light)
   - registry_sync (interval:2h,idle, db_heavy, memories)
   - nightly_sync (daily@02:30,idle, db_heavy, memories)
   - openwebui_import (interval:3h, db_light)
   - maintenance_mcp (interval:6h,anchor=03:00, db_heavy, conversations)
   - maintenance_24h (daily@05:00, db_heavy, conversations)
   - linking_validation (interval:6h,anchor=04:30, db_heavy, conversations)
   The map only shows 7 of ~14 registered tasks.

6. core_identity_progress.json MISSING ENTIRELY
   Map Section 2 line 195 and Section 6 line 511 say this file is written for
   crash recovery during core identity generation. It does not exist at
   /media/nate/Friday/Friday/ or /media/nate/Friday/Friday/memory_data/.
   If a generation run crashes mid-batch, progress is lost.

7. core_identity OUTPUT FILES IN WRONG LOCATIONS
   Map says:
   - friday_core_identity.json at /media/nate/Friday/Friday/
     Actual: /media/nate/Friday/Friday/memory_data/friday_core_identity_<uuid>.json
   - core_identity_tracking.json at /media/nate/Friday/Friday/
     Actual: /media/nate/Friday/Friday/memory_data/core_identity_tracking.json
   The map's documented paths are wrong for both files.

================================================================================
LOW SEVERITY
================================================================================

8. ORPHANED system_prompt.txt PATH IN core_identity.py
   Line 59 defines self.system_prompt_path but it is never read or written.
   The map's "FILES WRITTEN" section does not list it, but the code defines it.

9. FRIDAY UPGRADE FOLDER STALE
   /media/nate/Friday/Friday/Friday_Memory_System_Update/friday_memory_short_term.py
   is at v0.0.25, behind production's v0.0.26. The June 30 fixes (multi-user iteration,
   identity-missing logging) are missing from the upgrade folder.

10. STALE LINE COUNTS IN MAP
    - friday_memory_short_term.py: map says ~11,032, actual 11,137 (+105)
    - database_maintenance.py: map says ~2,132+, actual 2,910 (+778)
    - core_identity.py: map says 1,412, actual 1,510 (+98)
    Line numbers referenced in Section 7 (normalization chain) are off by ~42.

11. inlet_outlet_flow.log EXISTS BUT UNLISTED IN MAP
    /media/nate/Friday/Friday/logs/inlet_outlet_flow.log (6.5K) exists but is NOT
    mentioned in Section 12's log file reference. Its relationship to
    friday_short_term_inlet_outlet.log (0 bytes) is unclear.

12. ERRORS_*.log COUNT OFF BY ONE
    Map claims 67 ERROR log files. Actual count: 66.

13. DUPLICATE asyncio.get_running_loop() IN mcp_server.py
    Lines 2265-2269: first call on line 2265 is immediately overwritten by the
    try/except block on lines 2266-2269. First call is dead code.

14. BARE STRING DOCSTRING IN mcp_server.py
    Line 290: """MCP Server for Friday's Memory System""" sits between methods,
    not at class level. It evaluates as a no-op expression, not a real class docstring.

================================================================================
CONFIRMED CORRECT
================================================================================
- core_identity.py compiles cleanly
- All 13 maintenance pipeline steps present
- All retention policies match (8/8)
- All database ownerships match
- All 22+ tool registrations match
- TaskCoordinator classes and behavior match
- Version 0.0.26 matches
- Outlet normalization fix confirmed (lines 5390, 5400)
- Summarization fix confirmed (iterates all users)
- Identity injection works as described
- All key file paths on disk (39/39 primary paths)
- All key database files present (memory_data/ and archives/)
