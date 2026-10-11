import type { Calibration, Reason, Recommendation, TrustState } from "./types";

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
  return `within ${Number(bound.toFixed(1))} m`;
}

export function formatPercent(fraction: number, digits = 0): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

/** Plain explanation of where the bound comes from, for a tooltip. */
export function calibrationText(c: Calibration): string {
  return (
    `The true position error stayed within ${Number(c.bound_m.toFixed(1))} m in ` +
    `${formatPercent(c.development_coverage, 1)} of ${c.development_reports.toLocaleString("en")} ` +
    `GREEN reports it was calibrated on, and in ${formatPercent(c.heldout_coverage, 1)} of ` +
    `${c.heldout_reports.toLocaleString("en")} on a separate set. ${c.source}. Simulation only.`
  );
}

export type HeadroomLevel = "ample" | "shrinking" | "low";

/** Headroom is 0..1; the cut-offs only choose the colour and the word. */
export function headroomLevel(headroom: number): HeadroomLevel {
  if (headroom >= 0.5) return "ample";
  return headroom >= 0.25 ? "shrinking" : "low";
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

/** A re-task with no vehicle command: say so, and why, so the operator is not left asking what
 * happens to the vehicle itself. */
export function contextNote(rec: Recommendation): string | null {
  if (rec.command !== null || rec.sector_moves.length === 0) return null;
  if (rec.reason === "GNSS_LOSS") return `No command is sent to ${rec.vehicle_id}: its own failsafe is acting.`;
  if (rec.reason === "STALE") return `No command is sent to ${rec.vehicle_id}: it has stopped reporting.`;
  return null;
}

/** Extra warning when waiting is itself dangerous. */
export function urgencyNote(rec: Recommendation): string | null {
  if (rec.command === "LAND" && rec.reason === "INCONSISTENT_INNOVATION") {
    return "This vehicle may be flying away from where it thinks it is, and nothing else will stop it.";
  }
  return null;
}
