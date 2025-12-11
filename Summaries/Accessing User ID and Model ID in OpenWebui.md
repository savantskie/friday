Accessing User ID and Model ID in OpenWebUI (v0.6.34)

In OpenWebUI’s multi-user environment (with authentication enabled), each chat request carries context about which user is making the request and which model is being used. To implement a memory filter scoped per user and per model, you need to retrieve both identifiers in the backend. Below we explain how user IDs and model IDs are exposed in OpenWebUI and how to combine them for user+model-specific memory.

User ID: Retrieving the Logged-In User’s Identifier

OpenWebUI assigns each user a unique ID (UUID) stored in the database and used in associations (e.g. each chat session row has a user_id owner field
orionrobots.co.uk
docs.openwebui.com
). This user ID is not directly included in the frontend’s JSON payload for each request; instead, it’s attached server-side via the authentication/session context. You can access it in two primary ways:

Within plugin functions (Filters, Tools, Actions): OpenWebUI injects a special __user__ dictionary into your function if you include it as a parameter. This dict contains the current user’s info (id, name, email, role, etc). For example, in a custom filter you could do:

async def inlet(self, body: dict, __user__: dict = None, __model__: dict = None):
    user_id = __user__["id"]  # the active user's UUID
    logger.info(f"Current user: {user_id}")
    ...


In the code above, __user__["id"] yields the user’s unique ID string
openwebui.com
. This approach is used in OpenWebUI’s own plugins; for instance, the AutoTool filter grabs the user ID via user_id = __user__["id"]
openwebui.com
, and the Memory tool uses user_id = __user__.get("id") to look up the user’s memories
openwebui.com
. The __user__ dict also includes user-specific settings under __user__["valves"] (for user-enabled/disabled features).

Within backend API routes: OpenWebUI’s FastAPI backend uses dependency injection to provide a user object (usually an instance of UserModel) to route handlers. For example, internal routes often use user=Depends(get_verified_user) or similar. In such a context, you can get the ID via user.id. OpenWebUI then uses this ID for various purposes, like forwarding user info to external APIs. For example, when forwarding requests to OpenAI, the code includes a header X-OpenWebUI-User-Id: user.id
yanyikele.com
. This confirms that user.id (a UUID string) is accessible on the server side once the user is authenticated. If you are writing a custom router or function, you can similarly call request.user (or use the injected user) to obtain user.id.

Note: There is no need for the frontend to send user_id in the request body – OpenWebUI knows the user from the session/token. Likewise, you typically do not need to manually read X-OpenWebUI-User-Id headers internally; those headers are used when forwarding requests to external services. (If you enable the environment variable ENABLE_FORWARD_USER_INFO_HEADERS=True, OpenWebUI will automatically include headers like X-OpenWebUI-User-Id, X-OpenWebUI-User-Name, etc., in outgoing API calls
docs.openwebui.com
yanyikele.com
. But for internal logic, you should rely on the provided context rather than parsing these headers.)

Model ID: Identifying the Current Model in Use

OpenWebUI allows users to select different models (including custom “pipe” models or local LLMs). The model identifier (often a model name or ID string) is included with each inference request. Here’s how to access it:

From the request payload (body): Each chat/completion request JSON contains a "model" field indicating which model is being used. You can extract it directly from the body dictionary. For example:

model_id = body["model"]  # e.g. "llama2-13b-chat" or "gpt-4"


This will give you the model’s ID or name as chosen by the user
docs.openwebui.com
. In OpenWebUI’s plugin examples, you can see this in use: a custom pipe might do model = body.get("model", "") to decide behavior based on the model selected
docs.openwebui.com
.

Via the __model__ context (in plugin functions): Similar to __user__, OpenWebUI can inject a __model__ dictionary if you include it as a parameter. This __model__ dict provides information about the model that triggered the request. For instance, in a filter you could define async def inlet(self, body, __user__=None, __model__=None): .... The __model__ object typically includes the model’s id (same as body["model"]), its display name, and metadata. For example, a filter might use __model__["id"] to get the model’s key. In practice, many community filters simply use the body["model"] since it’s convenient, but both are available.

What exactly is “model_id”? In OpenWebUI’s database, models are listed in the model table with an id (primary key) and a name
docs.openwebui.com
. Often the model id is a slug or unique name for the model (for built-in providers it could be a slug like gpt-3.5-turbo, or for custom pipes it might include a prefix). The body["model"] will contain this identifier. If you created a custom manifold pipe that provides multiple models, OpenWebUI might prefix the model ID with the pipe name (e.g. "myPipe.modelA"), so be aware you might need to parse it (as shown in some plugin docs where they strip the prefix before sending to an API
docs.openwebui.com
). But for memory grouping, you can use the full identifier string as is.

Linking User ID and Model ID for Memory Isolation

To implement short-term memory scoped per user and per model, you will use both the above pieces of information as a composite key for storing/retrieving memory. In practice:

Default behavior: By default, OpenWebUI’s memory features are at least user-specific. The built-in Memories database (the “memory vault”) has a user_id column to tie each memory to its owner
docs.openwebui.com
. This means memories are already isolated per user account. For example, the Memories.get_memories_by_user_id(user_id) call returns all stored memory entries for that user
openwebui.com
. However, there is no separate field for model in that table (it only has an id, user_id, content, timestamps, etc.
docs.openwebui.com
), so by default a user’s memories apply to all models for that user.

Isolating by model: To segregate memory further by model, you need to incorporate the model_id in your storage/retrieval logic. There are a couple of ways to do this:

Composite Key or Tag: Use a combination of user ID and model ID as a key when storing memory. For example, you might construct a key string like "${user_id}_${model_id}" and use that to index a cache or an external store for short-term memory. Then, when retrieving, use the same composite key to get the relevant memory. This could be done in code directly. (If modifying the built-in Memories table isn’t feasible, you might maintain a separate in-memory dict or a new table keyed by user+model.)

Utilize “group” or context fields: OpenWebUI’s memory plugins sometimes allow grouping by user or other attributes. For instance, the Graphiti Memory filter uses a group_id_format setting to group memory by user – by default it’s {user_id} (each user has an isolated graph)
openwebui.com
. They even suggest patterns like '{user_id}_chat' or 'user_{user_id}' as examples
openwebui.com
. In your case, you could extend this concept to include the model. Although OpenWebUI doesn’t directly provide a {model_id} placeholder in that setting, you can programmatically create a group or key that includes both. For example, if you have the strings uid = __user__["id"] and mid = body["model"], you could form group_key = f"{uid}_{mid}" and use that to segregate memory. The idea is to treat memories of different models as separate buckets per user.

Hooking into the chat/session context: Each chat session in OpenWebUI doesn’t inherently lock to one model (the user can switch models mid-conversation, unless you enforce otherwise), and the messages don’t explicitly carry model info on each turn. The request to generate a reply does carry the model. So, if implementing a memory filter function, a good approach is to capture the model at query time (from the body or __model__) and combine it with the user ID to decide where to fetch/store memories. This ensures that when the user switches models, they get a fresh (or different) memory context. You might, for instance, maintain a dictionary like memory_store[(user_id, model_id)] = [...conversation snippets...] for short-term memory, or include the model in the key when querying a database.

Example – using combined key: Pseudocode for an inlet filter could be:

async def inlet(self, body: dict, __user__: dict = None, __model__: dict = None, ...):
    user_id = __user__["id"]
    model_id = body["model"]    # or __model__["id"]
    key = f"{user_id}_{model_id}"
    # Retrieve short-term memory for this user+model
    context = my_memory_cache.get(key, "")
    if context:
        # Inject the memory context into the conversation (e.g., as system prompt)
        body["messages"].insert(0, {"role": "system", "content": context})
    return body


And in the outlet (after the model responds), you would update my_memory_cache[key] with new info from the conversation. This way, each user & model combination indexes its own memory.

Remember to handle cases appropriately (e.g. a missing __user__ or no stored memory for that key). Also, if you use persistent storage, you may consider extending the memory table or using the meta field in the chat or memory table to tag the model. But a simpler approach is often sufficient: using an in-memory store or an external DB keyed by the composite.

Summary of Key Variables/Structures

__user__ (dict): Available in plugin function context – contains user info. Use __user__["id"] to get the user’s UUID
openwebui.com
. Also available: __user__["email"], __user__["name"], __user__["role"], etc. (No need for body["user_id"] – that’s not provided; use this context or the user object as below.)

user object in FastAPI routes: When writing or modifying backend routes, use the injected user object. For example, user.id gives the ID
yanyikele.com
, and can be used to filter queries or log the user. This is how OpenWebUI attaches user info for internal usage and external API calls.

body["model"] (str): The request JSON field specifying the model to use. This string is the model’s identifier (could be a model name or an internal ID)
docs.openwebui.com
. It corresponds to the model selected in the UI or API call. In a multi-model setup, always use this to know which model is currently handling the request.

__model__ (dict): An optional context dict with model details (if you include it in function signature). You can get __model__["id"] (same as body["model"] value) and possibly other metadata about the model (like __model__["name"] or __model__["meta"]). This is useful in advanced scenarios, but often the model ID string alone suffices for keying memory.

Headers like X-OpenWebUI-User-Id: These are only sent when OpenWebUI forwards requests to external model backends (like OpenAI or Ollama) and if forwarding is enabled
docs.openwebui.com
. They include the same info (user’s ID, email, etc.) for auditing or multi-tenant usage on those services. You generally do not use these headers inside OpenWebUI’s own code – instead, use the contexts above. (If you see them in logs or want to confirm, they will mirror user.id, user.email, etc., as shown in the code snippet where headers["X-OpenWebUI-User-Id"] = user.id
yanyikele.com
.)

By accessing user_id and model_id through the mechanisms above and using them together, you can store and retrieve chat memory in a way that is isolated for each user and each model. For example, User A’s conversation with Model X will have a different memory context than User A with Model Y, or User B with Model X. This ensures that short-term memory does not leak between different users or models.