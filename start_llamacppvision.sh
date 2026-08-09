#!/bin/bash
echo -ne "\033]0;LLAMA.CPP VISION\007"
echo "Starting vision encoder instance (mmproj-only mode)..."
echo "Press Ctrl+C to stop"
echo "========================================="

while true; do
    /media/nate/Friday/llama.cpp/build/bin/llama-server \
      --mmproj "/media/nate/Friday/lmstudio models/HauhauCS/Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-MTP/mmproj-Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-BF16.gguf" \
      --mmproj-only \
      --main-server-port 8080 \
      --no-mmap \
      --n-gpu-layers 999 \
      --host 0.0.0.0 \
      --port 8082 &

    LLAMA_PID=$!
    echo "========================================="
    echo "Vision encoder started - PID $LLAMA_PID"
    echo "Next restart: $(date -d 'tomorrow 00:30' '+%Y-%m-%d %H:%M:%S')"
    echo "========================================="

    sleep $(( $(date -d "tomorrow 00:30" +%s) - $(date +%s) ))

    echo "========================================="
    echo "Scheduled restart initiated - killing PID $LLAMA_PID"
    echo "========================================="
    kill $LLAMA_PID
    sleep 10
done
