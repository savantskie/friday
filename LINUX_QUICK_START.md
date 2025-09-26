# Friday Memory System - Linux Quick Start Guide

## 🎉 Migration Complete!
Your Friday Memory System has been successfully migrated to Linux!

## 🚀 Quick Start

### 1. Start the MCP Server
```bash
cd /media/nate/Friday/Friday
python3 friday_memory_mcp_server.py
```

### 2. Or use the shell script:
```bash
./openwebuifridayMCP.sh
```

### 3. Test the Memory System
```bash
cd /media/nate/Friday/Friday
python3 -c "
import asyncio
from friday_memory_system import FridayMemorySystem

async def test():
    memory = FridayMemorySystem(enable_file_monitoring=False)
    result = await memory.get_system_health()
    print('System Status:', result['status'])
    print('Database count:', len(result['databases']))

asyncio.run(test())
"
```

## 📁 Important Paths
- **Base Directory**: `/media/nate/Friday/Friday`
- **Memory Data**: `/media/nate/Friday/Friday/memory_data/`
- **Weather Cache**: `/media/nate/Friday/Friday/weather_directory/weather/`
- **Logs**: `/media/nate/Friday/Friday/logs/`
- **OpenWebUI Data**: `/media/nate/Friday/OpenWebUI/data/`

## 🔧 Available Scripts
- `openwebuifridayMCP.sh` - Start MCP server for OpenWebUI
- `fridaycaddylaunch.sh` - Start Caddy server (if needed)

## 📊 Database Files
Your existing databases from Windows are accessible:
- `conversations.db` - Chat conversations (250MB)
- `ai_memories.db` - Curated memories (1.7MB)  
- `schedule.db` - Appointments & reminders (1MB)
- `vscode_project.db` - Development sessions (158MB)
- `mcp_tool_calls.db` - Tool usage tracking (1.3GB)

## 🔍 Next Steps

### Update File Monitoring (Optional)
If you want to monitor LM Studio/VS Code on Linux, update the paths in the file monitoring configuration.

### Environment Variables (Optional)  
Add to your `~/.bashrc` or `~/.profile`:
```bash
export FRIDAY_BASE_PATH="/media/nate/Friday/Friday"
export OPENWEBUI_DATA_PATH="/media/nate/Friday/OpenWebUI/data"
export WEATHER_DIRECTORY="/media/nate/Friday/Friday/weather_directory"
```

## 🎯 Testing Checklist
- [x] Python imports working
- [x] Database connections working  
- [x] MCP server initializing
- [x] Dynamic paths working
- [x] Shell scripts executable
- [x] VS Code MCP configuration updated
- [ ] Test with actual VS Code MCP connection
- [ ] Test with actual OpenWebUI connection
- [ ] Test weather functionality
- [ ] Test reminder/appointment creation
- [ ] Test memory search functionality

## 🆘 Troubleshooting
If you encounter issues:
1. Check Python path: `which python3`
2. Check installed packages: `pip3 list | grep -E "(mcp|fastapi|aiohttp)"`
3. Check database permissions: `ls -la /media/nate/Friday/Friday/memory_data/`
4. Check logs: `tail -f /media/nate/Friday/Friday/logs/friday.log`

## 🎉 Success!
Your Friday Memory System is now fully migrated to Linux and ready to use!