import type { Reason, Recommendation, TrustState } from "./types";

export const STATE_LABEL: Record<TrustState, string> = {
  GREEN: "Trusted",
  AMBER: "Degraded",
  RED: "Not trusted",
};

export const REASON_LABEL: Record<Reason, string> = {
  GNSS_LOSS: "GNSS signal lost or degraded",
  INCONSISTENT_INNOVATION: "GNSS position disagrees with the vehicle's own sensors",
  BIAS_DRIFT: "Position is drifting",
  STALE: "No recent navigation data",
};

export function reasonText(reason: Reason | null): string {
  return reason ? REASON_LABEL[reason] : "Navigation consistent";
}

export function formatBound(bound: number | null): string {
  if (bound === null) return "unknown";
  return bound < 10 ? `±${bound.toFixed(2)} m` : `±${Math.round(bound)} m`;
}

/** 75 -> "1:15", 3725 -> "1:02:05" */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return `${h > 0 ? `${h}:` : ""}${mm}:${String(sec).padStart(2, "0")}`;
}

/** What approving a recommendation will do, one plain sentence per action. */
export function actionsOf(rec: Recommendation): string[] {
  const out: string[] = [];
  if (rec.command === "HOLD") out.push(`Hold ${rec.vehicle_id} in place`);
  if (rec.command === "RTL") out.push(`Send ${rec.vehicle_id} back to its launch point`);
  if (rec.command === "LAND") out.push(`Land ${rec.vehicle_id} where it is`);
  for (const m of rec.sector_moves) {
    out.push(`Move sector ${m.sector_id} from ${rec.vehicle_id} to ${m.to_vehicle}`);
  }
  return out;
}

export function titleOf(rec: Recommendation): string {
  const parts: string[] = [];
  if (rec.command === "HOLD") parts.push("Hold");
  if (rec.command === "RTL") parts.push("Return");
  if (rec.command === "LAND") parts.push("Land");
  if (rec.sector_moves.length > 0) parts.push("re-task");
  const text = parts.join(" and ");
  return `${text.charAt(0).toUpperCase()}${text.slice(1)} ${rec.vehicle_id}`;
}

export const ERROR_TEXT: Record<number, string> = {
  404: "This recommendation no longer exists.",
  409: "Someone has already decided on this recommendation.",
  410: "This recommendation expired before it was decided.",
  422: "The backend rejected the decision.",
};

/** Lower comes first: a warning-level recommendation, then any with a vehicle command, then re-tasks. */
export function urgencyRank(rec: Recommendation): number {
  if (urgencyNote(rec) !== null) return 0;
  return rec.command !== null ? 1 : 2;
}

/** Extra warning when waiting is itself dangerous. */
export function urgencyNote(rec: Recommendation): string | null {
  if (rec.command === "LAND" && rec.reason === "INCONSISTENT_INNOVATION") {
    return "This vehicle may be flying away from where it thinks it is, and nothing else will stop it.";
  }
  return null;
}
