# OpenWebUI 0.9.0 Plugin Compatibility Plan

**Status:** Investigation Complete - Ready for Implementation
**Date:** 2026-04-30
**Target:** Make friday_memory_short_term.py work with OpenWebUI 0.9.0 fork

## Executive Summary

Friday's short-term memory plugin IS mostly compatible with OpenWebUI 0.9.0, but there are specific issues preventing proper outlet filter execution. The main problem: outlet() method references an undefined `model_id` variable at line 6003, causing a NameError.

## Key Findings

### 1. OpenWebUI 0.8.12 → 0.9.0 Changes (Confirmed)

**Plugin System (filter.py):**
- ✅ Function signatures still support async inlet/outlet handlers
- ✅ `process_pipeline_inlet_filter()` behavior unchanged
- ✅ `process_pipeline_outlet_filter()` NOW ACTIVELY USED (was dead code in 0.8.12)
- ✅ All database calls in filter processing became async (forced migration)

**Key Breaking Changes:**
- `get_sorted_filter_ids()` now async (was sync)
- `get_function_module()` now async (was sync)  
- `Functions.get_functions_by_type()` now async (was sync)
- `Functions.get_function_valves_by_id()` now async (was sync)
- `Functions.get_user_valves_by_id_and_user_id()` now async (was sync)
- outlet filter NOW RUNS after LLM response (was skipped entirely)

**Parameters:**
- Inlet: `(request, form_data, user, models)` - unchanged
- Outlet: `(request, outlet_data, user, models)` - NEW in active use
  - outlet_data contains: model, messages, filter_ids, chat_id, session_id, id
  - Different from form_data (contains processed response, not request)

### 2. Friday's Plugin Status (Current)

**Working:**
- ✅ inlet() method is async with correct signature
- ✅ outlet() method is async with correct signature
- ✅ Both are being called correctly by 0.9.0
- ✅ Memory extraction and injection logic working
- ✅ Embeddings current (updated 2026-04-30 08:34:53)

**Broken:**
- ❌ outlet() references undefined `model_id` variable at line 6003
- ❌ This crashes the outlet filter when attempting to inject active reminders
- ❌ Partial outlet processing happens, then crashes

## Critical Bug Analysis

**Location:** `friday_memory_short_term.py:6003` (in outlet method)
```python
if self.valves.show_active_reminders and user_id and model_id:  # model_id NOT DEFINED
    active_reminders = await self.memory_system.get_active_reminders_for_injection(
        user_id=user_id,
        model_id=model_id
    )
```

**Root Cause:** outlet() method never extracts `model_id` from incoming body/metadata

**Available Values in outlet():**
- `body.get('model')` - returns model identifier (e.g., "friday")
- `__metadata__.get('model')` - may contain model object
- `self._current_model` - set from model card name (line 5850)

**Error Evidence (logs from 2026-04-28 10:10:01,755):**
```
Error injecting active reminders: name 'model_id' is not defined
NameError: name 'model_id' is not defined
```

## Implementation Plan

### Phase 1: Fix Critical Errors (Blocking outlet execution)

**Task 1.1: Extract model_id in outlet**
- File: `friday_memory_short_term.py` outlet() method, after line 5862
- Action: Add model_id extraction after user_id extraction
- Code:
```python
# Get model ID for memory system operations
model_id = body.get('model', 'default')
if not model_id:
    model_id = __metadata__.get('model', 'default') if __metadata__ else 'default'

self._current_model_id = model_id  # Store for access by other methods
logger.debug(f"Outlet: Extracted model_id={model_id}")
```
- Rationale: model_id needed for reminder injection and memory system operations; body.get('model') matches inlet pattern

**Task 1.2: Verify all database calls in outlet are async**
- Scan outlet() for synchronous database operations
- Convert any `Memories.get_*()` calls to `await Memories.get_*()`
- Convert any `Users.get_*()` calls to `await Users.get_*()`
- Check `memory_system.*` methods for async compliance

**Task 1.3: Review async function signatures**
- Confirm all helper methods called from outlet are async
- `get_relevant_memories()` - ✅ already async
- `_inject_memories_into_context()` - verify async
- `_format_active_reminders_for_context()` - verify async
- `_add_confirmation_message()` - verify async

### Phase 2: Verify 0.9.0 Compatibility (Full integration)

**Task 2.1: Parameter compatibility audit**
- Confirm outlet() correctly receives (body, __event_emitter__, __user__, __metadata__)
- Verify `__user__` and `__metadata__` not None before use
- Log parameter types/content for debugging

**Task 2.2: Test inlet filter with new async middleware**
- Confirm inlet() still receives correct parameters
- Verify form_data structure matches expectations
- Test message injection flow

**Task 2.3: Test outlet filter integration**
- Outlet should now execute (was dead code in 0.8.12)
- Test memory extraction after LLM response
- Test reminder injection into context
- Verify filter_ids are available in outlet_data

### Phase 3: Testing & Validation

**Task 3.1: Unit testing**
- Test inlet() with sample data
- Test outlet() with sample response data
- Test model_id extraction under various inputs

**Task 3.2: Integration testing**
- Run with live OpenWebUI 0.9.0 fork
- Verify inlet/outlet filters execute without errors
- Check logs for any remaining NameErrors or undefined variables
- Verify memory injection works on first message (inlet)
- Verify memory extraction works after LLM response (outlet)

**Task 3.3: Performance validation**
- Monitor that outlet doesn't cause response delays
- Check async task queue doesn't back up
- Verify reminder injection doesn't timeout

## Implementation Order

1. Add model_id extraction to outlet() ← START HERE
2. Audit async/await compliance in outlet and helpers
3. Run Friday's log validation
4. Test with live 0.9.0 fork
5. Monitor for 48 hours for stability
6. Document any additional issues found

## Files to Modify

- `/media/nate/Friday/Friday/friday_memory_short_term.py` (outlet method)

## Files Already Correct

- `/media/nate/Friday/Friday/friday_memory_short_term.py` (inlet method - no changes needed)
- No plugin configuration changes needed
- No OpenWebUI changes needed

## Rollback Plan

If issues arise:
1. Revert friday_memory_short_term.py to previous version
2. OpenWebUI 0.8.12 backup available at `/media/nate/Friday/OpenWebUIstock-0.8.2-backup/`
3. Current 0.9.0 stock at `/media/nate/Friday/OpenWebUIstock/`

## Notes

- outlet() filter was completely inactive in 0.8.12 (dead code path) - this is first time it's been tested
- The outlet filter integration is actually a FEATURE ADDITION in 0.9.0, not a breaking change
- All async conversions in filter.py already happened upstream; we just need to ensure outlet() provides correct variables
- The error only manifests when show_active_reminders valve is enabled

## Success Criteria

- [ ] outlet() executes without NameError
- [ ] Memory extraction happens after LLM response
- [ ] Memory injection happens before LLM response (inlet still works)
- [ ] Active reminders injected when enabled
- [ ] No errors in logs for 24+ hours
- [ ] User can toggle memory settings via valves
