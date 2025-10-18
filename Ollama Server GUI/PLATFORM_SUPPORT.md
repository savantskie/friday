# Ollama Control Panel - Cross-Platform Support

## Platform Support

The Ollama Control Panel now supports **Windows**, **macOS**, and **Linux**.

### Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| **Linux** | ✅ Full Support | Works with all major desktop environments |
| **macOS** | ✅ Full Support | Works with Terminal and iTerm2 |
| **Windows** | ✅ Full Support | Works with PowerShell and Command Prompt |

## Installation by Platform

### Windows

1. **Install Ollama**
   - Download from https://ollama.ai (official installer)
   - Or install via package managers:
     - **Scoop**: `scoop install ollama`
     - **Chocolatey**: `choco install ollama`
     - **WinGet**: `winget install Ollama.Ollama`

2. **Common Installation Paths (checked automatically)**:
   - `C:\Program Files\Ollama\ollama.exe` (default)
   - `C:\Program Files (x86)\Ollama\ollama.exe`
   - `%APPDATA%\Local\Programs\Ollama\ollama.exe`
   - `~/scoop/shims/ollama.exe` (if using Scoop)

3. **Run the Control Panel**
   - Double-click `ollama_control_panel.pyw`
   - Or run in PowerShell: `python ollama_control_panel.pyw`

### macOS

1. **Install Ollama**
   - Download from https://ollama.ai (official installer)
   - Or via Homebrew: `brew install ollama`

2. **Common Installation Paths** (checked automatically):
   - `/Applications/Ollama.app/Contents/MacOS/ollama` (default)
   - `/usr/local/bin/ollama` (Homebrew)
   - `~/bin/ollama` (user installation)

3. **Run the Control Panel**
   - Run in Terminal: `python3 ollama_control_panel.pyw`

### Linux

1. **Install Ollama**
   - Official installer: `curl -fsSL https://ollama.ai/install.sh | sh`
   - Or via package manager (distribution-specific)

2. **Common Installation Paths** (checked automatically):
   - `/usr/local/bin/ollama` (default)
   - `/usr/bin/ollama`
   - `/opt/ollama/bin/ollama`
   - `~/.ollama/bin/ollama` (user installation)
   - `/snap/bin/ollama` (Snap package)

3. **Run the Control Panel**
   - Run in Terminal: `python3 ollama_control_panel.pyw`

## Platform-Specific Features

### Windows Terminal Options

The app will try to start Ollama in:
1. **Background Process** (most reliable)
2. **PowerShell** (if available)
3. **Command Prompt** (if available)

### macOS Terminal Options

The app will try to start Ollama in:
1. **Background Process** (most reliable)
2. **iTerm2** (if available)
3. **Terminal.app** (if available)

### Linux Terminal Options

The app will try to start Ollama in:
1. **Background Process** (most reliable)
2. **Konsole** (if available)
3. **XFCE Terminal** (if available)
4. **GNOME Terminal** (if available)
5. **XTerm** (if available)

## Configuration

See `CONFIG_GUIDE.md` for configuration options available on all platforms.

### Remote Server Support

All platforms support connecting to a remote Ollama server:

```json
{
  "base_url": "http://192.168.1.100:11434"
}
```

## Troubleshooting

### "Ollama binary not found!" Error

1. **Windows**: Ensure Ollama is installed and in your system PATH
2. **macOS**: Check that Ollama is installed in `/Applications` or via Homebrew
3. **Linux**: Install Ollama or add it to your PATH

### Terminal Won't Open

- The app will fall back to running Ollama in the background
- Check the logs for which terminals are available on your system
- Edit config to specify a preferred method

### Process Won't Stop

- **Windows**: Task is killed using `taskkill`
- **macOS/Linux**: Process group is terminated using `signal.SIGTERM`, then `signal.SIGKILL`

## Architecture Notes

### Process Management
- **Unix/Linux/macOS**: Uses process groups (`os.setsid()`) for proper process hierarchy
- **Windows**: Uses `CREATE_NEW_PROCESS_GROUP` flag for process isolation

### Automatic Detection
- Ollama binary location: Checks PATH first, then common installation directories
- Terminal availability: Detects installed terminal emulators and uses appropriate launch commands
- Platform support: Automatically adapts UI and behavior for the running OS

## Dependencies

All platforms require:
- Python 3.7+
- `dearpygui`
- `requests`

No platform-specific Python packages required (uses standard library features).
