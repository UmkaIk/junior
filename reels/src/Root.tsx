import "./index.css";
import { Composition, Still } from "remotion";
import { REEL_DURATION_SECONDS, Reel } from "./Reel";
import { Status } from "./Status";

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
    </>
  );
};
