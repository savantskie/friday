# Refined vLLM Fork Architecture Design
**Date**: November 11, 2025  
**Status**: Clarified based on Nate's feedback

## Core Principles
1. **Pure OpenAI API Compatibility** - Works with any OpenAI-compatible frontend
2. **Generic GPU Support** - Leverage vLLM's existing multi-GPU capabilities  
3. **Resource Awareness** - Monitor and warn about VRAM/RAM limitations
4. **User-Controlled Settings** - Remember last-used parameters, user decides whether to apply
5. **Configurable Model Paths** - Flexible model directory configuration
6. **Production Ready** - Robust error handling, monitoring, graceful operations

## Refined Architecture

```
┌─────────────────────────────────────────────────┐
│           OpenAI Compatible API Server          │
│  /v1/chat/completions, /v1/models             │
│  /models/load, /models/status, /models/optimize│
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│              ModelOrchestrator                  │
│  • Request routing to loaded models            │
│  • Resource monitoring & warnings             │  
│  • Parameter memory & user preferences        │
│  • Model lifecycle management                 │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│          vLLM Engine Pool                      │
│  AsyncLLM₁      AsyncLLM₂      AsyncLLM₃       │
│  (Auto GPU)     (Auto GPU)     (Auto GPU)      │
│  Model A        Model B         Model C        │
└─────────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│           System Resources                      │
│  CUDA/ROCm/Vulkan(?), VRAM/RAM monitoring     │
└─────────────────────────────────────────────────┘
```

## Key Components

### **1. ModelOrchestrator** (Core Component)
```python
class ModelOrchestrator:
    def __init__(self, config):
        self.engine_pool = EnginePool()
        self.resource_monitor = ResourceMonitor()
        self.model_catalog = ModelCatalog(config.model_paths)
        self.settings_memory = SettingsMemory()
    
    async def route_request(self, request):
        # Route to appropriate loaded model
    
    async def load_model(self, model_id, settings=None):
        # Check resources, load if possible, warn if not
    
    def get_optimization_suggestions(self, target_model):
        # Suggest settings based on resources & catalog
```

### **2. ResourceMonitor** (Cross-Platform)
```python
class ResourceMonitor:
    def get_gpu_info(self):
        # Support CUDA (nvidia-ml-py), ROCm (rocm-smi), Vulkan (investigate)
    
    def get_memory_info(self):
        # Linux: /proc/meminfo, cross-platform: psutil
    
    def estimate_model_requirements(self, model_config):
        # Calculate VRAM needs based on parameters, quantization
```

### **3. SettingsMemory** (User-Controlled)
```python
class SettingsMemory:
    def remember_settings(self, model_id, settings):
        # Store last-used parameters per model
    
    def get_suggested_settings(self, model_id):
        # Return last-used settings with user choice options
    
    def apply_or_dismiss(self, model_id, user_choice):
        # Handle user decision on suggested settings
```

## Configuration Example

```yaml
# vllm-fork-config.yaml
server:
  host: "0.0.0.0"
  port: 8000
  
models:
  paths:
    - "/home/nate/models"
    - "~/.cache/huggingface/hub"
  auto_discover: true
  
resources:
  warn_on_low_memory: true
  minimum_free_vram_gb: 2.0
  enable_vulkan: false  # experimental
  
settings_memory:
  enabled: true
  remember_for_days: 30
```

## Updated Implementation Phases

### **Phase 1: Foundation** (Week 1-2)
- Fork vLLM, make model parameter optional
- Basic "empty server" startup
- Simple model loading/unloading

### **Phase 2: Core Orchestration** (Week 3-4)  
- ModelOrchestrator with engine pool
- Resource monitoring (VRAM/RAM)
- Basic model catalog and discovery

### **Phase 3: Advanced Features** (Week 5-6)
- Settings memory with user choice
- Multi-model routing and management
- Resource warnings and optimization suggestions

### **Phase 4: Polish & Compatibility** (Week 7-8)
- Multiple frontend testing (OpenWebUI, Chatbot UI, etc.)
- Robust error handling and logging
- Configuration management

### **Phase 5: Production Ready** (Week 9-10)
- Load testing and performance optimization
- Documentation and examples
- Deployment guides (Docker, systemd, etc.)

Does this refined design align better with your vision? The key changes:
- ✅ Generic GPU support (not hardware-specific)
- ✅ OpenAI API compatibility (not frontend-specific)  
- ✅ User-controlled settings memory
- ✅ Resource awareness with warnings
- ✅ Configurable model paths
- ✅ Clearer implementation phases