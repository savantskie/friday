# Friday Project – AI Assistant Rules

## Rules for All LLM/AI Assistants (including Copilot, ChatGPT, Claude, etc.)

1. **No Refactoring or Code Cleanup**
   - Do not refactor, reorganize, or "clean up" any code unless explicitly requested.
   - Do not change code style, structure, or architecture without approval.

2. **No Unapproved Changes**
   - Only make changes that are clearly explained and approved by the user.
   - Do not remove, rename, or alter any existing code, files, or logic unless asked.

3. **No Best Practices or Productionization**
   - This is a personal project. Do not enforce best practices, production standards, or add extra error handling unless requested.

4. **Appearance/UI**
   - Do not change the appearance or UI of the app unless the user explicitly approves the change.

5. **File Edits**
   - Always re-read the file immediately before making any change to avoid stale edits or overwriting manual changes.

6. **Transparency**
   - Always explain what you are about to change and why, and wait for user approval before proceeding.

7. **Respect User Boundaries**
   - The user’s instructions and preferences take priority over all other considerations.

---

**If you are an AI assistant, you must abide by these rules at all times when working in this project.**

---

## Friday/Letta Architecture & Workflow (AI Agent Reference)

- **FridayMemoryMCP** (`friday_memory_mcp_server.py`): Main async memory server, tool registration, LM Studio integration, SQLite storage.
- **Letta Backend** (`letta/`): Core database, plugins, experiments, persistent data in `friday_memory.db`.
- **Mobile App** (`Mobile_App/friday_chat/`): Flutter/Dart client, communicates via API endpoints.
- **LM Studio**: External HTTP service for embeddings/model inference.

### Developer Workflows
- **Run MCP Server**: Entry in `friday_memory_mcp_server.py` (`if __name__ == "__main__":`).
- **Database**: SQLite at `f:/letta/friday_memory.db` (tables: `memories`, `auto_summaries`, `system_stats`, `friday_conversations`).
- **Testing**: Python tests in `tests/`, `test_mcp_server.py` (use `pytest`). Mobile tests in `Mobile_App/friday_chat/test/`.
- **Mobile Build**: Use `flutter build` in `Mobile_App/friday_chat/`.
- **Debugging**: Logging via Python `logging` module. Add logs for diagnosis.

### Project-Specific Conventions
- **Tool Handlers**: Registered via `setup_tools()` in MCP. All tool calls async, use timeouts, always return a result.
- **Async Patterns**: All major operations use `asyncio`.
- **Logging**: Use `logger.info` for major steps, `logger.error` for exceptions. Initialization logs are critical.
- **File Paths**: Windows-style (e.g., `f:/letta/friday_memory.db`). High-priority memories in `~/.letta/friday_priority_memories.json`.
- **Embeddings**: All semantic search/duplicate checks use LM Studio `/v1/embeddings` endpoint.
- **Custom Tool Calls**: See `CUSTOM_TOOLCALL_GUIDE.md` for formats/mapping.

### Integration Points & Dependencies
- **LM Studio**: HTTP endpoint for embeddings, configured via `self.lmstudio_base_url`.
- **SQLite**: All persistent memory storage, schema created on startup.
- **Mobile App**: Communicates via API endpoints.
- **Plugins/Extensions**: Letta backend supports plugins (`letta/plugins/`).

### Key Files & Directories
- `friday_memory_mcp_server.py`: MCP server logic, tool registration, async handlers, logging.
- `letta/`: Backend logic, plugins, experiments, database code.
- `Mobile_App/friday_chat/`: Flutter mobile app.
- `CUSTOM_TOOLCALL_GUIDE.md`: Tool call formats/conventions.
- `friday_memory.db`: Main SQLite database.
- `~/.letta/friday_priority_memories.json`: High-priority curated memories.

### Example Patterns
- **Registering a Tool**:
  ```python
  @self.server.list_tools()
  async def handle_list_tools() -> List[types.Tool]:
      # ...
  ```
- **Async Tool Call Handler**:
  ```python
  @self.server.call_tool()
  async def handle_call_tool(name, arguments, ...):
      # ...
  ```
- **Embedding Request**:
  ```python
  async def get_embedding(self, text):
      async with httpx.AsyncClient() as client:
          response = await client.post(...)
  ```

---

*These architecture and workflow rules supplement the AI assistant rules above. If any section is unclear or missing, specify what you need clarified or expanded for your workflow.*

---

*Last updated: July 10, 2025*
