# Debug Analysis: LM Studio JSON Parsing Failure in Adaptive Memory v3

**Date**: November 9, 2025  
**Issue**: LLM returning empty or malformed JSON during memory relevance scoring  
**Affected Component**: `friday_memory_short_term.py` memory relevance scoring flow

---

## Problem Summary

When saving memories, Adaptive Memory v3 fails with:
- **First attempt**: Empty JSON response (`'text': '', completion_tokens: 0`)
- **Second attempt**: Invalid JSON that fails parsing (`Expecting value: line 1 column 2 (char 1)`)

This happens specifically during the LLM relevance scoring phase (line 3641).

---

## Root Cause Analysis

### Finding #1: LM Studio Configuration Mismatch (Line 4209-4219)

```python
if is_lm_studio:
    # LM Studio expects 'prompt' field instead of 'messages'
    combined_prompt = f"{system_prompt_with_date}\n\n{user_prompt}"
    data = {
        "model": model,
        "prompt": combined_prompt,
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 1024,  # ← POTENTIAL ISSUE #1
        "stream": False,
    }
```

**Issue**: LM Studio is NOT being told to return JSON format. Compare with non-LM Studio code:
```python
else:
    # Standard OpenAI-compatible API
    data = {
        ...
        "response_format": {"type": "json_object"},  # ← Force JSON mode
        ...
    }
```

LM Studio doesn't support `response_format` in the same way, but the combined prompt should explicitly request JSON.

---

### Finding #2: Prompt Length and Context Window (Line 3606-3643)

The prompt being constructed is:
```python
uncached_user_prompt = f"""Current user message: "{current_message}"

Available memories (evaluate relevance for these specific IDs):
{json.dumps(uncached_memory_strings)}

Rate the relevance of EACH listed memory to the current user message based *only* on the provided content and message context.

Current datetime: {current_datetime.strftime('%A, %B %d, %Y %H:%M:%S')} ({current_datetime.tzinfo})"""
```

The `system_prompt_with_date` adds even more:
```python
system_prompt_with_date = f"{system_prompt}\n\nCurrent date and time: {now.strftime('%Y-%m-%d %H:%M:%S')} {tzname}"
```

**Combined Content:**
- System prompt: ~800 tokens (memory_relevance_prompt from valves)
- System date: ~20 tokens
- User message: varies
- Memory list (5 memories × ~50 tokens each): ~250 tokens  
- Instructions: ~50 tokens
- **Total**: ~1,120 tokens

With `max_tokens: 1024`, if the input prompt fills 1,556 tokens (as shown in log), the model has NO room left in context window.

**Model**: llama2-7b-chat-hf-v4 has 4096 context window
- Input tokens: 1,556
- Max output tokens requested: 1,024
- **Total needed**: 2,580 (well within 4096)

But the log shows `completion_tokens: 0` on first attempt - the model stopped WITHOUT generating output.

---

### Finding #3: Timing/Race Condition Hypothesis

The logs show:
- **14:35:45.243**: First LLM request made
- **14:35:45.608**: Response received (365ms later) - EMPTY response
- **14:35:45.610**: Retry attempt 2 initiated immediately
- **14:35:58.148**: Second attempt response (12.5 seconds later) - Gets content but invalid JSON

**Possible Race Condition**:
1. First request made while model is still processing previous context
2. Model times out or returns early with empty response  
3. Retry sends new request
4. Model finally processes and returns content, but it's malformed

This could be related to:
- Model state not being reset between requests
- Asynchronous context handling in LM Studio
- Session reuse issues (`self._get_aiohttp_session()`)

---

### Finding #4: JSON Format Not Enforced for LM Studio

Looking at the system prompt (line 807-818):

```python
memory_relevance_prompt: str = Field(
    default="""You are a memory retrieval assistant...
    
Return your analysis as a JSON array with each memory's content, ID, and relevance score.
Example: [{"memory": "User likes coffee", "id": "123", "relevance": 0.8}]

Your output must be valid JSON only. No additional text.""",
```

The prompt **requests** JSON but doesn't **enforce** it for LM Studio. The model sees plain text prompt, not a structured JSON request.

---

## Key Differences Between Providers

| Aspect | Ollama | OpenAI API | LM Studio (Current) |
|--------|--------|-----------|---|
| Format request | `"format": "json"` in options | `"response_format": {"type": "json_object"}` | **NONE** |
| Prompt style | Messages array | Messages array | Raw prompt string |
| JSON guarantee | Enforced | Enforced | Text-based request only |
| Max tokens | `num_predict: 2048` | `max_tokens: 1024` | `max_tokens: 1024` |

---

## Likely Root Cause (Most Probable)

**The model is not being told to generate JSON format for LM Studio.**

When LM Studio receives a raw prompt string (not structured messages), it treats it as generic text completion. The small llama2-7b model may:

1. **First attempt**: Get confused by the complex JSON instruction in plain text → generate nothing (empty response)
2. **Retry with more context**: Generate text that looks like JSON but isn't valid (starts with `{` but malformed structure)

---

## Evidence from Logs

**Log Entry 1** (14:35:45.608):
```
"Could not extract content from openai_compatible response format: 
{'choices': [{'index': 0, 'text': '', 'logprobs': None, 'finish_reason': 'stop'}]}"
```
→ Model finished early with empty output

**Log Entry 2** (14:35:58.149):
```
"Retrieved content from LM Studio response (length: 878)"
"Direct JSON parsing failed after pre-processing: Expecting value: line 1 column 2 (char 1)"
```
→ Model returned 878 characters of invalid JSON

---

## Why Larger Models Have Same Issue

If the issue is **format/instruction clarity** (not context size), then:
- Larger models might also struggle if the prompt doesn't properly request JSON format
- The problem is **structural**, not **capacity-based**
- Simply increasing model size won't fix it if the LM Studio integration doesn't enforce JSON output

---

## Recommended Fixes

### Fix #1 (Immediate): Ensure LM Studio Enforces JSON

Add explicit JSON formatting instruction to the prompt when using LM Studio.

### Fix #2 (Best): Separate LM Studio Handler with Proper JSON Request

Create LM Studio-specific logic that:
1. Requests JSON output explicitly
2. Uses shorter, focused prompts
3. Validates response format before parsing

### Fix #3 (Fallback): Error Recovery

When JSON parsing fails:
- Don't retry indefinitely
- Return empty relevance scores instead
- Log the actual response for debugging
- Continue with memory save (graceful degradation)

### Fix #4 (Performance): Reduce Prompt Complexity

Simplify the memory relevance prompt to:
- Remove unnecessary context
- Reduce memory list size
- Use clearer JSON request format

---

## Next Steps

1. **Verify**: Print the actual combined prompt being sent to LM Studio
2. **Test**: Try sending a minimal JSON request to LM Studio
3. **Implement**: Add LM Studio-specific JSON formatting
4. **Validate**: Test with actual memory save workflow

