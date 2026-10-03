#!/usr/bin/env bash
# Step 1 of a new reel: turn the phone recording into material to choose
# takes from.
#   public/source.mp4           1080x1920, 30 fps, H.264 (Chromium can't decode HEVC)
#   public/source-captions.json word timings of the raw recording
# and print the transcript plus every pause, flagging long ones that are
# usually seams between two takes.
# Usage: scripts/prepare.sh path/to/recording.MOV
set -euo pipefail

cd "$(dirname "$0")/.."
input="$1"
mkdir -p .tmp

if ! command -v ffmpeg >/dev/null; then
  apt-get install -y -qq ffmpeg >/dev/null 2>&1 ||
    { apt-get update -qq >/dev/null && apt-get install -y -qq ffmpeg >/dev/null; }
fi

venv=/tmp/whisper-venv
if [ ! -x "$venv/bin/python" ]; then
  python3 -m venv "$venv"
  "$venv/bin/pip" install -q faster-whisper numpy
fi

# Portrait phone footage is stored landscape with a rotation flag; ffmpeg
# applies it automatically, so scaling to 1080x1920 keeps it upright.
ffmpeg -v error -y -i "$input" -map 0:v:0 -map 0:a:0 \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30" \
  -c:v libx264 -preset fast -crf 16 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart public/source.mp4

ffmpeg -v error -y -i public/source.mp4 -ar 16000 -ac 1 .tmp/source.wav
"$venv/bin/python" scripts/transcribe.py .tmp/source.wav public/source-captions.json
echo
"$venv/bin/python" scripts/speech.py public/source.mp4
