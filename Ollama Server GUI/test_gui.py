#!/usr/bin/env python3
"""
Simple Dear PyGui test to check if GUI can initialize
"""

import dearpygui.dearpygui as dpg

try:
    print("Creating Dear PyGui context...")
    dpg.create_context()
    
    print("Creating test window...")
    with dpg.window(label="Test Window", tag="test_window"):
        dpg.add_text("Hello World!")
        dpg.add_button(label="Test Button")
    
    print("Creating viewport...")
    dpg.create_viewport(title="Dear PyGui Test", width=400, height=200)
    
    print("Setting up...")
    dpg.setup_dearpygui()
    
    print("Showing viewport...")
    dpg.show_viewport()
    
    print("Setting primary window...")
    dpg.set_primary_window("test_window", True)
    
    print("Starting GUI loop...")
    dpg.start_dearpygui()
    
    print("Cleaning up...")
    dpg.destroy_context()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    input("Press Enter to continue...")