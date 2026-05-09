#!/usr/bin/env bash
# Encode the final MP4 from frames/ + audio.wav.
# 1920x1080, 60fps output (frames are 30fps, ffmpeg interpolates via minterpolate).
# H.264 high profile, yuv420p for broad compat, AAC audio.
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d frames ]] || [[ ! -f audio.wav ]]; then
  echo "Missing frames/ or audio.wav" >&2
  exit 1
fi

OUT="paypal.mp4"

# Pass 1: build a 30fps intermediate from frames + apply subtle motion blur trail
# Pass 2: motion-interpolate up to 60fps for ultra-smooth motion
INTER="paypal_30.mp4"

ffmpeg -y \
  -framerate 30 -i 'frames/f%05d.jpg' \
  -i audio.wav \
  -c:v libx264 -preset slow -crf 17 \
  -pix_fmt yuv420p -profile:v high -level 4.2 \
  -movflags +faststart \
  -vf "format=yuv420p" \
  -c:a aac -b:a 192k \
  -shortest \
  "$INTER"

# Up-interpolate to 60fps
ffmpeg -y \
  -i "$INTER" \
  -filter:v "minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1" \
  -c:v libx264 -preset slow -crf 17 \
  -pix_fmt yuv420p -profile:v high -level 4.2 \
  -movflags +faststart \
  -c:a copy \
  "$OUT"

ls -lh "$OUT"
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,duration \
  -of default=nw=1 "$OUT"
