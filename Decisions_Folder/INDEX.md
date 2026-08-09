# DECISIONS FOLDER INDEX
**Architecture decisions, plans, and design documents**
**Last Updated**: May 13, 2026

---

## Active Decisions (Main Folder)

### URGENT_POST_DEPLOY_AUDIT_20260513.md  [IN PROGRESS — PAUSED]
**Post-deploy audit findings — May 13, 2026**

Three tasks discovered that need investigation before the core identity fix is fully operational: memory_promotion (disabled since Apr 20, no long-term promotion for 3+ weeks), summarization (fires every 2h but bails with "User 'default' not found"), and model_discovery (same valve-timing vulnerability as core_identity, covered by fix but needs verification).

Files within a 2-week window of the most recent entry (April 16 - April 30, 2026):

### OPENWEBUI_0.9.0_PLUGIN_COMPATIBILITY_PLAN.md
**Open WebUI 0.9.0 plugin compatibility assessment** -- April 30, 2026

Plan for adapting the Friday Memory System short-term memory filter to work with Open WebUI 0.9.0's updated plugin interface. Documents breaking changes, compatibility requirements, and migration strategy.

### OWUI_0.9.0_SHORT_TERM_MEMORY_FIX_PLAN.md
**Open WebUI 0.9.0 short-term memory fix plan** -- April 30, 2026

Detailed fix plan for short-term memory issues in the 0.9.0 upgrade. Covers specific code changes needed, testing strategy, and rollback procedures.

### MEMORY_SCORING_IMPLEMENTATION_PLAN.md
**Memory scoring implementation plan** -- April 30, 2026

Plan for implementing a memory scoring system to evaluate and rank memory relevance, importance, and quality.

### Active_Files
**Current active file inventory** -- April 20, 2026

Lists all active files in Friday Memory System (friday_memory_short_term.py, friday_memory_mcp_server.py, etc.) and persistent-ai-memory (ai_memory_core.py, ai_memory_mcp_server.py, etc.).

---

## Archived Decisions (ARCHIVE Folder)

61 documents in `/media/nate/Friday/Friday/Decisions_Folder/ARCHIVE/`

All decisions older than April 16, 2026 have been moved to the archive to keep the main folder focused on current work. The archive contains:

- **System Architecture**: COMPLETE_SYSTEM_ARCHITECTURE, COMPREHENSIVE_FRIDAY_SYSTEM_REFERENCE (Parts 1-3 + Master), FRIDAY_MEMORY_SYSTEM_ARCHITECTURE, FRIDAY_MEMORY_SYSTEM_INTERNALS
- **Implementation Plans**: API_LAYER_IMPLEMENTATION, MEMORY_CLEANUP_FEATURE, MCP_PORT_MANAGEMENT, PHASE_5_MCP_IMPLEMENTATION_PLAN, PERSISTENT_AI_MEMORY_PARITY_PLAN, MEMORY_PROMOTION_API, MEMORY_PROMOTION_CORRECTED_REQUIREMENTS, MEMORY_PROMOTION_SIMPLIFIED_REQUIREMENTS
- **Bug Analysis & Fixes**: ORDER_OF_OPERATIONS_BUG_ANALYSIS, INLET_MEMORY_RETRIEVAL_ANALYSIS, VALVE_CONFIGURATION_NOT_RESPECTED_FIX, DEDUPLICATION_FIX, PROMOTION_VERIFICATION_FIX, MCP_TOOL_FIXES_DEFAULT_REMOVAL, VALVE_PERSISTENCE_SOLUTION, VALVE_PERSISTENCE_WORKING, DYNAMIC_TIMEOUT_IMPLEMENTATION, ARCHIVE_REPAIR_COMPLETE, DATABASE_MAINTENANCE_DEPLOYMENT
- **Audits**: AUDIT_FRIDAY_VS_PAM, DATABASE_MAINTENANCE_AUDIT, DATABASE_STRUCTURE_ANALYSIS, PROMOTION_VERIFICATION_AUDIT, TOOL_AUDIT_COMPLETION
- **Design Documents**: MEMORY_BANK_ARCHITECTURE, EMBEDDING_TAG_OPTIMIZATION, MCP_SOURCE_AUTO_INJECTION, tag_tool_plan, search_memories_source_attribution_design, EMBEDDING_RE_EMBEDDING_INVESTIGATION_PLAN, DIAGNOSTIC_MEMORY_LLM_CONFIG, MEMORY_IDENTIFICATION_PROMPT_REVIEW
- **Debug & Research**: DEBUG_MCP_TOOL_ERRORS, ACTIVE_DEBUG_INVESTIGATION, SYSTEM_PROMPT_AVAILABILITY_RESEARCH, VLLM_FORK_ANALYSIS, INLET_TIMING_ISSUE_ANALYSIS, ACTIVE_ACTIONS_20251222, TOOL_CALLS_EXPORT
- **Historical & Superseded**: ARCHIVED_INSTALLATION_COMPLETE, ARCHIVED_PROJECT_STRUCTURE

---

## How This Was Organized

On May 7, 2026:
- Reviewed all 64 files (4 root + 60 archived) plus 14 loose in `/media/nate/Friday/Friday/`
- Retained only decisions from the last 2 weeks (April 16 - April 30) in root
- Moved `search_memories_source_attribution_design.md` (April 13) to ARCHIVE
- Moved `MEMORY_SCORING_IMPLEMENTATION_PLAN.md` (April 30) to root
- Moved 14 remaining loose decision files from `/media/nate/Friday/Friday/` to ARCHIVE
- Created/updated INDEX.md for navigation

All older decisions remain in ARCHIVE/ for historical reference.
