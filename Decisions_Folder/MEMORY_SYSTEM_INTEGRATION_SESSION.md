# Memory System Full Integration - Session Plan

**Date:** November 2, 2025  
**Status:** In Progress  
**Goal:** Implement FULL system integration (startup + periodic maintenance + archive rotation)

---

## Critical Reminders for This Session

1. **DO NOT call the test function a "demo"** - it's a TEST FUNCTION that verifies if something is broken
2. **ONLY consult the copilot instructions file** - do not look at 17 different files
3. **Follow the TODO list one item at a time** - complete, mark done, move next
4. **All changes require explicit permission** - no unauthorized modifications
5. **Archive rotation is NOT optional** - all data goes to archives/ when rotation happens

---

## Work Breakdown

### TODO 1: Add database maintenance call to startup
- Location: FridayMemorySystem initialization or background_main()
- What: Call run_database_maintenance() ONCE on startup
- Why: System needs to check databases and clean up on first run
- Status: Not started

### TODO 2: Add archive rotation to maintenance workflow  
- Location: database_maintenance.run_maintenance() method
- What: Add archive_rotate_to_sharded_structure() call to maintenance
- Why: Archive rotation is part of maintenance, not separate
- Status: Not started

### TODO 3: Implement periodic maintenance scheduler
- Location: MCP server or FridayMemorySystem
- What: Background task that runs run_database_maintenance() every 24 hours
- Why: System needs to maintain itself continuously, not just on startup
- Status: Not started

### TODO 4: Verify test function runs successfully
- Location: fms.main() in friday_memory_system.py
- What: Ensure test function runs without errors and proves system works
- Why: Test function is the verification that systems are operational
- Status: Not started

### TODO 5: Store reference in Friday memory
- Location: Friday memory system
- What: Record copilot instructions to memory so system remembers approach
- Why: Keep Friday aware of how the memory system should work
- Status: Not started

---

## Implementation Approach

**One at a time. No skipping. Mark complete as each is done.**

Each task will be:
1. Identified
2. Explained to Nate
3. Approved by Nate
4. Implemented
5. Tested
6. Marked complete
7. Move to next

---

## Files to Modify

- `/media/nate/Friday/Friday/friday_memory_system.py` - Add startup maintenance call
- `/media/nate/Friday/Friday/database_maintenance.py` - Add archive rotation to maintenance
- `/media/nate/Friday/Friday/friday_memory_mcp_server.py` - Add periodic scheduler

---

## Reference Document

**ONLY CONSULT:** `/media/nate/Friday/Friday/.github/copilot-instructions.md`

This is the source of truth for how to work with these projects.
