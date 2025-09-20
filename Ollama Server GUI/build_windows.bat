@echo off
echo Building Ollama Control Panel Windows Executable...

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous builds
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "__pycache__" rmdir /s /q "__pycache__"

REM Build the executable
echo Building executable (this may take a few minutes)...
pyinstaller --clean --onefile ^
    --name "OllamaControlPanel" ^
    --add-data "README.md;." ^
    --hidden-import "dearpygui.dearpygui" ^
    --hidden-import "requests" ^
    --hidden-import "psutil" ^
    --windowed ^
    ollama_control_panel.py

if errorlevel 1 (
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo Build completed successfully!
echo Executable location: dist\OllamaControlPanel.exe
echo.
echo Creating release package...

REM Create release folder
if not exist "release" mkdir "release"
copy "dist\OllamaControlPanel.exe" "release\"
copy "README.md" "release\"
copy "requirements.txt" "release\"

echo.
echo Windows release package created in 'release' folder:
echo - OllamaControlPanel.exe (standalone executable)
echo - README.md (documentation)
echo - requirements.txt (for reference)
echo.

pause