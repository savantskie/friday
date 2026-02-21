#!/bin/bash
export COQUI_TTS_CACHE=/media/nate/Friday/Friday_Voices
cd /media/nate/Friday/openedai-speech
python3 speech.py --xtts_device cuda --host 192.168.1.50 --port 8002 --preload xtts --unload-timer 300
