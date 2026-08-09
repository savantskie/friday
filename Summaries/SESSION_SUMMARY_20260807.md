# SESSION SUMMARY: August 7, 2026
**Full-day session record from 00:04 to 03:26+ (next day)**

25 sessions across 6 phases covering core identity investigation, conversations_processed bug fix, llama.cpp Split Architecture PR #20228 assessment, and mmproj-only vision server implementation.

---

## PHASE 1 — Core Identity System Investigation (00:04 - 00:31)

### Sessions: 3 explore agents, 1 plan session

**What Prompted It:** Nate asked for a complete rundown of how the core identity system works — from nightly generation to file creation to injection.

**Key Findings:**
- Core identity is purely **incremental** — never regenerates from scratch. Each night fetches only unprocessed memories (where `core_identity_processed_until IS NULL`) and merges them into the existing identity via LLM.
- **Version tracking** exists per (user_id, model_id) — monotonically incremented integer, starts at 1. Live DB shows `friday/nate` at version 1 (new row) and version 29 (old row).
- **No change history, no rollback, no diff tracking.** Single row per pair overwritten on each UPDATE. File backup (`friday_core_identity_{user_id}.json`) also overwritten. No history table exists anywhere.
- **Five sections** with per-section prompt instructions: Personality, Relationship, Principles, Facts About Nate, Historical Context. The LLM must output all five in full each time.
- **Tracking file** stores only cursor positions (webui_last_processed_at/id, archive cursors) and `nightly_throughput` metadata (last 90 runs — counts only, no content/diffs).
- **accumulated_identity** is built incrementally across batches: Batch 1 gets no identity + memories, outputs fresh. Each subsequent batch gets previous output + new memories, merges. The LLM is instructed to prefer stability over churn.
- **Critical finding:** All `conversations_processed` values are 0 — the memory-to-conversation linking isn't working.

---

## PHASE 2 — conversations_processed Bug Fix Investigation (14:15 - 14:17)

### Sessions: 1 plan (Core identity crawler and nightly workflow rundown), 5 explore agents

**What Prompted It:** Nate wanted to fix `conversations_processed` being always 0 in core identity generation.

**Root Cause Found:** The `memory_conversation_links` table stores **OpenWebUI memory IDs** (UUIDs from webui.db's `memory` table), but `get_conversations_for_memories()` queries using **FMS curated_memories memory IDs** (different UUIDs from ai_memories.db's `curated_memories` table). Out of 4396 link entries, only **1** matches a curated_memory.

**The Real Fix:** 57,990 out of 57,994 curated_memories have `source_conversation_id` populated, and all 93 unique values exist in the `conversations` table (100% overlap). Instead of querying `memory_conversation_links` (broken), look up `source_conversation_id` directly from `curated_memories`.

**Files Modified (planned):**
- `core_identity.py` — `get_conversations_for_memories()` and `_build_memory_conversation_map()` to use `source_conversation_id` instead of the link table

**Files Explored:**
- `friday_memory_short_term.py` — memory extraction pipeline (lines 10049-10198), linking code at 4377-4418, 10147-10161
- `friday_memory_system.py` — `store_memory()` at line 6949 skips linking for `openwebui_promotion` source
- `database_maintenance.py` — `_retroactively_link_memories()` at line 2837
- `conversations.db` — link table has 4396 entries, conversations table has 356 rows

**Decision:** Hold off on implementation — this is lower priority than the mmproj work.

---

## PHASE 3 — llama.cpp Split Architecture PR #20228 Assessment (18:28 - 21:27)

### Sessions: 1 plan (llama.cpp Split Architecture PR #20228 Patch Feasibility), 1 build (Plan continuation), 2 explore agents

**What Prompted It:** Nate wanted to assess whether PR #20228 (ChenYFan, closed/unmerged) could be applied to current llama.cpp master to add `/vision/embedding` and precomputed embedding injection for split architecture (mmproj on separate server from text model).

**Key Findings:**
- **PR commits ARE still accessible** on GitHub despite fork deletion — GitHub preserves PR commit data under `refs/pull/20228/head` in the upstream repo. Combined diff at `https://github.com/ggml-org/llama.cpp/pull/20228.diff` returned the complete diff.
- **Patch does NOT apply cleanly** — current master has been heavily refactored since March 2026:
  - `server_tokens` struct significantly different (has slots, mtmd_chunk processing, `is_placeholder`)
  - `oaicompat_chat_params_parse()` signature has 4 params (adds `raw_buffer & out_files` for input_video)
  - `update_slots()` refactored into `pre_decode()` + `decode()` + `post_decode()`
  - Image processing loop in `pre_decode()` at lines 3452-3480 (different location/approach)
  - `llama_decode` API changed
  - `process_mtmd_prompt()` has different signature
  - Video support added (`input_video`, `LLAMA_TOKEN_NULL` chunks)
- **4 Copilot issues identified:**
  1. `reinterpret_cast<float *>(precomputed_embedding.data())` alignment issue — need `std::aligned_alloc` with `alignof(llama_batch)` or `float*` alignment
  2. `keep_first()` map-lookup logic — uses `find_chunk(i)` which calls `get_chunk_at(i)->n_tokens` but for precomputed entries without MTMD chunks, this throws
  3. 1GB hard-coded payload limit — DoS risk, needs configurable via `--max-payload-size`
  4. `/vision/embedding` endpoint uncontrolled — needs authentication/rate limiting or documented intent
- **No conflicts with role-aware caching** — Nate's custom `--keep-roles` caching changes and the PR's precomputed embedding changes target different subsystems (your n_keep logic at line ~2862 vs PR's pre_decode() at line ~3452). Precomputed embeddings use `LLAMA_TOKEN_NULL` just like MTMD media tokens.

**Decision:** Plan approved by Nate and Thomas. Implementation started using the PR's approach adapted to current master code structure.

---

## PHASE 4 — mmproj-only Mode Investigation (22:45 - 23:06)

### Sessions: 1 build (llama.cpp mmproj-only mode investigation), 6 explore agents

**What Prompted It:** Nate realized running a second llama-server instance with the mmproj required also loading the full 26B text model, doubling VRAM (~40GB instead of ~4GB for just the mmproj). Wanted to know if the mmproj could run standalone.

**Key Findings:**
- `mtmd_init_from_file()` requires `text_model*` but only reads 3 things at construction time (not stored afterwards): `n_embd_text` (int), `rope_type` (enum), `vocab` (pointer). The pointer itself is not stored.
- **nullptr is already tested/supported** — `mtmd_get_memory_usage()` passes nullptr for text_model.
- The CLIP model in the mmproj is **fully self-contained** with its own weights, backend, and compute graph. The encode step never calls back into the text model.
- 5 specific concerns identified and fixed during investigation:
  1. Image tiling — Gemma4 uses `mtmd_image_preprocessor_dyn_size` (aspect-ratio-preserving resize + normalization, no tiling). Created `mtmd_encode_bitmap()` API that handles full preprocess+encode pipeline internally.
  2. n_embd equivalence — Confirmed `clip_n_mmproj_embd()` and `llama_model_n_embd_inp()` are guaranteed equal by mtmd constructor validation. Added `mtmd_get_n_embd()` public API.
  3. Endpoint crashes — 20+ fields in `server_context_meta` would segfault with null model_tgt. Added null-safe `get_meta()` with accurate fallbacks. Guarded all endpoint handlers.
  4. Router mode override — Server entered router mode when no `-m` was provided, bypassing `load_model()`. Fixed by checking `!params.mmproj_only` in router detection logic.
  5. Chat template null deref — `oaicompat_chat_params_parse` crashed on null `tmpls` pointer. Fixed with null check at function entry.
- **Pre-existing test bug** found: `test-chat.cpp` was calling `oaicompat_chat_params_parse` with 3 args instead of 4.

**Recommended approach:** Modify llama-server to support `--mmproj-only` flag (Option B, not standalone server).

---

## PHASE 5 — mmproj Concerns & Plan Refinement (~23:06 - late)

### Sessions: Continuation of build session with concerns investigation

**4 Concerns Investigated:**

1. **Image tiling** — Not an issue for Gemma4. Uses `mtmd_image_preprocessor_dyn_size` which resizes (preserving aspect ratio, aligned to patch_size * n_merge = 42) and normalizes. No tiling, no grid, no overview. The `mtmd_encode_bitmap()` API handles the full pipeline.

2. **n_embd equivalence** — Confirmed safe. mtmd constructor validates `clip_n_mmproj_embd() == llama_model_n_embd_inp()` at init time. For Gemma4 specifically (no deepstack), `llama_model_n_embd() == llama_model_n_embd_inp() == clip_n_mmproj_embd()`.

3. **Health/model endpoints in mmproj-only mode** — This was the big one. 20+ fields in `server_context_meta` segfault without text model. OpenWebUI calls `/v1/models` on startup and expects valid response. Two options presented:
   - **Option A (Nate rejected)**: Standalone minimal server (~250 lines)
   - **Option B (Nate chose)**: Full server modification with `--mmproj-only` flag
   
   Nate added "no stubs" caveat — every value returned must be real/accurate, not fake. Endpoints that can't work return clear errors.

4. **AMD VRAM verification** — Use `rocm-smi --showmeminfo vram` instead of `nvidia-smi`.

**Plan Updated With:**
- `--main-server-port` flag (configurable, default 8080)
- Startup compatibility check: query main server `/v1/models` for n_embd, compare against mmproj's `clip.vision.projection_dim`
- Refuse to start if main server unreachable or n_embd mismatch
- Clear log messages for all three cases (success, unreachable, mismatch)

---

## PHASE 6 — Implementation: PR #20228 + FMS Vision Pipeline (21:27 - 03:26+)

### Sessions: 1 build (Plan continuation), 1 build (mmproj-only mode investigation + implementation)

### Part A: PR #20228 Implementation on llama.cpp

**Files Modified (production llama.cpp):**

- `common/common.h` — Added `mmproj_only`, `main_server_port`, `max_payload_size` fields to `common_params`
- `common/arg.cpp` — Added `--mmproj-only`, `--main-server-port`, `--max-payload-size` CLI flags
- `tools/server/server-common.h` — Added `server_precomputed_image` struct, extended `server_tokens` with `has_precomputed`, `map_idx_to_precomputed`, and related methods
- `tools/server/server-common.cpp` — Implemented `process_precomputed_chunk` (as free function), `push_back_precomputed`, `has_precomputed_at`, `find_precomputed`, `process_precomputed_image_prompt()`; updated `pos_next()`, `keep_first()`, `validate()`, `clone()`, `get_common_prefix()`, `push_back(server_tokens &)`, `oaicompat_chat_params_parse()`; made `base64_decode` externally linkable
- `tools/server/server-context.h` — Added `post_vision_embedding` handler declaration, updated `handle_completions_impl` signature
- `tools/server/server-context.cpp` — Updated `pre_decode()` image processing loop for precomputed paths, updated `handle_completions_impl`, updated 6 call sites in `init_routes()` for `oaicompat_chat_params_parse`, registered `/vision/embedding` endpoint, added `get_model_info_extended` for architecture awareness
- `tools/server/server-http.cpp` — Added `set_payload_max_length()` using configurable `max_payload_size`
- `tools/server/server.cpp` — Route registration, model info exposure
- `tools/mtmd/mtmd.h` — Added `mtmd_encode_bitmap()`, `mtmd_get_vision_projector_type()`, `mtmd_get_n_embd()` public API functions
- `tools/mtmd/mtmd.cpp` — Implemented `mtmd_encode_bitmap()` (full preprocess+encode pipeline), `mtmd_get_vision_projector_type()`, `mtmd_get_n_embd()`

**Compilation issues encountered and fixed:**
- `common_arg` doesn't support `int64_t`, changed `max_payload_size` to `int`
- `mtmd_helper_bitmap_init_from_buf` now takes 4th `bool placeholder` parameter
- `mtmd_input_text` struct has different layout now (`text_len` field)
- Function returns `mtmd_helper_bitmap_wrapper` struct (not `mtmd::bitmap` directly)
- `process_precomputed_chunk` needed declaration in header for cross-TU visibility

### Part B: FMS Vision Integration Pipeline

**Goal:** Send images to vision server (port 8082), get precomputed embeddings, cache them, and replace `image_url` with `image_embedding_b64` in outgoing body to main LLM (port 8080, no mmproj).

**File Modified:**
- `/media/nate/Friday/Friday/friday_memory_short_term.py`

**5 Edits (all verified with `ast.parse()`):**

1. **`ImageManager._init_db()`** — Added `image_embeddings` table (image_hash TEXT PK, embedding_b64 TEXT, n_tokens INTEGER, n_embd INTEGER, created_at TIMESTAMP)

2. **ImageManager class** — Added `get_embedding(image_hash)` returning cached `{embedding_b64, n_tokens, n_embd}` or None, and `store_embedding(image_hash, embedding_b64, n_tokens, n_embd)` with `INSERT OR REPLACE`

3. **Filter.Valves** — Added `vision_embedding_url` field defaulting to `http://localhost:8081/vision/embedding`

4. **Filter class** — Added `_get_image_embedding(base64_data, image_hash)` async method that checks ImageManager cache first, then POSTs to vision server with `{"image": base64_data, "b64": true}`, caches result, returns embedding dict

5. **inlet()** — Added second pass inside existing `if images and self.image_manager:` block. For each image: strips `data:image/...;base64,` prefix, calls `_get_image_embedding()`, on success replaces matching `{"type": "image_url", ...}` content part with `{"type": "image_embedding_b64", "image_embedding_b64": {n_tokens, n_embd, embedding_b64}}`. On failure, image_url left in place as fallback.

**Design Decision:** Both the existing memory-model image analysis loop AND the new precomputed embedding pass run independently — the text description goes to memory, and the embedding goes to the main LLM.

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total sessions | 25 |
| Build sessions | 4 |
| Plan sessions | 2 |
| Explore agents | 19 |
| Total tokens in | ~119M |
| Total tokens out | ~183K |
| Estimated cost | ~$13.50 |
| Files modified (llama.cpp) | ~12 |
| Files modified (FMS) | 1 |
| Compilation attempts | 3 (2 failed, 1 succeeded after fixes) |
| Pre-existing bugs found | 1 (test-chat.cpp) |

## Key Architectural Decisions Made

1. **Option B over Option A** — Full llama-server modification for `--mmproj-only`, not a standalone server
2. **No stubs** — Every returned value must be accurate; endpoints that can't work return clear errors
3. **source_conversation_id over memory_conversation_links** — For core identity conversation context
4. **Cache-first embedding** — ImageManager caches embeddings by hash to avoid redundant vision server calls
5. **Fallback-preserving** — If embedding generation fails, the original image_url stays in place rather than breaking the request
6. **Prefixed role messages** — Custom role messages (datetime, identity, summary, reminders, memories) continue as `<|role|>` format for Gemma4's Jinja template