# junior

Personal repo of a beginner. Talk to the owner in Russian, plainly, and explain terms. The owner usually works from a phone, through Claude Code on the web.

## Reels (`reels/`)

Remotion project that edits talking-head recordings into branded Reels/Shorts.

- **Read `reels/BRANDBOOK.md` before any edit** and follow it: colors, font, frame zones, hook, plaques, captions.
- The Remotion skills live in `.claude/skills/remotion-*`.

### Workflow for a new video

1. **Get the recording.** It is usually in the owner's Google Drive. The Drive connector downloads only up to 10 MB; for bigger files ask the owner to share the file "anyone with the link" and download it with
   `curl -sSL -o /tmp/rec.mov "https://drive.usercontent.google.com/download?id=<FILE_ID>&export=download&confirm=t"`,
   then tell them to restrict access again.
2. **Prepare it:** `cd reels && npm i && scripts/prepare.sh /tmp/rec.mov`. This writes `public/video.mp4` (H.264, 1080×1920) and `public/captions.json` (word timings), and prints the duration and low-confidence words.
3. **Check the transcript** and ask the owner about doubtful words.
4. **Edit `src/Reel.tsx`:** `REEL_DURATION_SECONDS`, the hook text, `PLAQUES` (text, accent words, `from`/`to` taken from word timings).
5. **Check stills** at the hook, each plaque and a few caption moments: `scripts/render.sh stills 30 150 620`, then look at `out/stills.png` for faces covered or text colliding.
6. **Render:** `scripts/render.sh video` writes `out/reel.mp4`. Send it to the owner.
7. Commit code only. Source footage and transcripts are gitignored because the repo is public.

## HyperFrames (`.claude/skills/hyperframes*`, `media-use`)

HeyGen's HTML-to-video framework, installed as agent skills. Its router skill calls itself the default for any video; in this repo that is overridden:

- **Talking-head Reels from the owner's recordings → the Remotion pipeline above**, brandbook included, unless the owner explicitly asks for HyperFrames.
- **HyperFrames for everything else**: motion graphics, explainers without a face, title cards, product/site promos, slideshows. Start with `/hyperframes`. Apply the brandbook colors and font there too.
- Create HyperFrames projects in their own folder (e.g. `videos/<name>/`) with `npx hyperframes init <name> --non-interactive --resolution=portrait`, render with `npx hyperframes render`.
- Set `HYPERFRAMES_SKIP_SKILLS=1` when running the CLI: otherwise `init` re-installs skills into the global `~/.claude`, which the sandbox throws away. Update the repo copies with `npx skills add heygen-com/hyperframes --skill <name> --agent claude-code -y`.

### Sandbox notes

- Chromium can't reach Google Fonts through the proxy (certificate), which is why the font is bundled locally.
- `render.sh` uses the preinstalled Chromium in `/opt/pw-browsers`.
- Remotion's bundled ffmpeg lacks filters; `prepare.sh` installs the system ffmpeg.
- Transcription runs faster-whisper `large-v3` on CPU: about 3 minutes for 25 seconds of audio. It needs access to huggingface.co.
- HyperFrames downloads its own headless Chrome on first render and needs the system ffmpeg (`apt-get install ffmpeg`).
