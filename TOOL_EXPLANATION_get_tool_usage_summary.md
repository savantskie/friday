# get_tool_usage_summary - Explanation

## What It Actually Does

`get_tool_usage_summary` is **NOT** for getting summaries about what tools DO. Instead, it's for **analyzing how the MCP server itself has been USED** - it's diagnostic/telemetry data.

## The Purpose

This tool:
1. **Tracks** all MCP tool calls made over the past N days (default: 7 days)
2. **Analyzes** statistics like:
   - Total number of tool calls made
   - Success rate (what % succeeded vs failed)
   - Average execution time
   - Which tools were used most frequently
   - Which tools had errors
   - Which clients (VS Code, LM Studio, OpenWebUI) made which calls

3. **Generates AI insights** from that usage data

## Example Output

```json
{
  "status": "success",
  "period_days": 7,
  "stats": {
    "total_calls": 157,
    "success_rate": 94.3,
    "avg_execution_time": 245.2,
    "tool_frequency": {
      "search_memories": 45,
      "get_reminders": 32,
      "create_memory": 28,
      "get_weather_open_meteo": 21,
      "update_memory": 15,
      ...
    },
    "error_patterns": [
      {
        "tool": "brave_web_search",
        "error_count": 9,
        "error_rate": 8.5
      }
    ],
    "client_activity": {
      "copilot": {"total": 89, "successful": 84},
      "lm_studio": {"total": 52, "successful": 49},
      "openwebui": {"total": 16, "successful": 15}
    }
  },
  "insights": {
    "total_tool_calls": 157,
    "success_rate_percent": 94.3,
    "most_used_tool": "search_memories",
    ...
  }
}
```

## Why It Exists

This tool was created to help **you (and AI assistants using the system)** understand:
- Which tools are being used most
- Where problems might be happening (tools with high error rates)
- Which client platform is most active
- Performance metrics (how fast tools execute)

It's for **system monitoring and optimization**, not for functional use.

## Confusion with Tool Descriptions

I see why the LLM got confused! The description "Get AI tool usage summary" could sound like:
- "Get a summary OF what tools DO" ❌ (This is what the LLM thought)
- "Get a summary ABOUT usage OF tools" ✅ (This is what it actually does)

## Related Tool: reflect_on_tool_usage

There's a companion tool called `reflect_on_tool_usage` that:
- Runs this same analysis
- **Plus** generates AI reflections on the patterns
- Stores the reflection for future reference
- Returns recommendations for improvement

## Should This Be Available to General Tools?

**Pros of keeping it available:**
- LLMs can use it to understand system health
- Can help identify broken tools
- Useful for debugging why something failed

**Cons:**
- LLMs might get confused (as you saw)
- It's more of an internal diagnostic tool
- Doesn't provide value for typical memory/reminder operations

## My Recommendation

This tool is useful but might benefit from:
1. **Better naming**: `get_mcp_server_diagnostics` or `get_system_usage_stats` would be clearer
2. **Better description**: Something like "Get MCP server usage statistics and performance diagnostics (for system health monitoring, not tool functionality)"
3. **Consider moving to VS Code tools only** - since it's more for debugging/optimization than user-facing functionality

Would you like me to:
- Rename it to something clearer?
- Move it to VS Code-specific tools only?
- Update its description to be less confusing?
- Leave it as-is since it's working correctly now?
