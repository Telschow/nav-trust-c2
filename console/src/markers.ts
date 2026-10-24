import { formatDuration } from "./language";
import type { LinkInfo } from "./store";
import { LINK_TONE, TONE } from "./tone";
import type { NavTrust } from "./types";

export interface MarkerView {
  /** colour of the marker, ring and tag */
  tone: string;
  /** the dashed ring: do not rely on this position */
  dashed: boolean;
  tag: string;
}

/** Seconds since a vehicle was last heard on the server clock, or null when not known. */
export function heardAgeS(link: LinkInfo | undefined, now: number | null): number | null {
  return link && now !== null ? now - link.lastHeardAt_s : null;
}

/** The clock the map's markers depend on. It is the real clock only while some vehicle has no
 * link, because only then does a marker show an age; otherwise it never changes, so the map is
 * not redrawn on a timer for nothing. */
export function tickWhileNoLink(links: Record<string, LinkInfo>, now: number | null): number | null {
  return Object.values(links).some((l) => l.state === "NO_LINK") ? now : null;
}

/** How a vehicle is drawn on the map. With no link its trust colour is only the last state it
 * reported, so it gets the link colour and the words, never a trust colour. `ageS` is how long
 * ago it was last heard, if the clock is known. */
export function markerView(
  vehicleId: string,
  trust: NavTrust | undefined,
  noLink: boolean,
  ageS?: number | null,
): MarkerView {
  if (noLink) {
    const heard = ageS == null ? "" : `, last heard ${formatDuration(ageS)}`;
    return { tone: LINK_TONE, dashed: true, tag: `${vehicleId} · NO LINK${heard}` };
  }
  const flagged = trust !== undefined && trust.state !== "GREEN";
  return {
    tone: TONE[trust?.state ?? "AMBER"].hex,
    dashed: flagged,
    tag: `${vehicleId}${flagged ? ` · ${trust.state}` : ""}`,
  };
}
