# Session Summary -- July 29-30, 2026
## Role-Aware KV Cache, --keep-roles Flag, and datetime Context Injection

### Initial Question

Nate asked whether the Friday short-term memory system invisibly injects the current time into user messages. Investigation revealed that time IS injected -- but only into internal memory LLM calls (extraction, relevance scoring), not the main chat model's context.

This led to the idea: give the main chat model (Gemma4) awareness of current time without modifying the system prompt (which would bust the KV cache). And while we're at it, make the --keep context shift flag role-aware instead of blindly pinning N raw tokens.

### Investigation Path

**1. Time injection in the short-term system**

Four injection points were found in friday_memory_short_term.py, all internal to the memory processing pipeline (query_llm_with_retry at line ~10500, _identify_memories_from_message at ~7983, get_relevant_memories at ~9325 and ~9402). The inlet/outlet never touch the user's message content. The user's chat messages are not modified.

**2. How llama.cpp processes our custom Jinja template**

The custom template at gemma4_prompt_template.jinja is intercepted by a specialized Gemma4 handler BEFORE the autoparser runs (chat.cpp:2990-2998). It matches on the string '<|tool_call>call:' in the template source and routes to common_chat_params_init_gemma4. The autoparser is never called. The Gemma4 handler hardcodes only two message delimiters: user (<|turn>user) and assistant (<|turn>model). System and all custom roles (identity, summary, reminders, memories) are lumped into UNKNOWN spans.

**3. The message_spans system**

llama.cpp has a message_spans system (common/chat.h:157-191) that tracks token positions for each role. The split() function at chat.cpp:152 scans the rendered token stream for delimiter sequences and maps them to common_chat_role values. Each span cleanly covers from one delimiter to the next, giving precise role-level boundaries. However, since our template's delimiters don't include system or identity, those roles were invisible to the span system.

**4. Gemma4's understanding of custom roles**

Google's official Gemma4 prompt formatting docs list exactly three trained roles: system, user, and model. Custom roles (identity, datetime, etc.) are not in the training data. However, they already work in production -- the model reads the content between <|turn> blocks regardless of the role name, since <|turn> is the actual control token that signals a turn boundary. The role name after it is just text. The existing identity/summary/reminders/memories roles already work this way, and datetime follows the same pattern.

**5. Thomas's review**

Nate's other AI assistant Thomas reviewed the plan and raised a question about whether keep_roles needed to go through task_params or could be read from a server global. Investigation confirmed that the existing pattern (n_keep, n_cache_reuse, etc.) all go through task_params via the eval_llama_cmpl_schema copy at server-schema.cpp:526. Following the same pattern for keep_roles was the correct approach.

### Changes Made

**llama.cpp (private fork at /media/nate/Friday/llama.cpp/)**

Seven files modified:

1. common/chat.h (line ~151) -- Added COMMON_CHAT_ROLE_IDENTITY to the common_chat_role enum

2. common/chat.cpp -- Added "identity" mapping in both common_chat_role_from_string and common_chat_role_to_string. Added system (<|turn>system) and identity (<|turn>identity) delimiters to common_chat_params_init_gemma4 at line ~1294, alongside the existing user and assistant delimiters.

3. common/arg.cpp (line ~1600) -- Added --keep-roles CLI flag that accepts a comma-separated list of role names (e.g., --keep-roles system,identity). Stored in params.keep_roles as a vector of strings.

4. common/common.h (line ~459) -- Added keep_roles field (std::vector<std::string>) to common_params struct.

5. tools/server/server-task.h (line ~65) -- Added keep_roles field to task_params struct.

6. tools/server/server-schema.cpp (line ~529) -- Added params.keep_roles = params_base.keep_roles copy in eval_llama_cmpl_schema.

7. tools/server/server-context.cpp (line ~2863) -- Replaced the flat n_keep calculation with dynamic role-aware logic. When --keep-roles is specified, it builds a set of common_chat_role values to match, iterates message_spans to find the end of the last matching span, and sets n_keep to that position. If no spans match, it logs a detailed warning (roles specified, spans found, task id) to both the normal server log and a dedicated keep_roles_error.log file, then falls back to keeping full context. When --keep-roles is not specified, falls back to the existing --keep behavior.

**Jinja template**

8. gemma4_prompt_template.jinja (line ~259) -- Added datetime role block between reminders and the general fallthrough. Renders as <|turn>datetime\n...content...\n<turn|>\n, same pattern as all existing custom roles.

**FMS**

9. friday_memory_short_term.py (line ~6834) -- Changed ORDER list from ["identity", "summary", "reminders", "memories"] to ["datetime", "identity", "summary", "reminders", "memories"]. Added datetime injection in the inlet (line ~5174) that calls self.get_formatted_datetime() and injects the current time as a "datetime" role message with seconds precision.

### How It All Fits Together

The prompt now renders as:
<|turn>system\n...system prompt...\n<turn|>\n
<|turn>datetime\nCurrent date and time: Wednesday, July 29, 2026, 11:28:47 PM CDT\n<turn|>\n
<|turn>identity\n[Personality]...[Relationship]...[Principles]...\n<turn|>\n
<|turn>summary\n[Earlier Conversation Summary]...\n<turn|>\n
<|turn>reminders\n...active reminders...\n<turn|>\n
<|turn>memories\n...relevant memories...\n<turn|>\n
<|turn>user\n[latest user message]\n<turn|>\n

message_spans now correctly identifies each role as a separate span. --keep-roles system,identity pins only system + identity during context shift. Everything else (datetime, summary, reminders, memories, conversation history) is shiftable. The datetime message changes every turn (~30 tokens), but LCP matching and --cache-reuse 256 handle this efficiently since only the timestamp content diverges.

### Key Design Decisions

- --keep-roles is a new CLI flag, not a replacement for --keep. When omitted, existing --keep behavior is preserved. When specified, it overrides --keep by calculating n_keep from message_spans.
- If --keep-roles is specified but no spans match (misconfiguration), a warning is logged and full context is kept. No silent fallback to --keep.
- The error log (keep_roles_error.log) includes which roles were specified, what spans were found, and the task id for traceability.
- The datetime role goes first in the ORDER list (farthest from user), so it's the first to shift out during context shift -- exactly what you want for something that changes every turn.
- Delimiter strings are "<|turn>role" without trailing \n (matches the existing pattern in the Gemma4 handler).

### Files Changed

File                                                   | Change
-------------------------------------------------------|--------------------------------------------------
llama.cpp/common/chat.h                                | Added COMMON_CHAT_ROLE_IDENTITY to enum
llama.cpp/common/chat.cpp                              | Role string mappings + delimiters in init_gemma4
llama.cpp/common/arg.cpp                               | Added --keep-roles CLI flag
llama.cpp/common/common.h                              | Added keep_roles field to common_params
llama.cpp/tools/server/server-task.h                   | Added keep_roles field to task_params
llama.cpp/tools/server/server-schema.cpp               | Copy keep_roles in eval_llama_cmpl_schema
llama.cpp/tools/server/server-context.cpp              | Dynamic n_keep from message_spans
gemma4_prompt_template.jinja                           | Added datetime role block
friday_memory_short_term.py                            | ORDER + inlet datetime injection

### Launch Script Change Needed

Replace:
  --keep 6793
With:
  --keep-roles system,identity

And the --keep flag can be removed from the command line.

### Optional: Role Descriptions in System Prompt

Since the system prompt is set once at model load time (KV cache built once, never invalidated), you can optionally describe the custom roles in the static system prompt:

Available context sections appear in labeled role blocks:
  <|turn>datetime  -- current date and time
  <|turn>identity  -- core identity, personality, relationship context
  <|turn>summary   -- conversation summary for long chats
  <|turn>reminders -- active reminders with due dates
  <|turn>memories  -- relevant stored memories about the user

This is not required -- the existing roles already work without it -- but makes their purpose unmistakable.

### Build Verification

llama.cpp server rebuild completed successfully with zero errors. All C++ changes compile cleanly.

### Plain Text Copy

A plain text version of the full plan (no markdown) was created at:
/media/nate/Friday/Friday/keep_roles_datetime_plan.txt