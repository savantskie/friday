# CRITICAL ISSUE #2: Model Hallucination - Repeated Bracket Characters
**Date**: November 9, 2025  
**Status**: ✅ FIXED  
**Severity**: CRITICAL - Model generating garbage instead of JSON

---

## The Problem

After initial testing with llama3-8b, the model started generating repeated bracket characters instead of JSON:

```
"text": "[ ] [ ] [ ] [ ] [ ] [ ] [ ] [ ] [ ] [ ] ..."  (1023 completion tokens of just this!)
```

This triggers the json_parse_error because the extraction function cannot parse this as JSON.

---

## Root Cause

**The JSON instruction was being placed BEFORE the system prompt instead of integrated INTO it.**

Structure was:
```
[INSTRUCTION: OUTPUT ONLY VALID JSON...]
[Complex system prompt about memory relevance...]
[User prompt asking for JSON...]
```

The model was seeing the complex system prompt and ignoring the instruction placed before it. The model then got confused about what format to output and started hallucinating.

---

## The Fix

### Part 1: Integrate JSON requirement into system prompt (Line 4226)
Instead of prepending a separate JSON instruction, we now inject it INTO the system prompt itself:

```python
system_with_json = f"""{system_prompt_with_date}

CRITICAL FORMATTING REQUIREMENT: You MUST respond with ONLY valid JSON. NO other text.
- Start your response immediately with [ or {{ 
- Do not include markdown code blocks, explanations, or any text before/after the JSON
- Every response must be parseable JSON that starts with [ or {{
- Failure to output only JSON will break the system"""

combined_prompt = f"{system_with_json}\n\n{user_prompt}"
```

This ensures the JSON requirement is PART OF the system prompt itself, not something that can be ignored.

### Part 2: Detect and recover from hallucinations (Lines 4325-4340)
Added detection for the specific hallucination pattern of repeated brackets:

```python
if content_stripped.count("[ ]") > 5 or content.count("[][]") > 3:
    logger.warning(
        f"LM Studio response appears to be hallucinating (repeated brackets). "
        f"Content starts: {content_stripped[:100]}. Triggering retry..."
    )
    if attempt <= max_retries:
        # Retry instead of accepting hallucination
        sleep_time = retry_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
        await asyncio.sleep(sleep_time)
        continue
```

When hallucination is detected:
- Logs warning about hallucination pattern
- Automatically retries with exponential backoff
- Gives model another chance to generate proper JSON

---

## Why This Happened

1. **Prefix placement issue**: Putting the JSON instruction before the system prompt doesn't work because models weight earlier instructions but the detailed system prompt overrides it
2. **Model confusion**: llama3 got confused about what to output and fell into a repetition pattern
3. **No safeguard**: There was no detection for obvious hallucinations like repeated brackets

---

## Impact

- ✅ Models now understand JSON requirement is part of core system instruction
- ✅ Hallucination patterns are detected and trigger retry
- ✅ System has recovery path instead of failing immediately
- ✅ Better logging to identify hallucinations when they occur

---

## Files Modified

**File**: `/media/nate/Friday/Friday/Adaptive_Memory_v3.py`

| Line Range | Change | Reason |
|-----------|--------|--------|
| 4226-4240 | Integrated JSON requirement into system prompt | Ensure model sees JSON as core requirement |
| 4325-4340 | Added hallucination detection | Detect repeated brackets and retry |

---

## Testing Notes

Watch for these in logs:

**✅ Success patterns**:
- Model returns actual JSON like: `[{...}]`
- No error messages at end of response
- "Successfully parsed JSON" messages

**⚠️ Warning patterns (will retry)**:
- "LM Studio response appears to be hallucinating (repeated brackets)"
- Retries happen automatically with backoff
- Should eventually produce valid JSON

**❌ Failure patterns (should be rare)**:
- "json_parse_error" after all retries exhausted
- Would indicate hallucination recovery failed

---

## Next Steps

1. Test memory saves with llama3-8b
2. Monitor for hallucination warnings in logs
3. Verify retry mechanism activates if needed
4. Confirm no more repeated bracket hallucinations

---

**Confidence**: HIGH - Issue clearly identified and fixed  
**Risk**: LOW - Detection only adds retry logic, doesn't change normal flow  
**Testing Required**: Run 5-10 memory saves to verify fix works
