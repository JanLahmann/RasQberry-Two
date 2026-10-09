#!/bin/bash
# Build the homepage demo loop from the screenshots in public/demo-screenshots/source/.
# Usage: scripts/create_demo_video.sh [source_dir] [output_dir]
# Writes rasqberry-demo.mp4 / .webm (1 s per frame), rasqberry-demo-slow.mp4
# (4 s per frame) and rasqberry-demo-poster.jpg (first frame). Needs ffmpeg.
set -euo pipefail

SRC="${1:-public/demo-screenshots/source}"
OUT="${2:-public/demo-screenshots}"
WIDTH=1920
VF="scale=${WIDTH}:-2:flags=lanczos,format=yuv420p"
# fps=2 + tpad: keep the last frame on screen for its full time too
vf() { echo "$VF,tpad=stop_mode=clone:stop_duration=$1,fps=2"; }

command -v ffmpeg >/dev/null || { echo "ffmpeg not found" >&2; exit 1; }
ls "$SRC"/*.png >/dev/null

mp4() { # seconds_per_frame output
  ffmpeg -y -loglevel error -framerate "1/$1" -pattern_type glob -i "$SRC/*.png" \
    -vf "$(vf "$1")" -c:v libx264 -preset veryslow -tune stillimage -crf 24 \
    -profile:v high -movflags +faststart -an "$2"
}

mp4 1 "$OUT/rasqberry-demo.mp4"
mp4 4 "$OUT/rasqberry-demo-slow.mp4"
ffmpeg -y -loglevel error -framerate 1 -pattern_type glob -i "$SRC/*.png" \
  -vf "$(vf 1)" -c:v libvpx-vp9 -b:v 0 -crf 40 -row-mt 1 -an "$OUT/rasqberry-demo.webm"
first=$(ls "$SRC"/*.png | head -1)
ffmpeg -y -loglevel error -i "$first" -vf "scale=${WIDTH}:-2:flags=lanczos" -q:v 4 \
  "$OUT/rasqberry-demo-poster.jpg"

ls -l "$OUT"/rasqberry-demo*
