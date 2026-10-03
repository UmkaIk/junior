#!/usr/bin/env bash
# Step 2 of a new reel, after the owner approved .tmp/takes.json:
# cut the takes, master the sound, re-transcribe the cut.
#   public/video.mp4     the edited reel footage with final sound
#   public/captions.json word timings of the edit (graphics and captions
#                        must use these, not the raw ones, or they drift)
# Usage: scripts/edit.sh [--music track.mp3 --music-start 12.5 --music-gap 15]
set -euo pipefail

cd "$(dirname "$0")/.."
py=/tmp/whisper-venv/bin/python

"$py" scripts/cut.py .tmp/takes.json .tmp/cut.mp4
"$py" scripts/audio.py .tmp/cut.mp4 public/video.mp4 "$@"

ffmpeg -v error -y -i public/video.mp4 -ar 16000 -ac 1 .tmp/video.wav
echo
echo "Transcript of the edit (must read as one clean script: no repeats, no chopped words):"
"$py" scripts/transcribe.py .tmp/video.wav public/captions.json
