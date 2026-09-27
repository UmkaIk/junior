"""Transcribe public/audio.wav into public/captions.json (Remotion Caption format).

Word timings drive both the captions and the moments plaques appear.
"""

import json
import sys

from faster_whisper import WhisperModel

# Brand and product names Whisper tends to spell phonetically.
REPLACEMENTS = {
    "Клауд": "Claude",
    "Клод": "Claude",
    "Ремоушн": "Remotion",
}

audio, out = sys.argv[1], sys.argv[2]
model = WhisperModel("large-v3", device="cpu", compute_type="int8")
# VAD trimming made large-v3 drop punctuation and mishear short words, so
# it stays off; the prompt nudges spelling and punctuation.
segments, _ = model.transcribe(
    audio,
    language="ru",
    word_timestamps=True,
    vad_filter=False,
    beam_size=5,
    initial_prompt="Привет. Сегодня монтирую ролик через Claude и Remotion.",
)

words = []
for segment in segments:
    print(f"[{segment.start:5.2f}-{segment.end:5.2f}] {segment.text.strip()}")
    for w in segment.words:
        text = w.word.strip()
        # Whisper splits hyphenated words ("из", "-за"): glue them back.
        if words and text.startswith("-"):
            words[-1]["text"] += text
            words[-1]["endMs"] = int(w.end * 1000)
            continue
        for wrong, right in REPLACEMENTS.items():
            text = text.replace(wrong, right).replace(wrong.lower(), right)
        words.append(
            {
                "text": text,
                "startMs": int(w.start * 1000),
                "endMs": int(w.end * 1000),
                "confidence": round(w.probability, 2),
            }
        )

captions = []
for i, w in enumerate(words):
    caption = {
        "text": (" " if i else "") + w["text"],
        "startMs": w["startMs"],
        "endMs": w["endMs"],
        "timestampMs": (w["startMs"] + w["endMs"]) // 2,
        "confidence": w["confidence"],
    }
    if w["text"][-1:] in ".!?":
        caption["pageBreakAfter"] = True
    captions.append(caption)

with open(out, "w", encoding="utf-8") as f:
    json.dump(captions, f, ensure_ascii=False, indent=1)

doubtful = [f'{w["text"]} ({w["confidence"]})' for w in words if w["confidence"] < 0.6]
if doubtful:
    print("Low-confidence words, check by ear:", ", ".join(doubtful))
