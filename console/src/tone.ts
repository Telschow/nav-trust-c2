import type { TrustState } from "./types";

export const TONE: Record<TrustState, { hex: string; text: string; bg: string; ring: string }> = {
  GREEN: { hex: "#34d399", text: "text-ok", bg: "bg-ok/12", ring: "ring-ok/35" },
  AMBER: { hex: "#fbbf24", text: "text-warn", bg: "bg-warn/12", ring: "ring-warn/40" },
  RED: { hex: "#f87171", text: "text-bad", bg: "bg-bad/14", ring: "ring-bad/45" },
};

/** One colour per vehicle for its sectors and trail. Kept away from the traffic-light hues. */
const VEHICLE_HUES = ["#60a5fa", "#c084fc", "#22d3ee", "#f472b6", "#a3e635", "#fb923c"];

export function vehicleColor(vehicleId: string): string {
  const n = Number.parseInt(vehicleId.replace(/\D+/g, ""), 10);
  const index = Number.isFinite(n) ? Math.max(0, n - 1) : 0;
  return VEHICLE_HUES[index % VEHICLE_HUES.length]!;
}
