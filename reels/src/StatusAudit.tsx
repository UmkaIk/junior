import { AbsoluteFill, Img, staticFile } from "remotion";
import { z } from "zod";
import { ACCENT, INK, TEXT, fontFamily } from "./brand";

// Texts, photo and contacts come from a gitignored JSON passed with --props.
export const statusAuditSchema = z.object({
  photo: z.string(),
  label: z.string(),
  headline: z.string(),
  headlineAccent: z.string(),
  audience: z.string(),
  offer: z.string(),
  offerNote: z.string(),
  scarcity: z.string().optional(),
  contacts: z.array(z.object({ label: z.string(), value: z.string() })),
});

type Props = z.infer<typeof statusAuditSchema>;

const SAFE_TOP = 180;
const SAFE_BOTTOM = 190;
const SIDE = 72;
const MUTED = "rgba(255, 255, 255, 0.62)";
const LINE = "rgba(255, 255, 255, 0.14)";

export const StatusAudit: React.FC<Props> = ({
  photo,
  label,
  headline,
  headlineAccent,
  audience,
  offer,
  offerNote,
  scarcity,
  contacts,
}) => {
  const accentAt = headline.indexOf(headlineAccent);

  return (
    <AbsoluteFill style={{ backgroundColor: INK, fontFamily, color: TEXT }}>
      <AbsoluteFill style={{ height: 1000, overflow: "hidden" }}>
        <Img
          src={staticFile(`status/${photo}`)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            // Lower part of the desk shot: notebook and book, not the screen.
            objectPosition: "50% 96%",
          }}
        />
        <AbsoluteFill
          style={{
            background: `linear-gradient(180deg, ${INK}00 35%, ${INK}D9 75%, ${INK} 100%)`,
          }}
        />
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          padding: `${SAFE_TOP}px ${SIDE}px ${SAFE_BOTTOM}px`,
          justifyContent: "flex-end",
        }}
      >
        <div
          style={{
            alignSelf: "flex-start",
            fontSize: 30,
            fontWeight: 700,
            letterSpacing: 1,
            textTransform: "uppercase",
            color: INK,
            background: ACCENT,
            padding: "12px 22px",
            borderRadius: 999,
          }}
        >
          {label}
        </div>

        <div
          style={{
            marginTop: 26,
            fontSize: 88,
            fontWeight: 800,
            lineHeight: 1.02,
            textWrap: "balance",
          }}
        >
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
            marginTop: 22,
            fontSize: 38,
            fontWeight: 500,
            lineHeight: 1.3,
            color: MUTED,
            textWrap: "balance",
          }}
        >
          {audience}
        </div>

        <div
          style={{
            marginTop: 40,
            paddingTop: 36,
            borderTop: `2px solid ${LINE}`,
          }}
        >
          <div
            style={{
              fontSize: 46,
              fontWeight: 800,
              lineHeight: 1.15,
              textWrap: "balance",
            }}
          >
            {offer}
          </div>
          <div
            style={{
              marginTop: 12,
              fontSize: 36,
              fontWeight: 500,
              lineHeight: 1.3,
              color: MUTED,
            }}
          >
            {offerNote}
          </div>
        </div>

        {scarcity ? (
          <div
            style={{
              marginTop: 36,
              fontSize: 36,
              fontWeight: 700,
              lineHeight: 1.3,
              textWrap: "balance",
            }}
          >
            {scarcity}
          </div>
        ) : null}

        <div
          style={{
            marginTop: 40,
            borderRadius: 28,
            border: `3px solid ${ACCENT}`,
            padding: "6px 34px",
          }}
        >
          {contacts.map((c, i) => (
            <div
              key={c.label}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "20px 0",
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
