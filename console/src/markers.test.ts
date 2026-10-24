import { describe, expect, it } from "vitest";
import { markerView } from "./markers";
import { LINK_TONE, TONE } from "./tone";
import type { NavTrust } from "./types";

const trust = (state: NavTrust["state"]): NavTrust => ({
  vehicle_id: "uav1", stamp_s: 1, state, reason: null,
  horizontal_bound_m: null, confidence: 0, headroom: 0,
});

describe("map marker for a vehicle the backend can hear (unchanged from before the link work)", () => {
  it.each([
    ["GREEN", TONE.GREEN.hex, false, "uav1"],
    ["AMBER", TONE.AMBER.hex, true, "uav1 · AMBER"],
    ["RED", TONE.RED.hex, true, "uav1 · RED"],
  ] as const)("%s", (state, tone, dashed, tag) => {
    expect(markerView("uav1", trust(state), false)).toEqual({ tone, dashed, tag });
  });

  it("a vehicle with a position but no trust report yet gets the amber colour and no ring", () => {
    expect(markerView("uav1", undefined, false)).toEqual({ tone: TONE.AMBER.hex, dashed: false, tag: "uav1" });
  });
});

describe("map marker for a vehicle with no link (LL-01: a state last known is not shown as current)", () => {
  it.each(["GREEN", "AMBER", "RED"] as const)("drops the %s colour and says no link", (state) => {
    const view = markerView("uav1", trust(state), true);
    expect(view.tone).toBe(LINK_TONE);
    expect(Object.values(TONE).map((t) => t.hex)).not.toContain(view.tone);
    expect(view.dashed).toBe(true); // do not rely on this position
    expect(view.tag).toBe("uav1 · NO LINK");
  });

  it("does not need a trust report to say it", () => {
    expect(markerView("uav1", undefined, true).tag).toBe("uav1 · NO LINK");
  });
});
