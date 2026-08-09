# URGENT TODO — Post-Deploy Audit Findings
## Created: 2026-05-13

### Three tasks need investigation before the core identity fix is fully operational:

---

### 1. memory_promotion — DISABLED since April 20

**Severity**: HIGH
**Symptom**: `CRITICAL: Memory promotion task disabled after 5 consecutive failures` — last seen Apr 20.
**Impact**: No short-term memories being promoted to long-term storage for 3+ weeks. Long-term memory (`ai_memories.db` > `curated_memories`) may be significantly less populated than expected.
**Where**: `_promote_old_memories_loop` in `friday_memory_short_term.py` — task was registered (default=True) but errored until disabled.
**Next step**: Check the actual error — likely LLM call failure or database constraint violation. Check `_promote_old_memories_loop` for the error path.

---

### 2. summarization — Running but always skipping

**Severity**: MODERATE
**Symptom**: Every 2 hours: `"Summarization skipped: User 'default' not found."`
**Impact**: Memory summarization has never actually done any work, despite the task firing 419 times.
**Where**: `_summarization_work` in `friday_memory_short_term.py` — the user_id context isn't being passed correctly.
**Next step**: Investigate how user_id is resolved in `_summarization_work` vs how it's resolved in `_core_identity_work`.

---

### 3. model_discovery — Valve-timing vulnerable (same as core_identity)

**Severity**: LOW (covered by our fix)
**Symptom**: `default=False` means it wouldn't register during init. Was apparently running earlier (persisted file existed). Our re-registration fix covers it going forward.
**Note**: Already addressed by `_register_valve_gated_tasks()` + re-registration on first inlet. No action needed unless it fails to start after deploy.