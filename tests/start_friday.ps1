# Friday Memory System Launcher
# Run this script to start Friday's memory services

Write-Host "🚀 Starting Friday Memory System..." -ForegroundColor Green
Write-Host "=" * 50

# Change to Friday directory
Set-Location "F:\Friday"

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found. Please install Python 3.8+ and add to PATH" -ForegroundColor Red
    exit 1
}

# Install required packages if needed
Write-Host "📦 Checking dependencies..." -ForegroundColor Yellow
python -m pip install fastapi uvicorn watchdog mcp python-dateutil > $null 2>&1

# Launch the memory system
Write-Host "🧠 Launching Friday's Memory System..." -ForegroundColor Cyan
Write-Host ""
Write-Host "Services starting:" -ForegroundColor Yellow
Write-Host "  • MCP Server (for VS Code integration)" -ForegroundColor White
Write-Host "  • Conversation Tool Bridge (for Ollama UI integration)" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

try {
    python launch_friday_memory.py
} catch {
    Write-Host "❌ Error starting Friday Memory System: $_" -ForegroundColor Red
} finally {
    Write-Host ""
    Write-Host "✅ Friday Memory System stopped" -ForegroundColor Green
}
