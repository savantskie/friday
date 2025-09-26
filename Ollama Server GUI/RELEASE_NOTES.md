# Ollama Control Panel - Release Notes

## What's New

### Model Management Dashboard
- **Real-time Model Monitoring**: See all installed and currently loaded models
- **One-Click Load/Unload**: Easy model management with custom parameters
- **Model Information**: View detailed model specs including context limits
- **System Monitoring**: Real-time CPU, memory, and GPU usage

### Advanced Parameter Control
- **Temperature Control**: Fine-tune creativity (0.0 - 2.0)
- **Top-K Selection**: Control vocabulary selection (1-100)
- **Context Size**: Support for up to 2M context length
- **Keep Alive**: Configure model memory retention

### Preset System
- **Save Configurations**: Store parameter sets per model
- **Quick Loading**: Instantly apply saved presets
- **JSON Storage**: Human-readable preset files
- **Model-Specific**: Different presets for different models

### System Requirements
- **Windows**: Windows 10/11 (x64)
- **Linux**: Ubuntu 18.04+ or equivalent
- **Ollama**: Server running on localhost:11434

### Installation Options

#### Option 1: Standalone Executable (Recommended)
1. Download `OllamaControlPanel.exe` (Windows) or `OllamaControlPanel` (Linux)
2. Ensure Ollama server is running: `ollama serve`
3. Run the executable

#### Option 2: Python Script
1. Install Python 3.8+
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python ollama_control_panel.py`

### Features
✅ Cross-platform (Windows & Linux)  
✅ Real-time model status updates  
✅ Parameter presets and saving  
✅ System resource monitoring  
✅ Model context size detection  
✅ Dark theme interface  
✅ No external dependencies (standalone)  

### API Compatibility
- Ollama REST API v1.x
- Endpoints: `/api/tags`, `/api/ps`, `/api/generate`, `/api/stop`, `/api/show`

### Known Limitations
- Requires Ollama server on localhost:11434
- GPU monitoring works best with NVIDIA cards
- Model info requires Ollama v0.3.0+

---

**Download the appropriate version for your system below** ⬇️