#!/usr/bin/env bash
# Render stills (quick layout check) or the full Reel with the preinstalled
# Chromium, which avoids downloading a browser in the cloud sandbox.
# Usage: scripts/render.sh stills 30 150 620   |   scripts/render.sh video
set -euo pipefail

cd "$(dirname "$0")/.."
browser=$(ls -d /opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell 2>/dev/null | head -1 || true)
flags=()
[ -n "$browser" ] && flags+=(--browser-executable="$browser")

case "$1" in
  stills)
    shift
    inputs=()
    for f in "$@"; do
      npx remotion still Reel "out/still-$f.png" --frame="$f" --scale=0.25 "${flags[@]}"
      inputs+=(-i "out/still-$f.png")
    done
    if [ "$#" -gt 1 ]; then
      ffmpeg -v error -y "${inputs[@]}" -filter_complex "hstack=$#" out/stills.png
    else
      cp "out/still-$1.png" out/stills.png
    fi
    echo "out/stills.png"
    ;;
  video)
    npx remotion render Reel out/reel.mp4 --crf=23 "${flags[@]}"
    ;;
esac
