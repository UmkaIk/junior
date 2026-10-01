import { AbsoluteFill, Img, staticFile } from "remotion";
import { ACCENT, INK, TEXT, fontFamily } from "./brand";

// WhatsApp status draws its UI over the top ~160px and bottom ~180px.
const SAFE_TOP = 180;
const SAFE_BOTTOM = 190;
const SIDE = 72;
const MUTED = "rgba(255, 255, 255, 0.62)";
const LINE = "rgba(255, 255, 255, 0.14)";

const Offer: React.FC<{
  title: React.ReactNode;
  note?: string;
}> = ({ title, note }) => (
  <div
    style={{
      padding: "30px 0",
      borderTop: `2px solid ${LINE}`,
    }}
  >
    <div
      style={{
        fontSize: 50,
        fontWeight: 800,
        lineHeight: 1.12,
        textWrap: "balance",
      }}
    >
      {title}
    </div>
    {note ? (
      <div
        style={{
          marginTop: 12,
          fontSize: 34,
          fontWeight: 500,
          lineHeight: 1.3,
          color: MUTED,
        }}
      >
        {note}
      </div>
    ) : null}
  </div>
);

export const Status: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: INK, fontFamily, color: TEXT }}>
      {/* Photo fills the top; the person sits left of centre in the source. */}
      <AbsoluteFill style={{ height: 1240, overflow: "hidden" }}>
        <Img
          src={staticFile("status/avatar.jpg")}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: "36% 18%",
            // Zoom towards the face so it reads at story size.
            scale: 1.35,
            transformOrigin: "34% 22%",
          }}
        />
        <AbsoluteFill
          style={{
            background: `linear-gradient(180deg, ${INK}00 45%, ${INK}CC 78%, ${INK} 100%)`,
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
          Беру 2 человек по стартовой цене
        </div>

        <div
          style={{
            marginTop: 28,
            marginBottom: 36,
            fontSize: 76,
            fontWeight: 800,
            lineHeight: 1.04,
            textWrap: "balance",
          }}
        >
          Собираю первые кейсы по рилсам для экспертов)
        </div>

        <Offer
          title={
            <>
              10 роликов в&nbsp;месяц —{" "}
              <span style={{ color: ACCENT }}>35 000 ₽</span>
            </>
          }
          note="Темы, сценарии, список кадров и монтаж на мне. Вы только снимаетесь."
        />
        <Offer title="Только монтаж — от 2 000 ₽ за&nbsp;ролик" />
        <Offer
          title="Посоветуете эксперта — 10% ваши"
          note="от его первой оплаты"
        />

        <div
          style={{
            marginTop: 24,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "26px 34px",
            borderRadius: 28,
            border: `3px solid ${ACCENT}`,
          }}
        >
          <span style={{ fontSize: 36, fontWeight: 600, color: MUTED }}>
            Написать
          </span>
          <span style={{ fontSize: 50, fontWeight: 800, color: ACCENT }}>
            @almatinskii
          </span>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
