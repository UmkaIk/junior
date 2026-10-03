import type { Caption } from "@remotion/captions";

// A moment in the reel named by a spoken word, so graphics follow the speech
// through every re-cut instead of holding hand-typed seconds.
export type Cue = {
  word: string;
  // Which occurrence of the word, counting from 1.
  n?: number;
  // Seconds to shift the moment by (negative = earlier).
  offset?: number;
};

// Whisper flips punctuation and case between runs ("эти" / "эти.",
// "Let's" / "let's"), so words are compared without them.
const normalize = (word: string) =>
  word
    .toLowerCase()
    .replace(/ё/g, "е")
    .replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, "");

const find = (captions: Caption[], cue: Cue) => {
  const target = normalize(cue.word);
  const matches = captions.filter((c) => normalize(c.text) === target);
  const hit = matches[(cue.n ?? 1) - 1];
  if (!hit) {
    throw new Error(
      `Cue "${cue.word}"${cue.n ? ` #${cue.n}` : ""} not found in captions.json ` +
        `(${matches.length} match${matches.length === 1 ? "" : "es"})`,
    );
  }
  return hit;
};

// When the cue word starts being spoken.
export const startOf = (captions: Caption[], cue: Cue) =>
  find(captions, cue).startMs / 1000 + (cue.offset ?? 0);

// When the cue word has been said.
export const endOf = (captions: Caption[], cue: Cue) =>
  find(captions, cue).endMs / 1000 + (cue.offset ?? 0);
