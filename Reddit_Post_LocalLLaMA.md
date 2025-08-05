# persistent-ai-memory - Major Update: 11+ Platform Support & SillyTavern MCP Integration

Hey r/LocalLLaMA! 

Almost a week ago, I shared my AI memory system project called **persistent-ai-memory**, and the response from this community was incredible. You all provided fantastic feedback and platform requests that I've been working hard to implement. Here's what's new!

 GitHub: https://github.com/savantskie/persistent-ai-memory

## 🎯 What persistent-ai-memory Does
persistent-ai-memory is an AI memory system that automatically captures conversations from multiple chat platforms and provides semantic search, context awareness, and development session tracking. Think of it as giving your AI a long-term memory that persists across all your different chat applications.

## 🌟 Major Updates Since Last Post

### Community-Requested Platform Support (11+ Platforms!)
Thanks to your feedback, Friday now supports:

**Original Platforms:**
- ChatGPT (desktop app)
- Claude (desktop app) 
- LM Studio conversations
- VS Code chat sessions
- Ollama database integration
- Perplexity conversations

**NEW - Community Requested:**
- **SillyTavern** (full chat format support)
- **Gemini CLI** (conversation exports)
- **OpenWebUI** (chat data)
- **Jan AI** (conversation files)
- **Text Generation WebUI** (logs & character chats)
- **Character.AI** format support

### 🤖 SillyTavern MCP Integration
One of the biggest additions - persistent-ai-memory now includes a full MCP (Model Context Protocol) server specifically designed for SillyTavern integration:

- **Character-specific memory tools** for roleplay contexts
- **Roleplay history search** with character awareness
- **Automatic client detection** (knows when SillyTavern is connected)
- **Character context management** for immersive conversations

### 🕐 Complete Timezone System Overhaul
- Converted from UTC to Central Time with full DST support
- Backward compatibility maintained for existing data
- Smart timezone detection and conversion helpers

### 📁 Enhanced File Monitoring
- **Hash-based change detection** (no more duplicate imports)
- **Cross-platform directory detection** (Windows/Linux/macOS)
- **Registry-based format parsing** (easily extensible for new platforms)
- **MCP-aware deduplication** (avoids conflicts with manual memory storage)

## 🛠 Technical Architecture

**Core Components:**
- **Memory MCP Server**: Persistent SQLite backend with FastAPI
- **File Monitor**: Real-time conversation import from 11+ platforms
- **VS Code Integration**: Development session tracking and context
- **Embedding System**: LM Studio integration for semantic search

**File Structure:**
```
persistent-ai-memory/
├── ai_memory_core.py                # Enhanced platform support
├── mcp_server.py                    # SillyTavern MCP integration
├── friday_memory_mcp_server.py      # Core MCP server implementation
├── database_maintenance.py          # Database management
└── tests/                           # Comprehensive test suite
```

## 🚀 What Makes persistent-ai-memory Special

1. **Zero Manual Input**: Automatically captures conversations from all your chat apps
2. **Cross-Platform**: Works on Windows/Linux/macOS with auto-detection
3. **Semantic Search**: Find conversations by meaning, not just keywords
4. **Development Focused**: Special handling for VS Code chat sessions
5. **Privacy First**: Everything runs locally, your data stays yours
6. **Extensible**: Easy to add new platforms via format registry

## 📈 Real-World Impact

Since implementing community feedback:
- **11+ chat platforms** now automatically monitored
- **Hash-based deduplication** eliminated duplicate imports
- **SillyTavern MCP integration** enables character-aware roleplay memory
- **Timezone conversion** provides proper local time handling
- **Enhanced error handling** for robust 24/7 operation

## 🔗 GitHub & Setup

The **persistent-ai-memory** project is designed to be community-focused and easily deployable:

**Key Features for the Community:**
- MIT License (completely open)
- Comprehensive documentation
- Platform-specific parsers for all major chat apps
- MCP server for SillyTavern integration
- Cross-platform installation scripts

## 🤝 Community Feedback Integration

This update directly addresses requests from r/LocalLLaMA users:
- ✅ SillyTavern support (with full MCP integration!)
- ✅ Gemini CLI conversation imports
- ✅ OpenWebUI chat monitoring
- ✅ Enhanced format detection
- ✅ Better error handling and logging

## 🎁 What's Next

Based on continued community interest:
- GraphDB integration (as requested)
- Additional MCP server capabilities
- Mobile app integration (Flutter-based)
- Plugin system for custom platforms
- Enhanced semantic search with local embeddings

## 💭 Why Share This?

r/LocalLLaMA has been incredibly supportive of this project. Unlike other communities that dismissed it for involving ChatGPT integration, you all saw the value in giving AI persistent memory across platforms. Your platform requests and technical feedback directly shaped these improvements.

This is what happens when a community actually supports innovation instead of gatekeeping. Thank you!

---
 GitHub: https://github.com/savantskie/persistent-ai-memory
 
**TL;DR**: persistent-ai-memory now supports 11+ chat platforms (including SillyTavern with full MCP integration), has robust file monitoring, and provides semantic search across all your AI conversations. All running locally with your data staying private.

Questions, feedback, or want to try it out? Happy to help! 🚀

---

*Edit: For those asking about the name - "persistent-ai-memory" does exactly what it says: provides persistent memory for AI across all your different chat applications and platforms!*
