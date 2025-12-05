# Tool Calls Export Tool

## Overview
The `export_all_tool_calls` tool exports all tool calls from your current and archived MCP databases into a single text file with multi-line JSON formatting. This is designed for building LORA training datasets.

## Access
**URL**: `https://fridayonline.bounceme.net/mcpo/docs`

Navigate to the `export_all_tool_calls` tool in the OpenWebUI MCP interface.

## Features
- ✅ Exports all tool calls from current database (`memory_data/mcp_tool_calls.db`)
- ✅ Exports all tool calls from archived databases (`memory_data/archives/mcp_tool_calls_*.db`)
- ✅ Includes full tool names, parameters (as JSON), timestamps, status, and results
- ✅ Multi-line JSON formatting for easy reading and parsing
- ✅ Automatic timestamp-based filename generation
- ✅ Error handling and reporting

## Data Exported
Each tool call record includes:
```json
{
  "tool_name": "tool_name_here",
  "parameters": {
    "param1": "value1",
    "param2": "value2"
  },
  "timestamp": "ISO-8601 timestamp",
  "status": "success" or "error",
  "result": { "result_object" } or null
}
```

## Statistics (as of December 5, 2025)
- **Current Database**: 612 tool calls
- **Archive (202508)**: 610 tool calls
- **Archive (202509)**: 430 tool calls
- **Archive (202510)**: 261 tool calls
- **Archive (202511)**: 30 tool calls
- **Total Exportable**: ~1,943 tool calls

## Usage

### Via OpenWebUI MCPO
1. Go to `https://fridayonline.bounceme.net/mcpo/docs`
2. Find `export_all_tool_calls` in the tools list
3. Click to expand it
4. (Optional) Enter a custom filename in `output_filename`
5. Click "Execute"
6. Review the result which shows:
   - Status (success/error)
   - File path where export was saved
   - Total number of tool calls exported
   - Any errors encountered

### Optional Parameters
- **output_filename** (string, optional): Custom filename for the export
  - If not provided, generates name like: `tool_calls_export_20251205_122100.txt`
  - Files are always saved in `/media/nate/Friday/Friday/tool calls/` directory

## Output Location
All exports are saved to:
```
/media/nate/Friday/Friday/tool calls/
```

You can download the files from there or access them directly from the filesystem.

## File Format
- **Format**: Plain text with multi-line JSON records
- **Encoding**: UTF-8
- **Separator**: Each JSON object is separated by a newline
- **Size**: Approximately 2.6GB for all 1,943 tool calls

## Data Curation
The tool does NOT format or curate the data. You mentioned you have another AI to handle that. The export provides raw data as it was stored:
- Some tool calls may have failed (status: "error")
- Parameters and results are exactly as logged
- Timestamps are in ISO-8601 format with timezone info
- No deduplication or filtering is applied

## Limitations
- Tool is NOT exposed to AI models (only accessible via web interface)
- Export is read-only (no deletion of tool call history)
- Large file size (2.6GB) requires sufficient disk space
- No incremental export (always exports all records)

## Use Cases
- Building LORA training datasets for smaller models
- Analyzing tool usage patterns
- Auditing tool call history
- Creating training data for specialized model fine-tuning

## Technical Details
- Queries both `tool_calls` table and archives
- Handles JSON parsing/re-encoding of parameters and results
- Includes error logging for any problematic records
- Returns detailed status with counts

## Notes
- The tool queries multiple databases, so export time depends on your hardware
- Archive databases are kept for historical reference
- Parameters are stored as JSON strings and re-exported as parsed JSON for readability
- Timezone information is preserved in timestamps

---
**Created**: December 5, 2025  
**Tool Name**: `export_all_tool_calls`  
**Status**: Ready for LORA training dataset generation
