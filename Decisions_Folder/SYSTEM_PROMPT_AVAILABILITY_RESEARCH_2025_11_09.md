# System Prompt Availability Research
**Date:** November 9, 2025  
**Question:** Can OpenWebUI's model card system prompt be extracted programmatically, or do we need separate storage?  
**Answer:** YES - System prompt is available through OpenWebUI's Models API

---

## Good News

OpenWebUI **does provide the system prompt from model cards** and it's accessible in your plugin code. You can grab it directly without needing separate storage.

---

## How to Access It

### 1. **The Data Structure**

In OpenWebUI, when you create a model card, the system prompt is stored in:

```python
model.params.system
```

This is from the OpenWebUI Models database structure:
```python
class ModelParams(BaseModel):
    # ... other params ...
    system: str  # <-- YOUR SYSTEM PROMPT IS HERE
```

### 2. **How to Retrieve It in Your Plugin**

You already have access to `Models` in your code. Here's how to use it:

```python
from open_webui.models.models import Models  # Already imported in your code

# In your inlet or anywhere in your plugin:
model_id = body.get("model")  # Get the model ID being used
model_info = Models.get_model_by_id(model_id)

if model_info:
    system_prompt = model_info.params.get("system", None)  # Extract system prompt
    logger.info(f"System prompt retrieved: {system_prompt[:100]}...")
```

### 3. **Full Structure You Have Access To**

```python
model_info = Models.get_model_by_id(model_id)

# Available fields:
model_info.id                    # Model ID
model_info.name                  # Model name
model_info.params                # Contains: system prompt + other params
model_info.params.system         # YOUR SYSTEM PROMPT (if set in model card)
model_info.meta                  # Metadata: description, profile_image_url, etc.
model_info.meta.description      # Model description
model_info.meta.profile_image_url # Model icon
```

---

## Where It's Stored

OpenWebUI stores this in the database:

**Table:** `model`  
**Column:** `params` (JSON field)  
**Structure:**
```json
{
  "system": "You are Friday, an AI assistant. You help with memory...",
  // other params
}
```

---

## How to Use It in Your Inlet for Summarization

When you hit the conversation summarization threshold, inject the system prompt:

```python
async def inlet(self, body, __event_emitter__, __user__):
    # ... existing code ...
    
    model_id = body.get("model")
    model_info = Models.get_model_by_id(model_id)
    
    # --- SUMMARIZATION GATE (when threshold hit) ---
    if self._should_summarize_now(user_id, body):
        # Generate summary
        summary = await self._generate_conversation_summary(body, user_id)
        
        # Store in cache
        self._conversation_summaries[f"{user_id}_{conversation_id}"] = summary
        
        # Get system prompt from model card
        system_prompt = None
        if model_info and model_info.params:
            system_prompt = model_info.params.get("system", None)
        
        # Inject all together: summary + memories + system prompt
        self._inject_summary_and_system_context(body, summary, system_prompt, user_id)
    
    # ... rest of inlet ...
```

---

## Why This is Perfect for You

1. ✅ **No separate storage needed** - It's already in the model card
2. ✅ **Automatic updates** - When you change the model card, Friday automatically uses the new prompt
3. ✅ **Per-model customization** - Each model can have its own system prompt
4. ✅ **Integrated with OpenWebUI** - No extra configuration needed

---

## Important Notes

### When System Prompt is NOT Set

If the user hasn't defined a system prompt in the model card:
```python
system_prompt = model_info.params.get("system", None)
if system_prompt is None:
    logger.debug("No system prompt defined in model card, skipping injection")
```

### When Model Info is Not Available

Very rare, but just in case:
```python
model_info = Models.get_model_by_id(model_id)
if not model_info:
    logger.warning(f"Model {model_id} not found in database")
    # Continue without system prompt
```

---

## Implementation Strategy

For your summarization feature:

**When threshold is hit:**
1. Generate conversation summary (you have this)
2. Retrieve system prompt from model card (use code above)
3. Get relevant memories (you have this)
4. Inject ALL THREE into the system context:
   - System prompt (from model card)
   - Conversation summary (your cache)
   - Relevant memories (your memory system)
5. Model receives everything it needs to respond properly

---

## Conclusion

**You're good to go.** You can grab the system prompt directly from the model card via `Models.get_model_by_id()`. No separate storage needed.

OpenWebUI designed it this way intentionally - model parameters (including system prompt) are stored WITH the model metadata, not separately.
