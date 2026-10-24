import { LINK_TONE, TONE } from "./tone";
import type { NavTrust } from "./types";

export interface MarkerView {
  /** colour of the marker, ring and tag */
  tone: string;
  /** the dashed ring: do not rely on this position */
  dashed: boolean;
  tag: string;
}

/** How a vehicle is drawn on the map. With no link its trust colour is only the last state it
 * reported, so it gets the link colour and the words, never a trust colour. */
export function markerView(vehicleId: string, trust: NavTrust | undefined, noLink: boolean): MarkerView {
  if (noLink) return { tone: LINK_TONE, dashed: true, tag: `${vehicleId} · NO LINK` };
  const flagged = trust !== undefined && trust.state !== "GREEN";
  return {
    tone: TONE[trust?.state ?? "AMBER"].hex,
    dashed: flagged,
    tag: `${vehicleId}${flagged ? ` · ${trust.state}` : ""}`,
  };
}
