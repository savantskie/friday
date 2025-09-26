# Ollama Server Control Panel

A comprehensive Python desktop application for managing Ollama models and parameters through a clean GUI interface.

## Features

- **Model Management**: View installed and currently loaded models
- **Load/Unload Control**: Easily load models with custom parameters or unload them
- **Parameter Tuning**: Adjust temperature, top_k, context size, and keep_alive settings
- **System Monitoring**: Real-time display of CPU and memory usage
- **Preset System**: Save and load parameter configurations per model
- **Auto-refresh**: Automatically updates model status and system info

## Requirements

- Python 3.8+
- Ollama server running on localhost:11434
- Required packages (see requirements.txt):
  - dearpygui>=1.10.1
  - requests>=2.31.0
  - psutil>=5.9.0

## Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Start your Ollama server:
   ```bash
   ollama serve
   ```

2. Run the control panel:
   ```bash
   python ollama_control_panel.py
   ```

## Interface Overview

### Model Management Panels
- **Installed Models**: Shows all models available on your system with "Load" buttons
- **Running Models**: Shows currently loaded models with "Unload" buttons

### Parameter Controls
- **Temperature**: Controls randomness (0.0 = deterministic, 2.0 = very random)
- **Top K**: Limits vocabulary selection to top K tokens
- **Context Size (num_ctx)**: Sets the context window size
- **Keep Alive**: How long to keep model in memory (-1 = forever)

### System Information
- Real-time CPU usage percentage
- Memory usage (used/total/percentage)
- GPU information (if available)

### Preset System
1. Select a model from the dropdown
2. Adjust parameters to your liking
3. Enter a preset name and click "Save Preset"
4. Later, select the preset from the dropdown to load those parameters

## Preset File Format

The application stores presets in `model_presets.json`:

```json
{
  "qwen:4b": {
    "default": {
      "temperature": 0.7,
      "top_k": 40,
      "num_ctx": 8192,
      "keep_alive": -1
    },
    "coding_mode": {
      "temperature": 0.2,
      "top_k": 20,
      "num_ctx": 4096,
      "keep_alive": 600
    }
  }
}
```

## API Endpoints Used

- `GET /api/tags` - List installed models
- `GET /api/ps` - List running models  
- `POST /api/generate` - Load model with parameters
- `POST /api/stop` - Unload model

## Troubleshooting

- **Connection Error**: Ensure Ollama server is running on localhost:11434
- **Models Not Loading**: Check that the model name is correct and available
- **GPU Info Not Available**: GPU monitoring requires nvidia-smi for NVIDIA cards
- **Preset File Issues**: The app will create an empty preset file if none exists

## Cross-Platform Compatibility

This application is designed to work on:
- Windows 11
- Linux (Ubuntu, CentOS, etc.)
- macOS (should work but not extensively tested)

The GUI uses Dear PyGui which provides consistent appearance across platforms.