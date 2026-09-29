import { AbsoluteFill, Img, staticFile } from "remotion";
import { z } from "zod";
import { ACCENT, INK, TEXT, fontFamily } from "./brand";

// Real texts and contacts come from a gitignored JSON passed with --props,
// so a phone number never lands in this public repo.
export const statusClientsSchema = z.object({
  headline: z.string(),
  headlineAccent: z.string(),
  subline: z.string(),
  body: z.string(),
  punch: z.string(),
  contacts: z.array(z.object({ label: z.string(), value: z.string() })),
});

type Props = z.infer<typeof statusClientsSchema>;

const SAFE_TOP = 180;
const SAFE_BOTTOM = 190;
const SIDE = 72;
const MUTED = "rgba(255, 255, 255, 0.62)";
const LINE = "rgba(255, 255, 255, 0.14)";

export const StatusClients: React.FC<Props> = ({
  headline,
  headlineAccent,
  subline,
  body,
  punch,
  contacts,
}) => {
  const accentAt = headline.indexOf(headlineAccent);

  return (
    <AbsoluteFill style={{ backgroundColor: INK, fontFamily, color: TEXT }}>
      <AbsoluteFill style={{ height: 1180, overflow: "hidden" }}>
        <Img
          src={staticFile("status/avatar.jpg")}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: "36% 18%",
            scale: 1.35,
            transformOrigin: "34% 22%",
          }}
        />
        <AbsoluteFill
          style={{
            background: `linear-gradient(180deg, ${INK}00 42%, ${INK}CC 76%, ${INK} 100%)`,
          }}
        />
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          padding: `${SAFE_TOP}px ${SIDE}px ${SAFE_BOTTOM}px`,
          justifyContent: "flex-end",
        }}
      >
        <div style={{ fontSize: 112, fontWeight: 800, lineHeight: 1 }}>
          {accentAt < 0 ? (
            headline
          ) : (
            <>
              {headline.slice(0, accentAt)}
              <span style={{ color: ACCENT }}>{headlineAccent}</span>
              {headline.slice(accentAt + headlineAccent.length)}
            </>
          )}
        </div>
        <div
          style={{
            marginTop: 26,
            fontSize: 50,
            fontWeight: 700,
            lineHeight: 1.15,
          }}
        >
          {subline}
        </div>

        <div
          style={{
            marginTop: 44,
            paddingTop: 40,
            borderTop: `2px solid ${LINE}`,
            fontSize: 40,
            fontWeight: 500,
            lineHeight: 1.3,
            color: MUTED,
            textWrap: "balance",
          }}
        >
          {body}
        </div>
        <div
          style={{
            marginTop: 20,
            fontSize: 44,
            fontWeight: 800,
            lineHeight: 1.2,
          }}
        >
          {punch}
        </div>

        <div
          style={{
            marginTop: 56,
            borderRadius: 28,
            border: `3px solid ${ACCENT}`,
            padding: "8px 34px",
          }}
        >
          {contacts.map((c, i) => (
            <div
              key={c.label}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "22px 0",
                borderTop: i === 0 ? "none" : `2px solid ${LINE}`,
              }}
            >
              <span style={{ fontSize: 34, fontWeight: 600, color: MUTED }}>
                {c.label}
              </span>
              <span style={{ fontSize: 44, fontWeight: 800, color: ACCENT }}>
                {c.value}
              </span>
            </div>
          ))}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
