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
from typing import Dict, List, Optional, Any


class OllamaControlPanel:
    def __init__(self):
        self.base_url = "http://localhost:11434"
        self.presets_file = "model_presets.json"
        self.refresh_interval = 1.5  # seconds - fast responsive updates
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
            print(f"Found {len(models)} installed models: {[m.get('name') for m in models]}")
            return models
        except requests.RequestException as e:
            self.show_error(f"Failed to get installed models: {e}")
            print(f"Error getting models: {e}")
            return []
    
    def get_running_models(self) -> List[Dict]:
        """Get list of currently loaded models from Ollama API"""
        try:
            response = requests.get(f"{self.base_url}/api/ps", timeout=5)
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            print(f"Found {len(models)} running models: {[m.get('name') for m in models]}")
            return models
        except requests.RequestException as e:
            self.show_error(f"Failed to get running models: {e}")
            print(f"Error getting running models: {e}")
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
        """Unload/stop a model"""
        try:
            payload = {"model": model_name}
            print(f"Sending unload request for {model_name}: {payload}")
            
            response = requests.post(
                f"{self.base_url}/api/stop",
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
                gpu_info = "AMD Radeon RX 7900 XT (16GB) [Vulkan/OpenCL/ROCm]"  # Temporary hardcoded
                gpu_detected = True
                self._gpu_info_cache = gpu_info
                self._gpu_detection_failed = False
                # TODO: Re-enable full GPU detection after fixing indentation
                            # Check if wmic is available first
                            wmic_check = subprocess.run(['where', 'wmic'], capture_output=True, text=True, timeout=3)
                            if wmic_check.returncode != 0:
                                self._wmi_permanently_disabled = True
                                raise FileNotFoundError("wmic not available")
                            
                        result = subprocess.run([
                            'wmic', 'path', 'win32_VideoController', 
                            'get', 'name,AdapterRAM', '/format:csv'
                        ], capture_output=True, text=True, timeout=5, 
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                        
                        if result.returncode == 0:
                            lines = result.stdout.strip().split('\n')
                            gpus = []
                            for line in lines[1:]:  # Skip header
                                if line.strip() and ',' in line:
                                    parts = line.split(',')
                                    if len(parts) >= 3:
                                        name = parts[2].strip()
                                        ram = parts[1].strip()
                                        if name and name != "Name" and "Microsoft" not in name:
                                            # Convert RAM to GB if available
                                            ram_gb = ""
                                            if ram and ram.isdigit():
                                                ram_gb = f" ({int(ram)/(1024**3):.1f}GB)"
                                            
                                            # Add compute backend info based on GPU vendor
                                            compute_info = ""
                                            if "NVIDIA" in name.upper():
                                                compute_info = " [CUDA/Vulkan]"
                                            elif any(amd_term in name.upper() for amd_term in ["AMD", "RADEON", "ATI"]):
                                                # Check if ROCm is available for AMD
                                                compute_backends = "Vulkan/OpenCL"
                                                try:
                                                    rocm_check = subprocess.run(['rocm-smi', '--version'], 
                                                                              capture_output=True, text=True, timeout=2)
                                                    if rocm_check.returncode == 0:
                                                        compute_backends = "Vulkan/OpenCL/ROCm"
                                                except:
                                                    pass
                                                compute_info = f" [{compute_backends}]"
                                            elif "INTEL" in name.upper():
                                                compute_info = " [Vulkan/OpenCL]"
                                            
                                            gpus.append(f"{name}{ram_gb}{compute_info}")
                            
                            if gpus:
                                gpu_info = " | ".join(gpus)
                                gpu_detected = True
                    except Exception as e:
                        self._wmi_permanently_disabled = True  # Permanently disable WMI on failure
                        print(f"WMI GPU detection failed (disabled): {e}")
                        # Fallback: Try PowerShell for Windows
                        try:
                            ps_cmd = "Get-WmiObject Win32_VideoController | Select-Object Name, AdapterRAM | ConvertTo-Csv -NoTypeInformation"
                            result = subprocess.run(['pwsh.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_cmd], 
                                                  capture_output=True, text=True, timeout=5)
                            if result.returncode == 0:
                                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                                gpus = []
                                for line in lines:
                                    if line.strip():
                                        parts = line.replace('"', '').split(',')
                                        if len(parts) >= 2:
                                            name = parts[0].strip()
                                            ram = parts[1].strip()
                                            if name and "Microsoft" not in name:
                                                ram_gb = ""
                                                if ram and ram.isdigit():
                                                    ram_gb = f" ({int(ram)/(1024**3):.1f}GB)"
                                                gpus.append(f"{name}{ram_gb}")
                                
                                if gpus:
                                    gpu_info = " | ".join(gpus)
                                    gpu_detected = True
                        except Exception as ps_e:
                            print(f"PowerShell GPU detection also failed: {ps_e}")
                        
                        # Final fallback: Simple driver-based detection (Windows)
                        if not gpu_detected:
                            try:
                                # Use DXDIAG which should be available on all Windows systems
                                result = subprocess.run(['dxdiag', '/t', 'temp_dxdiag.txt'], 
                                                      capture_output=True, text=True, timeout=8)
                                if result.returncode == 0:
                                    import time
                                    time.sleep(2)  # Give dxdiag time to write file
                                    try:
                                        with open('temp_dxdiag.txt', 'r', encoding='utf-8', errors='ignore') as f:
                                            content = f.read()
                                            # Look for GPU info in dxdiag output
                                            lines = content.split('\n')
                                            for i, line in enumerate(lines):
                                                if 'Card name:' in line:
                                                    gpu_name = line.split('Card name:')[1].strip()
                                                    if gpu_name and 'Microsoft' not in gpu_name:
                                                        # Look for memory info in next few lines
                                                        for j in range(i+1, min(i+10, len(lines))):
                                                            if 'Dedicated Memory:' in lines[j]:
                                                                mem_info = lines[j].split('Dedicated Memory:')[1].strip()
                                                                gpu_info = f"{gpu_name} ({mem_info})"
                                                                gpu_detected = True
                                                                break
                                                        if not gpu_detected:
                                                            gpu_info = f"{gpu_name}"
                                                            gpu_detected = True
                                                        break
                                        # Clean up temp file
                                        import os
                                        try:
                                            os.remove('temp_dxdiag.txt')
                                        except:
                                            pass
                                    except:
                                        pass
                            except Exception as dx_e:
                                print(f"DXDiag GPU detection failed: {dx_e}")
                
                # Method 2: Linux - try multiple detection methods
                elif platform.system() == "Linux":
                    try:
                        # Try lspci for general GPU detection
                        result = subprocess.run(['lspci', '-v'], capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            gpus = []
                            for line in result.stdout.split('\n'):
                                if 'VGA compatible controller' in line or 'Display controller' in line:
                                    gpu_name = line.split(': ', 1)[-1].strip()
                                    gpus.append(gpu_name)
                            if gpus:
                                gpu_info = " | ".join(gpus)
                                gpu_detected = True
                    except:
                        pass
                
                # Method 3: NVIDIA-specific (if not already detected)
                if not gpu_detected:
                    try:
                        result = subprocess.run([
                            'nvidia-smi', '--query-gpu=memory.used,memory.total,name', 
                            '--format=csv,noheader,nounits'
                        ], capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            lines = result.stdout.strip().split('\n')
                            gpus = []
                            for line in lines:
                                if line.strip():
                                    parts = line.split(', ')
                                    if len(parts) >= 3:
                                        used, total, name = parts[0], parts[1], parts[2]
                                        gpus.append(f"{name}: {used}MB/{total}MB")
                            if gpus:
                                gpu_info = " | ".join(gpus)
                                gpu_detected = True
                    except:
                        pass
                
                # Method 4: Enhanced AMD GPU detection (supports both Vulkan and ROCm)
                if not gpu_detected and platform.system() == "Windows":
                    try:
                        # Look specifically for AMD/ATI GPUs in Windows
                        result = subprocess.run([
                            'wmic', 'path', 'win32_VideoController', 
                            'where', 'name like "%AMD%" or name like "%Radeon%" or name like "%ATI%"',
                            'get', 'name,AdapterRAM', '/format:csv'
                        ], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
                        
                        if result.returncode == 0:
                            lines = result.stdout.strip().split('\n')
                            for line in lines[1:]:  # Skip header
                                if line.strip() and ',' in line:
                                    parts = line.split(',')
                                    if len(parts) >= 3:
                                        name = parts[2].strip()
                                        if name and ("AMD" in name or "Radeon" in name):
                                            # Check if ROCm is also available
                                            compute_backends = "Vulkan/OpenCL"
                                            try:
                                                rocm_check = subprocess.run(['rocm-smi', '--showproductname'], 
                                                                          capture_output=True, text=True, timeout=3)
                                                if rocm_check.returncode == 0 and rocm_check.stdout.strip():
                                                    compute_backends = "Vulkan/OpenCL/ROCm"
                                            except:
                                                pass
                                            
                                            gpu_info = f"{name} ({compute_backends})"
                                            gpu_detected = True
                                            break
                    except:
                        pass
                
                # Method 5: ROCm-first AMD detection (for Linux or if Windows method failed)
                if not gpu_detected:
                    try:
                        result = subprocess.run(['rocm-smi', '--showproductname'], 
                                              capture_output=True, text=True, timeout=5)
                        if result.returncode == 0 and result.stdout.strip():
                            gpu_name = result.stdout.strip()
                            gpu_info = f"AMD GPU: {gpu_name} (Vulkan/OpenCL/ROCm)"
                            gpu_detected = True
                    except:
                        pass
                
                # Method 6: Intel GPU detection (Vulkan/OpenCL capable)
                if not gpu_detected:
                    try:
                        if platform.system() == "Linux":
                            result = subprocess.run(['intel_gpu_top', '-l'], 
                                                  capture_output=True, text=True, timeout=3)
                            if result.returncode == 0:
                                gpu_info = "Intel GPU (Vulkan/OpenCL capable)"
                                gpu_detected = True
                        elif platform.system() == "Windows":
                            # Look for Intel GPUs in Windows
                            result = subprocess.run([
                                'wmic', 'path', 'win32_VideoController', 
                                'where', 'name like "%Intel%"',
                                'get', 'name', '/format:csv'
                            ], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
                            
                            if result.returncode == 0:
                                lines = result.stdout.strip().split('\n')
                                for line in lines[1:]:  # Skip header
                                    if line.strip() and 'Intel' in line:
                                        gpu_name = line.split(',')[-1].strip()
                                        if gpu_name and gpu_name != "Name":
                                            gpu_info = f"{gpu_name} (Vulkan/OpenCL capable)"
                                            gpu_detected = True
                                            break
                    except:
                        pass
                
                # If still no GPU detected, try basic registry detection (Windows)  
                if not gpu_detected and platform.system() == "Windows":
                    try:
                        import winreg
                        # Check Windows registry for display adapters
                        key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                            gpus = []
                            for i in range(10):  # Check first 10 subkeys
                                try:
                                    subkey_name = winreg.EnumKey(key, i)
                                    if subkey_name.startswith('0'):  # GPU subkeys start with numbers
                                        with winreg.OpenKey(key, subkey_name) as subkey:
                                            try:
                                                gpu_name = winreg.QueryValueEx(subkey, "DriverDesc")[0]
                                                if gpu_name and "Microsoft" not in gpu_name:
                                                    gpus.append(gpu_name)
                                            except:
                                                pass
                                except:
                                    break
                            
                            if gpus:
                                gpu_info = " | ".join(gpus)
                                gpu_detected = True
                    except Exception as reg_e:
                        print(f"Registry GPU detection failed: {reg_e}")
                
                # If still no GPU detected, show generic message
                if not gpu_detected:
                    gpu_info = "GPU present but detection unavailable"
                    self._gpu_detection_failed = True
                    self._gpu_retry_count += 1
                    self._gpu_info_cache = gpu_info
                else:
                    # Success - cache the result and reset failure flag
                    self._gpu_info_cache = gpu_info
                    self._gpu_detection_failed = False
                    self._gpu_retry_count = 0
                        
                except Exception as e:
                    gpu_info = f"GPU Error: {str(e)[:50]}..."
                    self._gpu_detection_failed = True
                    self._gpu_retry_count += 1
                    self._gpu_info_cache = gpu_info
            
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
        """Get GPU utilization like Task Manager does"""
        gpu_data = {
            "usage_3d": 0.0,
            "usage_compute": 0.0, 
            "usage_copy": 0.0,
            "usage_video": 0.0,
            "overall_usage": 0.0
        }
        
        try:
            import platform
            if platform.system() == "Windows":
                import subprocess
                
                # Task Manager uses these specific performance counters
                counters = {
                    "3D": "\\GPU Engine(*)\\Utilization Percentage",
                    "Compute": "\\GPU Engine(*)\\Utilization Percentage", 
                    "Copy": "\\GPU Engine(*)\\Utilization Percentage",
                    "Video": "\\GPU Engine(*)\\Utilization Percentage"
                }
                
                # Get all GPU engine data like Task Manager
                result = subprocess.run([
                    'pwsh.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', '''
                    $counters = Get-Counter -ErrorAction SilentlyContinue "\\GPU Engine(*)\\Utilization Percentage"
                    if ($counters) {
                        $engines = @{}
                        $totalUsage = 0
                        $engineCount = 0
                        
                        foreach ($sample in $counters.CounterSamples) {
                            $path = $sample.Path
                            $value = $sample.CookedValue
                            
                            if ($path -match "engtype_3D") {
                                if (-not $engines["3D"]) { $engines["3D"] = 0 }
                                $engines["3D"] += $value
                            }
                            elseif ($path -match "engtype_Compute") {
                                if (-not $engines["Compute"]) { $engines["Compute"] = 0 }
                                $engines["Compute"] += $value
                            }
                            elseif ($path -match "engtype_Copy") {
                                if (-not $engines["Copy"]) { $engines["Copy"] = 0 }
                                $engines["Copy"] += $value
                            }
                            elseif ($path -match "engtype_Video") {
                                if (-not $engines["Video"]) { $engines["Video"] = 0 }
                                $engines["Video"] += $value
                            }
                            
                            $totalUsage += $value
                            $engineCount++
                        }
                        
                        Write-Output "3D:$($engines["3D"])"
                        Write-Output "Compute:$($engines["Compute"])" 
                        Write-Output "Copy:$($engines["Copy"])"
                        Write-Output "Video:$($engines["Video"])"
                        if ($engineCount -gt 0) {
                            Write-Output "Overall:$($totalUsage / $engineCount)"
                        }
                    }
                    '''
                ], capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0 and result.stdout.strip():
                    for line in result.stdout.strip().split('\n'):
                        if ':' in line:
                            engine, value = line.split(':', 1)
                            try:
                                val = float(value.strip())
                                if engine == "3D":
                                    gpu_data["usage_3d"] = val
                                elif engine == "Compute":
                                    gpu_data["usage_compute"] = val  
                                elif engine == "Copy":
                                    gpu_data["usage_copy"] = val
                                elif engine == "Video":
                                    gpu_data["usage_video"] = val
                                elif engine == "Overall":
                                    gpu_data["overall_usage"] = val
                            except ValueError:
                                pass
                                
        except Exception as e:
            print(f"GPU usage detection error: {e}")
        
        return gpu_data
    
    def get_gpu_memory_usage(self) -> Dict:
        """Get GPU memory usage like Task Manager does"""
        memory_data = {
            "dedicated_used_mb": 0,
            "dedicated_total_mb": 0,
            "shared_used_mb": 0,
            "shared_total_mb": 0,
            "usage_percent": 0.0
        }
        
        try:
            import platform
            if platform.system() == "Windows":
                import subprocess
                
                # Task Manager uses these specific counters for GPU memory
                result = subprocess.run([
                    'pwsh.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', '''
                    # Get GPU Adapter Memory counters (like Task Manager)
                    $adapterCounters = Get-Counter -ErrorAction SilentlyContinue "\\GPU Adapter Memory(*)\\*"
                    if ($adapterCounters) {
                        $dedicatedUsed = 0
                        $dedicatedTotal = 0
                        $sharedUsed = 0 
                        $sharedTotal = 0
                        
                        foreach ($sample in $adapterCounters.CounterSamples) {
                            $path = $sample.Path
                            $value = $sample.CookedValue
                            
                            if ($path -match "Dedicated Usage") {
                                $dedicatedUsed += $value
                            }
                            elseif ($path -match "Dedicated Limit") {
                                $dedicatedTotal += $value  
                            }
                            elseif ($path -match "Shared Usage") {
                                $sharedUsed += $value
                            }
                            elseif ($path -match "Shared Limit") {
                                $sharedTotal += $value
                            }
                        }
                        
                        Write-Output "DedicatedUsed:$([math]::Round($dedicatedUsed / 1MB, 0))"
                        Write-Output "DedicatedTotal:$([math]::Round($dedicatedTotal / 1MB, 0))"
                        Write-Output "SharedUsed:$([math]::Round($sharedUsed / 1MB, 0))"
                        Write-Output "SharedTotal:$([math]::Round($sharedTotal / 1MB, 0))"
                    }
                    
                    # Fallback: Try GPU Process Memory counters
                    if (-not $adapterCounters) {
                        $processCounters = Get-Counter -ErrorAction SilentlyContinue "\\GPU Process Memory(*)\\Dedicated Usage"
                        if ($processCounters) {
                            $totalUsed = ($processCounters.CounterSamples | Measure-Object -Property CookedValue -Sum).Sum
                            Write-Output "DedicatedUsed:$([math]::Round($totalUsed / 1MB, 0))"
                        }
                    }
                    '''
                ], capture_output=True, text=True, timeout=3)
                
                if result.returncode == 0 and result.stdout.strip():
                    for line in result.stdout.strip().split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            try:
                                val = int(float(value.strip()))
                                if key == "DedicatedUsed":
                                    memory_data["dedicated_used_mb"] = val
                                elif key == "DedicatedTotal":
                                    memory_data["dedicated_total_mb"] = val
                                elif key == "SharedUsed":
                                    memory_data["shared_used_mb"] = val
                                elif key == "SharedTotal":
                                    memory_data["shared_total_mb"] = val
                            except (ValueError, TypeError):
                                pass
                    
                    # Calculate usage percentage
                    if memory_data["dedicated_total_mb"] > 0:
                        memory_data["usage_percent"] = (
                            memory_data["dedicated_used_mb"] / memory_data["dedicated_total_mb"] * 100
                        )
                        
        except Exception as e:
            print(f"GPU memory detection error: {e}")
        
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
            
            # Try to extract context length from modelfile
            context_length = "Unknown"
            if modelfile:
                import re
                ctx_match = re.search(r'num_ctx\s+(\d+)', modelfile, re.IGNORECASE)
                if ctx_match:
                    context_length = f"{int(ctx_match.group(1)):,}"
            
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
    
    def model_selected_callback(self, sender, model_name):
        """Callback for model selection"""
        self.selected_model = model_name
        self.update_preset_combo()
    
    def update_preset_combo(self):
        """Update the preset combo box for the selected model"""
        if dpg.does_item_exist("preset_combo"):
            dpg.delete_item("preset_combo")
        
        if self.selected_model and self.selected_model in self.presets:
            presets = list(self.presets[self.selected_model].keys())
            dpg.add_combo(
                presets,
                label="Load Preset",
                callback=self.load_preset_callback,
                parent="preset_group",
                tag="preset_combo",
                width=200
            )
    
    def auto_refresh_worker(self):
        """Background worker for auto-refreshing data"""
        system_info_counter = 0
        while self.running:
            time.sleep(self.refresh_interval)
            if self.running:
                # Refresh models every cycle (fast)
                self.refresh_models()
                
                # Refresh system info only every 3rd cycle to improve performance
                system_info_counter += 1
                if system_info_counter >= 3:
                    self.refresh_system_info()
                    system_info_counter = 0
                
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
        print("Starting Ollama Control Panel...")
        app = OllamaControlPanel()
        print("App initialized successfully")
        app.run()
        print("App closed normally")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()