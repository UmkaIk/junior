import { createTikTokStyleCaptions } from "@remotion/captions";
import type { Caption } from "@remotion/captions";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AbsoluteFill,
  staticFile,
  useCurrentFrame,
  useDelayRender,
  useVideoConfig,
} from "remotion";
import { ACCENT, INK, TEXT, fontFamily } from "./brand";

// How long a group of words stays on screen before the next one.
const SWITCH_CAPTIONS_EVERY_MS = 900;

type Props = {
  // Time windows (seconds) where a plaque already shows these words.
  hideDuring: { from: number; to: number }[];
};

export const Captions: React.FC<Props> = ({ hideDuring }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const [captions, setCaptions] = useState<Caption[] | null>(null);
  const { delayRender, continueRender, cancelRender } = useDelayRender();
  const [handle] = useState(() => delayRender());

  const fetchCaptions = useCallback(async () => {
    try {
      const response = await fetch(staticFile("captions.json"));
      setCaptions(await response.json());
      continueRender(handle);
    } catch (e) {
      cancelRender(e);
    }
  }, [continueRender, cancelRender, handle]);

  useEffect(() => {
    fetchCaptions();
  }, [fetchCaptions]);

  const pages = useMemo(() => {
    if (!captions) {
      return [];
    }
    return createTikTokStyleCaptions({
      captions,
      combineTokensWithinMilliseconds: SWITCH_CAPTIONS_EVERY_MS,
    }).pages;
  }, [captions]);

  const timeMs = (frame / fps) * 1000;
  const hidden = hideDuring.some(
    (w) => timeMs >= w.from * 1000 && timeMs < w.to * 1000,
  );
  const page = pages.find(
    (p, i) =>
      timeMs >= p.startMs &&
      timeMs < Math.min(p.startMs + p.durationMs, pages[i + 1]?.startMs ?? Infinity),
  );

  if (hidden || !page) {
    return null;
  }

  return (
    // Same lower-third slot as the plaques: on the chest, never on the face.
    <AbsoluteFill style={{ alignItems: "center", paddingTop: 1390 }}>
      <div
        style={{
          fontFamily,
          fontWeight: 800,
          fontSize: 78,
          lineHeight: 1.15,
          maxWidth: 920,
          textAlign: "center",
          whiteSpace: "pre-wrap",
          textWrap: "balance",
          color: TEXT,
          WebkitTextStroke: `12px ${INK}`,
          paintOrder: "stroke fill",
        }}
      >
        {page.tokens.map((t) => {
          const active = timeMs >= t.fromMs && timeMs < t.toMs;
          return (
            <span key={t.fromMs} style={{ color: active ? ACCENT : TEXT }}>
              {t.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
