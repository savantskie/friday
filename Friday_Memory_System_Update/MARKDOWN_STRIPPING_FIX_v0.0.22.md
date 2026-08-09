# Friday Memory System v0.0.22: Markdown JSON Stripping Fix

## Problem Identified
The short-term memory system was experiencing persistent JSON parsing errors across multiple models:
- **65 attempts on "friday" model**
- **21 attempts on "tara" model**  
- **Multiple failures on amelia, willow, roxy, tuesday, jessie models**

**Root Cause:** LLM responses wrapped in markdown code blocks (`\`\`\`json ... \`\`\``) or incomplete markdown fences were not being stripped completely before JSON parsing. This caused `json.loads()` to fail with `Expecting value: line 1 column 1 (char 0)`.

## Solution: Defense-in-Depth Markdown Stripping

Implemented complementary markdown stripping at two levels:

### 1. New Robust Function: `_strip_markdown_json_response()`

A comprehensive markdown stripping function that handles all edge cases:

**Capabilities:**
- Complete markdown fences: `\`\`\`json ... \`\`\``
- Incomplete/asymmetric fences: opening fence with no closing, or vice versa
- Text before/after JSON: intelligently finds `{` or `[` to `}` or `]` boundaries
- Balanced bracket/brace validation: ensures extracted JSON isn't random text
- Detailed logging for debugging: tracks what was stripped and why

**Three-Stage Process:**
1. **Stage 1:** Strip common markdown fence patterns (all variations)
2. **Stage 2:** Handle incomplete/broken markdown (opening fence without closing)
3. **Stage 3:** Intelligent JSON boundary extraction (find first `{`/`[` to last `}`/`]`)

### 2. Integration Points: Two Defense Layers

**Layer 1 - Memory Extraction (line ~7855):**
```python
# Apply robust markdown stripping BEFORE validation
llm_response = self._strip_markdown_json_response(llm_response)
```
Applied immediately after LLM response received, before any validation or parsing.

**Layer 2 - JSON Parser (line ~8353):**
```python
# Apply robust markdown stripping - handles all markdown variations as defense-in-depth
text = self._strip_markdown_json_response(text)
```
Applied during `_extract_and_parse_json()` as a secondary safeguard.

## Testing

All 8 edge cases pass:
- ✓ Complete ```json fences
- ✓ Incomplete opening ```json (no closing)
- ✓ Incomplete opening ``` (no closing)
- ✓ Text before and after JSON
- ✓ Complete ``` fences
- ✓ Array in ```json fences
- ✓ Already clean JSON
- ✓ Complex nested JSON with mixed brackets

## Version Update
- **Previous:** v0.0.21
- **Current:** v0.0.22
- **Change Type:** Bug fix (JSON parsing robustness)

## Files Modified
- `friday_memory_short_term.py`
  - Added `_strip_markdown_json_response()` function
  - Updated memory extraction markdown stripping (line ~7855)
  - Updated `_extract_and_parse_json()` function (line ~8353)
  - Version bumped to 0.0.22

## Expected Impact
This fix should resolve most of the JSON parsing errors in `memory_validation_errors.json`:
- **invalid_json errors:** Most cases should now parse successfully
- **Wrong bank/missing tags:** May still occur (validation layer handles these separately)
- **LLM failures:** Unrelated to markdown stripping (network/model issues)

## Logging Improvements
Added detailed `[MARKDOWN_STRIP]` debug logs to track:
- What was stripped
- Character count reduction
- Why text was kept vs. extracted
- Boundary detection decisions

## Behavioral Notes
- The function operates on all responses, even clean ones (minimal overhead)
- If response is already clean JSON with no markup, it's passed through unchanged
- Balanced bracket/brace check prevents false positives when extracting boundaries
- All stripping is logged at DEBUG level for troubleshooting

## Next Steps
1. Deploy to production and monitor `memory_validation_errors.json`
2. Check if `invalid_json` error count decreases significantly
3. If errors persist, check logs for specific models still having issues
4. Consider if other response wrapper formats need handling (e.g., XML, YAML)
