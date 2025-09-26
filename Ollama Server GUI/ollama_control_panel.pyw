#!/usr/bin/env python3
"""
Ollama Server Control Panel
A comprehensive GUI dashboard for managing Ollama models and parameters
"""

import dearpygui.dearpygui as dpg
import requests
import psutil
import json
import os
import threading
import time
import logging
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any


class OllamaControlPanel:
    def __init__(self):
        self.base_url = "http://localhost:11434"
        self.presets_file = "model_presets.json"
        self.refresh_interval = 1.0  # seconds - fast like professional GPU monitoring tools
        
        # Setup logging (simplified for GUI mode)
        self.setup_logging()
        
        # Track model changes to reduce spam
        self.last_installed_models = []
        self.last_running_models = []
        
        # Professional GPU monitoring - fresh connections to avoid COM issues
        self.initialize_gpu_monitoring()
        self.running = False
        
        # Current model parameters
        self.current_params = {
            "temperature": 0.7,
            "top_k": 40,
            "num_ctx": 8192,
            "keep_alive": -1,
            "num_gpu": -1,  # -1 = auto, 0 = CPU only, >0 = number of layers on GPU
            "main_gpu": 0,  # Which GPU to use (0-based index)
            "numa": False   # Enable NUMA support
        }
        
        # Model data
        self.installed_models = []
        self.running_models = []
        self.selected_model = None
        
        # Load presets
        self.presets = self.load_presets()
        
        # Initialize Dear PyGui
        self.setup_gui()
        
        self.refresh_system_info()
    
    def setup_logging(self):
        """Setup minimal logging for GUI mode"""
        try:
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # Create simple logger
            self.logger = logging.getLogger('OllamaControlPanel')
            self.logger.setLevel(logging.ERROR)  # Only log errors in GUI mode
            
            # Remove existing handlers
            for handler in self.logger.handlers[:]:
                self.logger.removeHandler(handler)
            
            # Simple file handler
            log_file = os.path.join(log_dir, f"ollama_gui_{datetime.now().strftime('%Y%m%d')}.log")
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.ERROR)
            
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception:
            # If logging fails, create a dummy logger
            self.logger = logging.getLogger('dummy')
            self.logger.addHandler(logging.NullHandler())
    
    def initialize_gpu_monitoring(self):
        """Initialize GPU monitoring variables"""
        # Real-time GPU monitoring - NO CACHING
        
        # Initialize persistent WMI connection for real-time monitoring
        self.wmi_connection = None
        try:
            import wmi
            self.wmi_connection = wmi.WMI()
        except Exception as e:
            print(f"Failed to initialize WMI connection: {e}")
            self.wmi_connection = None
        
        # Try to get GPU hardware info once
        self.gpu_info = None
        try:
            import wmi
            temp_wmi = wmi.WMI()
            gpus = temp_wmi.Win32_VideoController()
            for gpu in gpus:
                if gpu.Name and 'Microsoft' not in gpu.Name:
                    self.gpu_info = {
                        'name': gpu.Name,
                        'memory': gpu.AdapterRAM if gpu.AdapterRAM else 0
                    }
                    break
            del temp_wmi
        except Exception as e:
            self.logger.error(f"Failed to get GPU info: {e}")
            
        # Try to initialize OpenCL for AMD cards (like GPU-Z does)
        try:
            import pyopencl as cl
            platforms = cl.get_platforms()
            for platform in platforms:
                devices = platform.get_devices()
                for device in devices:
                    if device.type == cl.device_type.GPU:
                        self.opencl_device = device
                        break
        except:
            self.opencl_device = None
    
    def load_presets(self) -> Dict:
        """Load model presets from JSON file, create empty file if doesn't exist"""
        if not os.path.exists(self.presets_file):
            with open(self.presets_file, 'w') as f:
                json.dump({}, f, indent=2)
            return {}
        
        try:
            with open(self.presets_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    
    def save_presets(self):
        """Save current presets to JSON file"""
        try:
            with open(self.presets_file, 'w') as f:
                json.dump(self.presets, f, indent=2)
        except IOError as e:
            self.show_error(f"Failed to save presets: {e}")
    
    def get_installed_models(self) -> List[Dict]:
        """Get list of installed models from Ollama API"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            model_names = [m.get('name') for m in models]
            
            # Only log if models have changed
            if model_names != self.last_installed_models:
                self.logger.info(f"Installed models changed: {model_names}")
                self.last_installed_models = model_names.copy()
            
            return models
        except requests.RequestException as e:
            self.show_error(f"Failed to get installed models: {e}")
            self.logger.error(f"Error getting installed models: {e}")
            return []
    
    def get_running_models(self) -> List[Dict]:
        """Get list of currently loaded models from Ollama API"""
        try:
            response = requests.get(f"{self.base_url}/api/ps", timeout=5)
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            model_names = [m.get('name') for m in models]
            
            # Only log if models have changed
            if model_names != self.last_running_models:
                self.logger.info(f"Running models changed: {model_names}")
                self.last_running_models = model_names.copy()
            
            return models
        except requests.RequestException as e:
            self.show_error(f"Failed to get running models: {e}")
            self.logger.error(f"Error getting running models: {e}")
            return []
    
    def get_model_info(self, model_name: str) -> Dict:
        """Get detailed information about a specific model"""
        try:
            response = requests.post(
                f"{self.base_url}/api/show",
                json={"name": model_name},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.show_error(f"Failed to get model info for '{model_name}': {e}")
            return {}
    
    def load_model(self, model_name: str, params: Dict = None):
        """Load a model with specified parameters"""
        if params is None:
            params = self.current_params.copy()
        
        try:
            payload = {
                "model": model_name,
                "prompt": "",
                "options": params
            }
            
            print(f"Sending load request for {model_name}: {payload}")
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=60,  # Increased timeout for model loading
                stream=False
            )
            
            print(f"Response status: {response.status_code}")
            if response.status_code == 200:
                self.show_success(f"Model '{model_name}' loaded successfully")
                # Force refresh to show the loaded model
                self.refresh_data()
            else:
                self.show_error(f"Failed to load model '{model_name}': HTTP {response.status_code}")
                print(f"Response text: {response.text}")
            
        except requests.RequestException as e:
            self.show_error(f"Failed to load model '{model_name}': {e}")
            print(f"Load model error: {e}")
    
    def unload_model(self, model_name: str):
        """Unload/stop a model using keep_alive=0s method"""
        try:
            # Modern Ollama API approach: Use generate with keep_alive="0s" to immediately unload
            payload = {
                "model": model_name,
                "prompt": "",
                "keep_alive": "0s",  # Immediately unload after this request
                "stream": False
            }
            print(f"Sending unload request for {model_name} using keep_alive=0s")
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=10
            )
            
            print(f"Unload response status: {response.status_code}")
            if response.status_code == 200:
                self.show_success(f"Model '{model_name}' unloaded successfully")
                # Force refresh to show the change
                self.refresh_data()
            else:
                self.show_error(f"Failed to unload model '{model_name}': HTTP {response.status_code}")
                print(f"Unload response text: {response.text}")
            
        except requests.RequestException as e:
            self.show_error(f"Failed to unload model '{model_name}': {e}")
            print(f"Unload model error: {e}")
    
    def get_system_info(self) -> Dict:
        """Get current system memory and CPU usage"""
        try:
            # Get system memory info
            memory = psutil.virtual_memory()
            
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Get GPU usage and VRAM info (MSI Afterburner style)
            gpu_usage_percent = self.get_gpu_usage()
            gpu_memory_info = self.get_gpu_memory_usage()
            
            # Try to get GPU info (comprehensive multi-vendor approach)
            # Skip GPU detection if it failed recently to reduce spam
            if not hasattr(self, '_gpu_detection_failed'):
                self._gpu_detection_failed = False
                self._gpu_info_cache = "N/A"
                self._wmi_permanently_disabled = False
                self._gpu_retry_count = 0
            
            # Use cached GPU info most of the time for performance
            import time
            if not hasattr(self, '_gpu_info_last_update'):
                self._gpu_info_last_update = 0
            
            # Initialize variables
            gpu_info = "N/A"
            gpu_detected = False
            
            # Only update GPU info every 10 seconds to improve performance
            gpu_info_age = time.time() - self._gpu_info_last_update
            if self._gpu_detection_failed and self._gpu_retry_count > 2:
                gpu_info = self._gpu_info_cache or "Detection failed"
            elif gpu_info_age < 10 and self._gpu_info_cache:
                gpu_info = self._gpu_info_cache  # Use cached info
            else:
                # Time to refresh GPU info - run detection
                self._gpu_info_last_update = time.time()
                
                try:
                    import subprocess
                    import platform
                    
                    # Try PowerShell GPU detection first (most reliable on Windows)
                    if platform.system() == "Windows":
                        try:
                            ps_cmd = 'Get-WmiObject Win32_VideoController | Where-Object {$_.Name -notlike "*Microsoft*"} | Select-Object Name, AdapterRAM | ConvertTo-Json'
                            result = subprocess.run(['pwsh.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_cmd], 
                                                  capture_output=True, text=True, timeout=5, 
                                                  creationflags=subprocess.CREATE_NO_WINDOW)
                            if result.returncode == 0 and result.stdout.strip():
                                import json
                                gpu_data = json.loads(result.stdout)
                                if isinstance(gpu_data, list):
                                    gpu_data = gpu_data[0]  # Take first GPU
                                
                                name = gpu_data.get('Name', 'Unknown GPU')
                                ram = gpu_data.get('AdapterRAM')
                                
                                ram_gb = ""
                                if ram and isinstance(ram, (int, float)) and ram > 0:
                                    ram_gb = f" ({ram/(1024**3):.0f}GB)"
                                
                                # Add compute capability info
                                compute_info = ""
                                if "AMD" in name.upper() or "RADEON" in name.upper():
                                    compute_info = " [Vulkan/OpenCL]"
                                elif "NVIDIA" in name.upper() or "GEFORCE" in name.upper() or "RTX" in name.upper():
                                    compute_info = " [CUDA/Vulkan/OpenCL]"
                                elif "INTEL" in name.upper():
                                    compute_info = " [Vulkan/OpenCL]"
                                
                                gpu_info = f"{name}{ram_gb}{compute_info}"
                                gpu_detected = True
                        except Exception as e:
                            print(f"PowerShell GPU detection failed: {e}")
                    
                    # Fallback: Registry detection for Windows
                    if not gpu_detected and platform.system() == "Windows":
                        try:
                            result = subprocess.run([
                                'reg', 'query', 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}', 
                                '/s', '/v', 'DriverDesc'
                            ], capture_output=True, text=True, timeout=3, 
                               creationflags=subprocess.CREATE_NO_WINDOW)
                            
                            if result.returncode == 0:
                                import re
                                gpu_matches = re.findall(r'DriverDesc\s+REG_SZ\s+(.+)', result.stdout)
                                if gpu_matches:
                                    # Filter out Microsoft Basic Display Adapter
                                    valid_gpus = [gpu.strip() for gpu in gpu_matches if "Microsoft" not in gpu and "Basic Display" not in gpu]
                                    if valid_gpus:
                                        gpu_info = valid_gpus[0]
                                        gpu_detected = True
                        except Exception as e:
                            print(f"Registry GPU detection failed: {e}")
                    
                    # If still no GPU detected, use generic message
                    if not gpu_detected:
                        gpu_info = "GPU present but detection unavailable"
                        self._gpu_detection_failed = True
                        self._gpu_retry_count += 1
                    else:
                        # Success - reset failure flags
                        self._gpu_detection_failed = False
                        self._gpu_retry_count = 0
                    
                    self._gpu_info_cache = gpu_info
                    
                except Exception as e:
                    gpu_info = f"GPU Error: {str(e)[:50]}..."
                    self._gpu_detection_failed = True
                    self._gpu_retry_count += 1
                    self._gpu_info_cache = gpu_info
                
            # TODO: Re-enable full GPU detection after fixing indentation
            
            return {
                "memory_used_gb": memory.used / (1024**3),
                "memory_total_gb": memory.total / (1024**3),
                "memory_percent": memory.percent,
                "cpu_percent": cpu_percent,
                "gpu_info": gpu_info,
                "gpu_usage_percent": gpu_usage_percent,
                "gpu_usage_data": gpu_usage_percent,  # Pass the full GPU usage data
                "gpu_memory": gpu_memory_info
            }
        except Exception as e:
            return {
                "memory_used_gb": 0,
                "memory_total_gb": 0,
                "memory_percent": 0,
                "cpu_percent": 0,
                "gpu_info": f"Error: {e}"
            }
    
    def show_error(self, message: str):
        """Show error message in status"""
        if dpg.does_item_exist("status_text"):
            dpg.set_value("status_text", f"❌ {message}")
    
    def show_success(self, message: str):
        """Show success message in status"""
        if dpg.does_item_exist("status_text"):
            dpg.set_value("status_text", f"✅ {message}")
    
    def test_connection(self):
        """Test connection to Ollama server"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                model_count = len(data.get("models", []))
                self.show_success(f"Connected! Found {model_count} models")
            else:
                self.show_error(f"Connection failed: HTTP {response.status_code}")
        except Exception as e:
            self.show_error(f"Connection test failed: {e}")
            print(f"Connection test error: {e}")
    
    def retry_gpu_detection(self):
        """Reset GPU detection and try again"""
        self._gpu_detection_failed = False
        self._gpu_info_cache = "N/A"
        self.show_success("Retrying GPU detection...")
        self.update_system_info()
    
    def get_gpu_usage(self) -> Dict:
        """Get GPU usage using lightweight WMI like Task Manager"""
        gpu_data = {
            "usage_3d": 0.0,
            "usage_compute": 0.0, 
            "usage_copy": 0.0,
            "usage_video": 0.0,
            "overall_usage": 0.0
        }
        
        try:
            # Initialize COM for this thread (required for WMI in background threads)
            import pythoncom
            pythoncom.CoInitialize()
            
            # Create fresh WMI connection each time
            import wmi
            wmi_conn = wmi.WMI()
            engine_counters = wmi_conn.Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine()
            engine_usage = {"3D": [], "Compute": [], "Copy": [], "Video": []}
            
            for counter in engine_counters:
                name = getattr(counter, 'Name', '')
                utilization = getattr(counter, 'UtilizationPercentage', 0)
                
                if not utilization:
                    continue
                    
                util_val = float(utilization)
                if util_val <= 0:
                    continue
                
                # Parse engine type from name (Task Manager style)
                name_lower = name.lower()
                if 'engtype_3d' in name_lower:
                    engine_usage["3D"].append(util_val)
                elif 'engtype_compute' in name_lower:
                    engine_usage["Compute"].append(util_val)
                elif 'engtype_copy' in name_lower:
                    engine_usage["Copy"].append(util_val)
                elif 'engtype_video' in name_lower:
                    engine_usage["Video"].append(util_val)
            
            # Calculate averages for each engine type
            if engine_usage["3D"]:
                gpu_data["usage_3d"] = sum(engine_usage["3D"]) / len(engine_usage["3D"])
            if engine_usage["Compute"]:
                gpu_data["usage_compute"] = sum(engine_usage["Compute"]) / len(engine_usage["Compute"])
            if engine_usage["Copy"]:
                gpu_data["usage_copy"] = sum(engine_usage["Copy"]) / len(engine_usage["Copy"])
            if engine_usage["Video"]:
                gpu_data["usage_video"] = sum(engine_usage["Video"]) / len(engine_usage["Video"])
            
            # Overall usage is the highest of all engines
            all_values = []
            for values in engine_usage.values():
                if values:
                    all_values.extend(values)
            
            if all_values:
                gpu_data["overall_usage"] = max(all_values)
            
            # Clean up WMI connection and COM
            del wmi_conn
            pythoncom.CoUninitialize()
                    
        except Exception as e:
            # Silent fail for lightweight monitoring
            pass
        
        return gpu_data
    
    def get_gpu_memory_usage(self) -> Dict:
        """Get GPU memory usage in REAL-TIME - NO CACHING"""
        memory_data = {
            "dedicated_used_mb": 0,
            "dedicated_total_mb": 20464,  # Your RX 7900 XT VRAM
            "shared_used_mb": 0,
            "shared_total_mb": 0,
            "usage_percent": 0.0
        }
        
        try:
            # Initialize COM for this thread (required for WMI in background threads)
            import pythoncom
            pythoncom.CoInitialize()
            
            # Create fresh WMI connection each time - prevents COM errors
            import wmi
            wmi_conn = wmi.WMI()
            adapter_counters = wmi_conn.Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory()
            
            max_dedicated = 0
            max_shared = 0
            
            for counter in adapter_counters:
                dedicated_usage = getattr(counter, 'DedicatedUsage', 0)
                shared_usage = getattr(counter, 'SharedUsage', 0)
                
                if dedicated_usage:
                    dedicated_mb = int(dedicated_usage) // (1024*1024)
                    if dedicated_mb > max_dedicated:
                        max_dedicated = dedicated_mb
                
                if shared_usage:
                    shared_mb = int(shared_usage) // (1024*1024)
                    if shared_mb > max_shared:
                        max_shared = shared_mb
            
            # ALWAYS use fresh data - no cache checking
            memory_data["dedicated_used_mb"] = max_dedicated
            memory_data["shared_used_mb"] = max_shared
            
            # Calculate usage percentage
            if memory_data["dedicated_total_mb"] > 0:
                memory_data["usage_percent"] = (memory_data["dedicated_used_mb"] / memory_data["dedicated_total_mb"]) * 100
            
            # Clean up WMI connection and COM
            del wmi_conn
            pythoncom.CoUninitialize()
                    
        except Exception as e:
            print(f"GPU memory error: {e}")
        
        return memory_data
    

    
    def refresh_data(self):
        """Refresh all data from Ollama server"""
        try:
            self.installed_models = self.get_installed_models()
            self.running_models = self.get_running_models()
            self.update_model_lists()
            self.update_system_info()
        except Exception as e:
            print(f"Error refreshing data: {e}")
            self.show_error(f"Refresh failed: {e}")
    
    def update_model_lists(self):
        """Update the model list displays"""
        try:
            # Update installed models list
            if dpg.does_item_exist("installed_models_list"):
                dpg.delete_item("installed_models_list", children_only=True)
                
                if not self.installed_models:
                    with dpg.group(parent="installed_models_list"):
                        dpg.add_text("No models found or connection error")
                else:
                    for model in self.installed_models:
                        model_name = model.get("name", "Unknown")
                        size = model.get("size", 0)
                        size_gb = size / (1024**3) if size > 0 else 0
                        
                        with dpg.group(parent="installed_models_list", horizontal=True):
                            dpg.add_text(f"{model_name} ({size_gb:.1f}GB)")
                            dpg.add_button(
                                label="Load",
                                callback=self.create_load_callback(model_name),
                                width=50
                            )
                            dpg.add_button(
                                label="Info",
                                callback=self.create_info_callback(model_name),
                                width=40
                            )
            
            # Update running models list
            if dpg.does_item_exist("running_models_list"):
                dpg.delete_item("running_models_list", children_only=True)
                
                if not self.running_models:
                    with dpg.group(parent="running_models_list"):
                        dpg.add_text("No models currently loaded")
                else:
                    for model in self.running_models:
                        model_name = model.get("name", "Unknown")
                        size = model.get("size", 0)
                        size_gb = size / (1024**3) if size > 0 else 0
                        
                        with dpg.group(parent="running_models_list", horizontal=True):
                            dpg.add_text(f"{model_name} ({size_gb:.1f}GB)")
                            dpg.add_button(
                                label="Unload",
                                callback=self.create_unload_callback(model_name),
                                width=60
                            )
                            
        except Exception as e:
            print(f"Error updating model lists: {e}")
            if dpg.does_item_exist("installed_models_list"):
                dpg.delete_item("installed_models_list", children_only=True)
                with dpg.group(parent="installed_models_list"):
                    dpg.add_text(f"Error: {e}")
            if dpg.does_item_exist("running_models_list"):
                dpg.delete_item("running_models_list", children_only=True)
                with dpg.group(parent="running_models_list"):
                    dpg.add_text(f"Error: {e}")
        
        # Update model selection combo for presets
        try:
            if dpg.does_item_exist("model_select_combo") and self.installed_models:
                model_names = [model.get("name", "Unknown") for model in self.installed_models]
                dpg.configure_item("model_select_combo", items=model_names)
        except Exception as e:
            print(f"Error updating model selection combo: {e}")
    
    def update_system_info(self):
        """Update system information display"""
        sys_info = self.get_system_info()
        
        # Update basic system info
        if dpg.does_item_exist("memory_text"):
            dpg.set_value("memory_text", 
                f"Memory: {sys_info['memory_used_gb']:.1f}GB / {sys_info['memory_total_gb']:.1f}GB ({sys_info['memory_percent']:.1f}%)")
        
        if dpg.does_item_exist("cpu_text"):
            dpg.set_value("cpu_text", f"CPU: {sys_info['cpu_percent']:.1f}%")
        
        # Update detailed GPU usage information
        gpu_usage = sys_info.get('gpu_usage_data', {})
        gpu_memory = sys_info.get('gpu_memory', {})
        
        # Update GPU engine usage displays
        if dpg.does_item_exist("gpu_overall_usage"):
            overall = gpu_usage.get('overall_percent', 0.0)
            dpg.set_value("gpu_overall_usage", f"{overall:.1f}%")
            
        if dpg.does_item_exist("gpu_3d_usage"):
            engine_3d = gpu_usage.get('3d_percent', 0.0)
            dpg.set_value("gpu_3d_usage", f"{engine_3d:.1f}%")
            
        if dpg.does_item_exist("gpu_compute_usage"):
            compute = gpu_usage.get('compute_percent', 0.0)
            dpg.set_value("gpu_compute_usage", f"{compute:.1f}%")
            
        if dpg.does_item_exist("gpu_copy_usage"):
            copy = gpu_usage.get('copy_percent', 0.0)
            dpg.set_value("gpu_copy_usage", f"{copy:.1f}%")
            
        if dpg.does_item_exist("gpu_video_usage"):
            video = gpu_usage.get('video_percent', 0.0)
            dpg.set_value("gpu_video_usage", f"{video:.1f}%")
        
        # Update GPU memory displays
        if dpg.does_item_exist("gpu_vram_usage"):
            dedicated_used = gpu_memory.get('dedicated_used_mb', 0)
            dedicated_total = gpu_memory.get('dedicated_total_mb', 0)
            usage_percent = gpu_memory.get('usage_percent', 0.0)
            
            if dedicated_total > 0:
                vram_text = f"{dedicated_used} MB / {dedicated_total} MB ({usage_percent:.1f}%)"
            else:
                vram_text = f"{dedicated_used} MB (Total Unknown)"
            dpg.set_value("gpu_vram_usage", vram_text)
            
        if dpg.does_item_exist("gpu_shared_usage"):
            shared_used = gpu_memory.get('shared_used_mb', 0)
            shared_total = gpu_memory.get('shared_total_mb', 0)
            
            if shared_total > 0:
                shared_text = f"{shared_used} MB / {shared_total} MB"
            else:
                shared_text = f"{shared_used} MB"
            dpg.set_value("gpu_shared_usage", shared_text)
        
        # Update GPU info text (basic info)
        if dpg.does_item_exist("gpu_text"):
            gpu_info = sys_info['gpu_info']
            dpg.set_value("gpu_text", f"GPU: {gpu_info}")
    
    def create_load_callback(self, model_name: str):
        """Create a load callback with proper closure"""
        def callback(sender, app_data):
            self.load_model_callback(model_name)
        return callback
    
    def create_unload_callback(self, model_name: str):
        """Create an unload callback with proper closure"""
        def callback(sender, app_data):
            self.unload_model_callback(model_name)
        return callback
    
    def create_info_callback(self, model_name: str):
        """Create an info callback with proper closure"""
        def callback(sender, app_data):
            self.show_model_info_callback(model_name)
        return callback

    def load_model_callback(self, model_name: str):
        """Callback for load model button"""
        print(f"Loading model: {model_name} with params: {self.current_params}")
        self.show_success(f"Loading model '{model_name}'...")
        threading.Thread(target=self.load_model, args=(model_name, self.current_params), daemon=True).start()
    
    def unload_model_callback(self, model_name: str):
        """Callback for unload model button"""
        threading.Thread(target=self.unload_model, args=(model_name,), daemon=True).start()
    
    def show_model_info_callback(self, model_name: str):
        """Show detailed model information in a popup"""
        def show_info():
            model_info = self.get_model_info(model_name)
            if not model_info:
                return
            
            # Extract key information
            template = model_info.get("template", "N/A")
            parameters = model_info.get("parameters", "N/A")
            modelfile = model_info.get("modelfile", "")
            
            # Try to extract context length from modelfile or use model defaults
            context_length = "Unknown"
            if modelfile:
                import re
                # First try PARAMETER format
                ctx_match = re.search(r'PARAMETER\s+num_ctx\s+(\d+)', modelfile, re.IGNORECASE)
                if not ctx_match:
                    # Try simple num_ctx format
                    ctx_match = re.search(r'num_ctx\s+(\d+)', modelfile, re.IGNORECASE)
                
                if ctx_match:
                    context_length = f"{int(ctx_match.group(1)):,}"
                else:
                    # Use known defaults for common models
                    model_lower = model_name.lower()
                    if 'qwen2.5' in model_lower:
                        context_length = "32,768"  # Qwen2.5 default context length
                    elif 'qwen2' in model_lower:
                        context_length = "32,768"  # Qwen2 default context length
                    elif 'qwen' in model_lower:
                        context_length = "8,192"   # Qwen1 default context length
                    elif 'llama' in model_lower:
                        if '3' in model_lower:
                            context_length = "128,000"  # Llama 3 extended context
                        else:
                            context_length = "4,096"    # Llama 2 default
                    elif 'mistral' in model_lower:
                        context_length = "32,768"  # Mistral default
                    elif 'gemma' in model_lower:
                        context_length = "8,192"   # Gemma default
            
            # Create info popup
            with dpg.window(label=f"Model Info: {model_name}", modal=True, show=True, 
                          width=600, height=400, pos=[100, 100]):
                dpg.add_text(f"Model: {model_name}", color=(150, 255, 150))
                dpg.add_separator()
                
                dpg.add_text(f"Context Length: {context_length}")
                dpg.add_text(f"Template: {template}")
                
                if isinstance(parameters, str) and parameters != "N/A":
                    dpg.add_text("Parameters:")
                    dpg.add_input_text(
                        default_value=parameters,
                        multiline=True,
                        readonly=True,
                        height=150,
                        width=550
                    )
                
                if modelfile:
                    dpg.add_text("Modelfile:")
                    dpg.add_input_text(
                        default_value=modelfile,
                        multiline=True,
                        readonly=True,
                        height=100,
                        width=550
                    )
                
                dpg.add_button(
                    label="Close",
                    callback=lambda: dpg.delete_item(dpg.last_container())
                )
        
        threading.Thread(target=show_info, daemon=True).start()
    
    def parameter_changed(self, sender, value, param_name):
        """Callback for parameter changes"""
        self.current_params[param_name] = value
    
    def set_inference_preset(self, preset_type):
        """Set GPU/CPU inference presets"""
        if preset_type == "cpu_only":
            self.current_params["num_gpu"] = 0
            dpg.set_value("num_gpu_input", 0)
            self.show_success("Set to CPU-only inference")
            
        elif preset_type == "gpu_only":
            self.current_params["num_gpu"] = 999  # Very high number = all layers
            dpg.set_value("num_gpu_input", 999)
            self.show_success("Set to GPU-only inference")
            
        elif preset_type == "auto":
            self.current_params["num_gpu"] = -1
            dpg.set_value("num_gpu_input", -1)
            self.show_success("Set to auto-balance inference")
    
    def save_preset_callback(self):
        """Save current parameters as a preset"""
        if not self.selected_model:
            self.show_error("Please select a model first")
            return
        
        preset_name = dpg.get_value("preset_name_input")
        if not preset_name:
            self.show_error("Please enter a preset name")
            return
        
        if self.selected_model not in self.presets:
            self.presets[self.selected_model] = {}
        
        self.presets[self.selected_model][preset_name] = self.current_params.copy()
        self.save_presets()
        self.update_preset_combo()
        self.show_success(f"Preset '{preset_name}' saved for {self.selected_model}")
    
    def load_preset_callback(self, sender, preset_name):
        """Load a preset configuration"""
        if not self.selected_model or self.selected_model not in self.presets:
            return
        
        if preset_name in self.presets[self.selected_model]:
            preset_params = self.presets[self.selected_model][preset_name]
            
            # Update current parameters
            self.current_params.update(preset_params)
            
            # Update UI controls
            dpg.set_value("temperature_slider", self.current_params["temperature"])
            dpg.set_value("top_k_input", self.current_params["top_k"])
            dpg.set_value("num_ctx_input", self.current_params["num_ctx"])
            dpg.set_value("keep_alive_input", self.current_params["keep_alive"])
            dpg.set_value("num_gpu_input", self.current_params.get("num_gpu", -1))
            dpg.set_value("main_gpu_input", self.current_params.get("main_gpu", 0))
            dpg.set_value("numa_checkbox", self.current_params.get("numa", False))
            
            self.show_success(f"Loaded preset '{preset_name}'")
    
    def load_preset_button_callback(self):
        """Callback for the Load Preset button"""
        if not self.selected_model:
            self.show_error("Please select a model first")
            return
        
        selected_preset = dpg.get_value("preset_dropdown")
        if not selected_preset or selected_preset == "No presets available":
            self.show_error("Please select a preset to load")
            return
        
        # Load the selected preset and the model
        self.load_preset_callback(None, selected_preset)
        
        # Load the model with the preset parameters
        self.show_success(f"Loading model '{self.selected_model}' with preset '{selected_preset}'...")
        threading.Thread(target=self.load_model, args=(self.selected_model, self.current_params), daemon=True).start()
    
    def model_selected_callback(self, sender, model_name):
        """Callback for model selection"""
        self.selected_model = model_name
        self.update_preset_combo()
    
    def update_preset_combo(self):
        """Update the preset combo box for the selected model"""
        if dpg.does_item_exist("preset_dropdown"):
            if self.selected_model and self.selected_model in self.presets:
                presets = list(self.presets[self.selected_model].keys())
                if presets:
                    dpg.configure_item("preset_dropdown", items=presets)
                else:
                    dpg.configure_item("preset_dropdown", items=["No presets available"])
            else:
                dpg.configure_item("preset_dropdown", items=["No presets available"])
    
    def auto_refresh_worker(self):
        """Background worker for auto-refreshing data"""
        while self.running:
            time.sleep(self.refresh_interval)
            if self.running:
                # Refresh models every cycle (fast)
                self.refresh_models()
                
                # Refresh system info every cycle for real-time GPU monitoring
                self.refresh_system_info()
                
    def refresh_models(self):
        """Fast refresh for just model data"""
        try:
            # Fetch models from server (this is fast)
            self.installed_models = self.get_installed_models()
            self.running_models = self.get_running_models()
            # Update UI model lists
            self.update_model_lists()
        except Exception as e:
            print(f"Model refresh error: {e}")
            
    def refresh_system_info(self):
        """Slower refresh for system monitoring data"""
        try:
            # Update system information (this can be slow)
            self.update_system_info()
        except Exception as e:
            print(f"System info refresh error: {e}")
    
    def update_system_info(self):
        """Update system information display using lightweight WMI"""
        try:
            # Get system memory info
            memory = psutil.virtual_memory()
            memory_text = f"Memory: {memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB ({memory.percent:.1f}%)"
            if dpg.does_item_exist("memory_text"):
                dpg.set_value("memory_text", memory_text)
            
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_text = f"CPU: {cpu_percent:.1f}%"
            if dpg.does_item_exist("cpu_text"):
                dpg.set_value("cpu_text", cpu_text)
            
            # Get GPU usage data
            gpu_usage = self.get_gpu_usage()
            if dpg.does_item_exist("gpu_overall_usage"):
                dpg.set_value("gpu_overall_usage", f"{gpu_usage['overall_usage']:.1f}%")
            if dpg.does_item_exist("gpu_3d_usage"):
                dpg.set_value("gpu_3d_usage", f"{gpu_usage['usage_3d']:.1f}%")
            if dpg.does_item_exist("gpu_compute_usage"):
                dpg.set_value("gpu_compute_usage", f"{gpu_usage['usage_compute']:.1f}%")
            if dpg.does_item_exist("gpu_copy_usage"):
                dpg.set_value("gpu_copy_usage", f"{gpu_usage['usage_copy']:.1f}%")
            if dpg.does_item_exist("gpu_video_usage"):
                dpg.set_value("gpu_video_usage", f"{gpu_usage['usage_video']:.1f}%")
            
            # Get GPU memory data
            gpu_memory = self.get_gpu_memory_usage()
            
            # Debug logging to see what's happening
            print(f"DEBUG: GPU memory data: {gpu_memory}")
            
            # Update VRAM display
            if gpu_memory["dedicated_total_mb"] > 0:
                vram_text = f"{gpu_memory['dedicated_used_mb']} MB / {gpu_memory['dedicated_total_mb']} MB ({gpu_memory['usage_percent']:.1f}%)"
            else:
                vram_text = f"{gpu_memory['dedicated_used_mb']} MB (Total Unknown)"
            
            print(f"DEBUG: Setting VRAM text to: {vram_text}")
            
            if dpg.does_item_exist("gpu_vram_usage"):
                dpg.set_value("gpu_vram_usage", vram_text)
                print("DEBUG: VRAM text updated successfully")
            else:
                print("DEBUG: gpu_vram_usage element doesn't exist!")
            
            # Update shared memory display
            shared_text = f"{gpu_memory['shared_used_mb']} MB"
            print(f"DEBUG: Setting shared memory text to: {shared_text}")
            
            if dpg.does_item_exist("gpu_shared_usage"):
                dpg.set_value("gpu_shared_usage", shared_text)
                print("DEBUG: Shared memory text updated successfully")
            else:
                print("DEBUG: gpu_shared_usage element doesn't exist!")
            
            # Get GPU info (only update occasionally to avoid spam)
            if not hasattr(self, '_last_gpu_info_update'):
                self._last_gpu_info_update = 0
            
            current_time = time.time()
            if current_time - self._last_gpu_info_update > 10:  # Update every 10 seconds
                self._last_gpu_info_update = current_time
                gpu_info = "AMD Radeon RX 7900 XT (4GB) [Vulkan/OpenCL]"  # Your known GPU
                if dpg.does_item_exist("gpu_text"):
                    dpg.set_value("gpu_text", f"GPU: {gpu_info}")
            
        except Exception as e:
            print(f"Error updating system info: {e}")
            # Set error state
            if dpg.does_item_exist("memory_text"):
                dpg.set_value("memory_text", "Memory: Error")
            if dpg.does_item_exist("cpu_text"):
                dpg.set_value("cpu_text", "CPU: Error")
            if dpg.does_item_exist("gpu_vram_usage"):
                dpg.set_value("gpu_vram_usage", "VRAM: Error")
    
    def refresh_data(self):
        """Legacy method - now calls separate refresh methods"""
        self.refresh_models()
        self.refresh_system_info()
    
    def setup_gui(self):
        """Initialize the Dear PyGui interface"""
        dpg.create_context()
        
        # Configure theme
        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (25, 25, 25))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (70, 70, 70))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (90, 90, 90))
        
        dpg.bind_theme(global_theme)
        
        # Main window
        with dpg.window(label="Ollama Server Control Panel", tag="main_window"):
            
            # Status bar and controls
            with dpg.group(horizontal=True):
                dpg.add_text("Ready", tag="status_text")
                dpg.add_button(
                    label="❌ Close App",
                    callback=lambda: dpg.stop_dearpygui(),
                    width=100
                )
            dpg.add_separator()
            
            # Control buttons
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="🔄 Refresh Data",
                    callback=lambda: threading.Thread(target=self.refresh_data, daemon=True).start(),
                    width=120
                )
                dpg.add_button(
                    label="🧪 Test Connection",
                    callback=lambda: threading.Thread(target=self.test_connection, daemon=True).start(),
                    width=120
                )
                dpg.add_button(
                    label="🖥️ Retry GPU Detection",
                    callback=lambda: self.retry_gpu_detection(),
                    width=140
                )
            dpg.add_separator()
            
            # System Information Panel
            with dpg.collapsing_header(label="📊 System Information", default_open=True):
                dpg.add_text("Memory: Loading...", tag="memory_text")
                dpg.add_text("CPU: Loading...", tag="cpu_text")
                
                dpg.add_separator()
                dpg.add_text("🎮 GPU Usage", color=(100, 200, 255))
                
                with dpg.group(horizontal=True):
                    dpg.add_text("Overall:")
                    dpg.add_text("0.0%", tag="gpu_overall_usage")
                    
                with dpg.group(horizontal=True):
                    dpg.add_text("3D Engine:")
                    dpg.add_text("0.0%", tag="gpu_3d_usage")
                    
                with dpg.group(horizontal=True):
                    dpg.add_text("Compute:")
                    dpg.add_text("0.0%", tag="gpu_compute_usage")
                    
                with dpg.group(horizontal=True):
                    dpg.add_text("Copy Engine:")
                    dpg.add_text("0.0%", tag="gpu_copy_usage")
                    
                with dpg.group(horizontal=True):
                    dpg.add_text("Video Engine:")
                    dpg.add_text("0.0%", tag="gpu_video_usage")
                
                dpg.add_separator()
                dpg.add_text("💾 GPU Memory", color=(255, 200, 100))
                
                with dpg.group(horizontal=True):
                    dpg.add_text("Dedicated VRAM:")
                    dpg.add_text("0 MB / 0 MB (0%)", tag="gpu_vram_usage")
                    
                with dpg.group(horizontal=True):
                    dpg.add_text("Shared Memory:")
                    dpg.add_text("0 MB / 0 MB", tag="gpu_shared_usage")
                
                dpg.add_separator()
                dpg.add_text("GPU: Loading...", tag="gpu_text")

            
            dpg.add_separator()
            
            # Model Management Panels
            with dpg.group(horizontal=True):
                
                # Installed Models Panel
                with dpg.child_window(width=350, height=300, label="Installed Models"):
                    dpg.add_text("📦 Installed Models", color=(150, 255, 150))
                    dpg.add_separator()
                    with dpg.group(tag="installed_models_list"):
                        dpg.add_text("Loading models...")
                
                # Running Models Panel
                with dpg.child_window(width=350, height=300, label="Running Models"):
                    dpg.add_text("🚀 Running Models", color=(255, 150, 150))
                    dpg.add_separator()
                    with dpg.group(tag="running_models_list"):
                        dpg.add_text("Loading models...")
            
            dpg.add_separator()
            
            # Parameter Control Panel
            with dpg.collapsing_header(label="⚙️ Model Parameters", default_open=True):
                
                with dpg.group(horizontal=True):
                    # Parameter controls
                    with dpg.group():
                        dpg.add_text("Temperature:")
                        dpg.add_slider_float(
                            label="##temperature",
                            default_value=0.7,
                            min_value=0.0,
                            max_value=2.0,
                            format="%.2f",
                            callback=lambda s, v: self.parameter_changed(s, v, "temperature"),
                            tag="temperature_slider",
                            width=200
                        )
                        
                        dpg.add_text("Top K:")
                        dpg.add_input_int(
                            label="##top_k",
                            default_value=40,
                            min_value=1,
                            max_value=100,
                            callback=lambda s, v: self.parameter_changed(s, v, "top_k"),
                            tag="top_k_input",
                            width=200
                        )
                    
                    with dpg.group():
                        dpg.add_text("Context Size (num_ctx):")
                        dpg.add_input_int(
                            label="##num_ctx",
                            default_value=8192,
                            min_value=512,
                            max_value=2097152,  # 2M context max
                            callback=lambda s, v: self.parameter_changed(s, v, "num_ctx"),
                            tag="num_ctx_input",
                            width=200
                        )
                        
                        dpg.add_text("Keep Alive (seconds, -1=forever):")
                        dpg.add_input_int(
                            label="##keep_alive",
                            default_value=-1,
                            min_value=-1,
                            max_value=3600,
                            callback=lambda s, v: self.parameter_changed(s, v, "keep_alive"),
                            tag="keep_alive_input",
                            width=200
                        )
            
            dpg.add_separator()
            
            # GPU/CPU Inference Control Panel
            with dpg.collapsing_header(label="🖥️ GPU/CPU Inference Control", default_open=True):
                dpg.add_text("Control how Ollama distributes model layers between GPU and CPU", color=(200, 200, 200))
                
                with dpg.group(horizontal=True):
                    # GPU Controls - Left column
                    with dpg.group():
                        dpg.add_text("GPU Layers (num_gpu):")
                        dpg.add_input_int(
                            label="##num_gpu",
                            default_value=-1,
                            min_value=-1,
                            max_value=200,  # Most models have <200 layers
                            callback=lambda s, v: self.parameter_changed(s, v, "num_gpu"),
                            tag="num_gpu_input",
                            width=200
                        )
                        dpg.add_text("-1=Auto, 0=CPU only, >0=GPU layers", color=(150, 150, 150))
                        
                        dpg.add_text("Main GPU (multi-GPU setups):")
                        dpg.add_input_int(
                            label="##main_gpu",
                            default_value=0,
                            min_value=0,
                            max_value=7,  # Support up to 8 GPUs
                            callback=lambda s, v: self.parameter_changed(s, v, "main_gpu"),
                            tag="main_gpu_input",
                            width=200
                        )
                    
                    # System Controls - Right column  
                    with dpg.group():
                        dpg.add_text("NUMA Support:")
                        dpg.add_checkbox(
                            label="Enable NUMA",
                            default_value=False,
                            callback=lambda s, v: self.parameter_changed(s, v, "numa"),
                            tag="numa_checkbox"
                        )
                        dpg.add_text("For multi-socket CPU systems", color=(150, 150, 150))
                        
                        dpg.add_text("Quick Presets:")
                        with dpg.group():
                            dpg.add_button(
                                label="🖥️ CPU Only",
                                callback=lambda: self.set_inference_preset("cpu_only"),
                                width=100
                            )
                            dpg.add_button(
                                label="⚡ GPU Only", 
                                callback=lambda: self.set_inference_preset("gpu_only"),
                                width=100
                            )
                            dpg.add_button(
                                label="🔄 Auto Balance",
                                callback=lambda: self.set_inference_preset("auto"),
                                width=100
                            )
            
            dpg.add_separator()
            
            # Preset Management Panel
            with dpg.collapsing_header(label="💾 Parameter Presets", default_open=False):
                
                # Model selection for presets
                with dpg.group(horizontal=True, tag="model_selection_group"):
                    dpg.add_text("Select Model:")
                    # Placeholder - will be populated when models are loaded
                    dpg.add_combo(
                        ["Loading models..."],
                        label="##model_select",
                        callback=self.model_selected_callback,
                        width=200,
                        tag="model_select_combo"
                    )
                
                dpg.add_separator()
                
                # Preset save/load
                with dpg.group(horizontal=True, tag="preset_group"):
                    dpg.add_input_text(
                        label="Preset Name",
                        tag="preset_name_input",
                        width=150
                    )
                    dpg.add_button(
                        label="Save Preset",
                        callback=self.save_preset_callback
                    )
                    dpg.add_combo(
                        ["No presets available"],
                        label="##preset_dropdown",
                        tag="preset_dropdown",
                        width=150
                    )
                    dpg.add_button(
                        label="Load Preset",
                        callback=self.load_preset_button_callback
                    )
        
        # Set main window as primary
        dpg.create_viewport(title="Ollama Control Panel", width=800, height=900)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)
    
    def run(self):
        """Run the application"""
        try:
            self.running = True
            
            # Start auto-refresh thread
            refresh_thread = threading.Thread(target=self.auto_refresh_worker, daemon=True)
            refresh_thread.start()
            
            # Initial data load (with delay to let GUI initialize)
            def delayed_refresh():
                time.sleep(1)  # Give GUI time to initialize
                self.refresh_data()
            
            threading.Thread(target=delayed_refresh, daemon=True).start()
            
            # Main GUI loop
            dpg.start_dearpygui()
            
        except Exception as e:
            print(f"Error in main loop: {e}")
            import traceback
            traceback.print_exc()
            input("Press Enter to continue...")
        finally:
            # Cleanup
            self.running = False
            try:
                dpg.destroy_context()
            except:
                pass


def main():
    """Main entry point"""
    try:
        # Setup basic logging before app creation
        import logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)
        
        logger.info("Starting Ollama Control Panel...")
        app = OllamaControlPanel()
        logger.info("App initialized successfully")
        app.run()
        logger.info("App closed normally")
    except Exception as e:
        import logging
        logging.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
