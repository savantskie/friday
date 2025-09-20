#!/bin/bash

echo "Building Ollama Control Panel Linux Executable..."

# Check if PyInstaller is installed
if ! pip show pyinstaller > /dev/null 2>&1; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Clean previous builds
rm -rf build dist __pycache__

# Build the executable
echo "Building executable (this may take a few minutes)..."
pyinstaller --clean --onefile \
    --name "OllamaControlPanel" \
    --add-data "README.md:." \
    --hidden-import "dearpygui.dearpygui" \
    --hidden-import "requests" \
    --hidden-import "psutil" \
    ollama_control_panel.py

if [ $? -ne 0 ]; then
    echo "Build failed!"
    exit 1
fi

echo
echo "Build completed successfully!"
echo "Executable location: dist/OllamaControlPanel"
echo

echo "Creating release package..."

# Create release folder
mkdir -p release
cp dist/OllamaControlPanel release/
cp README.md release/
cp requirements.txt release/

# Make executable
chmod +x release/OllamaControlPanel

echo
echo "Linux release package created in 'release' folder:"
echo "- OllamaControlPanel (standalone executable)"
echo "- README.md (documentation)"
echo "- requirements.txt (for reference)"
echo

echo "To run: ./release/OllamaControlPanel"