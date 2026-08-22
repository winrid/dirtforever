#!/bin/bash
# Usage: rxshot.sh <name> [wait_seconds]
# Optionally wait (1s polls), then screenshot the game window region
# (windowed 1920x1080 at top-left) to runtime/discovery/<name>_c.png.
set -e
name="${1:-shot}"
wait="${2:-0}"
dir="C:/Users/winrid/dr2server/runtime/discovery"
for i in $(seq 1 "$wait"); do sleep 1; done
bash "C:/Users/winrid/dr2server/scripts/shot.sh" "$name" >/dev/null
python "C:/Users/winrid/dr2server/scripts/crop.py" "$dir/$name.png" "$dir/${name}_c.png" 0 0 1920 1080 >/dev/null
echo "$dir/${name}_c.png"
