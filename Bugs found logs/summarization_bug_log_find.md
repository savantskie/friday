2025-11-18 14:26:19  [INFO]
 [qwen/qwen3-vl-4b] Model generated tool calls:  []
2025-11-18 14:26:19  [INFO]
 [qwen/qwen3-vl-4b] Generated prediction:  {
  "id": "chatcmpl-9xvagmfrrqabuikcv6nikf",
  "object": "chat.completion",
  "created": 1763497517,
  "model": "qwen/qwen3-vl-4b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The conversation centers on Nate’s efforts to improve and stabilize the AI system’s memory and context handling, particularly around preserving short-term memory tags during transitions to long-term storage. Nate expresses frustration with past system instability, including a 70-second power outage that caused model resets, and seeks to prevent future data loss. He’s currently working on integrating Claude Haiku 4.5 into his workflow and is preparing to dive into memory system architecture. The AI acknowledges the challenges, confirms 32K",
        "reasoning_content": "",
        "tool_calls": []
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 3154,
    "completion_tokens": 101,
    "total_tokens": 3255
  },
  "stats": {},
  "system_fingerprint": "qwen/qwen3-vl-4b"
}
2025-11-18 14:26:51 [DEBUG]
 Received request: POST to /v1/chat/completions with body  {
  "model": "qwen/qwen3-vl-4b",
  "messages": [
    {
      "role": "system",
      "content": "You are a conversation summarizer. Your task is to... <Truncated in logs> ...y.\n\nCurrent date and time: 2025-11-18 14:19:42 CST"
    },
    {
      "role": "user",
      "content": "Conversation to summarize:\n\nUSER: Good morning\n\nAS... <Truncated in logs> ...de a concise summary of this conversation segment."
    }
  ],
  "temperature": 0,
  "top_p": 1,
  "max_tokens": 1024,
  "stream": false
}
2025-11-18 14:26:51  [INFO]
 [qwen/qwen3-vl-4b] Running chat completion on conversation with 2 messages.
2025-11-18 14:26:51 [DEBUG]
 Sampling params:	repeat_last_n = 64, repeat_penalty = 1.000, frequency_penalty = 0.000, presence_penalty = 0.000
	dry_multiplier = 0.000, dry_base = 1.750, dry_allowed_length = 2, dry_penalty_last_n = -1
	top_k = 20, top_p = 1.000, min_p = 0.050, xtc_probability = 0.000, xtc_threshold = 0.100, typical_p = 1.000, top_n_sigma = -1.000, temp = 0.000
	mirostat = 0, mirostat_lr = 0.100, mirostat_ent = 5.000
Sampling: 
logits -> logit-bias -> penalties -> dry -> top-n-sigma -> top-k -> typical -> top-p -> min-p -> xtc -> temp-ext -> dist 
Generate: n_ctx = 16384, n_batch = 512, n_predict = 1024, n_keep = 3154
2025-11-18 14:26:51 [DEBUG]
 Cache reuse summary: 3154/3154 of prompt (100%), 3154 prefix, 0 non-prefix
Total prompt tokens: 3154
Prompt tokens to decode: 1
BeginProcessingPrompt
2025-11-18 14:26:51  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 0.0%
2025-11-18 14:26:52 [DEBUG]
 FinishedProcessingPrompt. Progress: 100
2025-11-18 14:26:52  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 100.0%
2025-11-18 14:27:51  [INFO]
 [LM STUDIO SERVER] Client disconnected. Stopping generation... (If the model is busy processing the prompt, it will finish first.)
2025-11-18 14:27:52 [DEBUG]
 Target model llama_perf stats:
llama_perf_sampler_print:    sampling time =       9.48 ms /  3254 runs   (    0.00 ms per token, 343357.60 tokens per second)
llama_perf_context_print:        load time =    3103.96 ms
llama_perf_context_print: prompt eval time =       0.00 ms /     1 tokens (    0.00 ms per token,      inf tokens per second)
llama_perf_context_print:        eval time =   60652.46 ms /   100 runs   (  606.52 ms per token,     1.65 tokens per second)
llama_perf_context_print:       total time =   60690.69 ms /   101 tokens
llama_perf_context_print:    graphs reused =          0
2025-11-18 14:27:52 [DEBUG]
 llama_memory_breakdown_print: | memory breakdown [MiB]                 | total    free    self   model   context   compute       unaccounted |
llama_memory_breakdown_print: |   - Vulkan0 (RX 7900 XT (RADV NAVI31)) | 20224 =  3982 + (2398 =  1089 +    1216 +      93) +          13842 |
llama_memory_breakdown_print: |   - Vulkan1 (RX 6800 (RADV NAVI21))    | 16128 = 13503 + (2675 =  1285 +    1088 +     301) + 17592186044365 |
llama_memory_breakdown_print: |   - Host                               |                   341 =   304 +       0 +      37                   |
2025-11-18 14:27:52  [INFO]
 [qwen/qwen3-vl-4b] Model generated tool calls:  []
2025-11-18 14:27:52  [INFO]
 [qwen/qwen3-vl-4b] Generated prediction:  {
  "id": "chatcmpl-q5fknhhionekjjuq15yu0f",
  "object": "chat.completion",
  "created": 1763497611,
  "model": "qwen/qwen3-vl-4b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The conversation centers on Nate’s efforts to improve and stabilize the AI system’s memory and context handling, particularly around preserving short-term memory tags during transitions to long-term storage. Nate expresses frustration with past system instability, including a 70-second power outage that caused model resets, and seeks to prevent future data loss. He’s currently working on integrating Claude Haiku 4.5 into his workflow and is preparing to dive into memory system architecture. The AI acknowledges the challenges, confirms 32",
        "reasoning_content": "",
        "tool_calls": []
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 3154,
    "completion_tokens": 100,
    "total_tokens": 3254
  },
  "stats": {},
  "system_fingerprint": "qwen/qwen3-vl-4b"
}
2025-11-18 14:28:56 [DEBUG]
 Received request: POST to /v1/chat/completions with body  {
  "model": "qwen/qwen3-vl-4b",
  "messages": [
    {
      "role": "system",
      "content": "You are a conversation summarizer. Your task is to... <Truncated in logs> ...y.\n\nCurrent date and time: 2025-11-18 14:19:42 CST"
    },
    {
      "role": "user",
      "content": "Conversation to summarize:\n\nUSER: Good morning\n\nAS... <Truncated in logs> ...de a concise summary of this conversation segment."
    }
  ],
  "temperature": 0,
  "top_p": 1,
  "max_tokens": 1024,
  "stream": false
}
2025-11-18 14:28:56  [INFO]
 [qwen/qwen3-vl-4b] Running chat completion on conversation with 2 messages.
2025-11-18 14:28:56 [DEBUG]
 Sampling params:	repeat_last_n = 64, repeat_penalty = 1.000, frequency_penalty = 0.000, presence_penalty = 0.000
	dry_multiplier = 0.000, dry_base = 1.750, dry_allowed_length = 2, dry_penalty_last_n = -1
	top_k = 20, top_p = 1.000, min_p = 0.050, xtc_probability = 0.000, xtc_threshold = 0.100, typical_p = 1.000, top_n_sigma = -1.000, temp = 0.000
	mirostat = 0, mirostat_lr = 0.100, mirostat_ent = 5.000
Sampling: 
logits -> logit-bias -> penalties -> dry -> top-n-sigma -> top-k -> typical -> top-p -> min-p -> xtc -> temp-ext -> dist 
Generate: n_ctx = 16384, n_batch = 512, n_predict = 1024, n_keep = 3154
2025-11-18 14:28:56 [DEBUG]
 Cache reuse summary: 3154/3154 of prompt (100%), 3154 prefix, 0 non-prefix
Total prompt tokens: 3154
Prompt tokens to decode: 1
BeginProcessingPrompt
2025-11-18 14:28:56  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 0.0%
2025-11-18 14:28:57 [DEBUG]
 FinishedProcessingPrompt. Progress: 100
2025-11-18 14:28:57  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 100.0%
2025-11-18 14:29:56  [INFO]
 [LM STUDIO SERVER] Client disconnected. Stopping generation... (If the model is busy processing the prompt, it will finish first.)
2025-11-18 14:29:57 [DEBUG]
 Target model llama_perf stats:
llama_perf_sampler_print:    sampling time =       9.24 ms /  3255 runs   (    0.00 ms per token, 352196.49 tokens per second)
llama_perf_context_print:        load time =    3103.96 ms
llama_perf_context_print: prompt eval time =       0.00 ms /     1 tokens (    0.00 ms per token,      inf tokens per second)
llama_perf_context_print:        eval time =   61000.64 ms /   101 runs   (  603.97 ms per token,     1.66 tokens per second)
llama_perf_context_print:       total time =   61038.13 ms /   102 tokens
llama_perf_context_print:    graphs reused =          0
2025-11-18 14:29:57 [DEBUG]
 llama_memory_breakdown_print: | memory breakdown [MiB]                 | total    free    self   model   context   compute       unaccounted |
llama_memory_breakdown_print: |   - Vulkan0 (RX 7900 XT (RADV NAVI31)) | 20224 =  3982 + (2398 =  1089 +    1216 +      93) +          13842 |
llama_memory_breakdown_print: |   - Vulkan1 (RX 6800 (RADV NAVI21))    | 16128 = 13503 + (2675 =  1285 +    1088 +     301) + 17592186044365 |
llama_memory_breakdown_print: |   - Host                               |                   341 =   304 +       0 +      37                   |
2025-11-18 14:29:57  [INFO]
 [qwen/qwen3-vl-4b] Model generated tool calls:  []
2025-11-18 14:29:57  [INFO]
 [qwen/qwen3-vl-4b] Generated prediction:  {
  "id": "chatcmpl-wsd84msth0n7indvl2gonm",
  "object": "chat.completion",
  "created": 1763497736,
  "model": "qwen/qwen3-vl-4b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The conversation centers on Nate’s efforts to improve and stabilize the AI system’s memory and context handling, particularly around preserving short-term memory tags during transitions to long-term storage. Nate expresses frustration with past system instability, including a 70-second power outage that caused model resets, and seeks to prevent future data loss. He’s currently working on integrating Claude Haiku 4.5 into his workflow and is preparing to dive into memory system architecture. The AI acknowledges the challenges, confirms 32K",
        "reasoning_content": "",
        "tool_calls": []
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 3154,
    "completion_tokens": 101,
    "total_tokens": 3255
  },
  "stats": {},
  "system_fingerprint": "qwen/qwen3-vl-4b"
}
2025-11-18 14:32:04 [DEBUG]
 Received request: POST to /v1/chat/completions with body  {
  "model": "qwen/qwen3-vl-4b",
  "messages": [
    {
      "role": "system",
      "content": "You are a conversation summarizer. Your task is to... <Truncated in logs> ...y.\n\nCurrent date and time: 2025-11-18 14:19:42 CST"
    },
    {
      "role": "user",
      "content": "Conversation to summarize:\n\nUSER: Good morning\n\nAS... <Truncated in logs> ...de a concise summary of this conversation segment."
    }
  ],
  "temperature": 0,
  "top_p": 1,
  "max_tokens": 1024,
  "stream": false
}
2025-11-18 14:32:04  [INFO]
 [qwen/qwen3-vl-4b] Running chat completion on conversation with 2 messages.
2025-11-18 14:32:05 [DEBUG]
 Sampling params:	repeat_last_n = 64, repeat_penalty = 1.000, frequency_penalty = 0.000, presence_penalty = 0.000
	dry_multiplier = 0.000, dry_base = 1.750, dry_allowed_length = 2, dry_penalty_last_n = -1
	top_k = 20, top_p = 1.000, min_p = 0.050, xtc_probability = 0.000, xtc_threshold = 0.100, typical_p = 1.000, top_n_sigma = -1.000, temp = 0.000
	mirostat = 0, mirostat_lr = 0.100, mirostat_ent = 5.000
Sampling: 
logits -> logit-bias -> penalties -> dry -> top-n-sigma -> top-k -> typical -> top-p -> min-p -> xtc -> temp-ext -> dist 
Generate: n_ctx = 16384, n_batch = 512, n_predict = 1024, n_keep = 3154
2025-11-18 14:32:05 [DEBUG]
 Cache reuse summary: 3154/3154 of prompt (100%), 3154 prefix, 0 non-prefix
Total prompt tokens: 3154
Prompt tokens to decode: 1
BeginProcessingPrompt
2025-11-18 14:32:05  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 0.0%
2025-11-18 14:32:06 [DEBUG]
 FinishedProcessingPrompt. Progress: 100
2025-11-18 14:32:06  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 100.0%
2025-11-18 14:33:05  [INFO]
 [LM STUDIO SERVER] Client disconnected. Stopping generation... (If the model is busy processing the prompt, it will finish first.)
2025-11-18 14:33:06 [DEBUG]
 Target model llama_perf stats:
llama_perf_sampler_print:    sampling time =       9.32 ms /  3255 runs   (    0.00 ms per token, 349323.89 tokens per second)
llama_perf_context_print:        load time =    3103.96 ms
llama_perf_context_print: prompt eval time =       0.00 ms /     1 tokens (    0.00 ms per token,      inf tokens per second)
llama_perf_context_print:        eval time =   61099.10 ms /   101 runs   (  604.94 ms per token,     1.65 tokens per second)
llama_perf_context_print:       total time =   61136.39 ms /   102 tokens
llama_perf_context_print:    graphs reused =          0
2025-11-18 14:33:06 [DEBUG]
 llama_memory_breakdown_print: | memory breakdown [MiB]                 | total    free    self   model   context   compute       unaccounted |
llama_memory_breakdown_print: |   - Vulkan0 (RX 7900 XT (RADV NAVI31)) | 20224 =  3982 + (2398 =  1089 +    1216 +      93) +          13842 |
llama_memory_breakdown_print: |   - Vulkan1 (RX 6800 (RADV NAVI21))    | 16128 = 13503 + (2675 =  1285 +    1088 +     301) + 17592186044365 |
llama_memory_breakdown_print: |   - Host                               |                   341 =   304 +       0 +      37                   |
2025-11-18 14:33:06  [INFO]
 [qwen/qwen3-vl-4b] Model generated tool calls:  []
2025-11-18 14:33:06  [INFO]
 [qwen/qwen3-vl-4b] Generated prediction:  {
  "id": "chatcmpl-2e9j981mjj3zoc4is7cpka",
  "object": "chat.completion",
  "created": 1763497924,
  "model": "qwen/qwen3-vl-4b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The conversation centers on Nate’s efforts to improve and stabilize the AI system’s memory and context handling, particularly around preserving short-term memory tags during transitions to long-term storage. Nate expresses frustration with past system instability, including a 70-second power outage that caused model resets, and seeks to prevent future data loss. He’s currently working on integrating Claude Haiku 4.5 into his workflow and is preparing to dive into memory system architecture. The AI acknowledges the challenges, confirms 32K",
        "reasoning_content": "",
        "tool_calls": []
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 3154,
    "completion_tokens": 101,
    "total_tokens": 3255
  },
  "stats": {},
  "system_fingerprint": "qwen/qwen3-vl-4b"
}
2025-11-18 14:37:22 [DEBUG]
 Received request: POST to /v1/chat/completions with body  {
  "model": "qwen/qwen3-vl-4b",
  "messages": [
    {
      "role": "system",
      "content": "You are a conversation summarizer. Your task is to... <Truncated in logs> ...y.\n\nCurrent date and time: 2025-11-18 14:19:42 CST"
    },
    {
      "role": "user",
      "content": "Conversation to summarize:\n\nUSER: Good morning\n\nAS... <Truncated in logs> ...de a concise summary of this conversation segment."
    }
  ],
  "temperature": 0,
  "top_p": 1,
  "max_tokens": 1024,
  "stream": false
}
2025-11-18 14:37:22  [INFO]
 [qwen/qwen3-vl-4b] Running chat completion on conversation with 2 messages.
2025-11-18 14:37:22 [DEBUG]
 Sampling params:	repeat_last_n = 64, repeat_penalty = 1.000, frequency_penalty = 0.000, presence_penalty = 0.000
	dry_multiplier = 0.000, dry_base = 1.750, dry_allowed_length = 2, dry_penalty_last_n = -1
	top_k = 20, top_p = 1.000, min_p = 0.050, xtc_probability = 0.000, xtc_threshold = 0.100, typical_p = 1.000, top_n_sigma = -1.000, temp = 0.000
	mirostat = 0, mirostat_lr = 0.100, mirostat_ent = 5.000
2025-11-18 14:37:22 [DEBUG]
 Sampling: 
logits -> logit-bias -> penalties -> dry -> top-n-sigma -> top-k -> typical -> top-p -> min-p -> xtc -> temp-ext -> dist 
Generate: n_ctx = 16384, n_batch = 512, n_predict = 1024, n_keep = 3154
2025-11-18 14:37:22 [DEBUG]
 Cache reuse summary: 3154/3154 of prompt (100%), 3154 prefix, 0 non-prefix
Total prompt tokens: 3154
Prompt tokens to decode: 1
BeginProcessingPrompt
2025-11-18 14:37:22  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 0.0%
2025-11-18 14:37:23 [DEBUG]
 FinishedProcessingPrompt. Progress: 100
2025-11-18 14:37:23  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 100.0%
2025-11-18 14:38:22  [INFO]
 [LM STUDIO SERVER] Client disconnected. Stopping generation... (If the model is busy processing the prompt, it will finish first.)
2025-11-18 14:38:23 [DEBUG]
 Target model llama_perf stats:
llama_perf_sampler_print:    sampling time =       9.72 ms /  3255 runs   (    0.00 ms per token, 334911.00 tokens per second)
llama_perf_context_print:        load time =    3103.96 ms
llama_perf_context_print: prompt eval time =       0.00 ms /     1 tokens (    0.00 ms per token,      inf tokens per second)
llama_perf_context_print:        eval time =   60965.00 ms /   101 runs   (  603.61 ms per token,     1.66 tokens per second)
llama_perf_context_print:       total time =   61002.88 ms /   102 tokens
llama_perf_context_print:    graphs reused =          0
2025-11-18 14:38:23 [DEBUG]
 llama_memory_breakdown_print: | memory breakdown [MiB]                 | total    free    self   model   context   compute       unaccounted |
llama_memory_breakdown_print: |   - Vulkan0 (RX 7900 XT (RADV NAVI31)) | 20224 =  3982 + (2398 =  1089 +    1216 +      93) +          13842 |
llama_memory_breakdown_print: |   - Vulkan1 (RX 6800 (RADV NAVI21))    | 16128 = 13503 + (2675 =  1285 +    1088 +     301) + 17592186044365 |
llama_memory_breakdown_print: |   - Host                               |                   341 =   304 +       0 +      37                   |
2025-11-18 14:38:23  [INFO]
 [qwen/qwen3-vl-4b] Model generated tool calls:  []
2025-11-18 14:38:23  [INFO]
 [qwen/qwen3-vl-4b] Generated prediction:  {
  "id": "chatcmpl-wrv61pwz7ihptu7qdn129",
  "object": "chat.completion",
  "created": 1763498242,
  "model": "qwen/qwen3-vl-4b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The conversation centers on Nate’s efforts to improve and stabilize the AI system’s memory and context handling, particularly around preserving short-term memory tags during transitions to long-term storage. Nate expresses frustration with past system instability, including a 70-second power outage that caused model resets, and seeks to prevent future data loss. He’s currently working on integrating Claude Haiku 4.5 into his workflow and is preparing to dive into memory system architecture. The AI acknowledges the challenges, confirms 32K",
        "reasoning_content": "",
        "tool_calls": []
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 3154,
    "completion_tokens": 101,
    "total_tokens": 3255
  },
  "stats": {},
  "system_fingerprint": "qwen/qwen3-vl-4b"
}
2025-11-18 14:46:55 [DEBUG]
 Received request: POST to /v1/chat/completions with body  {
  "model": "qwen/qwen3-vl-4b",
  "messages": [
    {
      "role": "system",
      "content": "You are a conversation summarizer. Your task is to... <Truncated in logs> ...y.\n\nCurrent date and time: 2025-11-18 14:19:42 CST"
    },
    {
      "role": "user",
      "content": "Conversation to summarize:\n\nUSER: Good morning\n\nAS... <Truncated in logs> ...de a concise summary of this conversation segment."
    }
  ],
  "temperature": 0,
  "top_p": 1,
  "max_tokens": 1024,
  "stream": false
}
2025-11-18 14:46:55  [INFO]
 [qwen/qwen3-vl-4b] Running chat completion on conversation with 2 messages.
2025-11-18 14:46:55 [DEBUG]
 Sampling params:	repeat_last_n = 64, repeat_penalty = 1.000, frequency_penalty = 0.000, presence_penalty = 0.000
	dry_multiplier = 0.000, dry_base = 1.750, dry_allowed_length = 2, dry_penalty_last_n = -1
	top_k = 20, top_p = 1.000, min_p = 0.050, xtc_probability = 0.000, xtc_threshold = 0.100, typical_p = 1.000, top_n_sigma = -1.000, temp = 0.000
	mirostat = 0, mirostat_lr = 0.100, mirostat_ent = 5.000
Sampling: 
logits -> logit-bias -> penalties -> dry -> top-n-sigma -> top-k -> typical -> top-p -> min-p -> xtc -> temp-ext -> dist 
Generate: n_ctx = 16384, n_batch = 512, n_predict = 1024, n_keep = 3154
2025-11-18 14:46:55 [DEBUG]
 Cache reuse summary: 3154/3154 of prompt (100%), 3154 prefix, 0 non-prefix
Total prompt tokens: 3154
Prompt tokens to decode: 1
BeginProcessingPrompt
2025-11-18 14:46:55  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 0.0%
2025-11-18 14:46:56 [DEBUG]
 FinishedProcessingPrompt. Progress: 100
2025-11-18 14:46:56  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 100.0%
2025-11-18 14:47:55  [INFO]
 [LM STUDIO SERVER] Client disconnected. Stopping generation... (If the model is busy processing the prompt, it will finish first.)
2025-11-18 14:47:56 [DEBUG]
 Target model llama_perf stats:
llama_perf_sampler_print:    sampling time =       9.64 ms /  3255 runs   (    0.00 ms per token, 337585.56 tokens per second)
llama_perf_context_print:        load time =    3103.96 ms
llama_perf_context_print: prompt eval time =       0.00 ms /     1 tokens (    0.00 ms per token,      inf tokens per second)
llama_perf_context_print:        eval time =   61107.56 ms /   101 runs   (  605.03 ms per token,     1.65 tokens per second)
llama_perf_context_print:       total time =   61145.52 ms /   102 tokens
llama_perf_context_print:    graphs reused =          0
2025-11-18 14:47:56 [DEBUG]
 llama_memory_breakdown_print: | memory breakdown [MiB]                 | total    free    self   model   context   compute       unaccounted |
llama_memory_breakdown_print: |   - Vulkan0 (RX 7900 XT (RADV NAVI31)) | 20224 =  3982 + (2398 =  1089 +    1216 +      93) +          13842 |
llama_memory_breakdown_print: |   - Vulkan1 (RX 6800 (RADV NAVI21))    | 16128 = 13503 + (2675 =  1285 +    1088 +     301) + 17592186044365 |
llama_memory_breakdown_print: |   - Host                               |                   341 =   304 +       0 +      37                   |
2025-11-18 14:47:56  [INFO]
 [qwen/qwen3-vl-4b] Model generated tool calls:  []
2025-11-18 14:47:56  [INFO]
 [qwen/qwen3-vl-4b] Generated prediction:  {
  "id": "chatcmpl-7y4v6pwe4flqm7v8yzhme",
  "object": "chat.completion",
  "created": 1763498815,
  "model": "qwen/qwen3-vl-4b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The conversation centers on Nate’s efforts to improve and stabilize the AI system’s memory and context handling, particularly around preserving short-term memory tags during transitions to long-term storage. Nate expresses frustration with past system instability, including a 70-second power outage that caused model resets, and seeks to prevent future data loss. He’s currently working on integrating Claude Haiku 4.5 into his workflow and is preparing to dive into memory system architecture. The AI acknowledges the challenges, confirms 32K",
        "reasoning_content": "",
        "tool_calls": []
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 3154,
    "completion_tokens": 101,
    "total_tokens": 3255
  },
  "stats": {},
  "system_fingerprint": "qwen/qwen3-vl-4b"
}
2025-11-18 14:52:07 [DEBUG]
 Received request: GET to /v1/models
2025-11-18 14:52:07  [INFO]
 Returning {
  "data": [
    {
      "id": "text-embedding-nomic-embed-text-v1.5",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "qwen/qwen3-vl-30b",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "qwen/qwen3-vl-4b",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "qwen2.5-0.5b-instruct",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "qwen/qwen3-4b",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "openai/gpt-oss-120b",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "llama-3-8b-lexi-uncensored",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "google/gemma-3-1b",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "text-embedding-nomic-embed-text-v1.5-embedding",
      "object": "model",
      "owned_by": "organization_owner"
    }
  ],
  "object": "list"
}
2025-11-18 14:52:19 [DEBUG]
 Received request: POST to /v1/chat/completions with body  {
  "model": "qwen/qwen3-vl-4b",
  "messages": [
    {
      "role": "system",
      "content": "You are a conversation summarizer. Your task is to... <Truncated in logs> ...y.\n\nCurrent date and time: 2025-11-18 14:52:19 CST"
    },
    {
      "role": "user",
      "content": "Conversation to summarize:\n\nUSER: Good morning\n\nAS... <Truncated in logs> ...de a concise summary of this conversation segment."
    }
  ],
  "temperature": 0,
  "top_p": 1,
  "max_tokens": 1024,
  "stream": false
}
2025-11-18 14:52:19  [INFO]
 [qwen/qwen3-vl-4b] Running chat completion on conversation with 2 messages.
2025-11-18 14:52:19 [DEBUG]
 Sampling params:	repeat_last_n = 64, repeat_penalty = 1.000, frequency_penalty = 0.000, presence_penalty = 0.000
	dry_multiplier = 0.000, dry_base = 1.750, dry_allowed_length = 2, dry_penalty_last_n = -1
	top_k = 20, top_p = 1.000, min_p = 0.050, xtc_probability = 0.000, xtc_threshold = 0.100, typical_p = 1.000, top_n_sigma = -1.000, temp = 0.000
	mirostat = 0, mirostat_lr = 0.100, mirostat_ent = 5.000
Sampling: 
logits -> logit-bias -> penalties -> dry -> top-n-sigma -> top-k -> typical -> top-p -> min-p -> xtc -> temp-ext -> dist 
Generate: n_ctx = 16384, n_batch = 512, n_predict = 1024, n_keep = 3154
2025-11-18 14:52:19 [DEBUG]
 Cache reuse summary: 233/3154 of prompt (7.38744%), 233 prefix, 0 non-prefix
2025-11-18 14:52:19 [DEBUG]
 Total prompt tokens: 3154
Prompt tokens to decode: 2921
BeginProcessingPrompt
2025-11-18 14:52:19  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 0.0%
2025-11-18 14:52:29 [DEBUG]
 PromptProcessing: 9.55152
2025-11-18 14:52:29  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 9.6%
2025-11-18 14:52:52 [DEBUG]
 PromptProcessing: 27.0798
2025-11-18 14:52:52  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 27.1%
2025-11-18 14:53:18 [DEBUG]
 PromptProcessing: 44.608
2025-11-18 14:53:18  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 44.6%
2025-11-18 14:53:20  [INFO]
 [LM STUDIO SERVER] Client disconnected. Stopping generation... (If the model is busy processing the prompt, it will finish first.)
2025-11-18 14:53:21 [DEBUG]
 Received request: POST to /v1/chat/completions with body  {
  "model": "qwen/qwen3-vl-4b",
  "messages": [
    {
      "role": "system",
      "content": "You are a conversation summarizer. Your task is to... <Truncated in logs> ...y.\n\nCurrent date and time: 2025-11-18 14:52:19 CST"
    },
    {
      "role": "user",
      "content": "Conversation to summarize:\n\nUSER: Good morning\n\nAS... <Truncated in logs> ...de a concise summary of this conversation segment."
    }
  ],
  "temperature": 0,
  "top_p": 1,
  "max_tokens": 1024,
  "stream": false
}
2025-11-18 14:53:21  [INFO]
 [qwen/qwen3-vl-4b] Running chat completion on conversation with 2 messages.
2025-11-18 14:53:48 [DEBUG]
 PromptProcessing: 62.1363
Target model llama_perf stats:
llama_perf_sampler_print:    sampling time =       0.27 ms /  2048 runs   (    0.00 ms per token, 7699248.12 tokens per second)
llama_perf_context_print:        load time =    3103.96 ms
llama_perf_context_print: prompt eval time =       0.00 ms /     1 tokens (    0.00 ms per token,      inf tokens per second)
llama_perf_context_print:        eval time =       0.00 ms /     1 runs   (    0.00 ms per token,      inf tokens per second)
llama_perf_context_print:       total time =   88611.66 ms /     2 tokens
llama_perf_context_print:    graphs reused =          0
2025-11-18 14:53:48  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 62.1%
2025-11-18 14:53:48 [DEBUG]
 llama_memory_breakdown_print: | memory breakdown [MiB]                 | total    free    self   model   context   compute       unaccounted |
llama_memory_breakdown_print: |   - Vulkan0 (RX 7900 XT (RADV NAVI31)) | 20224 =  3955 + (2398 =  1089 +    1216 +      93) +          13869 |
llama_memory_breakdown_print: |   - Vulkan1 (RX 6800 (RADV NAVI21))    | 16128 = 13503 + (2675 =  1285 +    1088 +     301) + 17592186044365 |
llama_memory_breakdown_print: |   - Host                               |                   341 =   304 +       0 +      37                   |
2025-11-18 14:53:48  [INFO]
 [qwen/qwen3-vl-4b] Model generated tool calls:  []
2025-11-18 14:53:48  [INFO]
 [qwen/qwen3-vl-4b] Generated prediction:  {
  "id": "chatcmpl-0tllracnlqysm666cw9ij",
  "object": "chat.completion",
  "created": 1763499139,
  "model": "qwen/qwen3-vl-4b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "",
        "reasoning_content": "",
        "tool_calls": []
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 3154,
    "completion_tokens": 0,
    "total_tokens": 3154
  },
  "stats": {},
  "system_fingerprint": "qwen/qwen3-vl-4b"
}
2025-11-18 14:53:48 [DEBUG]
 Sampling params:	repeat_last_n = 64, repeat_penalty = 1.000, frequency_penalty = 0.000, presence_penalty = 0.000
	dry_multiplier = 0.000, dry_base = 1.750, dry_allowed_length = 2, dry_penalty_last_n = -1
	top_k = 20, top_p = 1.000, min_p = 0.050, xtc_probability = 0.000, xtc_threshold = 0.100, typical_p = 1.000, top_n_sigma = -1.000, temp = 0.000
	mirostat = 0, mirostat_lr = 0.100, mirostat_ent = 5.000
Sampling: 
logits -> logit-bias -> penalties -> dry -> top-n-sigma -> top-k -> typical -> top-p -> min-p -> xtc -> temp-ext -> dist 
Generate: n_ctx = 16384, n_batch = 512, n_predict = 1024, n_keep = 3154
2025-11-18 14:53:48 [DEBUG]
 Total prompt tokens: 3154
Prompt tokens to decode: 1106
BeginProcessingPrompt
2025-11-18 14:53:48  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 0.0%
2025-11-18 14:54:22 [DEBUG]
 PromptProcessing: 46.2929
2025-11-18 14:54:22  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 46.3%
2025-11-18 14:54:22  [INFO]
 [LM STUDIO SERVER] Client disconnected. Stopping generation... (If the model is busy processing the prompt, it will finish first.)
2025-11-18 14:54:25 [DEBUG]
 Received request: POST to /v1/chat/completions with body  {
  "model": "qwen/qwen3-vl-4b",
  "messages": [
    {
      "role": "system",
      "content": "You are a conversation summarizer. Your task is to... <Truncated in logs> ...y.\n\nCurrent date and time: 2025-11-18 14:52:19 CST"
    },
    {
      "role": "user",
      "content": "Conversation to summarize:\n\nUSER: Good morning\n\nAS... <Truncated in logs> ...de a concise summary of this conversation segment."
    }
  ],
  "temperature": 0,
  "top_p": 1,
  "max_tokens": 1024,
  "stream": false
}
2025-11-18 14:54:25  [INFO]
 [qwen/qwen3-vl-4b] Running chat completion on conversation with 2 messages.
2025-11-18 14:54:59 [DEBUG]
 PromptProcessing: 92.5859
Target model llama_perf stats:
llama_perf_sampler_print:    sampling time =       0.32 ms /  3072 runs   (    0.00 ms per token, 9630094.04 tokens per second)
llama_perf_context_print:        load time =    3103.96 ms
llama_perf_context_print: prompt eval time =       0.00 ms /     1 tokens (    0.00 ms per token,      inf tokens per second)
llama_perf_context_print:        eval time =       0.00 ms /     1 runs   (    0.00 ms per token,      inf tokens per second)
llama_perf_context_print:       total time =   71017.22 ms /     2 tokens
llama_perf_context_print:    graphs reused =          0
2025-11-18 14:54:59  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 92.6%
2025-11-18 14:54:59 [DEBUG]
 llama_memory_breakdown_print: | memory breakdown [MiB]                 | total    free    self   model   context   compute       unaccounted |
llama_memory_breakdown_print: |   - Vulkan0 (RX 7900 XT (RADV NAVI31)) | 20224 =  3953 + (2398 =  1089 +    1216 +      93) +          13871 |
llama_memory_breakdown_print: |   - Vulkan1 (RX 6800 (RADV NAVI21))    | 16128 = 13503 + (2675 =  1285 +    1088 +     301) + 17592186044365 |
llama_memory_breakdown_print: |   - Host                               |                   341 =   304 +       0 +      37                   |
2025-11-18 14:54:59  [INFO]
 [qwen/qwen3-vl-4b] Model generated tool calls:  []
2025-11-18 14:54:59  [INFO]
 [qwen/qwen3-vl-4b] Generated prediction:  {
  "id": "chatcmpl-qvxvawy0iyr4u7zuk38ygd",
  "object": "chat.completion",
  "created": 1763499201,
  "model": "qwen/qwen3-vl-4b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "",
        "reasoning_content": "",
        "tool_calls": []
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 3154,
    "completion_tokens": 0,
    "total_tokens": 3154
  },
  "stats": {},
  "system_fingerprint": "qwen/qwen3-vl-4b"
}
2025-11-18 14:54:59 [DEBUG]
 Sampling params:	repeat_last_n = 64, repeat_penalty = 1.000, frequency_penalty = 0.000, presence_penalty = 0.000
	dry_multiplier = 0.000, dry_base = 1.750, dry_allowed_length = 2, dry_penalty_last_n = -1
	top_k = 20, top_p = 1.000, min_p = 0.050, xtc_probability = 0.000, xtc_threshold = 0.100, typical_p = 1.000, top_n_sigma = -1.000, temp = 0.000
	mirostat = 0, mirostat_lr = 0.100, mirostat_ent = 5.000
2025-11-18 14:54:59 [DEBUG]
 Sampling: 
logits -> logit-bias -> penalties -> dry -> top-n-sigma -> top-k -> typical -> top-p -> min-p -> xtc -> temp-ext -> dist 
Generate: n_ctx = 16384, n_batch = 512, n_predict = 1024, n_keep = 3154
2025-11-18 14:54:59 [DEBUG]
 Total prompt tokens: 3154
Prompt tokens to decode: 82
BeginProcessingPrompt
2025-11-18 14:54:59  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 0.0%
2025-11-18 14:55:04 [DEBUG]
 FinishedProcessingPrompt. Progress: 100
2025-11-18 14:55:04  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 100.0%
2025-11-18 14:55:25  [INFO]
 [LM STUDIO SERVER] Client disconnected. Stopping generation... (If the model is busy processing the prompt, it will finish first.)
2025-11-18 14:55:26 [DEBUG]
 Target model llama_perf stats:
llama_perf_sampler_print:    sampling time =       4.49 ms /  3191 runs   (    0.00 ms per token, 710532.18 tokens per second)
llama_perf_context_print:        load time =    3103.96 ms
llama_perf_context_print: prompt eval time =  164611.81 ms /  2921 tokens (   56.35 ms per token,    17.74 tokens per second)
llama_perf_context_print:        eval time =   21623.96 ms /    36 runs   (  600.67 ms per token,     1.66 tokens per second)
llama_perf_context_print:       total time =   26548.52 ms /  2957 tokens
llama_perf_context_print:    graphs reused =          0
2025-11-18 14:55:26 [DEBUG]
 llama_memory_breakdown_print: | memory breakdown [MiB]                 | total    free    self   model   context   compute       unaccounted |
llama_memory_breakdown_print: |   - Vulkan0 (RX 7900 XT (RADV NAVI31)) | 20224 =  3936 + (2398 =  1089 +    1216 +      93) +          13888 |
llama_memory_breakdown_print: |   - Vulkan1 (RX 6800 (RADV NAVI21))    | 16128 = 13503 + (2675 =  1285 +    1088 +     301) + 17592186044365 |
llama_memory_breakdown_print: |   - Host                               |                   341 =   304 +       0 +      37                   |
2025-11-18 14:55:26  [INFO]
 [qwen/qwen3-vl-4b] Model generated tool calls:  []
2025-11-18 14:55:26  [INFO]
 [qwen/qwen3-vl-4b] Generated prediction:  {
  "id": "chatcmpl-6oewk4oetr48cgg116441c",
  "object": "chat.completion",
  "created": 1763499265,
  "model": "qwen/qwen3-vl-4b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The conversation centers on Nate’s efforts to improve and stabilize the AI system’s memory and context handling, particularly around preserving short-term memory tags during transitions to long-term storage. Nate expresses",
        "reasoning_content": "",
        "tool_calls": []
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 3154,
    "completion_tokens": 37,
    "total_tokens": 3191
  },
  "stats": {},
  "system_fingerprint": "qwen/qwen3-vl-4b"
}
2025-11-18 14:55:30 [DEBUG]
 Received request: POST to /v1/chat/completions with body  {
  "model": "qwen/qwen3-vl-4b",
  "messages": [
    {
      "role": "system",
      "content": "You are a conversation summarizer. Your task is to... <Truncated in logs> ...y.\n\nCurrent date and time: 2025-11-18 14:52:19 CST"
    },
    {
      "role": "user",
      "content": "Conversation to summarize:\n\nUSER: Good morning\n\nAS... <Truncated in logs> ...de a concise summary of this conversation segment."
    }
  ],
  "temperature": 0,
  "top_p": 1,
  "max_tokens": 1024,
  "stream": false
}
2025-11-18 14:55:30  [INFO]
 [qwen/qwen3-vl-4b] Running chat completion on conversation with 2 messages.
2025-11-18 14:55:30 [DEBUG]
 Sampling params:	repeat_last_n = 64, repeat_penalty = 1.000, frequency_penalty = 0.000, presence_penalty = 0.000
	dry_multiplier = 0.000, dry_base = 1.750, dry_allowed_length = 2, dry_penalty_last_n = -1
	top_k = 20, top_p = 1.000, min_p = 0.050, xtc_probability = 0.000, xtc_threshold = 0.100, typical_p = 1.000, top_n_sigma = -1.000, temp = 0.000
	mirostat = 0, mirostat_lr = 0.100, mirostat_ent = 5.000
2025-11-18 14:55:30 [DEBUG]
 Sampling: 
logits -> logit-bias -> penalties -> dry -> top-n-sigma -> top-k -> typical -> top-p -> min-p -> xtc -> temp-ext -> dist 
Generate: n_ctx = 16384, n_batch = 512, n_predict = 1024, n_keep = 3154
2025-11-18 14:55:30 [DEBUG]
 Cache reuse summary: 3154/3154 of prompt (100%), 3154 prefix, 0 non-prefix
Total prompt tokens: 3154
Prompt tokens to decode: 1
BeginProcessingPrompt
2025-11-18 14:55:30  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 0.0%
2025-11-18 14:55:30 [DEBUG]
 FinishedProcessingPrompt. Progress: 100
2025-11-18 14:55:30  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 100.0%
2025-11-18 14:56:30  [INFO]
 [LM STUDIO SERVER] Client disconnected. Stopping generation... (If the model is busy processing the prompt, it will finish first.)
2025-11-18 14:56:30 [DEBUG]
 Target model llama_perf stats:
2025-11-18 14:56:30 [DEBUG]
 llama_perf_sampler_print:    sampling time =       9.90 ms /  3255 runs   (    0.00 ms per token, 328821.09 tokens per second)
llama_perf_context_print:        load time =    3103.96 ms
llama_perf_context_print: prompt eval time =       0.00 ms /     1 tokens (    0.00 ms per token,      inf tokens per second)
llama_perf_context_print:        eval time =   60630.96 ms /   101 runs   (  600.31 ms per token,     1.67 tokens per second)
llama_perf_context_print:       total time =   60670.60 ms /   102 tokens
llama_perf_context_print:    graphs reused =          0
2025-11-18 14:56:30 [DEBUG]
 llama_memory_breakdown_print: | memory breakdown [MiB]                 | total    free    self   model   context   compute       unaccounted |
llama_memory_breakdown_print: |   - Vulkan0 (RX 7900 XT (RADV NAVI31)) | 20224 =  3930 + (2398 =  1089 +    1216 +      93) +          13894 |
llama_memory_breakdown_print: |   - Vulkan1 (RX 6800 (RADV NAVI21))    | 16128 = 13503 + (2675 =  1285 +    1088 +     301) + 17592186044365 |
llama_memory_breakdown_print: |   - Host                               |                   341 =   304 +       0 +      37                   |
2025-11-18 14:56:30  [INFO]
 [qwen/qwen3-vl-4b] Model generated tool calls:  []
2025-11-18 14:56:30  [INFO]
 [qwen/qwen3-vl-4b] Generated prediction:  {
  "id": "chatcmpl-l629txhjtkfsbpb09lpwes",
  "object": "chat.completion",
  "created": 1763499330,
  "model": "qwen/qwen3-vl-4b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The conversation centers on Nate’s efforts to improve and stabilize the AI system’s memory and context handling, particularly around preserving short-term memory tags during transitions to long-term storage. Nate expresses frustration with past system instability—especially after a 70-second power outage—and seeks to prevent data loss when promoting memories to long-term storage. He’s currently managing this with Claude, and wants to ensure seamless integration between short-term and long-term memory systems. The AI acknowledges the challenge, confirming that 32K",
        "reasoning_content": "",
        "tool_calls": []
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 3154,
    "completion_tokens": 101,
    "total_tokens": 3255
  },
  "stats": {},
  "system_fingerprint": "qwen/qwen3-vl-4b"
}
2025-11-18 14:56:39 [DEBUG]
 Received request: POST to /v1/chat/completions with body  {
  "model": "qwen/qwen3-vl-4b",
  "messages": [
    {
      "role": "system",
      "content": "You are a conversation summarizer. Your task is to... <Truncated in logs> ...y.\n\nCurrent date and time: 2025-11-18 14:52:19 CST"
    },
    {
      "role": "user",
      "content": "Conversation to summarize:\n\nUSER: Good morning\n\nAS... <Truncated in logs> ...de a concise summary of this conversation segment."
    }
  ],
  "temperature": 0,
  "top_p": 1,
  "max_tokens": 1024,
  "stream": false
}
2025-11-18 14:56:39  [INFO]
 [qwen/qwen3-vl-4b] Running chat completion on conversation with 2 messages.
2025-11-18 14:56:39 [DEBUG]
 Sampling params:	repeat_last_n = 64, repeat_penalty = 1.000, frequency_penalty = 0.000, presence_penalty = 0.000
	dry_multiplier = 0.000, dry_base = 1.750, dry_allowed_length = 2, dry_penalty_last_n = -1
	top_k = 20, top_p = 1.000, min_p = 0.050, xtc_probability = 0.000, xtc_threshold = 0.100, typical_p = 1.000, top_n_sigma = -1.000, temp = 0.000
	mirostat = 0, mirostat_lr = 0.100, mirostat_ent = 5.000
2025-11-18 14:56:39 [DEBUG]
 Sampling: 
logits -> logit-bias -> penalties -> dry -> top-n-sigma -> top-k -> typical -> top-p -> min-p -> xtc -> temp-ext -> dist 
Generate: n_ctx = 16384, n_batch = 512, n_predict = 1024, n_keep = 3154
2025-11-18 14:56:39 [DEBUG]
 Cache reuse summary: 3154/3154 of prompt (100%), 3154 prefix, 0 non-prefix
Total prompt tokens: 3154
Prompt tokens to decode: 1
BeginProcessingPrompt
2025-11-18 14:56:39  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 0.0%
2025-11-18 14:56:39 [DEBUG]
 FinishedProcessingPrompt. Progress: 100
2025-11-18 14:56:39  [INFO]
 [qwen/qwen3-vl-4b] Prompt processing progress: 100.0%
2025-11-18 14:57:18  [INFO]
 [LM STUDIO SERVER] Client disconnected. Stopping generation... (If the model is busy processing the prompt, it will finish first.)
2025-11-18 14:57:18 [DEBUG]
 Target model llama_perf stats:
llama_perf_sampler_print:    sampling time =       6.48 ms /  3219 runs   (    0.00 ms per token, 496835.93 tokens per second)
llama_perf_context_print:        load time =    3103.96 ms
llama_perf_context_print: prompt eval time =       0.00 ms /     1 tokens (    0.00 ms per token,      inf tokens per second)
llama_perf_context_print:        eval time =   39034.33 ms /    65 runs   (  600.53 ms per token,     1.67 tokens per second)
llama_perf_context_print:       total time =   39064.89 ms /    66 tokens
llama_perf_context_print:    graphs reused =          0
2025-11-18 14:57:18 [DEBUG]
 llama_memory_breakdown_print: | memory breakdown [MiB]                 | total    free    self   model   context   compute       unaccounted |
llama_memory_breakdown_print: |   - Vulkan0 (RX 7900 XT (RADV NAVI31)) | 20224 =  3905 + (2398 =  1089 +    1216 +      93) +          13919 |
llama_memory_breakdown_print: |   - Vulkan1 (RX 6800 (RADV NAVI21))    | 16128 = 13503 + (2675 =  1285 +    1088 +     301) + 17592186044365 |
llama_memory_breakdown_print: |   - Host                               |                   341 =   304 +       0 +      37                   |
2025-11-18 14:57:18  [INFO]
 [qwen/qwen3-vl-4b] Model generated tool calls:  []
2025-11-18 14:57:18  [INFO]
 [qwen/qwen3-vl-4b] Generated prediction:  {
  "id": "chatcmpl-cwmik51mljrjjs35ln5ec",
  "object": "chat.completion",
  "created": 1763499399,
  "model": "qwen/qwen3-vl-4b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The conversation centers on Nate’s efforts to improve and stabilize the AI system’s memory and context handling, particularly around preserving short-term memory tags during transitions to long-term storage. Nate expresses frustration with past system instability—especially after a 70-second power outage—and seeks to prevent data loss when promoting memories to long-term storage",
        "reasoning_content": "",
        "tool_calls": []
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 3154,
    "completion_tokens": 65,
    "total_tokens": 3219
  },
  "stats": {},
  "system_fingerprint": "qwen/qwen3-vl-4b"
}
2025-11-18 14:58:17 [DEBUG]
 Received request: GET to /v1/models
2025-11-18 14:58:17  [INFO]
 Returning {
  "data": [
    {
      "id": "text-embedding-nomic-embed-text-v1.5",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "qwen/qwen3-vl-30b",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "qwen/qwen3-vl-4b",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "qwen2.5-0.5b-instruct",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "qwen/qwen3-4b",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "openai/gpt-oss-120b",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "llama-3-8b-lexi-uncensored",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "google/gemma-3-1b",
      "object": "model",
      "owned_by": "organization_owner"
    },
    {
      "id": "text-embedding-nomic-embed-text-v1.5-embedding",
      "object": "model",
      "owned_by": "organization_owner"
    }
  ],
  "object": "list"
}