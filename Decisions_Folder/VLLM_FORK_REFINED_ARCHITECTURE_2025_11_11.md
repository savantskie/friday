# Refined vLLM Fork Architecture Design
**Date**: November 11, 2025  
**Status**: Clarified based on Nate's feedback

## Core Principles
1. **Pure OpenAI API Compatibility** - Works with any OpenAI-compatible frontend
2. **Generic GPU Support** - Leverage vLLM's existing multi-GPU capabilities, investigate Vulkan (low priority)
3. **Smart Resource Management** - Warn users about limitations, allow override, graceful failure before system crash
4. **Global Model Settings Memory** - Remember last-used parameters per model globally (not per-user/frontend)
5. **Flexible Configuration** - Support YAML files, environment variables, and web-based setup UI
6. **Minimal Core Changes** - Preserve vLLM's inference behavior, only modify model loading behavior
7. **Easy Updates** - Architecture allows easier merging of upstream vLLM updates

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
        # Priority: CUDA (nvidia-ml-py), ROCm (rocm-smi)
        # Future: Vulkan support (Phase 5 investigation)
    
    def get_memory_info(self):
        # Linux: /proc/meminfo, cross-platform: psutil
    
    def estimate_model_requirements(self, model_config):
        # Calculate VRAM needs based on parameters, quantization
    
    def check_loading_safety(self, model_requirements):
        # Warn user of potential issues, allow override
        # Detect likely crashes before they happen
        return {"safe": bool, "warning": str, "allow_override": bool}
```

### **3. SettingsMemory** (Global Per-Model)
```python
class SettingsMemory:
    def remember_settings(self, model_id, settings):
        # Store last-used parameters per model globally
        # Not per-user or per-frontend - simple global memory
    
    def get_suggested_settings(self, model_id):
        # Return last-used settings for this model
        # User can apply, dismiss, or customize
    
    def apply_or_dismiss(self, model_id, user_choice):
        # Simple: apply last settings or start fresh
        # No complex user/session tracking needed
```

## Configuration Options (Multiple Methods)

### **Option 1: YAML Config File**
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
  warn_on_insufficient_memory: true
  allow_resource_override: true  # Let users ignore warnings
  crash_prevention: true        # Try to fail gracefully
  enable_vulkan: false         # Phase 5 investigation
  
settings_memory:
  enabled: true
  remember_for_days: 30
  global_per_model: true       # Not per-user tracking
```

### **Option 2: Environment Variables**
```bash
VLLM_FORK_HOST=0.0.0.0
VLLM_FORK_PORT=8000
VLLM_FORK_MODEL_PATHS="/home/nate/models,~/.cache/huggingface/hub"
VLLM_FORK_ALLOW_RESOURCE_OVERRIDE=true
VLLM_FORK_CRASH_PREVENTION=true
```

### **Option 3: Web-Based Setup UI**
- First-run configuration wizard
- Runtime settings adjustment
- Model path management
- Resource monitoring dashboard

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
- Multiple frontend testing (OpenWebUI, Chatbot UI, LibreChat, etc.)
- Robust error handling and graceful failure mechanisms
- All three configuration methods (YAML, ENV, Web UI)
- Resource override controls and crash prevention

### **Phase 5: Production Ready & Future Features** (Week 9-10)
- Load testing and performance optimization
- Documentation and deployment examples (Docker, systemd)
- **Vulkan support investigation** (low priority but user-requested)
- Upstream vLLM update integration testing

## Key Architectural Benefits

### **Easy vLLM Updates**
Since we're only modifying model loading behavior (not inference), merging upstream vLLM updates should be straightforward:
- Core inference engine remains untouched
- Changes focused on orchestration layer
- Minimal conflicts with upstream development

### **Resource Management Philosophy**
- **Warn, Don't Block**: Alert users to potential issues
- **User Override**: Allow experienced users to ignore warnings  
- **Graceful Failure**: Detect and prevent system crashes when possible
- **Safety Setting**: Option to completely disable warnings for power users

### **Simplicity Focus**
- **Global model settings** (not per-user complexity)
- **Pure model runner** (not a chat interface)
- **Minimal core changes** (preserve vLLM's strengths)
- **Multiple config options** (flexibility without forcing one approach)

This design addresses all feedback:
- ✅ Vulkan support as Phase 5 investigation (low priority)
- ✅ Global per-model settings memory (not per-user/frontend)
- ✅ Warn and allow override for resource issues
- ✅ Triple configuration support (YAML + ENV + Web UI)
- ✅ Focus on easy upstream updates
- ✅ Graceful failure mechanisms