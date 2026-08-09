#!/bin/bash
echo -ne "\033]0;Chatterbox-FridayTTS\007"
cd /media/nate/Friday/chatterbox-tts-api
export EXAGGERATION=0.5
export CFG_WEIGHT=0.8  # Faster pace control
export TEMPERATURE=0.3 # Less random = faster generation
export MAX_CHUNK_LENGTH=14000 # Fewer chunks per request
export MEMORY_CLEANUP_INTERVAL=10
export ENABLE_MEMORY_MONITORING=true
export HF_HUB_DISABLE_TELEMETRY=true
export MAX_TOTAL_LENGTH=14000
# Before python main.py, add:
export CUDA_VISIBLE_DEVICES=1
export TORCH_SDPA_ENABLE_ATTN=true  # Disable attention overhead on ROCm              
export HSA_OVERRIDE_GFX_VERSION=9.0.0
export HIP_PLATFORM=amd
/media/nate/Friday/chatterbox-tts-api/venv/bin/python main.py
