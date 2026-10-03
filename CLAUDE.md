# junior

Personal repo of a beginner. Talk to the owner in Russian, plainly, and explain terms. The owner usually works from a phone, through Claude Code on the web.

## Reels (`reels/`)

Remotion project that edits talking-head recordings into branded Reels/Shorts.

- **Read `reels/BRANDBOOK.md` before any edit** and follow it: colors, font, frame zones, hook, plaques, captions.
- The Remotion skills live in `.claude/skills/remotion-*`.

### Workflow for a new video

1. **Get the recording** (and music, if any). It is usually in the owner's Google Drive. The Drive connector downloads only up to 10 MB; for bigger files ask the owner to share the file "anyone with the link" and download it with
   `curl -sSL -o /tmp/rec.mov "https://drive.usercontent.google.com/download?id=<FILE_ID>&export=download&confirm=t"`,
   then tell them to restrict access again.
2. **Prepare:** `cd reels && npm i && scripts/prepare.sh /tmp/rec.mov`. Writes `public/source.mp4` and `public/source-captions.json`, prints the transcript, low-confidence words and every pause (long ones flagged as likely seams between takes).
3. **Choose takes** — your judgement, not a script. Pick the best take of each line and write `.tmp/takes.json` (format in `scripts/cut.py`): one span per line with `in`/`out`, the text, and **what was rejected and why**. Signals:
   - the speaker cancels a take out loud ("не, не пойдёт", "стоп", "нет,") → drop it;
   - the speaker approves one ("вот это хорошо") → keep the take *before* it;
   - a whole, fluent line beats a broken one even if the broken one is worded better;
   - before fixing a span, check it has no pause over a second inside (two takes glued) and does not start with the tail of the previous take.
4. ⛔ **STOP. Show the owner the takes (text, what was rejected and why) and the doubtful words. Do not cut until they approve.** Emphasis can't be guessed.
5. **Edit:** `scripts/edit.sh [--music track.mp3 --music-start <s> --music-gap 15]`. Cuts the takes and compresses pauses (`density`: `tight` keeps 50 ms of every pause ≥160 ms, `natural` keeps 220 ms of pauses ≥400 ms), masters the sound, re-transcribes the cut into `public/captions.json`. Read its numbers: longest quiet stretch (≤ ~150 ms when tight), −14 LUFS, true peak ≤ −1, and the edit transcript — it must read as one clean script. Whisper merges a line said twice into one, so for any doubtful span also listen to the cut around it, and check for the warning about long pauses inside spans.
6. **Graphics in `src/Reel.tsx`:** the hook text and `PLAQUES`. Plaques are tied to **spoken words** (`from`/`until` cues, matched without case or punctuation, `n` for the 2nd, 3rd… occurrence), never to seconds; duration and captions load from `public/` by themselves. Show the owner the plaque texts before rendering — wording almost always gets edited.
7. **Check stills** at the hook, each plaque and a few caption moments: `scripts/render.sh stills 30 150 620`, then look at `out/stills.png` for faces covered or text colliding.
8. **Render:** `scripts/render.sh video` writes `out/reel.mp4`. Send it with the numbers (length before/after, loudness), wait for edits.
9. Commit code only. Footage, music, takes and transcripts are gitignored because the repo is public.

### Traps already paid for

- **Whisper merges repeats.** Two attempts at the same line come out as one line of text while the audio plays it twice. The whole-file transcript can't show it → look for pauses over a second inside spans; re-check doubtful spans in clips under 5 s.
- **Breathing is not silence**: a close-mic breath peaks well above the noise floor. That is why speech = loudness that *holds* ≥110 ms (`scripts/speech.py`).
- **The same rule eats soft word endings** (10–20 ms) → the mask extends runs by up to 250 ms; never compress pauses under ~150 ms or syllables get chopped ("пока вы спите" → "ка вы спите").
- **Rustling clothes pass for speech** (loud, but an empty stretch in the transcript). Only eyes catch it: look at frames around joins.
- **The gate is relative** (16 dB under the file's loudness): a phone records ~15 dB quieter than a mastered file, a fixed −30 dBFS gate threw away half the speech.
- **`sidechaincompress` returns ~1 s less than it gets** → `audio.py` pads with silence, trims, and prints the duration to compare.
- **Cut in one ffmpeg graph with the concat filter**, 15 ms fades at joins: frame-accurate, no A/V drift, no clicks.

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
