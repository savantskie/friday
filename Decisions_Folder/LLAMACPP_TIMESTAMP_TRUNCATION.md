# Decision: Timestamp-Aware Context Truncation in llama.cpp Router

**Date:** July 23, 2026
**Status:** Implemented

## Problem

In router mode, when OpenWebUI sends a chat with accumulated conversation history exceeding `n_ctx`, llama.cpp's server returns a 400 error instead of intelligently truncating old messages. The `--keep` flag only helps during KV cache shifting mid-generation, not for the initial prompt.

## Solution

Two-layer approach:

### Layer 1: llama.cpp Router (proxy_request)
Smart message-level truncation in `server_models::proxy_request()` that:
- Reads `ctx_size` and `n_keep` from the model's preset
- Calculates budget: `(ctx_size - n_keep) * 0.8`
- Estimates tokens per message: `content.length() / 4.0`
- Always preserves all `system` role messages
- Drops oldest non-system messages from the front until budget fits
- Uses per-message `timestamp` field if present; falls back to array position (chronological)

### Layer 2: OpenWebUI Fork (middleware.py)
Timestamps are now included in the outgoing LLM payload via the `load_messages_from_db` field whitelist.

## Files Changed

- `/media/nate/Games/Openwebuifork/backend/open_webui/utils/middleware.py` — Added `'timestamp'` to field whitelist
- `/media/nate/Friday/llama.cpp/common/arg.cpp` — Added `.set_env("LLAMA_ARG_KEEP")` to `--keep` option
- `/media/nate/Friday/llama.cpp/tools/server/server-models.cpp` — Truncation logic in `proxy_request`, `/tokenize` handler in `init_routes`
- `/media/nate/Friday/llama.cpp/tools/server/server-models.h` — Added `post_tokenize` handler field
- `/media/nate/Friday/llama.cpp/tools/server/server.cpp` — Route registration for `post_tokenize`

## Why Not Client-Side Only

The existing "Chat Context Clipper" OpenWebUI filter clips by message count, not token count. The llama.cpp-side solution is token-aware, timestamp-aware, and doesn't require any OpenWebUI configuration changes (aside from enabling the clipper or relying on the router's built-in truncation).