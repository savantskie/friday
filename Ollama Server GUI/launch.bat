@echo off
echo Starting Ollama Control Panel...

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if required packages are installed
python -c "import dearpygui, requests, psutil" >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    pip install -r requirements.txt
)

REM Start the application
python ollama_control_panel.py

pause