# Dynamic LLM Timeout Implementation (December 27, 2025)

## Problem Solved
Memory creation was silently failing with long text due to a hardcoded 60-second timeout that was too short for complex memory extraction tasks. When the LLM call exceeded 60 seconds, the system would timeout and return empty memories without any visible error.

## Solution Implemented
Replaced the hardcoded `timeout=60` with a **dynamic timeout calculation** that scales based on input size, with a 5-minute maximum.

## Technical Details

### New Method: `_calculate_dynamic_timeout()`
**Location:** [friday_memory_short_term.py](friday_memory_short_term.py#L8210)

**Formula:**
```
timeout_seconds = min(30 + (total_input_length // 500), 300)
```

**Breakdown:**
- **Base timeout:** 30 seconds (minimum for any request)
- **Scaling:** +1 second per 500 characters of input
- **Maximum cap:** 300 seconds (5 minutes)

**Examples:**
- Short message (100 chars): 30 seconds
- Medium message (1000 chars): 32 seconds
- Long message (5000 chars): 40 seconds
- Very long message (10,000 chars): 50 seconds
- Extremely long (50,000 chars): 300 seconds (capped)

### Key Features
1. **Smart scaling:** Longer, more complex prompts get more time
2. **Immediate return:** Doesn't wait the full timeout - returns when LLM finishes
3. **Configurable cap:** The 300-second (5-minute) maximum prevents runaway timeouts
4. **Per-request calculation:** Timeout is recalculated for each LLM call based on actual input size
5. **Retry-aware:** If retries occur, timeout remains dynamic and consistent

### Implementation Changes

#### Change 1: Added Helper Method
**File:** `friday_memory_short_term.py` lines 8210-8241

```python
def _calculate_dynamic_timeout(self, system_prompt: str, user_prompt: str) -> int:
    """Calculate dynamic LLM timeout based on input size..."""
    total_input_length = len(system_prompt) + len(user_prompt)
    timeout_seconds = min(30 + (total_input_length // 500), 300)
    logger.debug(f"Dynamic timeout calculated: {timeout_seconds}s for {total_input_length} input characters...")
    return timeout_seconds
```

#### Change 2: Updated `query_llm_with_retry()` Method
**File:** `friday_memory_short_term.py` line 8295

Before:
```python
for attempt in range(1, max_retries + 2):
    # ... later in the function ...
    async with session.post(api_url, json=data, headers=headers, timeout=60) as response:
```

After:
```python
# Calculate dynamic timeout based on input size (will be reused if we retry)
timeout_seconds = self._calculate_dynamic_timeout(system_prompt_with_date, user_prompt)

for attempt in range(1, max_retries + 2):
    # ... later in the function ...
    logger.info(f"Making API request to {api_url} (attempt {attempt}/{max_retries+1}, timeout={timeout_seconds}s)")
    async with session.post(api_url, json=data, headers=headers, timeout=timeout_seconds) as response:
```

## Behavior

### Timeout Calculation Occurs Once
- The timeout is calculated **before** the retry loop
- The same timeout value is reused across all retry attempts (no recalculation needed)
- This ensures consistent behavior and predictable backoff behavior

### Logging
- Debug log shows the calculated timeout when the method is called
- API call log includes the actual timeout used in each attempt
- Example: `"Making API request to http://... (attempt 1/2, timeout=45s)"`

### Request Flow
1. Message arrives in `outlet()` → calls `_process_user_memories()`
2. `_process_user_memories()` → calls `identify_memories()`
3. `identify_memories()` → calls `query_llm_with_retry()`
4. **NEW:** `query_llm_with_retry()` calculates timeout based on system_prompt + user_prompt size
5. LLM call made with dynamic timeout
6. Response arrives (or timeout expires after N seconds)
7. Memory creation continues based on response

## Testing Recommendations

Test with messages of increasing length:
1. **Short message (100 chars):** Should complete in ~30-40 seconds
2. **Medium message (1000 chars):** Should complete in ~32-50 seconds
3. **Long message (5000 chars):** Should complete in ~40-60 seconds
4. **Very long message (50,000 chars):** Should complete before hitting 300-second cap

Monitor logs for:
- "Dynamic timeout calculated: Xs for Y input characters"
- "Making API request to ... (attempt X/Y, timeout=Zs)"
- "Retrieved content from ... response (length: X)"

## Fallback Behavior

If timeout is still exceeded even with the dynamic calculation:
1. System logs "Attempt X failed: LLM API request timed out"
2. Retries up to `max_retries` times (default 2 additional attempts)
3. After all retries exhausted, returns: `"Error: LLM API request timed out after multiple retries."`
4. Memory creation fails gracefully with appropriate error message
5. User sees status message indicating the error (not silent failure anymore)

## Future Improvements

If needed, these could be added:
1. **Configurable scaling formula** - Add a valve to control the multiplier (currently hardcoded at 500 chars per second)
2. **Model-based adjustment** - Different timeouts for different models (fast vs. slow)
3. **Adaptive timeout** - Track actual response times and adjust the formula dynamically
4. **Per-user settings** - Allow users to override the maximum timeout if their LLM is very slow

## Related Files

- **Primary:** [friday_memory_short_term.py](friday_memory_short_term.py) (lines 8210-8241, 8295)
- **Called from:** `identify_memories()` → `query_llm_with_retry()`
- **Used by:** All memory extraction via LLM (both user and assistant messages)
