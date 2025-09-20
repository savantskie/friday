#!/usr/bin/env python3
"""
Debug version with more verbose output and forced window positioning
"""

import dearpygui.dearpygui as dpg
import requests
import time

def test_ollama():
    """Quick test of Ollama connection"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        print(f"Ollama connection: OK (status {response.status_code})")
        models = response.json().get("models", [])
        print(f"Found {len(models)} models")
        return True
    except Exception as e:
        print(f"Ollama connection failed: {e}")
        return False

def main():
    print("=== Ollama Control Panel Debug ===")
    
    # Test Ollama first
    if not test_ollama():
        input("Ollama connection failed. Press Enter to exit...")
        return
    
    try:
        print("Step 1: Creating Dear PyGui context...")
        dpg.create_context()
        
        print("Step 2: Creating window...")
        with dpg.window(label="Ollama Control Panel - Debug", tag="main_window", width=600, height=400):
            dpg.add_text("Debug Mode - If you see this, Dear PyGui is working!")
            dpg.add_separator()
            dpg.add_text("Ollama server is connected and working.")
            dpg.add_button(label="Close", callback=lambda: dpg.stop_dearpygui())
        
        print("Step 3: Creating viewport...")
        dpg.create_viewport(
            title="Ollama Control Panel Debug", 
            width=650, 
            height=450,
            x_pos=100,  # Force specific position
            y_pos=100,
            always_on_top=True  # Force window to front
        )
        
        print("Step 4: Setup...")
        dpg.setup_dearpygui()
        
        print("Step 5: Show viewport...")
        dpg.show_viewport()
        
        print("Step 6: Set primary window...")
        dpg.set_primary_window("main_window", True)
        
        print("Step 7: Starting GUI (you should see window now)...")
        print("Window should be at position 100,100 on your screen")
        
        dpg.start_dearpygui()
        
        print("Step 8: Cleaning up...")
        dpg.destroy_context()
        print("Debug session complete.")
        
    except Exception as e:
        print(f"Error in step: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()