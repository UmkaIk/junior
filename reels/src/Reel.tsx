import { Video } from "@remotion/media";
import {
  AbsoluteFill,
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

// Seconds come from the word timings of the recording, so each plaque
// appears on the word it quotes.
// `accent` is the part of the text painted in the accent color.
const PLAQUES = [
  { text: "Без монтажёра", accent: "монтажёра", from: 4.0, to: 5.7 },
  { text: "Без ничего", accent: "ничего", from: 9.42, to: 10.8 },
  {
    text: "Смотрят по всему миру",
    accent: "всему миру",
    from: 19.12,
    to: 22.4,
  },
];

const HOOK_END = 2.3;

export const REEL_DURATION_SECONDS = 23.6;

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

export const Reel: React.FC = () => {
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
      <Captions hideDuring={PLAQUES} />
      {PLAQUES.map((p) => {
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
