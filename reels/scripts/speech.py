"""Where the speech is, measured from the audio itself.

Word timings from Whisper drift by 0.1-0.2 s, so every cut point comes from
the loudness envelope instead: Whisper says *what* was said, the envelope
says *where*.

Run directly to list the pauses of a file:
    python scripts/speech.py public/source.mp4
"""

import json
import subprocess
import sys

import numpy as np

RATE = 16000
HOP_S = 0.010  # envelope window: 10 ms
# A window counts as loud at or above (integrated loudness - LOUD_BELOW_LUFS).
# Relative, because a phone records ~15 dB quieter than a mastered track:
# on a file mastered to -14 LUFS this is the classic -30 dBFS gate.
LOUD_BELOW_LUFS = 16.0
SMOOTH_HOPS = 3  # sliding max over +-30 ms keeps dips inside words loud
MIN_SPEECH_S = 0.110  # loud runs shorter than this are breaths or clicks
TAIL_S = 0.250  # look this far past a run for a soft word ending


def load_audio(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(RATE),
         "-f", "s16le", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def integrated_lufs(path):
    """Integrated loudness (EBU R128) as measured by ffmpeg's loudnorm."""
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", path, "-vn", "-af",
         "loudnorm=print_format=json", "-f", "null", "-"],
        check=True, capture_output=True, text=True,
    ).stderr
    return float(json.loads(err[err.rindex("{"):])["input_i"])


def envelope_db(samples):
    hop = int(RATE * HOP_S)
    n = len(samples) // hop
    frames = samples[: n * hop].reshape(n, hop)
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    return 20 * np.log10(rms)


def _runs(mask):
    """(start, end) index pairs of consecutive True values, end exclusive."""
    edges = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


def speech_mask(env, loud_db):
    # Sliding max: a short dip inside a word must not read as a pause, and
    # short words get lifted over the duration threshold.
    padded = np.pad(env, SMOOTH_HOPS, mode="edge")
    sdb = np.max(
        np.lib.stride_tricks.sliding_window_view(padded, 2 * SMOOTH_HOPS + 1), axis=1
    )
    loud = sdb >= loud_db

    # Speech is loudness that holds; breaths into a close mic peak but don't.
    min_hops = round(MIN_SPEECH_S / HOP_S)
    speech = np.zeros_like(loud)
    for a, b in _runs(loud):
        if b - a >= min_hops:
            speech[a:b] = True

    # A soft final syllable lasts 10-20 ms and fails the duration test like a
    # breath, so extend each run while a loud hop follows within TAIL_S.
    # This lives in the mask, not in span trimming, because pause
    # compression cuts inside spans too.
    tail = round(TAIL_S / HOP_S)
    for a, b in _runs(speech):
        end = b
        while True:
            ahead = np.flatnonzero(loud[end : end + tail])
            if len(ahead) == 0:
                break
            end = end + ahead[-1] + 1
            if speech[end:end + 1].any():
                break
        speech[b:end] = True
    return speech, sdb


def analyse(path):
    env = envelope_db(load_audio(path))
    loud_db = integrated_lufs(path) - LOUD_BELOW_LUFS
    speech, sdb = speech_mask(env, loud_db)
    return speech, sdb, loud_db


def speech_runs(speech):
    """Speech intervals in seconds."""
    return [(a * HOP_S, b * HOP_S) for a, b in _runs(speech)]


def pauses(speech, min_s=0.0):
    """Gaps between speech runs, in seconds."""
    runs = speech_runs(speech)
    return [
        (end, start)
        for (_, end), (start, _) in zip(runs, runs[1:])
        if start - end >= min_s
    ]


if __name__ == "__main__":
    mask, _, gate = analyse(sys.argv[1])
    runs = speech_runs(mask)
    total = len(mask) * HOP_S
    print(f"Duration {total:.2f}s, speech {sum(b - a for a, b in runs):.2f}s, "
          f"gate {gate:.1f} dBFS")
    for a, b in pauses(mask, 0.16):
        flag = "  <- long: a seam between two takes?" if b - a > 1.0 else ""
        print(f"  pause {a:6.2f}-{b:6.2f}  {b - a:4.2f}s{flag}")
