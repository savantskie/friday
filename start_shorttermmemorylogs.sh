#!/bin/bash
echo "Starting Short Term Memory logs..."
echo "Press Ctrl+C to stop"
echo "========================================="

tail -f /media/nate/Friday/Friday/logs/friday_short_term_memory.log | grep -E "✅|ERROR|saved|skipped|compaction"
