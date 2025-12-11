# OpenWebUI function development: user and model identification guide

Building user+model-specific memory filters in OpenWebUI requires accessing two key context variables: **`__user__`** (a dictionary containing user metadata) and **`body.get("model")`** (the model identifier). OpenWebUI's plugin system uses Python dependency injection to pass these context variables to custom functions when included in their signatures—simply add `__user__: Optional[dict] = None` and `__model__: Optional[dict] = None` as parameters to your `inlet()` or `outlet()` methods, and OpenWebUI automatically populates them.

## The `__user__` dictionary provides complete user identification

The primary method for accessing user information is through the `__user__` parameter, which OpenWebUI injects as a **dictionary** (not an object) with the following structure:

```python
{
    "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # Unique UUID
    "email": "user@example.com",
    "name": "Display Name",
    "role": "user",  # or "admin"
    "valves": UserValves  # User-specific settings instance
}
```

Access user identification in your filter with `user_id = __user__.get("id")`. For safe access when `__user__` might be None, use the pattern `user_id = __user__.get("id") if __user__ else None`. The **role** field enables permission-based logic—check `__user__.get("role") == "admin"` to implement admin-only features.

## Model identification comes from multiple sources

The current model can be accessed through several channels:

| Source | Access Pattern | Contains |
|--------|---------------|----------|
| `body` dict | `body.get("model")` | Model ID string |
| `__model__` param | `__model__.get("id")` | Full model config dict |
| `metadata` | `body.get("metadata", {}).get("model", {})` | Model metadata including name |

For user+model isolation, extract the model ID directly from the body: `model_id = body.get("model")`. The `__model__` parameter provides richer information including `name`, `owned_by` ("ollama", "openai"), and nested `info` containing base model configuration.

## Complete filter API structure with all available context variables

OpenWebUI injects these special "dunder" parameters automatically when included in function signatures:

```python
from pydantic import BaseModel, Field
from typing import Optional, Callable, Any, Awaitable

class Filter:
    class Valves(BaseModel):
        enabled: bool = Field(default=True, description="Enable filter")
        
    class UserValves(BaseModel):
        show_status: bool = Field(default=True, description="Show processing status")
    
    def __init__(self):
        self.valves = self.Valves()

    async def inlet(
        self,
        body: dict,                                              # Chat completion request
        __user__: Optional[dict] = None,                        # User info dictionary
        __model__: Optional[dict] = None,                       # Model configuration
        __metadata__: Optional[dict] = None,                    # Chat metadata (chat_id, session_id)
        __event_emitter__: Callable[[dict], Awaitable[None]] = None,  # UI events
        __request__: Any = None,                                # FastAPI Request (v0.5+)
    ) -> dict:
        return body

    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __model__: Optional[dict] = None,
    ) -> dict:
        return body
```

The **`__metadata__`** dictionary provides additional context including `chat_id`, `message_id`, `session_id`, and template variables like `{{USER_NAME}}` and `{{CURRENT_DATETIME}}`.

## Implementing user+model memory isolation

For your memory filter requiring per-user+model isolation, combine identifiers into a unique key:

```python
from open_webui.models.memories import Memories
from open_webui.routers.memories import add_memory, query_memory, AddMemoryForm, QueryMemoryForm

class Filter:
    class Valves(BaseModel):
        model_specific: bool = Field(default=True, description="Isolate memories per model")
        
    def __init__(self):
        self.valves = self.Valves()
        
    def get_memory_key(self, user_id: str, model_id: str = None) -> str:
        """Generate unique key for user+model combination"""
        if self.valves.model_specific and model_id:
            return f"{user_id}:{model_id}"
        return user_id

    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Callable[[dict], Awaitable[None]] = None,
    ) -> dict:
        if not __user__:
            return body
            
        user_id = __user__.get("id")
        model_id = body.get("model")
        memory_key = self.get_memory_key(user_id, model_id)
        
        # Retrieve user-specific memories from OpenWebUI's memory system
        user_memories = Memories.get_memories_by_user_id(user_id)
        
        # Inject relevant memories into system context
        if user_memories:
            memory_text = "\n".join([m.content for m in user_memories])
            system_msg = {"role": "system", "content": f"User memories:\n{memory_text}"}
            body.setdefault("messages", []).insert(0, system_msg)
            
        return body
```

The OpenWebUI memory API accessed via `open_webui.models.memories.Memories` provides these key methods: **`get_memories_by_user_id(user_id)`** for retrieval, while `open_webui.routers.memories` offers `add_memory()`, `query_memory()`, `update_memory_by_id()`, and `delete_memory_by_id()` for full CRUD operations.

## Memory operations require the Request object in v0.5+

For programmatic memory operations in OpenWebUI 0.5+, you must construct a FastAPI Request:

```python
from fastapi import Request
from open_webui.main import app as webui_app
from open_webui.models.users import Users
from open_webui.routers.memories import query_memory, QueryMemoryForm

async def get_related_memories(self, query: str, __user__: dict) -> list:
    # Get full user model from database
    user = Users.get_user_by_id(__user__["id"])
    
    # Create request object
    request = Request(scope={"type": "http", "app": webui_app})
    
    # Query memories semantically
    results = await query_memory(
        request=request,
        form_data=QueryMemoryForm(content=query, k=5),
        user=user,
    )
    return results
```

## UserValves enable per-user configuration

**UserValves** allow users to customize filter behavior independently of admin-set **Valves**:

```python
class Filter:
    class Valves(BaseModel):  # Admin-controlled
        max_memories: int = Field(default=10)
        allow_user_override: bool = Field(default=True)
        
    class UserValves(BaseModel):  # User-controlled
        enabled: bool = Field(default=True)
        max_memories: int = Field(default=5)

    async def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        # Access user-specific valves
        user_valves = __user__.get("valves") if __user__ else None
        
        # Important: access valve values correctly
        if user_valves:
            # Use attribute access or dict() conversion
            user_max = user_valves.max_memories  # Correct
            # OR: user_max = dict(user_valves)["max_memories"]
```

**Critical note**: When accessing UserValves, use attribute access (`user_valves.field_name`) or convert with `dict(user_valves)["field_name"]`—direct dictionary access like `user_valves["field_name"]` returns default values rather than actual user settings.

## Complete implementation template for user+model memory isolation

```python
"""
title: User+Model Memory Filter
description: Isolates memories per user and model combination
version: 1.0.0
required_open_webui_version: 0.5.0
"""
from pydantic import BaseModel, Field
from typing import Optional, Callable, Any, Awaitable
from open_webui.models.memories import Memories

class Filter:
    class Valves(BaseModel):
        enabled: bool = Field(default=True, description="Enable memory injection")
        model_specific: bool = Field(default=True, description="Separate memories per model")
        prepend_text: str = Field(default="Relevant user memories:", description="Text before memories")
        
    class UserValves(BaseModel):
        enabled: bool = Field(default=True, description="Enable for this user")
        
    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True  # Creates UI toggle (v0.6.10+)
        
    def get_isolation_key(self, user_id: str, model_id: str) -> str:
        if self.valves.model_specific:
            return f"{user_id}:{model_id}"
        return user_id

    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __model__: Optional[dict] = None,
        __event_emitter__: Callable[[dict], Awaitable[None]] = None,
    ) -> dict:
        if not self.valves.enabled or not __user__:
            return body
            
        # Check user-specific enable setting
        user_valves = __user__.get("valves")
        if user_valves and not user_valves.enabled:
            return body
            
        # Extract identifiers
        user_id = __user__.get("id")
        user_name = __user__.get("name", "Unknown")
        model_id = body.get("model")
        isolation_key = self.get_isolation_key(user_id, model_id)
        
        # Emit status
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": f"Loading memories for {user_name}...", "done": False}
            })
        
        # Retrieve user memories
        user_memories = Memories.get_memories_by_user_id(user_id)
        
        # Filter or tag memories for model-specific handling if needed
        if self.valves.model_specific and user_memories:
            # Custom logic: filter memories tagged for this model
            # Or store model_id in memory metadata for filtering
            pass
        
        # Inject into context
        if user_memories:
            memory_content = "\n".join([f"- {m.content}" for m in user_memories])
            injection = f"{self.valves.prepend_text}\n{memory_content}"
            
            messages = body.get("messages", [])
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] += f"\n\n{injection}"
            else:
                body["messages"] = [{"role": "system", "content": injection}] + messages
        
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": f"Loaded {len(user_memories or [])} memories", "done": True}
            })
            
        return body

    async def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        # Optional: Extract and store new memories from assistant response
        return body
```

## Conclusion

Building user+model memory isolation in OpenWebUI centers on three techniques: accessing `__user__.get("id")` for user identification, extracting `body.get("model")` for model identification, and combining these into unique isolation keys. The OpenWebUI memory system through `Memories.get_memories_by_user_id()` already provides per-user isolation—model-specific isolation requires implementing custom tagging or key-based filtering logic within your filter. For v0.5+, remember to include `__request__: Request` when calling internal OpenWebUI functions like `query_memory()` that require the FastAPI request context.