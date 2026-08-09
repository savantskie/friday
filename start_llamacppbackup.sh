#!/bin/bash
echo "Starting llama.cpp..."
echo "Press Ctrl+C to stop"
echo "========================================="

while true; do
    /media/nate/Friday/llama.cpp/build/bin/llama-server \
      -m "/media/nate/Friday/lmstudio models/HauhauCS/Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced/Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced-Q8_K_P.gguf" \
      --chat-template-kwargs '{"enable_thinking":false}' \
      --no-mmap \
      --cache-reuse 256 \
      --keep 6539 \
      --n-gpu-layers 999 \
      --cache-ram 2048 \
      --split-mode layer \
      --tensor-split 1,1 \
      --fit off \
      --batch-size 16384 \
      --ctx-size 131072 \
      --threads 10 \
      --threads-batch 10 \
      --ubatch-size 8192 \
      --parallel 1 \
      --flash-attn on \
      --jinja \
      --alias "Gemma4-26B-A4B-Uncensored-HauhauCS-Balanced" \
      --chat-template-file /media/nate/Friday/Friday/gemma4_prompt_template.jinja \
      --host 0.0.0.0 \
      --port 8080 &

    LLAMA_PID=$!
    echo "========================================="
    echo "llama.cpp started - PID $LLAMA_PID"
    echo "Next restart: $(date -d 'tomorrow 00:00' '+%Y-%m-%d %H:%M:%S')"
    echo "========================================="

    sleep $(( $(date -d "tomorrow 00:00" +%s) - $(date +%s) ))

    echo "========================================="
    echo "Scheduled restart initiated - killing PID $LLAMA_PID"
    echo "========================================="
    kill $LLAMA_PID
    sleep 10
done
