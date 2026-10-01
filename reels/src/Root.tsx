import "./index.css";
import { Composition, Still } from "remotion";
import { REEL_DURATION_SECONDS, Reel } from "./Reel";
import { Status } from "./Status";
import { StatusAudit, statusAuditSchema } from "./StatusAudit";
import { StatusClients, statusClientsSchema } from "./StatusClients";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Reel"
        component={Reel}
        durationInFrames={Math.round(REEL_DURATION_SECONDS * 30)}
        fps={30}
        width={1080}
        height={1920}
      />
      <Still id="Status" component={Status} width={1080} height={1920} />
      {/* Render with --props=public/status/clients.json for the real texts. */}
      <Still
        id="StatusClients"
        component={StatusClients}
        schema={statusClientsSchema}
        defaultProps={{
          headline: "Клиенты из рилсов.",
          headlineAccent: "рилсов",
          subline: "Вы только снимаете на телефон.",
          body: "Остальное делаю я: монтаж, о чём снять, что сказать.",
          punch: "Без кривляний и трендов.",
          contacts: [{ label: "Telegram", value: "@username" }],
        }}
        width={1080}
        height={1920}
      />
      {/* Render with --props=public/status/audit.json for the real texts. */}
      <Still
        id="StatusAudit"
        component={StatusAudit}
        schema={statusAuditSchema}
        defaultProps={{
          photo: "desk.jpg",
          label: "Для кого это",
          headline: "Вам нужно больше клиентов",
          headlineAccent: "клиентов",
          audience: "Своё дело или свои услуги.",
          offer: "Бесплатно посмотрю вашу страницу",
          offerNote: "Страницы нет — подскажу, с чего начать.",
          contacts: [{ label: "Telegram", value: "@username" }],
        }}
        width={1080}
        height={1920}
      />
    </>
  );
};
