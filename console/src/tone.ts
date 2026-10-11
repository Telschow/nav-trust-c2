import type { TrustState } from "./types";

export const TONE: Record<TrustState, { hex: string; text: string; bg: string; ring: string }> = {
  GREEN: { hex: "#52c28a", text: "text-ok", bg: "bg-ok/12", ring: "ring-ok/35" },
  AMBER: { hex: "#e3b341", text: "text-warn", bg: "bg-warn/12", ring: "ring-warn/40" },
  RED: { hex: "#f06262", text: "text-bad", bg: "bg-bad/14", ring: "ring-bad/45" },
};

/** One colour per vehicle for its sectors and trail. Kept away from the traffic-light hues. */
const VEHICLE_HUES = ["#6aa9e9", "#b59cf0", "#4cc2d1", "#e48bb8", "#a9c85a", "#e8955a"];

export function vehicleColor(vehicleId: string): string {
  const n = Number.parseInt(vehicleId.replace(/\D+/g, ""), 10);
  const index = Number.isFinite(n) ? Math.max(0, n - 1) : 0;
  return VEHICLE_HUES[index % VEHICLE_HUES.length]!;
}
