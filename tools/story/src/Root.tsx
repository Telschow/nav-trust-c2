import { Composition } from "remotion";
import { Story, DURATION_FRAMES, FPS } from "./Story";

export const Root = () => (
  <Composition id="Story" component={Story} durationInFrames={DURATION_FRAMES} fps={FPS} width={1080} height={1920} />
);
