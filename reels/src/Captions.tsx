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

// At most this many words on screen at once, so the pill stays small.
const MAX_WORDS_PER_PAGE = 2;
// A page lingers this long after its last word unless the next one starts.
const LINGER_MS = 400;

type Page = { startMs: number; endMs: number; tokens: Caption[] };

const toPages = (captions: Caption[]): Page[] => {
  const pages: Page[] = [];
  let current: Caption[] = [];
  const flush = () => {
    if (current.length > 0) {
      pages.push({
        startMs: current[0].startMs,
        endMs: current[current.length - 1].endMs,
        tokens: current,
      });
      current = [];
    }
  };
  for (const c of captions) {
    const prev = current[current.length - 1];
    if (
      current.length >= MAX_WORDS_PER_PAGE ||
      (prev && (prev.pageBreakAfter || c.startMs - prev.endMs > LINGER_MS))
    ) {
      flush();
    }
    current.push(c);
  }
  flush();
  return pages;
};

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
    // Words a plaque already shows never appear as captions.
    const spoken = captions.filter(
      (c) =>
        !hideDuring.some(
          (w) => c.startMs >= w.from * 1000 && c.startMs < w.to * 1000,
        ),
    );
    return toPages(spoken);
  }, [captions, hideDuring]);

  const timeMs = (frame / fps) * 1000;
  const hidden = hideDuring.some(
    (w) => timeMs >= w.from * 1000 && timeMs < w.to * 1000,
  );
  const page = pages.find(
    (p, i) =>
      timeMs >= p.startMs &&
      timeMs < Math.min(p.endMs + LINGER_MS, pages[i + 1]?.startMs ?? Infinity),
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
          fontSize: 72,
          lineHeight: 1.1,
          textAlign: "center",
          // One short line on a compact translucent pill.
          whiteSpace: "pre",
          color: TEXT,
          background: `${INK}B8`,
          padding: "10px 24px",
          borderRadius: 18,
        }}
      >
        {page.tokens.map((t, i) => {
          const active = timeMs >= t.startMs && timeMs < t.endMs;
          return (
            <span key={t.startMs} style={{ color: active ? ACCENT : TEXT }}>
              {(i === 0 ? t.text.trimStart() : t.text).replace(/[.,]$/, "")}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
