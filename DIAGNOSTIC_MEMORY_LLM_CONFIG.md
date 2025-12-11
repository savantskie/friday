# Memory LLM Configuration Diagnostic

## PROBLEM IDENTIFIED

The adaptive_memory plugin is receiving responses in **OpenAI chat completion format** but the code expects **Ollama format**.

**Log Evidence:**
```
{"timestamp": "2025-12-10 23:30:38,528", "level": "ERROR", "logger": "openwebui.plugins.adaptive_memory", 
"message": "Could not extract content from ollama response format: {'id': 'chatcmpl-u986...', 'object': 'chat.completion', 'created': 1765409437, 'model': 'friday/helpermodel',...}"
```

**Root Cause:** The response format is OpenAI (has `'object': 'chat.completion'`), but the code is trying to extract it as Ollama format (looking for `data.get("message").get("content")`).

## CURRENT CODE STATE

**File:** `/media/nate/Friday/Friday/friday_memory_short_term.py`

**Lines 1048-1058 (Valve Defaults):**
```python
llm_provider_type: Literal["ollama", "openai_compatible"] = Field(
    default="ollama",
    description="Type of LLM provider ('ollama' or 'openai_compatible')",
)
llm_model_name: str = Field(
    default="llama3:latest",
    description="Name of the LLM model to use (e.g., 'llama3:latest', 'gpt-4o')",
)
llm_api_endpoint_url: str = Field(
    default="http://172.17.0.1:11434/api/chat",
    description="API endpoint URL for the LLM provider...",
)
```

**Lines 6940-6970 (Response Parsing in query_llm_with_retry):**
```python
if provider_type == "openai_compatible":
    # ... handles OpenAI format correctly
elif provider_type == "ollama":
    if data.get("message") and data["message"].get("content"):
        content = data["message"]["content"]
        logger.info(f"Retrieved content from Ollama response (length: {len(content)})")
```

## THE DISCREPANCY

| Config Item | Valve Default | Actual in Use |
|------------|--------------|--------------|
| Provider Type | `"ollama"` | Should be `"openai_compatible"` |
| Endpoint URL | `http://172.17.0.1:11434/api/chat` (Ollama) | Actually `http://172.17.0.1:1234/v1/chat/completions` (LM Studio) |
| Model Name | `llama3:latest` | Actually `friday/helpermodel` (LM Studio model) |
| Response Format | Expects Ollama format | Getting OpenAI format |

## FIX REQUIRED

In **OpenWebUI UI** → Adaptive Memory v3 plugin settings, update these valves:

1. **llm_provider_type**: Change from `"ollama"` to `"openai_compatible"`
2. **llm_api_endpoint_url**: Change to `http://172.17.0.1:1234/v1/chat/completions`
3. **llm_model_name**: Set to `friday/helpermodel` (or whatever your LM Studio memory model is)
4. **llm_api_key**: Leave empty (LM Studio doesn't require API key on localhost)

## VERIFICATION STEPS

After updating the valves:
1. Restart the adaptive_memory plugin or reload OpenWebUI
2. Send a test message that should trigger memory extraction
3. Check the logs for: `"LLM Query: Provider=openai_compatible, Model=friday/helpermodel, URL=http://172.17.0.1:1234/v1/chat/completions"`
4. Verify response format matches: `"Retrieved content from chat completions response"`

## WHY THIS HAPPENED

The default valve settings assume **Ollama**, but you're using **LM Studio** for the memory LLM. Someone/something overrode the valves in OpenWebUI's UI, but the code's provider detection wasn't catching the mismatch. The response format validation happens AFTER the provider type is determined, causing a format extraction error.
