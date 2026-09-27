#!/usr/bin/env bash
# Prepare a phone recording for the Reel composition:
#   public/video.mp4     1080x1920, 30 fps, H.264 (Chromium can't decode HEVC)
#   public/captions.json word-timed captions
# Usage: scripts/prepare.sh path/to/recording.MOV
set -euo pipefail

cd "$(dirname "$0")/.."
input="$1"

if ! command -v ffmpeg >/dev/null; then
  apt-get install -y -qq ffmpeg >/dev/null 2>&1 ||
    { apt-get update -qq >/dev/null && apt-get install -y -qq ffmpeg >/dev/null; }
fi

# Portrait phone footage is stored landscape with a rotation flag; ffmpeg
# applies it automatically, so scaling to 1080x1920 keeps it upright.
ffmpeg -v error -y -i "$input" -map 0:v:0 -map 0:a:0 \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30" \
  -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 160k -movflags +faststart public/video.mp4
ffmpeg -v error -y -i public/video.mp4 -ar 16000 -ac 1 public/audio.wav

duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 public/video.mp4)
echo "Duration: ${duration}s -> set REEL_DURATION_SECONDS in src/Reel.tsx"

venv=/tmp/whisper-venv
if [ ! -x "$venv/bin/python" ]; then
  python3 -m venv "$venv"
  "$venv/bin/pip" install -q faster-whisper
fi
"$venv/bin/python" scripts/transcribe.py public/audio.wav public/captions.json
rm public/audio.wav
