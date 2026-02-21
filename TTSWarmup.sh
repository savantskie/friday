gnome-terminal -- bash -c '
sleep 15
curl -X POST http://localhost:8002/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '"'"'{
    "model": "tts-1-hd",
    "input": "Hey Nate, what are your plans for today?",
    "voice": "shimmer"
  }'"'"' \
  --output /media/nate/Friday/test_gpu.wav

echo "Warmup complete. Press Enter to close."
read
'
