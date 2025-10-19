#!/usr/bin/env python3
"""
Ollama Server Control Panel - Full Featured
Complete parameter controls with presets and server management
"""

import dearpygui.dearpygui as dpg
import requests
import json
import threading
import time
import os
import logging
import subprocess
import sys
import platform
from typing import Dict, List, Optional

class OllamaControlPanel:
    def __init__(self):
        self.base_url = "http://localhost:11434"
        self.running = False
        self.models = []
        self.current_model = None
        self.running_models = []
        self.ollama_process = None
        
        # Window dimensions
        self.window_width = 1500
        self.window_height = 900
        
        # Column widths
        self.left_col = 330
        self.middle_col = 550
        self.right_col = 580
        
        # All Ollama parameters - COMPLETE SET
        self.current_params = {
            # Generation/Sampling
            "temperature": 0.8,
            "top_k": 40,
            "top_p": 0.9,
            "min_p": 0.0,
            "typical_p": 1.0,
            "tfs_z": 1.0,
            
            # Repetition
            "repeat_penalty": 1.1,
            "repeat_last_n": 64,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            
            # Advanced
            "mirostat": 0,
            "mirostat_tau": 5.0,
            "mirostat_eta": 0.1,
            "penalty_alpha": 0.0,
            
            # Context & Performance
            "num_predict": 128,
            "num_ctx": 2048,
            "num_batch": 512,
            "num_thread": 8,
            "num_gpu": -1,
            "main_gpu": 0,
            
            # Other
            "seed": -1,
            "timeout": 30,
        }
        
        # Presets
        self.quick_presets = {
            "Performance": {"temperature": 0.1, "top_k": 20, "top_p": 0.5},
            "Quality": {"temperature": 0.5, "top_k": 40, "top_p": 0.9},
            "Creativity": {"temperature": 1.2, "top_k": 50, "top_p": 0.95},
        }
        
        self.presets_dir = os.path.join(os.path.dirname(__file__), "presets")
        os.makedirs(self.presets_dir, exist_ok=True)
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
    
    # ==================== SERVER MANAGEMENT ====================
    
    def start_ollama_server(self):
        """Start Ollama server in background"""
        if self.ollama_process is not None:
            self.show_status("⚠️ Ollama server already running")
            return
        
        try:
            env = os.environ.copy()
            if platform.system() == "Windows":
                self.ollama_process = subprocess.Popen(
                    ["ollama", "serve"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                self.ollama_process = subprocess.Popen(
                    ["ollama", "serve"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            
            self.show_status("⏳ Ollama server starting...")
            time.sleep(2)
            self.test_connection()
        except FileNotFoundError:
            self.show_error("❌ Ollama not found. Install it first.")
        except Exception as e:
            self.show_error(f"❌ Failed to start Ollama: {e}")
    
    def stop_ollama_server(self):
        """Stop Ollama server"""
        if self.ollama_process is None:
            self.show_status("⚠️ Ollama server not running")
            return
        
        try:
            self.ollama_process.terminate()
            self.ollama_process.wait(timeout=5)
            self.ollama_process = None
            self.show_status("✅ Ollama server stopped")
            self.running = False
        except subprocess.TimeoutExpired:
            self.ollama_process.kill()
            self.ollama_process = None
            self.show_error("❌ Server killed (timeout)")
        except Exception as e:
            self.show_error(f"❌ Failed to stop: {e}")
    
    def test_connection(self):
        """Test connection to Ollama server"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                self.show_status("✅ Connected to Ollama server")
                self.running = True
                self.refresh_data()
            else:
                self.show_error(f"❌ Server error: {response.status_code}")
                self.running = False
        except requests.RequestException as e:
            self.show_error(f"❌ Cannot connect: {e}")
            self.running = False
    
    def refresh_data(self):
        """Refresh all data from server"""
        try:
            self.refresh_models()
            self.refresh_running_models()
            self.show_status("✅ Data refreshed successfully")
        except Exception as e:
            self.show_error(f"❌ Failed to refresh: {e}")
    
    def refresh_models(self):
        """Get list of installed models"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.models = [m.get("name", "unknown") for m in data.get("models", [])]
                if dpg.does_item_exist("models_list"):
                    dpg.configure_item("models_list", items=self.models)
        except Exception as e:
            self.logger.error(f"Failed to refresh models: {e}")
    
    def refresh_running_models(self):
        """Get list of currently running models"""
        try:
            response = requests.get(f"{self.base_url}/api/ps", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.running_models = [m.get("name", "unknown") for m in data.get("models", [])]
                if dpg.does_item_exist("running_models_text"):
                    dpg.set_value("running_models_text", f"Loaded: {len(self.running_models)}")
        except Exception as e:
            self.logger.error(f"Failed to refresh running models: {e}")
    
    def show_error(self, message: str):
        """Display error message"""
        self.logger.error(message)
        if dpg.does_item_exist("status_text"):
            dpg.set_value("status_text", message)
    
    def show_status(self, message: str):
        """Display status message"""
        self.logger.info(message)
        if dpg.does_item_exist("status_text"):
            dpg.set_value("status_text", message)
    
    def update_parameter(self, param_name: str, value):
        """Update a parameter value"""
        self.current_params[param_name] = value
        self.update_settings_display()
    
    def update_settings_display(self):
        """Update the current settings display"""
        if dpg.does_item_exist("current_settings_text"):
            lines = []
            for key in ["temperature", "top_k", "top_p", "repeat_penalty", "num_ctx", "num_predict"]:
                lines.append(f"{key}: {self.current_params[key]}")
            dpg.set_value("current_settings_text", "\n".join(lines))
    
    def apply_preset(self, preset_dict: dict):
        """Apply a preset to current parameters"""
        self.current_params.update(preset_dict)
        self.update_settings_display()
        self.show_status(f"✅ Preset applied")
    
    def setup_gui(self):
        """Setup the GUI layout"""
        dpg.create_context()
        
        # Set theme
        with dpg.theme() as theme_id:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (45, 45, 50))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (35, 35, 40))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 100, 200))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (0, 150, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 100, 200))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (30, 30, 35))
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (0, 150, 255))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3)
                dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 1)
        
        dpg.bind_theme(theme_id)
        
        # Main window
        with dpg.window(label="Ollama Control Panel - Horizontal", tag="main_window", 
                       width=self.window_width, height=self.window_height,
                       no_move=True, no_resize=True):
            
            # Top status and buttons
            dpg.add_text("Data refreshed successfully", tag="status_text", color=(0, 255, 0))
            
            with dpg.group(horizontal=True):
                dpg.add_button(label="▶ Start Server", width=110, height=28,
                              callback=lambda: self.start_ollama_server())
                dpg.add_button(label="⏹ Stop Server", width=110, height=28,
                              callback=lambda: self.stop_ollama_server())
                dpg.add_button(label="🔄 Refresh", width=90, height=28,
                              callback=lambda: self.refresh_data())
                dpg.add_button(label="? Test", width=70, height=28,
                              callback=lambda: self.test_connection())
                dpg.add_button(label="✕ Close", width=70, height=28)
            
            dpg.add_separator()
            
            # Main 3-column layout
            with dpg.group(horizontal=True):
                
                # ==================== LEFT COLUMN ====================
                with dpg.child_window(width=self.left_col, height=self.window_height - 180, border=True):
                    dpg.add_text("? System Information", color=(0, 255, 100))
                    dpg.add_separator()
                    dpg.add_text("Server Status: Checking...")
                    dpg.add_text("Models Available: 0")
                    dpg.add_text("Loaded: 0", tag="running_models_text")
                    
                    dpg.add_separator()
                    dpg.add_text("? Model Management", color=(0, 255, 100))
                    dpg.add_separator()
                    dpg.add_text("Available Models:")
                    dpg.add_listbox(items=[], tag="models_list", width=self.left_col - 20, num_items=15)
                    
                    dpg.add_separator()
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="? Load", width=75)
                        dpg.add_button(label="?? Unload", width=75)
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="? Refresh", width=75)
                        dpg.add_button(label="? Test", width=75)
                
                # ==================== MIDDLE COLUMN ====================
                with dpg.child_window(width=self.middle_col, height=self.window_height - 180, border=True):
                    dpg.add_text("?? Model Parameters (Scrollable)", color=(0, 255, 100))
                    dpg.add_separator()
                    
                    # SCROLLABLE PARAMETERS
                    with dpg.child_window(width=self.middle_col - 20, height=self.window_height - 350):
                        
                        # ========== CORE GENERATION ==========
                        dpg.add_text("▼ Core Generation - Sampling Methods", color=(100, 200, 255))
                        
                        dpg.add_slider_float(label="Temperature", 
                                           default_value=self.current_params["temperature"],
                                           min_value=0.0, max_value=2.0, width=self.middle_col - 60,
                                           callback=lambda s, v: self.update_parameter("temperature", v))
                        
                        dpg.add_slider_int(label="Top K", 
                                         default_value=self.current_params["top_k"],
                                         min_value=0, max_value=100, width=self.middle_col - 60,
                                         callback=lambda s, v: self.update_parameter("top_k", v))
                        
                        dpg.add_slider_float(label="Top P", 
                                           default_value=self.current_params["top_p"],
                                           min_value=0.0, max_value=1.0, width=self.middle_col - 60,
                                           callback=lambda s, v: self.update_parameter("top_p", v))
                        
                        dpg.add_slider_float(label="Min P", 
                                           default_value=self.current_params["min_p"],
                                           min_value=0.0, max_value=1.0, width=self.middle_col - 60,
                                           callback=lambda s, v: self.update_parameter("min_p", v))
                        
                        dpg.add_slider_float(label="Typical P", 
                                           default_value=self.current_params["typical_p"],
                                           min_value=0.0, max_value=1.0, width=self.middle_col - 60,
                                           callback=lambda s, v: self.update_parameter("typical_p", v))
                        
                        dpg.add_separator()
                        
                        # ========== REPETITION CONTROL ==========
                        dpg.add_text("▼ Repetition Control - Reduce Repetition", color=(100, 200, 255))
                        
                        dpg.add_slider_float(label="Repeat Penalty", 
                                           default_value=self.current_params["repeat_penalty"],
                                           min_value=1.0, max_value=2.0, width=self.middle_col - 60,
                                           callback=lambda s, v: self.update_parameter("repeat_penalty", v))
                        
                        dpg.add_slider_int(label="Repeat Lookback", 
                                         default_value=self.current_params["repeat_last_n"],
                                         min_value=0, max_value=256, width=self.middle_col - 60,
                                         callback=lambda s, v: self.update_parameter("repeat_last_n", v))
                        
                        dpg.add_slider_float(label="Presence Penalty", 
                                           default_value=self.current_params["presence_penalty"],
                                           min_value=0.0, max_value=2.0, width=self.middle_col - 60,
                                           callback=lambda s, v: self.update_parameter("presence_penalty", v))
                        
                        dpg.add_slider_float(label="Frequency Penalty", 
                                           default_value=self.current_params["frequency_penalty"],
                                           min_value=0.0, max_value=2.0, width=self.middle_col - 60,
                                           callback=lambda s, v: self.update_parameter("frequency_penalty", v))
                        
                        dpg.add_separator()
                        
                        # ========== CONTEXT & PERFORMANCE ==========
                        dpg.add_text("▼ Context & Performance - Resource Control", color=(100, 200, 255))
                        
                        dpg.add_slider_int(label="Context Size", 
                                         default_value=self.current_params["num_ctx"],
                                         min_value=128, max_value=32768, width=self.middle_col - 60,
                                         callback=lambda s, v: self.update_parameter("num_ctx", v))
                        
                        dpg.add_slider_int(label="Batch Size", 
                                         default_value=self.current_params["num_batch"],
                                         min_value=32, max_value=2048, width=self.middle_col - 60,
                                         callback=lambda s, v: self.update_parameter("num_batch", v))
                        
                        dpg.add_slider_int(label="Max Tokens", 
                                         default_value=self.current_params["num_predict"],
                                         min_value=1, max_value=4096, width=self.middle_col - 60,
                                         callback=lambda s, v: self.update_parameter("num_predict", v))
                        
                        dpg.add_separator()
                        
                        # ========== ADVANCED ==========
                        dpg.add_text("▼ Advanced Parameters - Expert Controls", color=(100, 200, 255))
                        
                        dpg.add_slider_float(label="TFS Z", 
                                           default_value=self.current_params["tfs_z"],
                                           min_value=0.0, max_value=1.0, width=self.middle_col - 60,
                                           callback=lambda s, v: self.update_parameter("tfs_z", v))
                        
                        dpg.add_slider_int(label="Mirostat (0=off)", 
                                         default_value=self.current_params["mirostat"],
                                         min_value=0, max_value=2, width=self.middle_col - 60,
                                         callback=lambda s, v: self.update_parameter("mirostat", v))
                        
                        dpg.add_slider_float(label="Mirostat Tau", 
                                           default_value=self.current_params["mirostat_tau"],
                                           min_value=0.0, max_value=10.0, width=self.middle_col - 60,
                                           callback=lambda s, v: self.update_parameter("mirostat_tau", v))
                        
                        dpg.add_slider_float(label="Mirostat Eta", 
                                           default_value=self.current_params["mirostat_eta"],
                                           min_value=0.0, max_value=1.0, width=self.middle_col - 60,
                                           callback=lambda s, v: self.update_parameter("mirostat_eta", v))
                        
                        dpg.add_slider_float(label="Penalty Alpha", 
                                           default_value=self.current_params["penalty_alpha"],
                                           min_value=0.0, max_value=1.0, width=self.middle_col - 60,
                                           callback=lambda s, v: self.update_parameter("penalty_alpha", v))
                        
                        dpg.add_slider_int(label="GPU Layers", 
                                         default_value=self.current_params["num_gpu"],
                                         min_value=-1, max_value=100, width=self.middle_col - 60,
                                         callback=lambda s, v: self.update_parameter("num_gpu", v))
                        
                        dpg.add_slider_int(label="Threads", 
                                         default_value=self.current_params["num_thread"],
                                         min_value=1, max_value=64, width=self.middle_col - 60,
                                         callback=lambda s, v: self.update_parameter("num_thread", v))
                
                # ==================== RIGHT COLUMN ====================
                with dpg.child_window(width=self.right_col, height=self.window_height - 180, border=True):
                    dpg.add_text("? Parameter Presets", color=(0, 255, 100))
                    dpg.add_separator()
                    
                    # Quick presets buttons
                    dpg.add_text("Quick Presets:", color=(100, 200, 255))
                    dpg.add_button(label="⚡ Performance", width=200,
                                  callback=lambda: self.apply_preset(self.quick_presets["Performance"]))
                    dpg.add_text("Fast, efficient generation", color=(150, 150, 150))
                    
                    dpg.add_button(label="⚖️ Balanced", width=200,
                                  callback=lambda: self.apply_preset(self.quick_presets["Quality"]))
                    dpg.add_text("Balanced quality and speed", color=(150, 150, 150))
                    
                    dpg.add_button(label="✨ Creativity", width=200,
                                  callback=lambda: self.apply_preset(self.quick_presets["Creativity"]))
                    dpg.add_text("High creativity and diversity", color=(150, 150, 150))
                    
                    dpg.add_separator()
                    
                    # Custom presets
                    dpg.add_text("Custom Presets:", color=(100, 200, 255))
                    dpg.add_text("No presets available", color=(150, 150, 150))
                    
                    dpg.add_separator()
                    
                    # Actions
                    dpg.add_text("Actions:", color=(100, 200, 255))
                    dpg.add_button(label="? Reset to Defaults", width=200,
                                  callback=lambda: self.reset_parameters())
                    dpg.add_button(label="💾 Save Current Preset", width=200)
                    dpg.add_button(label="📂 Load Custom Preset", width=200)
                    
                    dpg.add_separator()
                    
                    # Current settings display
                    dpg.add_text("Current Settings:", color=(100, 200, 255))
                    dpg.add_text("Temperature: 0.80\nTop K: 40\nTop P: 0.90\nRepeat Penalty: 1.10\nContext: 2048\nMax Tokens: 128", 
                                tag="current_settings_text", color=(200, 200, 200))
    
    def reset_parameters(self):
        """Reset all parameters to defaults"""
        self.current_params = {
            "temperature": 0.8,
            "top_k": 40,
            "top_p": 0.9,
            "min_p": 0.0,
            "typical_p": 1.0,
            "repeat_penalty": 1.1,
            "repeat_last_n": 64,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "tfs_z": 1.0,
            "mirostat": 0,
            "mirostat_tau": 5.0,
            "mirostat_eta": 0.1,
            "penalty_alpha": 0.0,
            "num_predict": 128,
            "num_ctx": 2048,
            "num_batch": 512,
            "num_thread": 8,
            "num_gpu": -1,
            "main_gpu": 0,
            "seed": -1,
            "timeout": 30,
        }
        self.update_settings_display()
        self.show_status("✅ Parameters reset to defaults")
    
    def run(self):
        """Run the GUI"""
        dpg.create_viewport(title="Ollama Control Panel", 
                           width=self.window_width, height=self.window_height)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)
        
        # Auto-refresh thread
        def auto_refresh():
            while True:
                if self.running:
                    try:
                        self.refresh_data()
                    except:
                        pass
                time.sleep(3)
        
        refresh_thread = threading.Thread(target=auto_refresh, daemon=True)
        refresh_thread.start()
        
        # Main loop
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
        
        # Cleanup
        if self.ollama_process:
            self.stop_ollama_server()
        
        dpg.destroy_context()


def main():
    try:
        app = OllamaControlPanel()
        app.setup_gui()
        app.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
