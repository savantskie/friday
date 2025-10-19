#!/usr/bin/env python3
"""
Ollama Server Control Panel - Horizontal Layout Version
A comprehensive GUI for managing Ollama models and parameters with a horizontal layout
that fits on screen without scrolling.
"""

import dearpygui.dearpygui as dpg
import requests
import json
import threading
import time
import os
import logging
from typing import Dict, List, Optional
import sys

class OllamaControlPanel:
    def __init__(self):
        self.base_url = "http://localhost:11434"
        self.running = False
        self.models = []
        self.current_model = None
        self.running_models = []
        
        # Window dimensions for responsive layout
        self.window_width = 1400
        self.window_height = 750
        
        # All Ollama parameters with defaults
        self.current_params = {
            # Generation parameters
            "temperature": 0.8,
            "top_k": 40,
            "top_p": 0.9,
            "min_p": 0.0,
            "typical_p": 1.0,
            
            # Repetition control
            "repeat_penalty": 1.1,
            "repeat_last_n": 64,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            
            # Context and performance
            "num_predict": 128,
            "num_ctx": 2048,
            "num_batch": 512,
            "num_thread": 8,
            "timeout": 30,
            
            # Advanced parameters
            "tfs_z": 1.0,
            "mirostat": 0,
            "mirostat_tau": 5.0,
            "mirostat_eta": 0.1,
            "penalty_alpha": 0.0,
            "seed": -1,
            "stop": []
        }
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Custom preset directory
        self.presets_dir = os.path.join(os.path.dirname(__file__), "presets")
        os.makedirs(self.presets_dir, exist_ok=True)
    
    def show_error(self, message: str):
        """Display error message"""
        self.logger.error(message)
        if dpg.does_item_exist("status_text"):
            dpg.set_value("status_text", f"Error: {message}")
    
    def show_status(self, message: str):
        """Display status message"""
        self.logger.info(message)
        if dpg.does_item_exist("status_text"):
            dpg.set_value("status_text", message)
    
    def test_connection(self):
        """Test connection to Ollama server"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                self.show_status("✅ Connected to Ollama server")
                self.refresh_data()
            else:
                self.show_error(f"Server responded with status {response.status_code}")
        except requests.RequestException as e:
            self.show_error(f"Cannot connect to Ollama server: {e}")
    
    def refresh_data(self):
        """Refresh all data from server"""
        try:
            self.refresh_models()
            self.refresh_running_models()
            self.show_status("Data refreshed successfully")
        except Exception as e:
            self.show_error(f"Failed to refresh data: {e}")
    
    def refresh_models(self):
        """Refresh the list of available models"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.models = [model['name'] for model in data.get('models', [])]
                
                # Update UI
                if dpg.does_item_exist("model_list"):
                    dpg.configure_item("model_list", items=self.models if self.models else ["No models available"])
                
                self.logger.info(f"Found {len(self.models)} models")
            else:
                self.show_error(f"Failed to get models: HTTP {response.status_code}")
        except requests.RequestException as e:
            self.show_error(f"Failed to refresh models: {e}")
    
    def refresh_running_models(self):
        """Get list of currently running models"""
        try:
            response = requests.get(f"{self.base_url}/api/ps", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.running_models = data.get('models', [])
                
                # Update loaded model display
                if self.running_models:
                    model_name = self.running_models[0].get('name', 'Unknown')
                    if dpg.does_item_exist("loaded_model"):
                        dpg.set_value("loaded_model", model_name)
                        dpg.configure_item("loaded_model", color=(100, 255, 100))
                else:
                    if dpg.does_item_exist("loaded_model"):
                        dpg.set_value("loaded_model", "None")
                        dpg.configure_item("loaded_model", color=(255, 100, 100))
        except requests.RequestException as e:
            self.logger.warning(f"Failed to get running models: {e}")
    
    def model_selected(self, sender, app_data):
        """Handle model selection"""
        if app_data and app_data != "No models available":
            self.current_model = app_data
            self.show_status(f"Selected model: {app_data}")
    
    def load_model(self):
        """Load the selected model"""
        if not self.current_model:
            self.show_error("No model selected")
            return
        
        try:
            self.show_status(f"Loading model {self.current_model}...")
            
            # Prepare parameters for the request
            clean_params = self.get_clean_parameters()
            
            payload = {
                "model": self.current_model,
                "options": clean_params
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                self.show_status(f"✅ Model {self.current_model} loaded successfully")
                self.refresh_running_models()
            else:
                self.show_error(f"Failed to load model: HTTP {response.status_code}")
                
        except requests.RequestException as e:
            self.show_error(f"Failed to load model: {e}")
    
    def unload_model(self):
        """Unload the current model"""
        if not self.running_models:
            self.show_error("No models are currently running")
            return
        
        try:
            model_name = self.running_models[0].get('name', 'Unknown')
            self.show_status(f"Unloading model {model_name}...")
            
            payload = {"model": model_name}
            response = requests.delete(f"{self.base_url}/api/generate", json=payload, timeout=10)
            
            if response.status_code == 200:
                self.show_status(f"✅ Model {model_name} unloaded successfully")
                self.refresh_running_models()
            else:
                self.show_error(f"Failed to unload model: HTTP {response.status_code}")
                
        except requests.RequestException as e:
            self.show_error(f"Failed to unload model: {e}")
    
    def parameter_changed(self, sender, app_data, user_data):
        """Handle parameter changes"""
        param_name = user_data
        self.current_params[param_name] = app_data
        self.update_summary()
        self.logger.debug(f"Parameter {param_name} changed to {app_data}")
    
    def stop_sequences_changed(self, sender, app_data):
        """Handle stop sequences changes"""
        if app_data:
            # Split by comma or newline
            stops = [s.strip() for s in app_data.replace('\n', ',').split(',') if s.strip()]
            self.current_params["stop"] = stops
        else:
            self.current_params["stop"] = []
    
    def get_clean_parameters(self) -> Dict:
        """Get parameters with proper types and validation"""
        params = {}
        for key, value in self.current_params.items():
            if key == "stop":
                if value:  # Only include if not empty
                    params[key] = value
            elif key == "seed" and value == -1:
                # Don't include seed if it's -1 (random)
                continue
            elif isinstance(value, (int, float)) and value > 0:
                params[key] = value
            elif key in ["temperature", "top_p", "min_p", "typical_p", "repeat_penalty", 
                        "presence_penalty", "frequency_penalty", "tfs_z", "mirostat_tau", 
                        "mirostat_eta", "penalty_alpha"] and value >= 0:
                params[key] = value
        return params
    
    def update_summary(self):
        """Update the parameter summary display"""
        try:
            if dpg.does_item_exist("summary_temp"):
                dpg.set_value("summary_temp", f"Temperature: {self.current_params['temperature']:.2f}")
            if dpg.does_item_exist("summary_top_k"):
                dpg.set_value("summary_top_k", f"Top K: {self.current_params['top_k']}")
            if dpg.does_item_exist("summary_top_p"):
                dpg.set_value("summary_top_p", f"Top P: {self.current_params['top_p']:.3f}")
            if dpg.does_item_exist("summary_repeat"):
                dpg.set_value("summary_repeat", f"Repeat Penalty: {self.current_params['repeat_penalty']:.2f}")
            if dpg.does_item_exist("summary_tokens"):
                dpg.set_value("summary_tokens", f"Max Tokens: {self.current_params['num_predict']}")
            if dpg.does_item_exist("summary_context"):
                dpg.set_value("summary_context", f"Context: {self.current_params['num_ctx']}")
        except Exception as e:
            self.logger.warning(f"Failed to update summary: {e}")
    
    # Preset methods
    def set_performance_preset(self):
        """Set parameters for fast performance"""
        self.current_params.update({
            "temperature": 0.3,
            "top_k": 20,
            "top_p": 0.8,
            "repeat_penalty": 1.05,
            "num_predict": 64,
            "num_ctx": 1024
        })
        self.update_ui_from_params()
        self.show_status("Performance preset applied")
    
    def set_quality_preset(self):
        """Set parameters for balanced quality"""
        self.current_params.update({
            "temperature": 0.7,
            "top_k": 40,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
            "num_predict": 128,
            "num_ctx": 2048
        })
        self.update_ui_from_params()
        self.show_status("Quality preset applied")
    
    def set_creativity_preset(self):
        """Set parameters for high creativity"""
        self.current_params.update({
            "temperature": 1.2,
            "top_k": 80,
            "top_p": 0.95,
            "repeat_penalty": 1.15,
            "num_predict": 256,
            "num_ctx": 4096
        })
        self.update_ui_from_params()
        self.show_status("Creativity preset applied")
    
    def update_ui_from_params(self):
        """Update all UI elements from current parameters"""
        try:
            for param, value in self.current_params.items():
                tag_name = f"{param}_slider" if param in ["temperature", "top_p", "min_p", "typical_p", 
                                                        "repeat_penalty", "presence_penalty", "frequency_penalty", 
                                                        "tfs_z", "mirostat_tau", "mirostat_eta", "penalty_alpha"] else f"{param}_input"
                if dpg.does_item_exist(tag_name):
                    dpg.set_value(tag_name, value)
            self.update_summary()
        except Exception as e:
            self.logger.warning(f"Failed to update UI from params: {e}")
    
    def reset_parameters(self):
        """Reset all parameters to defaults"""
        self.current_params = {
            "temperature": 0.8, "top_k": 40, "top_p": 0.9, "min_p": 0.0, "typical_p": 1.0,
            "repeat_penalty": 1.1, "repeat_last_n": 64, "presence_penalty": 0.0, "frequency_penalty": 0.0,
            "num_predict": 128, "num_ctx": 2048, "num_batch": 512, "num_thread": 8, "timeout": 30,
            "tfs_z": 1.0, "mirostat": 0, "mirostat_tau": 5.0, "mirostat_eta": 0.1, "penalty_alpha": 0.0,
            "seed": -1, "stop": []
        }
        self.update_ui_from_params()
        self.show_status("Parameters reset to defaults")
    
    def save_preset(self):
        """Save current parameters as a preset"""
        # This would open a dialog to save preset - simplified for now
        self.show_status("Preset save functionality - to be implemented")
    
    def load_preset_callback(self):
        """Load selected preset"""
        self.show_status("Preset load functionality - to be implemented")
    
    def delete_preset(self):
        """Delete selected preset"""
        self.show_status("Preset delete functionality - to be implemented")
    
    def copy_parameters(self):
        """Copy parameters to clipboard"""
        self.show_status("Copy parameters functionality - to be implemented")
    
    def paste_parameters(self):
        """Paste parameters from clipboard"""
        self.show_status("Paste parameters functionality - to be implemented")
    
    def resize_callback(self, sender, app_data):
        """Handle window resize to maintain responsive layout"""
        try:
            # Get viewport size
            viewport_width = dpg.get_viewport_width()
            viewport_height = dpg.get_viewport_height()
            
            # Ensure minimum size
            if viewport_width < 800 or viewport_height < 500:
                return
            
            # Calculate usable area (accounting for status bar and padding)
            usable_width = viewport_width - 40  # 40px total padding
            usable_height = viewport_height - 90  # 90px for status bar and padding
            
            # Calculate column widths (30%, 40%, 30%)
            left_width = max(250, int(usable_width * 0.30))   # Min 250px
            middle_width = max(400, int(usable_width * 0.40)) # Min 400px  
            right_width = max(250, int(usable_width * 0.30))  # Min 250px
            
            # Adjust if total exceeds available width
            total_width = left_width + middle_width + right_width
            if total_width > usable_width:
                scale_factor = usable_width / total_width
                left_width = int(left_width * scale_factor)
                middle_width = int(middle_width * scale_factor)
                right_width = int(right_width * scale_factor)
            
            # Update column sizes
            if dpg.does_item_exist("left_column"):
                dpg.configure_item("left_column", width=left_width, height=usable_height)
            if dpg.does_item_exist("middle_column"):
                dpg.configure_item("middle_column", width=middle_width, height=usable_height)
            if dpg.does_item_exist("right_column"):
                dpg.configure_item("right_column", width=right_width, height=usable_height)
                
            self.logger.debug(f"Resized to {viewport_width}x{viewport_height}, columns: {left_width}, {middle_width}, {right_width}")
            
        except Exception as e:
            self.logger.warning(f"Error in resize callback: {e}")
    
    
    def setup_gui(self):
        """Initialize the Dear PyGui interface with horizontal layout"""
        dpg.create_context()
        
        # Enhanced theme for better visual organization
        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (20, 25, 30))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (60, 80, 100))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (80, 100, 120))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (100, 120, 140))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (30, 35, 40))
                dpg.add_theme_color(dpg.mvThemeCol_Header, (50, 60, 70))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (60, 70, 80))
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (80, 120, 160))
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, (100, 140, 180))
        
        dpg.bind_theme(global_theme)
        
        # Main window with horizontal layout
        with dpg.window(label="Ollama Control Panel - Horizontal Layout", tag="main_window"):
            
            # Top Status Bar
            with dpg.group(horizontal=True):
                dpg.add_text("Ready", tag="status_text")
                dpg.add_spacer(width=20)
                dpg.add_button(
                    label="🔄 Refresh",
                    callback=lambda: threading.Thread(target=self.refresh_data, daemon=True).start(),
                    width=80
                )
                dpg.add_button(
                    label="🧪 Test",
                    callback=lambda: threading.Thread(target=self.test_connection, daemon=True).start(),
                    width=60
                )
                dpg.add_spacer()
                dpg.add_button(
                    label="❌ Close",
                    callback=lambda: dpg.stop_dearpygui(),
                    width=70
                )
            dpg.add_separator()
            
            # Main 3-column responsive horizontal layout
            with dpg.group(horizontal=True, tag="main_layout"):
                
                # Column 1: System Information & Model Management (30% width)
                with dpg.child_window(width=-1, height=-1, tag="left_column", autosize_x=False, autosize_y=False):
                    # System Information
                    dpg.add_text("📊 System Information", color=(150, 255, 150))
                    dpg.add_separator()
                    
                    with dpg.group():
                        dpg.add_text("Server Status: Checking...", tag="server_status")
                        dpg.add_text("Models Available: 0", tag="model_count")
                        dpg.add_text("Currently Loaded:", tag="loaded_label")
                        dpg.add_text("None", tag="loaded_model", color=(255, 100, 100))
                    
                    dpg.add_separator()
                    
                    # Model Management
                    dpg.add_text("📦 Model Management", color=(255, 255, 100))
                    dpg.add_separator()
                    
                    dpg.add_text("Available Models:")
                    dpg.add_listbox(
                        items=["Loading..."],
                        tag="model_list",
                        callback=self.model_selected,
                        width=-1,  # Full width of container
                        num_items=12
                    )
                    
                    dpg.add_spacer(height=10)
                    
                    with dpg.group(horizontal=True):
                        dpg.add_button(
                            label="🚀 Load",
                            callback=self.load_model,
                            width=90
                        )
                        dpg.add_button(
                            label="🗑️ Unload",
                            callback=self.unload_model,
                            width=90
                        )
                        dpg.add_button(
                            label="🔄 Refresh",
                            callback=lambda: threading.Thread(target=self.refresh_models, daemon=True).start(),
                            width=90
                        )
                        dpg.add_button(
                            label="🧪 Test",
                            callback=lambda: threading.Thread(target=self.test_connection, daemon=True).start(),
                            width=90
                        )
                
                # Column 2: Parameters (40% width)
                with dpg.child_window(width=-1, height=-1, tag="middle_column", autosize_x=False, autosize_y=False):
                    dpg.add_text("⚙️ Model Parameters", color=(255, 255, 100))
                    dpg.add_separator()
                    
                    # Scrollable parameter area
                    with dpg.child_window(width=-1, height=-1):
                        # Core Generation Parameters
                        with dpg.collapsing_header(label="🎯 Core Generation", default_open=True):
                            with dpg.group(horizontal=True):
                                # Left column
                                with dpg.group():
                                    dpg.add_text("Temperature:")
                                    dpg.add_slider_float(
                                        label="##temperature",
                                        default_value=0.8,
                                        min_value=0.0,
                                        max_value=2.0,
                                        format="%.2f",
                                        callback=self.parameter_changed,
                                        user_data="temperature",
                                        tag="temperature_slider",
                                        width=-1  # Responsive width
                                    )
                                    
                                    dpg.add_text("Top K:")
                                    dpg.add_input_int(
                                        label="##top_k",
                                        default_value=40,
                                        callback=self.parameter_changed,
                                        user_data="top_k",
                                        tag="top_k_input",
                                        width=-1
                                    )
                                    
                                    dpg.add_text("Top P:")
                                    dpg.add_slider_float(
                                        label="##top_p",
                                        default_value=0.9,
                                        min_value=0.0,
                                        max_value=1.0,
                                        format="%.2f",
                                        callback=self.parameter_changed,
                                        user_data="top_p",
                                        tag="top_p_slider",
                                        width=-1
                                    )
                                
                                # Right column
                                with dpg.group():
                                    dpg.add_text("Min P:")
                                    dpg.add_slider_float(
                                        label="##min_p",
                                        default_value=0.0,
                                        min_value=0.0,
                                        max_value=0.5,
                                        format="%.3f",
                                        callback=self.parameter_changed,
                                        user_data="min_p",
                                        tag="min_p_slider",
                                        width=-1
                                    )
                                    
                                    dpg.add_text("Typical P:")
                                    dpg.add_slider_float(
                                        label="##typical_p",
                                        default_value=1.0,
                                        min_value=0.0,
                                        max_value=1.0,
                                        format="%.2f",
                                        callback=self.parameter_changed,
                                        user_data="typical_p",
                                        tag="typical_p_slider",
                                        width=-1
                                    )
                                    
                                    dpg.add_text("Random Seed:")
                                    dpg.add_input_int(
                                        label="##seed",
                                        default_value=-1,
                                        callback=self.parameter_changed,
                                        user_data="seed",
                                        tag="seed_input",
                                        width=-1
                                    )
                        
                        # Repetition Control
                        with dpg.collapsing_header(label="🔁 Repetition Control", default_open=True):
                            with dpg.group(horizontal=True):
                                # Left column
                                with dpg.group():
                                    dpg.add_text("Repeat Penalty:")
                                    dpg.add_slider_float(
                                        label="##repeat_penalty",
                                        default_value=1.1,
                                        min_value=0.5,
                                        max_value=2.0,
                                        format="%.2f",
                                        callback=self.parameter_changed,
                                        user_data="repeat_penalty",
                                        tag="repeat_penalty_slider",
                                        width=-1
                                    )
                                    
                                    dpg.add_text("Repeat Lookback:")
                                    dpg.add_input_int(
                                        label="##repeat_last_n",
                                        default_value=64,
                                        callback=self.parameter_changed,
                                        user_data="repeat_last_n",
                                        tag="repeat_last_n_input",
                                        width=-1
                                    )
                                
                                # Right column
                                with dpg.group():
                                    dpg.add_text("Presence Penalty:")
                                    dpg.add_slider_float(
                                        label="##presence_penalty",
                                        default_value=0.0,
                                        min_value=-2.0,
                                        max_value=2.0,
                                        format="%.2f",
                                        callback=self.parameter_changed,
                                        user_data="presence_penalty",
                                        tag="presence_penalty_slider",
                                        width=-1
                                    )
                                    
                                    dpg.add_text("Frequency Penalty:")
                                    dpg.add_slider_float(
                                        label="##frequency_penalty",
                                        default_value=0.0,
                                        min_value=-2.0,
                                        max_value=2.0,
                                        format="%.2f",
                                        callback=self.parameter_changed,
                                        user_data="frequency_penalty",
                                        tag="frequency_penalty_slider",
                                        width=-1
                                    )
                        
                        # Context & Performance
                        with dpg.collapsing_header(label="⚡ Context & Performance", default_open=False):
                            with dpg.group(horizontal=True):
                                # Left column
                                with dpg.group():
                                    dpg.add_text("Context Size:")
                                    dpg.add_input_int(
                                        label="##num_ctx",
                                        default_value=2048,
                                        callback=self.parameter_changed,
                                        user_data="num_ctx",
                                        tag="num_ctx_input",
                                        width=-1
                                    )
                                    
                                    dpg.add_text("Max Tokens:")
                                    dpg.add_input_int(
                                        label="##num_predict",
                                        default_value=128,
                                        callback=self.parameter_changed,
                                        user_data="num_predict",
                                        tag="num_predict_input",
                                        width=-1
                                    )
                                    
                                    dpg.add_text("Batch Size:")
                                    dpg.add_input_int(
                                        label="##num_batch",
                                        default_value=512,
                                        callback=self.parameter_changed,
                                        user_data="num_batch",
                                        tag="num_batch_input",
                                        width=-1
                                    )
                                
                                # Right column
                                with dpg.group():
                                    dpg.add_text("Thread Count:")
                                    dpg.add_input_int(
                                        label="##num_thread",
                                        default_value=8,
                                        callback=self.parameter_changed,
                                        user_data="num_thread",
                                        tag="num_thread_input",
                                        width=-1
                                    )
                                    
                                    dpg.add_text("Timeout:")
                                    dpg.add_input_int(
                                        label="##timeout",
                                        default_value=30,
                                        callback=self.parameter_changed,
                                        user_data="timeout",
                                        tag="timeout_input",
                                        width=-1
                                    )
                        
                        # Advanced Parameters
                        with dpg.collapsing_header(label="🔬 Advanced Parameters", default_open=False):
                            with dpg.group(horizontal=True):
                                # Left column
                                with dpg.group():
                                    dpg.add_text("TFS Z:")
                                    dpg.add_slider_float(
                                        label="##tfs_z",
                                        default_value=1.0,
                                        min_value=0.0,
                                        max_value=2.0,
                                        format="%.2f",
                                        callback=self.parameter_changed,
                                        user_data="tfs_z",
                                        tag="tfs_z_slider",
                                        width=-1
                                    )
                                    
                                    dpg.add_text("Mirostat:")
                                    dpg.add_input_int(
                                        label="##mirostat",
                                        default_value=0,
                                        callback=self.parameter_changed,
                                        user_data="mirostat",
                                        tag="mirostat_input",
                                        width=-1
                                    )
                                    
                                    dpg.add_text("Mirostat Tau:")
                                    dpg.add_slider_float(
                                        label="##mirostat_tau",
                                        default_value=5.0,
                                        min_value=0.0,
                                        max_value=10.0,
                                        format="%.2f",
                                        callback=self.parameter_changed,
                                        user_data="mirostat_tau",
                                        tag="mirostat_tau_slider",
                                        width=-1
                                    )
                                
                                # Right column
                                with dpg.group():
                                    dpg.add_text("Mirostat Eta:")
                                    dpg.add_slider_float(
                                        label="##mirostat_eta",
                                        default_value=0.1,
                                        min_value=0.0,
                                        max_value=1.0,
                                        format="%.3f",
                                        callback=self.parameter_changed,
                                        user_data="mirostat_eta",
                                        tag="mirostat_eta_slider",
                                        width=-1
                                    )
                                    
                                    dpg.add_text("Penalty Alpha:")
                                    dpg.add_slider_float(
                                        label="##penalty_alpha",
                                        default_value=0.0,
                                        min_value=0.0,
                                        max_value=2.0,
                                        format="%.2f",
                                        callback=self.parameter_changed,
                                        user_data="penalty_alpha",
                                        tag="penalty_alpha_slider",
                                        width=-1
                                    )
                            
                            dpg.add_spacer(height=10)
                            dpg.add_text("Stop Sequences (comma-separated):")
                            dpg.add_input_text(
                                label="##stop",
                                default_value="",
                                callback=self.stop_sequences_changed,
                                width=-1,
                                multiline=True,
                                height=40
                            )
                
                # Column 3: Presets & Actions (30% width)
                with dpg.child_window(width=-1, height=-1, tag="right_column", autosize_x=False, autosize_y=False):
                    dpg.add_text("🎨 Parameter Presets", color=(255, 255, 100))
                    dpg.add_separator()
                    
                    # Quick Presets
                    dpg.add_text("Quick Presets:")
                    
                    dpg.add_button(
                        label="⚡ Performance",
                        callback=self.set_performance_preset,
                        width=-1
                    )
                    dpg.add_text("Fast, efficient generation", color=(150, 150, 150))
                    
                    dpg.add_spacer(height=5)
                    
                    dpg.add_button(
                        label="🎯 Quality",
                        callback=self.set_quality_preset,
                        width=-1
                    )
                    dpg.add_text("Balanced quality and speed", color=(150, 150, 150))
                    
                    dpg.add_spacer(height=5)
                    
                    dpg.add_button(
                        label="🎨 Creativity",
                        callback=self.set_creativity_preset,
                        width=-1
                    )
                    dpg.add_text("High creativity and diversity", color=(150, 150, 150))
                    
                    dpg.add_separator()
                    
                    # Custom Presets
                    dpg.add_text("Custom Presets:")
                    
                    dpg.add_listbox(
                        items=["No presets available"],
                        tag="preset_list",
                        width=-1,
                        num_items=8
                    )
                    
                    dpg.add_spacer(height=10)
                    
                    with dpg.group(horizontal=True):
                        dpg.add_button(
                            label="💾 Save",
                            callback=self.save_preset,
                            width=-1
                        )
                        dpg.add_button(
                            label="📂 Load",
                            callback=self.load_preset_callback,
                            width=-1
                        )
                        dpg.add_button(
                            label="🗑️ Delete",
                            callback=self.delete_preset,
                            width=-1
                        )
                    
                    dpg.add_separator()
                    
                    # Actions
                    dpg.add_text("Actions:")
                    
                    dpg.add_button(
                        label="🔄 Reset to Defaults",
                        callback=self.reset_parameters,
                        width=-1
                    )
                    
                    dpg.add_button(
                        label="📋 Copy Parameters",
                        callback=self.copy_parameters,
                        width=-1
                    )
                    
                    dpg.add_button(
                        label="📄 Paste Parameters",
                        callback=self.paste_parameters,
                        width=-1
                    )
                    
                    dpg.add_separator()
                    
                    # Current Settings Summary
                    dpg.add_text("Current Settings:", color=(200, 200, 200))
                    with dpg.child_window(width=-1, height=180):
                        dpg.add_text("Temperature: 0.80", tag="summary_temp")
                        dpg.add_text("Top K: 40", tag="summary_top_k")
                        dpg.add_text("Top P: 0.90", tag="summary_top_p")
                        dpg.add_text("Repeat Penalty: 1.10", tag="summary_repeat")
                        dpg.add_text("Context: 2048", tag="summary_context")
                        dpg.add_text("Max Tokens: 128", tag="summary_tokens")
        
        # Set main window as primary and configure viewport for responsive layout
        dpg.create_viewport(title="Ollama Control Panel - Horizontal", width=1400, height=750, min_width=1000, min_height=600)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)
        
        # Set up resize callback for responsive layout
        dpg.set_viewport_resize_callback(self.resize_callback)
        
        # Initial resize to set proper proportions
        self.resize_callback(None, None)
    
    def run(self):
        """Run the application"""
        try:
            self.running = True
            
            # Initial data load (with delay to let GUI initialize)
            def delayed_refresh():
                time.sleep(1)  # Give GUI time to initialize
                self.refresh_data()
            
            refresh_thread = threading.Thread(target=delayed_refresh, daemon=True)
            refresh_thread.start()
            
            dpg.start_dearpygui()
            
        except Exception as e:
            self.logger.error(f"Application error: {e}")
            raise
        finally:
            self.running = False
            dpg.destroy_context()

def main():
    """Main entry point"""
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
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()