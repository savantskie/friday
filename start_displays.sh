#!/bin/bash
echo "Setting up displays..."
xrandr --output HDMI-A-0 --primary --mode 3440x1440 --pos 0x0 --rotate normal \
       --output DisplayPort-12 --mode 1920x1080 --pos 3440x0 --rotate left
echo "Display setup complete."
