LOGS DIRECTORY SPLIT EXPLANATION
=================================
Last updated: June 28, 2026

Two log directories exist and serve different purposes:

logs/ (lowercase) -- RUNTIME ACTIVE LOGS
  /media/nate/Friday/Friday/logs/
  - 82 files
  - Where ALL runtime logging goes
  - Contains: friday_short_term_memory.log, friday_short_term_errors.log,
    friday_short_term_inlet_outlet.log, tool_calls.log, brave_search.log,
    embedding logs, ERROR_*.log timestamped dumps
  - Short-term system code writes here via the "openwebui.plugins.adaptive_memory" logger
  - Core identity logs also write here (short_term_memory.log)
  - valve_settings.json should be saved here (consistent with runtime logs)

Logs/ (uppercase) -- ARCHIVAL ONE-TIME RECORDS
  /media/nate/Friday/Friday/Logs/
  - 7 files
  - Contains: migration logs, error analysis, manual log grabs, test outputs
  - NOT actively written to by running code
  - Historical records kept for reference

DO NOT CONSOLIDATE THESE. The split is intentional:
  - logs/ = noisy, daily, rotating, active
  - Logs/ = curated, permanent, reference

SEARCH ORDER FOR DEBUGGING:
  1. Check logs/ first for runtime errors (friday_short_term_errors.log is primary)
  2. Check journalctl for service-level issues
  3. Check Logs/ for historical reference or migration issues

KNOWN ISSUE:
  Some code paths may inconsistently write to one or the other.
  All new code should target logs/ (lowercase) for runtime output.