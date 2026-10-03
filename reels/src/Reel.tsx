import type { Caption } from "@remotion/captions";
import { Video } from "@remotion/media";
import { ALL_FORMATS, Input, UrlSource } from "mediabunny";
import {
  AbsoluteFill,
  CalculateMetadataFunction,
  Easing,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { ACCENT, INK, TEXT, fontFamily } from "./brand";
import { Captions } from "./Captions";
import { Cue, endOf, startOf } from "./cues";

// Each plaque appears on the word it quotes and stays until `until` has been
// said, plus HOLD_S. Cues are words, not seconds, so after any re-cut the
// graphics follow the speech on their own.
// `accent` is the part of the text painted in the accent color.
const PLAQUES: { text: string; accent: string; from: Cue; until: Cue }[] = [
  {
    text: "Без монтажёра",
    accent: "монтажёра",
    from: { word: "без" },
    until: { word: "монтажёра" },
  },
  {
    text: "Без ничего",
    accent: "ничего",
    from: { word: "без", n: 2 },
    until: { word: "ничего" },
  },
  {
    text: "Смотрят по всему миру",
    accent: "всему миру",
    from: { word: "смотрят" },
    until: { word: "миру" },
  },
];
const HOLD_S = 0.6;

const HOOK_END = 2.3;
const FPS = 30;

type Window = { text: string; accent: string; from: number; to: number };

export type ReelProps = {
  captions: Caption[];
  plaques: Window[];
};

// Reads the prepared files once: the reel lasts as long as the video, and
// plaque cues turn into seconds against the word timings.
export const calculateReelMetadata: CalculateMetadataFunction<
  ReelProps
> = async () => {
  const captions: Caption[] = await (
    await fetch(staticFile("captions.json"))
  ).json();
  const input = new Input({
    formats: ALL_FORMATS,
    source: new UrlSource(staticFile("video.mp4")),
  });
  const seconds = await input.computeDuration();
  const plaques = PLAQUES.map((p) => ({
    text: p.text,
    accent: p.accent,
    from: startOf(captions, p.from),
    to: Math.min(endOf(captions, p.until) + HOLD_S, seconds),
  }));
  return {
    durationInFrames: Math.round(seconds * FPS),
    fps: FPS,
    props: { captions, plaques },
  };
};

const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 200 } });
  const exit = interpolate(
    frame,
    [(HOOK_END - 0.35) * fps, HOOK_END * fps],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.cubic),
    },
  );

  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: 170 }}>
      <div
        style={{
          fontFamily,
          fontWeight: 800,
          fontSize: 96,
          lineHeight: 1.05,
          textAlign: "center",
          textTransform: "uppercase",
          color: TEXT,
          background: INK,
          padding: "28px 44px",
          borderRadius: 28,
          opacity: enter * (1 - exit),
          translate: `0px ${(1 - enter) * -60 - exit * 60}px`,
          scale: 0.9 + enter * 0.1,
        }}
      >
        Монтаж через
        <br />
        <span style={{ color: ACCENT }}>Claude</span>
      </div>
    </AbsoluteFill>
  );
};

const Plaque: React.FC<{
  text: string;
  accent: string;
  durationInFrames: number;
}> = ({ text, accent, durationInFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 18, mass: 0.6 } });
  const exit = interpolate(
    frame,
    [durationInFrames - 0.25 * fps, durationInFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    // Lower third: sits on the chest, never over the face.
    <AbsoluteFill style={{ alignItems: "center", paddingTop: 1380 }}>
      <div
        style={{
          fontFamily,
          fontWeight: 800,
          fontSize: 72,
          lineHeight: 1.15,
          color: TEXT,
          background: INK,
          padding: "22px 36px",
          borderRadius: 22,
          maxWidth: 900,
          textAlign: "center",
          textWrap: "balance",
          opacity: Math.min(enter, 1) * (1 - exit),
          scale: 0.85 + Math.min(enter, 1.05) * 0.15,
        }}
      >
        {text.slice(0, text.indexOf(accent))}
        <span style={{ color: ACCENT }}>{accent}</span>
        {text.slice(text.indexOf(accent) + accent.length)}
      </div>
    </AbsoluteFill>
  );
};

export const Reel: React.FC<ReelProps> = ({ captions, plaques }) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <Video
        src={staticFile("video.mp4")}
        objectFit="cover"
        style={{ width: "100%", height: "100%" }}
      />
      <Sequence name="Hook" durationInFrames={Math.round(HOOK_END * fps)}>
        <Hook />
      </Sequence>
      <Captions captions={captions} hideDuring={plaques} />
      {plaques.map((p) => {
        const durationInFrames = Math.round((p.to - p.from) * fps);
        return (
          <Sequence
            key={p.text}
            name={p.text}
            from={Math.round(p.from * fps)}
            durationInFrames={durationInFrames}
          >
            <Plaque
              text={p.text}
              accent={p.accent}
              durationInFrames={durationInFrames}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
