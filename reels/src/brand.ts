import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

// Brand palette: accent only on 1–2 words per frame, dark plaques, white text.
export const ACCENT = "#72D680";
export const INK = "#0E1211";
export const TEXT = "#FFFFFF";

// Bundled locally (variable font, Latin + Cyrillic) so renders never depend
// on reaching Google Fonts.
export const fontFamily = "Montserrat";
loadFont({
  family: fontFamily,
  url: staticFile("fonts/Montserrat.ttf"),
  weight: "100 900",
});
