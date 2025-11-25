# Summarization Feedback Loop Analysis
**Date**: November 11, 2025  
**Status**: ROOT CAUSE IDENTIFIED - FIX PROPOSED  
**Priority**: HIGH

---

## The Problem (What User Reported)

User said: *"The memory model gets done with the summary, it sends off its summary, and it's treating it as a new message... happening with regular chat too, think we broke something"*

**Symptoms**:
- Summary is generated and injected into system message
- On next turn, it appears the summary is being re-processed
- User sees summary generation happening multiple times
- Memory extraction treats summary content as new user input

---

## Root Cause Analysis

### The Actual Flow (Current)

**Turn 1-24**: Regular conversation
```
User: "Hello"
Assistant: "Hi there"
User: "How are you?"
Assistant: "I'm doing well"
... (25 messages total)
```

**Turn 25 (Summary Trigger)**:
1. `inlet()` is called with Turn 25's user message + assistant response
2. `_should_summarize_now()` evaluates: 25 messages >= 25 threshold → **returns TRUE**
3. `_generate_conversation_summary()` is called
   - Extracts messages 0-24
   - Calls LLM with summarization prompt
   - Returns summary: `"User greeted me and asked how I'm doing"`
4. `_inject_summary_into_context()` modifies `body["messages"]`:
   - Finds the system message (Friday's personality)
   - **APPENDS the summary to it**: `"system_content += summary"`
   - Now system message is: `"You are Friday... [Earlier Conversation Summary] User greeted me..."`

**Turn 26 (The Bug Manifests)**:
1. `inlet()` is called with Turn 26's user message
2. `_process_user_memories()` is called
   - Extracts ALL messages from `body["messages"]`
   - This includes the **SYSTEM MESSAGE WITH THE SUMMARY APPENDED**
3. `identify_memories()` analyzes the messages:
   - It sees the system message content (which now includes the summary)
   - Treats the summary text as "context about the conversation"
   - **Extracts memories from the summary text itself**
   - "User greeted me" becomes a memory
   - "User asked how I'm doing" becomes a memory

**The Feedback Loop**:
- Summary gets injected into system message (persistent across turns)
- Next turn, `identify_memories()` processes system message
- Finds the injected summary
- Treats summary as new context
- Extracts memories from summary content
- Memory extraction sees the summary as "new information"
- If summarization tries to process those extracted memories... **circular reference**

---

## Why This "Looks Like" Retry Cascade

The LM Studio logs showing repeated requests aren't actually about summarization retrying. They're about:
1. Summary injection happens
2. Memories extracted from system message
3. Memory analysis LLM call starts
4. If LM Studio disconnects mid-analysis, `query_llm_with_retry()` retries
5. User sees multiple attempts in logs
6. But it's memory analysis retrying, not summarization

The confusion comes from: **multiple LLM operations** happening in sequence:
1. Summarization LLM call (generates summary)
2. Memory extraction from that summary (analysis LLM call)
3. Each can retry independently if there's a timeout

---

## Why It's Not a Retry Problem

Looking at the `query_llm_with_retry()` code (lines 5999-6300+):
- ✅ Has exponential backoff
- ✅ Has timeout handling
- ✅ Has proper error detection
- ✅ Distinguishes between retryable errors (429, 5xx) and non-retryable ones

The retry logic is **actually working correctly**. The problem isn't there.

---

## The Real Fix

We need to prevent the summary from being processed as **new context** in subsequent turns. There are three approaches:

### Option 1: Mark Summary Content as Non-Contextual (RECOMMENDED)

Wrap the summary injection with metadata markers:

```python
def _inject_summary_into_context(self, body, summary, system_prompt=None):
    # ... existing code ...
    
    # Mark summary so memory operations skip it
    injection = (
        "\n\n[INTERNAL_SUMMARY_MARKER_START]\n"
        f"{summary}"
        "\n[INTERNAL_SUMMARY_MARKER_END]\n"
    )
    
    # When processing memories, skip content between markers
```

Then in `identify_memories()`:
```python
# Remove internal markers before processing
messages_text = re.sub(
    r'\[INTERNAL_SUMMARY_MARKER_START\].*?\[INTERNAL_SUMMARY_MARKER_END\]',
    '',
    messages_text,
    flags=re.DOTALL
)
```

**Pros**: Simple, clear, explicit  
**Cons**: Requires regex handling

### Option 2: Don't Persist Summary Across Turns (BETTER UX)

Instead of appending to system message, pass summary in a separate channel:

```python
# Current (WRONG):
messages[system_msg_idx]["content"] += f"\n\nSummary: {summary}"

# Better:
body["_summary_context"] = summary  # Don't add to messages
# LLM sees summary differently (passed separately to LM Studio)
```

**Pros**: Summary doesn't get mixed with system prompt  
**Cons**: Requires changes to how summary is passed to LLM

### Option 3: Only Include Summary For Current Turn

Make summary injection temporary:

```python
def _inject_summary_into_context(self, body, summary):
    # Create a COPY of messages for this turn only
    messages_copy = copy.deepcopy(body["messages"])
    
    # Inject into the copy
    # Store the copy somewhere temporary
    # Pass it ONLY for this LLM call
    # Don't modify body["messages"] permanently
```

**Pros**: Cleanest - summary doesn't persist  
**Cons**: More complex to implement

---

## Recommended Approach

**Option 1 + better logging**:

1. Add markers around injected summary content
2. Add debug logging showing exactly what's being injected
3. In `identify_memories()`, strip marker content before analyzing
4. Log what was stripped
5. Verify memory extraction doesn't include summary

This approach:
- ✅ Requires minimal code changes
- ✅ Is easy to understand and maintain
- ✅ Is easy to disable (remove markers if needed)
- ✅ Provides clear audit trail in logs
- ✅ Doesn't break existing system message handling

---

## Implementation Plan

### Step 1: Add Markers to Summary Injection
**File**: `friday_memory_short_term.py` line 2118  
**Change**: Add markers around injection

```python
injection = (
    "\n\n[SUMMARY_CONTENT_START]\n"
    f"{summary}\n"
    "[SUMMARY_CONTENT_END]\n"
)
```

### Step 2: Skip Marked Content in Memory Extraction
**File**: `friday_memory_short_term.py` in `identify_memories()`  
**Change**: Strip summary markers before processing

```python
# Strip internal markers before processing
messages_text = re.sub(
    r'\[SUMMARY_CONTENT_START\].*?\[SUMMARY_CONTENT_END\]',
    '',
    messages_text,
    flags=re.DOTALL
)
logger.debug(f"Stripped summary markers from context before memory analysis")
```

### Step 3: Add Logging
**File**: `friday_memory_short_term.py` in `identify_memories()`  
**Change**: Log before/after

```python
original_length = len(messages_text)
messages_text = re.sub(...)
if len(messages_text) < original_length:
    logger.info(f"Stripped {original_length - len(messages_text)} chars of summary markers")
```

### Step 4: Test
1. Enable summarization (trigger at 25 messages)
2. Have a conversation with 30+ messages
3. Check logs:
   - Summary generated? ✓
   - Summary injected with markers? ✓
   - Markers stripped before memory analysis? ✓
   - No summary content in extracted memories? ✓

---

## Testing Checklist

```
[ ] Summarization happens at correct message threshold
[ ] Summary is injected into system message with markers
[ ] Markers are logged when injected
[ ] Memory extraction finds and removes markers
[ ] Extracted memories don't include summary content
[ ] Regular conversation continues working
[ ] No error messages about markers
[ ] LM Studio logs don't show excessive retries
```

---

## Expected Outcome After Fix

**Before**:
- Summary generated
- Injected into system message
- Next turn, memory extraction processes system message
- Extracts memories from summary content
- Looks like feedback loop

**After**:
- Summary generated
- Injected into system message with markers
- Next turn, memory extraction processes system message
- **Markers are removed before analysis**
- Summary content is skipped
- Memories extracted from actual user conversation only
- No feedback loop

---

## Why This Fixes "Regular Chat Too" Problem

User said it's happening with regular chat also. This makes sense because:
- Any content in system message gets processed by `identify_memories()`
- If system message accidentally includes previous turn's content
- `identify_memories()` will re-process it
- Applying marker stripping prevents any system message content from being treated as new context

The markers approach is general-purpose and helps with anything accidentally injected into system message.
