"""Master the voice, optionally lay music under it, write the final video.

    python scripts/audio.py .tmp/cut.mp4 public/video.mp4 [--music track.mp3]
                            [--music-start 12.5] [--music-gap 15]

Voice: highpass 80 Hz -> two-pass loudnorm to -14 LUFS, true peak -1 dBFS.
Denoise only when the noise floor is above -50 dBFS: on a clean recording it
adds artifacts and nothing else.

Music: normalised to an absolute level below the voice (the gap, 15 dB by
default), then ducked by a sidechain on the voice. Cut pauses leave speech
back to back, so a static bed either buries the voice or disappears.
The video stream is copied, never re-encoded.
"""

import argparse
import json
import subprocess

import numpy as np

import speech

VOICE_LUFS = -14.0
TRUE_PEAK = -1.5  # AAC encoding adds ~0.5 dB; this lands the file under -1
NOISY_FLOOR_DB = -50.0
FADE_OUT_S = 1.5


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def duration(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", path]).stdout)


# loudnorm can silently skip peak limiting (linear mode it can't honour), so
# a hard limiter closes every chain: -2 dBFS sample peak keeps the AAC file's
# true peak under -1.
LIMITER = f"alimiter=limit={10 ** (-2 / 20):.3f}:level=false"


def loudnorm(target, peak=TRUE_PEAK):
    return f"loudnorm=I={target}:TP={peak}:LRA=11"


def measured(src, chain, target):
    """First loudnorm pass: measure what the second pass needs."""
    err = run(["ffmpeg", "-hide_banner", "-i", src, "-vn", "-af",
               f"{chain},{loudnorm(target)}:print_format=json", "-f", "null", "-"]).stderr
    m = json.loads(err[err.rindex("{"):])
    return (f"{loudnorm(target)}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
            f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
            f":offset={m['target_offset']}:linear=true")


def noise_floor_db(src):
    env = speech.envelope_db(speech.load_audio(src))
    return float(np.percentile(env, 10))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("out")
    p.add_argument("--music")
    p.add_argument("--music-start", type=float, default=0.0,
                   help="where in the track to start, e.g. so its drop lands on the last line")
    p.add_argument("--music-gap", type=float, default=15.0,
                   help="dB between voice and music; 13 is louder, 17 quieter")
    a = p.parse_args()

    total = duration(a.src)
    floor = noise_floor_db(a.src)
    voice_chain = "highpass=f=80"
    if floor > NOISY_FLOOR_DB:
        voice_chain += ",afftdn=nf=-25"
    voice = f"{voice_chain},{measured(a.src, voice_chain, VOICE_LUFS)},{LIMITER}"
    print(f"Noise floor {floor:.1f} dBFS -> denoise {'on' if 'afftdn' in voice else 'off'}")

    tmp_voice = ".tmp/voice.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-vn", "-af", voice,
         "-ar", "48000", tmp_voice])

    if a.music:
        bed_lufs = VOICE_LUFS - a.music_gap
        tmp_music = ".tmp/music.wav"
        trim = f"atrim=start={a.music_start},asetpts=PTS-STARTPTS"
        run(["ffmpeg", "-v", "error", "-y", "-i", a.music, "-vn", "-af",
             f"{trim},{measured(a.music, trim, bed_lufs)}", "-ar", "48000", "-ac", "2",
             tmp_music])
        # sidechaincompress returns about a second less than it gets: pad both
        # inputs with silence and trim the result to the video length.
        graph = (
            f"[1:a]apad,asplit=2[sc][vmix];"
            f"[2:a]apad,atrim=end={total + 2}[bed];"
            f"[bed][sc]sidechaincompress=ratio=3:threshold=0.10:attack=20:release=380[duck];"
            f"[vmix][duck]amix=inputs=2:normalize=0:duration=longest,"
            f"atrim=end={total},afade=t=out:st={max(total - FADE_OUT_S, 0)}:d={FADE_OUT_S}[mix]"
        )
        tmp_mix = ".tmp/mix.wav"
        run(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-i", tmp_voice, "-i", tmp_music,
             "-filter_complex", graph, "-map", "[mix]", "-ar", "48000", tmp_mix])
        final = ".tmp/final.wav"
        run(["ffmpeg", "-v", "error", "-y", "-i", tmp_mix, "-af",
             f"{measured(tmp_mix, 'anull', VOICE_LUFS)},{LIMITER}", "-ar", "48000", final])
    else:
        final = tmp_voice

    run(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-i", final, "-map", "0:v:0",
         "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
         "-shortest", "-movflags", "+faststart", a.out])

    # Check, as numbers: loudness, true peak, duration.
    err = run(["ffmpeg", "-hide_banner", "-i", a.out, "-vn", "-af", "ebur128=peak=true",
               "-f", "null", "-"]).stderr
    summary = err[err.rindex("Summary:"):]
    lufs = float(summary.split("I:")[1].split("LUFS")[0])
    peak = float(summary.split("Peak:")[1].split("dBFS")[0])
    print(f"Result: {lufs:.1f} LUFS, true peak {peak:.1f} dBFS, "
          f"{duration(a.out):.2f}s (source {total:.2f}s)")


if __name__ == "__main__":
    main()
