import { describe, expect, it } from "vitest";
import { tickWhileNoLink, heardAgeS, markerView } from "./markers";
import { LINK_TONE, TONE } from "./tone";
import type { NavTrust } from "./types";

const trust = (state: NavTrust["state"]): NavTrust => ({
  vehicle_id: "uav1", stamp_s: 1, state, reason: null,
  horizontal_bound_m: null, confidence: 0, headroom: 0,
});

describe("map marker for a vehicle the backend can hear", () => {
  it.each([
    ["GREEN", TONE.GREEN.hex, false, "uav1"],
    ["AMBER", TONE.AMBER.hex, true, "uav1 · AMBER"],
    ["RED", TONE.RED.hex, true, "uav1 · RED"],
  ] as const)("%s", (state, tone, dashed, tag) => {
    expect(markerView("uav1", trust(state), false)).toEqual({ tone, dashed, tag });
  });

  it("draws the three trust states in three different colours", () => {
    const tones = (["GREEN", "AMBER", "RED"] as const).map((s) => markerView("uav1", trust(s), false).tone);
    expect(new Set(tones).size).toBe(3);
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

describe("age on the map for a vehicle with no link (issue 114)", () => {
  it("the no-link tag says how long ago the vehicle was last heard", () => {
    expect(markerView("uav1", trust("GREEN"), true, 42).tag).toBe("uav1 · NO LINK\nlast heard 0:42");
    expect(markerView("uav1", trust("RED"), true, 75).tag).toBe("uav1 · NO LINK\nlast heard 1:15");
  });

  it("keeps the vehicle's name on the first line, so a narrow tag at the map's edge still says which vehicle", () => {
    const [first] = markerView("uav3", trust("GREEN"), true, 16).tag.split("\n");
    expect(first).toBe("uav3 · NO LINK");
    expect(first!.length).toBeLessThanOrEqual("uav3 · NO LINK".length);
  });

  it("invents no age before the server clock is known", () => {
    expect(markerView("uav1", trust("GREEN"), true, null).tag).toBe("uav1 · NO LINK");
    expect(markerView("uav1", trust("GREEN"), true).tag).toBe("uav1 · NO LINK");
  });

  it("a vehicle with its link up is drawn exactly as before, whatever age is passed", () => {
    expect(markerView("uav1", trust("AMBER"), false, 42)).toEqual(markerView("uav1", trust("AMBER"), false));
  });

  it("works out the age on the server clock, or none", () => {
    expect(heardAgeS({ state: "NO_LINK", lastHeardAt_s: 18 }, 30)).toBe(12);
    expect(heardAgeS({ state: "NO_LINK", lastHeardAt_s: 18 }, null)).toBeNull();
    expect(heardAgeS(undefined, 30)).toBeNull();
  });

  it("the map needs the clock to tick only while some vehicle has no link", () => {
    const up = { uav1: { state: "LINK_OK" as const, lastHeardAt_s: 29 } };
    const down = { ...up, uav2: { state: "NO_LINK" as const, lastHeardAt_s: 18 } };
    // with every link up the value never changes, so nothing is redrawn as the clock advances
    expect([tickWhileNoLink({}, 10), tickWhileNoLink(up, 11), tickWhileNoLink(up, 12)]).toEqual([null, null, null]);
    expect([tickWhileNoLink(down, 30), tickWhileNoLink(down, 31)]).toEqual([30, 31]);
  });
});

describe("map marker while the backend is lost (issue 120)", () => {
  it("is never drawn in a trust colour, and says last known", () => {
    for (const state of ["GREEN", "AMBER", "RED"] as const) {
      const view = markerView("uav1", trust(state), false, null, true);
      expect(Object.values(TONE).map((t) => t.hex)).not.toContain(view.tone);
      expect(view.tag).toBe("uav1 · LAST KNOWN");
      expect(view.dashed).toBe(true);
    }
  });

  it("a vehicle with no link keeps its own wording", () => {
    expect(markerView("uav1", trust("GREEN"), true, 4, true).tag).toContain("NO LINK");
  });

  it("is the same as before while the backend is not lost", () => {
    expect(markerView("uav1", trust("RED"), false, null, false)).toEqual(markerView("uav1", trust("RED"), false));
  });
});
