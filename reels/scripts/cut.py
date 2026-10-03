"""Cut the chosen takes out of the source and tighten the pauses.

    python scripts/cut.py takes.json .tmp/cut.mp4

takes.json is written by the agent from the transcript and approved by the
owner before this runs:

    {
      "source": "public/source.mp4",
      "density": "tight",                # tight | natural
      "spans": [
        {"id": "S1", "in": 18.40, "out": 23.20, "text": "...",
         "note": "4th take, right after it the speaker says 'that one'",
         "rejected": ["0.0-8.6 too slow", "9.2-12.4 broken off"]}
      ]
    }

One ffmpeg pass: trim/atrim per segment, then the concat *filter* (frame
accurate, video and audio in one graph so they can't drift), a 15 ms audio
fade on every join so cuts don't click.
"""

import json
import subprocess
import sys

import speech

# density -> (shortest pause that gets compressed, how much of it is kept)
DENSITY = {
    # Never compress pauses under ~150 ms: a soft unstressed syllable is that
    # short and would get chopped ("пока вы спите" -> "ка вы спите").
    "tight": (0.160, 0.050),
    "natural": (0.400, 0.220),
}
LEAD_S = 0.020  # keep this much before the first word of a span
TRAIL_S = 0.030  # and this much after the last one
FADE_S = 0.015
SEAM_S = 1.0  # a pause this long inside a span is usually two takes glued


def fps_of(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=r_frame_rate", "-of", "csv=p=0", path],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    num, den = out.split("/")
    return int(num) / int(den)


def plan(spans, runs, min_pause, keep, fps):
    """Segments (start, end) in source seconds, snapped to the frame grid."""
    segments, warnings = [], []
    for span in spans:
        inside = [(max(a, span["in"]), min(b, span["out"]))
                  for a, b in runs if b > span["in"] and a < span["out"]]
        if not inside:
            warnings.append(f'{span["id"]}: no speech between {span["in"]} and {span["out"]}')
            continue
        for (_, end), (start, _) in zip(inside, inside[1:]):
            if start - end > SEAM_S:
                warnings.append(
                    f'{span["id"]}: {start - end:.2f}s pause at {end:.2f} - '
                    "two takes glued together? Check before approving.")
        # Start just before the first word, end just after the last one, and
        # inside the span compress every pause down to `keep`.
        current = [inside[0][0] - LEAD_S, None]
        for (_, end), (start, _) in zip(inside, inside[1:]):
            if start - end >= min_pause:
                current[1] = end + keep / 2
                segments.append(tuple(current))
                current = [start - keep / 2, None]
        current[1] = inside[-1][1] + TRAIL_S
        segments.append(tuple(current))

    snapped = []
    for a, b in segments:
        a, b = round(a * fps) / fps, round(b * fps) / fps
        if b > a:
            snapped.append((max(a, 0.0), b))
    return snapped, warnings


def render(source, segments, out):
    parts, labels = [], []
    for i, (a, b) in enumerate(segments):
        d = b - a
        parts.append(f"[0:v]trim=start={a:.4f}:end={b:.4f},setpts=PTS-STARTPTS[v{i}]")
        parts.append(
            f"[0:a]atrim=start={a:.4f}:end={b:.4f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d={FADE_S},afade=t=out:st={max(d - FADE_S, 0):.4f}:d={FADE_S}[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    parts.append(f"{''.join(labels)}concat=n={len(segments)}:v=1:a=1[v][a]")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", source, "-filter_complex", ";".join(parts),
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "fast", "-crf", "16",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out],
        check=True,
    )


def main():
    takes_path, out = sys.argv[1], sys.argv[2]
    takes = json.load(open(takes_path, encoding="utf-8"))
    source = takes["source"]
    min_pause, keep = DENSITY[takes.get("density", "tight")]

    mask, _, gate = speech.analyse(source)
    segments, warnings = plan(
        takes["spans"], speech.speech_runs(mask), min_pause, keep, fps_of(source))
    for w in warnings:
        print("WARNING:", w)
    render(source, segments, out)

    # Report what is left, as numbers: raw quiet stretches under the same
    # gate (no smoothing, which would hide the short pauses we kept).
    env = speech.envelope_db(speech.load_audio(out))
    quiet = [(a * speech.HOP_S, b * speech.HOP_S) for a, b in speech._runs(env < gate)]
    inner = [(a, b) for a, b in quiet if a > 0 and b < len(env) * speech.HOP_S]
    longest = max((b - a for a, b in inner), default=0.0)
    print(f"Segments: {len(segments)}, gate {gate:.1f} dBFS")
    print(f"Result: {len(env) * speech.HOP_S:.2f}s, "
          f"longest quiet stretch {longest * 1000:.0f} ms")


if __name__ == "__main__":
    main()
