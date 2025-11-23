#!/usr/bin/env python3
"""
Test script to verify client type detection for the MCP server.

This helps debug which platform is being detected when the MCP server starts.
Run this to see detection diagnostics.
"""

import sys
import os
from pathlib import Path

# Add the Friday directory to the path
friday_path = Path(__file__).parent
sys.path.insert(0, str(friday_path))

from port_manager import PortManager, CallerProgram
import psutil
import logging

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def diagnose_process_tree():
    """Show the process tree to understand parent/grandparent relationships"""
    print("\n" + "="*80)
    print("PROCESS TREE DIAGNOSTICS")
    print("="*80)
    
    current_pid = os.getpid()
    current_process = psutil.Process(current_pid)
    
    print(f"\n📌 Current Process:")
    print(f"   PID: {current_pid}")
    print(f"   Name: {current_process.name()}")
    print(f"   Executable: {current_process.exe()}")
    print(f"   Command Line: {' '.join(current_process.cmdline()[:3])}...")
    
    try:
        parent = current_process.parent()
        print(f"\n👨 Parent Process:")
        print(f"   PID: {parent.pid}")
        print(f"   Name: {parent.name()}")
        print(f"   Executable: {parent.exe()}")
        
        try:
            grandparent = parent.parent()
            print(f"\n👴 Grandparent Process:")
            print(f"   PID: {grandparent.pid}")
            print(f"   Name: {grandparent.name()}")
            print(f"   Executable: {grandparent.exe()}")
        except:
            print(f"\n👴 Grandparent Process: (unable to access)")
    except:
        print(f"\n👨 Parent Process: (unable to access)")

def test_caller_detection():
    """Test the port manager's caller detection"""
    print("\n" + "="*80)
    print("CALLER PROGRAM DETECTION TEST")
    print("="*80)
    
    try:
        port_manager = PortManager(memory_data_path=str(friday_path / "memory_data"))
        
        # Run detection
        detected = port_manager.detect_caller_program()
        
        print(f"\n✅ Detection Result: {detected.value}")
        print(f"   Enum: {detected}")
        print(f"   CallerProgram.VSCODE: {CallerProgram.VSCODE.value}")
        print(f"   CallerProgram.LM_STUDIO: {CallerProgram.LM_STUDIO.value}")
        print(f"   CallerProgram.OPENWEBUI: {CallerProgram.OPENWEBUI.value}")
        print(f"   CallerProgram.OLLAMA: {CallerProgram.OLLAMA.value}")
        print(f"   CallerProgram.UNKNOWN: {CallerProgram.UNKNOWN.value}")
        
        if detected == CallerProgram.VSCODE:
            print("\n🎯 VSCODE DETECTED - VS Code development tools will be available")
        elif detected == CallerProgram.LM_STUDIO:
            print("\n🎯 LM_STUDIO DETECTED - Core memory tools will be available")
        elif detected == CallerProgram.OPENWEBUI:
            print("\n🎯 OPENWEBUI DETECTED - Core memory tools will be available")
        elif detected == CallerProgram.OLLAMA:
            print("\n🎯 OLLAMA DETECTED - Core memory tools will be available")
        else:
            print("\n🎯 UNKNOWN DETECTED - Core memory tools will be available (default)")
            
    except Exception as e:
        print(f"\n❌ Error during detection: {e}")
        import traceback
        traceback.print_exc()

def show_environment_hints():
    """Show environment hints that might affect detection"""
    print("\n" + "="*80)
    print("ENVIRONMENT HINTS")
    print("="*80)
    
    env_vars_to_check = [
        'VSCODE_PID',
        'VSCODE_FOLDER',
        'VSCODE_CWD',
        'LM_STUDIO_PATH',
        'OLLAMA_HOME',
        'OPENWEBUI_PATH',
    ]
    
    print("\nChecking for environment variables that indicate parent program:")
    for var in env_vars_to_check:
        value = os.environ.get(var)
        if value:
            print(f"   ✓ {var} = {value}")
        else:
            print(f"   - {var} (not set)")

def main():
    """Run all diagnostics"""
    print("\n🔍 MCP Server Client Detection Diagnostics")
    print("This helps debug which platform is being detected when MCP server starts.\n")
    
    diagnose_process_tree()
    test_caller_detection()
    show_environment_hints()
    
    print("\n" + "="*80)
    print("WHAT TO EXPECT")
    print("="*80)
    print("""
If you're running FROM VS CODE Copilot Extension:
    - You should see "vscode" or "code" in parent process
    - VS Code development tools will be enabled

If you're running FROM LM Studio:
    - You should see "lm-studio" or "lmstudio" in parent process
    - Core memory tools will be enabled

If you're running FROM OpenWebUI on port 12345:
    - Port detection will identify port 12345
    - Core memory tools will be enabled

If detection isn't working as expected:
    - Check the process tree output above
    - Verify parent process names match expected values
    - Check if restarting the parent application helps
    """)
    
    print("\n✅ Diagnostics complete!")

if __name__ == "__main__":
    main()
