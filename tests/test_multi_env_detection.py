#!/usr/bin/env python3
"""
Multi-Environment Client Detection Tester

This script helps you test client detection in three different environments:
1. LM Studio (imports MCP server as module)
2. VS Code (imports MCP server as module)  
3. OpenWebUI via MCPO (HTTP server on port 12345)

Usage:
  - From LM Studio: Run this to see what LM Studio detects
  - From VS Code Terminal: Run this to see what VS Code detects
  - From OpenWebUI machine: Run this to see what OpenWebUI detects
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

def show_detection_summary():
    """Show what will be detected and what tools will be available"""
    print("\n" + "="*80)
    print("DETECTION SUMMARY - WHAT WILL YOUR CLIENT SEE?")
    print("="*80)
    
    try:
        port_manager = PortManager(memory_data_path=str(friday_path / "memory_data"))
        detected = port_manager.detect_caller_program()
        
        print(f"\n✅ Your environment: {detected.value.upper()}")
        print(f"\n   Caller Program Detected: {detected.value}")
        
        # Show what tools you'll get
        print("\n🛠️  Tools you'll have access to:")
        
        if detected == CallerProgram.VSCODE:
            print("""
   ✓ Core Memory Tools:
     - search_memories
     - create_memory, update_memory
     - get_recent_context
     - store_conversation
     - All reminder/appointment tools
     - Weather and search tools
   
   ✓ VS CODE-SPECIFIC Tools:
     - save_development_session
     - store_project_insight
     - search_project_history
     - link_code_context
     - get_project_continuity
   
   🎯 BEST FOR: Development context tracking and project insights
   """)
        else:
            print(f"""
   ✓ Core Memory Tools:
     - search_memories
     - create_memory, update_memory
     - get_recent_context
     - store_conversation
     - All reminder/appointment tools
     - Weather and search tools
   
   ℹ️  {detected.value.upper()}-SPECIFIC Tools: None (using standard core tools)
   
   🎯 BEST FOR: General memory and scheduling
   """)
            
    except Exception as e:
        print(f"\n❌ Error during detection: {e}")
        import traceback
        traceback.print_exc()

def show_environment_details():
    """Show detailed environment information"""
    print("\n" + "="*80)
    print("DETAILED ENVIRONMENT INFORMATION")
    print("="*80)
    
    current_pid = os.getpid()
    current_process = psutil.Process(current_pid)
    
    print(f"\n📌 CURRENT PROCESS (This Script):")
    print(f"   PID: {current_pid}")
    print(f"   Name: {current_process.name()}")
    print(f"   Executable: {current_process.exe()}")
    
    try:
        print(f"   Command: {' '.join(current_process.cmdline())}")
    except:
        print(f"   Command: (unable to retrieve)")
    
    try:
        parent = current_process.parent()
        print(f"\n👨 PARENT PROCESS:")
        print(f"   PID: {parent.pid}")
        print(f"   Name: {parent.name()}")
        print(f"   Executable: {parent.exe()}")
        
        try:
            grandparent = parent.parent()
            print(f"\n👴 GRANDPARENT PROCESS:")
            print(f"   PID: {grandparent.pid}")
            print(f"   Name: {grandparent.name()}")
            print(f"   Executable: {grandparent.exe()}")
        except:
            pass
    except:
        pass
    
    try:
        port_manager = PortManager(memory_data_path=str(friday_path / "memory_data"))
        print(f"\n🔌 PORT INFORMATION:")
        print(f"   Active Port: {port_manager.active_port if port_manager.active_port else '(not set - using module import)'}")
        print(f"   Primary Port: {port_manager.PRIMARY_PORT}")
        print(f"   OpenWebUI Port: 12345 (if running there)")
    except:
        pass

def show_instructions():
    """Show instructions for each platform"""
    print("\n" + "="*80)
    print("INSTRUCTIONS FOR EACH PLATFORM")
    print("="*80)
    
    print("""
🤖 IF YOU'RE IN LM STUDIO:
   1. LM Studio imports the MCP server as a module
   2. Detection happens when tools are first requested
   3. You should see: "🤖 LM Studio detected" in logs
   4. You'll get core memory tools (no LM Studio-specific tools exist yet)
   5. Expected: Unknown or "lm_studio"

📝 IF YOU'RE IN VS CODE:
   1. VS Code Extension imports the MCP server as a module
   2. Detection happens when you first ask for tools
   3. You should see: "📝 VS Code detected" in logs
   4. You'll get VS Code development tools + core tools
   5. Expected: "vscode"

🌐 IF YOU'RE IN OPENWEBUI via MCPO:
   1. MCPO runs the MCP server via HTTP on port 12345
   2. Detection happens when server starts (start_http_server)
   3. You should see: "🌐 OpenWebUI detected via port 12345" in logs
   4. You'll get core memory tools
   5. Expected: "unknown" but with port 12345 detection

⚠️  TROUBLESHOOTING:
   - If you see "Unknown caller program":
     * Check the process tree above - parent process name might not match expected
     * Try restarting the parent application
     * Check logs for the full parent process name
   
   - If VS Code tools don't appear:
     * Make sure parent process is "code" or "electron"
     * Check if VS Code is nested deeper in process tree (grandparent check)
     * Look for "vscode-server" or ".vscode" in command line
""")

def main():
    """Run all diagnostics"""
    print("\n🔍 CLIENT DETECTION TEST - Multi-Environment")
    print("=" * 80)
    
    show_environment_details()
    show_detection_summary()
    show_instructions()
    
    print("\n" + "="*80)
    print("✅ Diagnostics complete!")
    print("="*80)
    
    # Also show what the MCP server will detect when tools are requested
    print("\n📊 When you request tools, the MCP server will:")
    print("   1. Call _detect_client_type()")
    print("   2. Check for caller detection")
    print("   3. Map to appropriate tool set")
    print("   4. Return VS Code tools if detected, otherwise core tools")

if __name__ == "__main__":
    main()
