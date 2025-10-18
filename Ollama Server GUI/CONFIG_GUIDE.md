# Ollama Control Panel - Configuration Guide

## Configuration File

The Ollama Control Panel can be configured using a JSON configuration file: `ollama_control_panel.config.json`

### Auto-Generated Configuration

When you first run the application, it will automatically create a default configuration file in the same directory as the application if one doesn't exist.

### Configuration Options

```json
{
  "custom_script_path": null,
  "prefer_terminal": false,
  "startup_timeout": 5,
  "base_url": "http://localhost:11434"
}
```

#### `custom_script_path` (string or null)
- **Purpose**: Path to a custom shell script that starts your Ollama server
- **Default**: `null` (disabled)
- **Example**: `"/home/user/scripts/start_ollama.sh"`
- **Usage**: If set to a valid script path, the application will try to use this script to start Ollama
- **Note**: The script must be executable (`chmod +x script.sh`)

#### `prefer_terminal` (boolean)
- **Purpose**: Whether to prefer opening Ollama in a terminal window
- **Default**: `false` (uses background process)
- **Options**: 
  - `true` - Try to open Ollama in an available terminal emulator
  - `false` - Start Ollama as a background process
- **Note**: The app will fall back to background process if no terminal is available

#### `startup_timeout` (integer)
- **Purpose**: Seconds to wait for the Ollama server to become responsive after starting
- **Default**: `5`
- **Range**: `1` to `60` (recommended)
- **Note**: Increase this if your system is slow or you're loading large models

#### `base_url` (string)
- **Purpose**: The base URL for connecting to the Ollama server
- **Default**: `"http://localhost:11434"`
- **Example**: `"http://192.168.1.100:11434"` (remote server)
- **Note**: Use this if Ollama is running on a different machine or port

### Example Configurations

#### Configuration 1: Remote Ollama Server
```json
{
  "custom_script_path": null,
  "prefer_terminal": false,
  "startup_timeout": 10,
  "base_url": "http://192.168.1.100:11434"
}
```

#### Configuration 2: Custom Start Script
```json
{
  "custom_script_path": "/home/user/scripts/start_ollama.sh",
  "prefer_terminal": false,
  "startup_timeout": 5,
  "base_url": "http://localhost:11434"
}
```

#### Configuration 3: Terminal Preference
```json
{
  "custom_script_path": null,
  "prefer_terminal": true,
  "startup_timeout": 5,
  "base_url": "http://localhost:11434"
}
```

### How to Customize

1. Look for `ollama_control_panel.config.json` in the same directory as `ollama_control_panel.pyw`
2. Edit the file with your preferred settings
3. Save the file
4. Restart the application (changes take effect on next run)

### Automatic Detection

The application will also automatically:
- Detect Ollama binary locations (PATH, `/usr/local/bin`, `/usr/bin`, etc.)
- Find available terminal emulators on your system (Konsole, XFCE Terminal, XTerm)
- Use sensible defaults if configuration is missing
