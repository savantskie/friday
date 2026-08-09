# Core Identity Investigation
- Status: Investigation Complete, Implementation Complete (Phase 1 + 2)
- Objectives:
  1. Verify normalization system for `user_id` and `model_id`.
  2. Check for `user_id`/`model_id` mismatches (e.g., UUID vs nate/friday).
  3. Identify why core identity is failing to find existing memories.

## Progress
- [x] Initialize investigation files and index.
- [x] Search for normalization implementation.
- [x] Inspect `core_identity.py` and related files.
- [x] Check logs for identity retrieval issues.
- [x] Verify database content for `user_id`/`model_id` mismatches.
- [x] Check injection path for normalization gaps.
- [x] Full distribution analysis across ALL sources
- [x] Verify model_id casing conventions in OpenWebUI
- [x] Verify ASCII safety of LOWER()
- [x] Full audit of every user_id/model_id reference across FMS
- [x] Phase 1 implemented and verified
- [x] Phase 2 implemented and verified
- [x] Final grep across all production files confirms zero remaining `model_id = ?`

## Distribution Analysis — Complete Dataset

### curated_memories (ai_memories.db — current)
| user_id | model_id | Count |
|---|---|---|
| 9d08cfbb-b8ca-484d-bd37-c5c383c1e5d6 | Friday | 6531 |
| nate | friday | 2 |
| test_user_source | test_model_source | 3 |

### Archives — ai_memories_*.db
1,559,878 of 1,560,751 archive entries (99.94%) have NULL/empty user_id+model_id. Handled by existing NULL-filter.

### webui.db (OpenWebUI memory table)
10173 entries for nate's UUID. No model_id column.

### conversations.db
UUID user: 110 `Friday`, 40 `friday`, ~28 other models at 1-3 each.

## Root Cause

**model_id**: Both code paths produce lowercase `"friday"` (from `_normalize_name` and from `body.get('model')`), but the database stores capital-F `"Friday"` for 6,531/6,533 entries. Exact-match SQL finds nothing.

**user_id**: The generation path passes `"nate"` (name string), but 6,531/6,533 entries are stored under the OpenWebUI UUID. The existing `_resolve_owu_user_id` only applied to OpenWebUI sources, not curated_memories or archives.

## Phase 1 Plan

### Files Modified

**1. `/media/nate/Friday/Friday/core_identity.py`**

New method `_resolve_canonical_model_id(self, model_id: str) -> str`:
- Simply returns `model_id.strip().lower()`
- The OpenWebUI model card ID convention (lowercase) is the canonical form

Changes in `run_generation()`:
- After `_check_and_handle_rescan` at line 1114:
  - `resolved_user_id = self._resolve_owu_user_id(user_id)`
  - `resolved_model_id = self._resolve_canonical_model_id(model_id)`
- Remove the separate `owu_user_id = self._resolve_owu_user_id(user_id)` at line 1117
- Pass `resolved_user_id` and `resolved_model_id` to ALL calls:
  - `get_new_memories_since_processing`
  - `_get_archived_memories`
  - `_get_openwebui_conversations`
  - `save_to_database`
  - `load_core_identity` (the comparison at line 1304)

Changes in `get_core_identity_for_injection()`:
- At entry: resolve user_id and model_id before calling `load_core_identity`
- `resolved_user_id = self._resolve_owu_user_id(user_id)`
- `resolved_model_id = self._resolve_canonical_model_id(model_id)`

Changes in 8 SQL queries — all `model_id = ?` → `LOWER(model_id) = ?`:
| Line | Table | Query |
|---|---|---|
| 170 | curated_memories | `WHERE user_id = ? AND` **`LOWER(model_id) = ?`** |
| 179 | curated_memories | `WHERE user_id = ? AND` **`LOWER(model_id) = ?`** |
| 191 | curated_memories | `WHERE user_id = ? AND` **`LOWER(model_id) = ?`** |
| 478 | curated_memories (archive) | `(user_id = ? AND` **`LOWER(model_id) = ?`** `) OR ...` (4 variants) |
| 495 | curated_memories (archive) | `(user_id = ? AND` **`LOWER(model_id) = ?`** `) OR ...` |
| 872 | core_identity | `WHERE user_id = ? AND` **`LOWER(model_id) = ?`** |
| 888 | core_identity | `WHERE user_id = ? AND` **`LOWER(model_id) = ?`** |
| 996 | core_identity | `WHERE user_id = ? AND` **`LOWER(model_id) = ?`** |

**2. `/media/nate/Friday/Friday/friday_memory_system.py`**

| Line | Current | New |
|---|---|---|
| 896 | `DEFAULT 'Friday'` | `DEFAULT 'friday'` |
| 932 | `DEFAULT 'Friday'` | `DEFAULT 'friday'` |
| 970 | `DEFAULT 'Friday'` | `DEFAULT 'friday'` |
| 1069 | `if model_id and model_id != "Friday" and not existing_model:` | `if model_id and model_id.lower() != "friday" and not existing_model:` |

### Files NOT Modified

- `friday_memory_mcp_server.py` — schema-only, casing irrelevant
- `database_maintenance.py` — reads user_id/model_id as data, not filter criteria
- `friday_memory_maintenance.py` — reads user_id/model_id as data, not filter criteria
- All other files — zero references

### Phase 2 (completed)

Applied `LOWER(model_id) = ?` to all remaining `model_id = ?` comparisons across:
- `friday_memory_system.py`: 27 queries across conversations, curated_memories, reminders, reminder_notifications, appointments, vscode_sessions, and dynamic WHERE builders. Lines 407, 507, 510, 1142, 1155, 1174, 1182, 1221, 2460, 5519, 5530, 5623, 5673, 5755, 5772, 5790, 5823, 5893, 5910, 5929, 5947, 5981, 7521, 7529, 8065, 8224, 8889.
- `friday_memory_short_term.py`: line 4328 (conversations lookup).

### Final Verification

Zero `model_id = ?` without `LOWER()` in any production `.py` file across the entire `/media/nate/Friday/Friday/` directory. Confirmed by final grep.
