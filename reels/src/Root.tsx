import "./index.css";
import { Composition } from "remotion";
import { REEL_DURATION_SECONDS, Reel } from "./Reel";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Reel"
      component={Reel}
      durationInFrames={Math.round(REEL_DURATION_SECONDS * 30)}
      fps={30}
      width={1080}
      height={1920}
    />
  );
};
