import { describe, expect, it, vi } from "vitest";
import { announce, cuesFor } from "./cues";
import { initialState, reducer } from "./store";
import type { Action, ConsoleState } from "./store";
import type { Recommendation, ServerEvent, StateSnapshot } from "./types";

const rec: Recommendation = {
  id: "r1", vehicle_id: "uav2", created_s: 100, expires_s: 160, reason: "INCONSISTENT_INNOVATION",
  command: "LAND", sector_moves: [], rationale: "x",
};
const server = (e: Omit<ServerEvent, "server_s"> & { server_s?: number }): Action =>
  ({ type: "server", event: { server_s: 10, ...e } as ServerEvent, clientNow: 0 });
const step = (s: ConsoleState, a: Action) => {
  const next = reducer(s, a);
  return { next, cues: cuesFor(s, a, next) };
};
const link = (state: "LINK_OK" | "NO_LINK") => server({ type: "link", data: { vehicle_id: "uav2", state, last_report_age_s: 3 } });
const snapshot = (links: StateSnapshot["links"] = {}): Action =>
  server({ type: "state", server_s: 50, data: { server_s: 50, source: "live", origin: null, positions: {}, vehicles: {}, open_recommendations: [rec], links } });

describe("which tone a change deserves (issues 116, 117)", () => {
  it("a new recommendation sounds the decision-required tone", () => {
    expect(step(initialState, server({ type: "recommendation", data: rec })).cues).toEqual(["decision-required"]);
  });

  it("a re-raised recommendation sounds again", () => {
    let s = step(initialState, server({ type: "recommendation", data: rec })).next;
    s = step(s, server({ type: "decision", data: { recommendation_id: "r1", outcome: "EXPIRED", decided_s: 160, operator: "system", note: "" } })).next;
    expect(step(s, server({ type: "recommendation", data: { ...rec, id: "r2", created_s: 200, expires_s: 260 } })).cues).toEqual(["decision-required"]);
  });

  it("marking a decision seen is silent", () => {
    const s = step(initialState, server({ type: "recommendation", data: rec })).next;
    expect(step(s, { type: "seen", id: "r1" }).cues).toEqual([]);
  });

  it("a fresh snapshot is silent for what was already there", () => {
    expect(step(initialState, snapshot({ uav2: { vehicle_id: "uav2", state: "NO_LINK", last_report_age_s: 9 } })).cues).toEqual([]);
  });

  it("a decision being answered or expiring is silent", () => {
    const s = step(initialState, server({ type: "recommendation", data: rec })).next;
    expect(step(s, server({ type: "decision", data: { recommendation_id: "r1", outcome: "APPROVED", decided_s: 120, operator: "o", note: "" } })).cues).toEqual([]);
  });

  it("a vehicle losing its link sounds the link-lost tone", () => {
    let s = step(initialState, server({ type: "navtrust", data: { vehicle_id: "uav2", stamp_s: 1, state: "GREEN", reason: null, horizontal_bound_m: 3, confidence: 0.99, headroom: 0.9 } })).next;
    s = step(s, link("LINK_OK")).next;
    expect(step(s, link("NO_LINK")).cues).toEqual(["link-lost"]);
  });

  it("a link restored is silent", () => {
    const s = step(step(initialState, link("LINK_OK")).next, link("NO_LINK")).next;
    expect(step(s, link("LINK_OK")).cues).toEqual([]);
  });

  it("a vehicle that already has no link does not sound again", () => {
    const s = step(step(initialState, link("LINK_OK")).next, link("NO_LINK")).next;
    expect(step(s, link("NO_LINK")).cues).toEqual([]);
  });
});

describe("announce", () => {
  it("plays nothing while sound is off", () => {
    const play = vi.fn();
    announce(["decision-required"], false, { play });
    expect(play).not.toHaveBeenCalled();
  });

  it("plays each cue once when sound is on", () => {
    const play = vi.fn();
    announce(["decision-required", "link-lost"], true, { play });
    expect(play.mock.calls).toEqual([["decision-required"], ["link-lost"]]);
  });
});

import { loadSoundChoice, saveSoundChoice } from "./cues";

describe("the sound choice (issue 116)", () => {
  const memory = () => {
    const data = new Map<string, string>();
    return { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) };
  };

  it("is off until the operator turns it on", () => {
    expect(loadSoundChoice(memory())).toBe(false);
  });

  it("survives a reload", () => {
    const store = memory();
    saveSoundChoice(true, store);
    expect(loadSoundChoice(store)).toBe(true);
    saveSoundChoice(false, store);
    expect(loadSoundChoice(store)).toBe(false);
  });

  it("still works when storage throws", () => {
    const broken = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };
    expect(loadSoundChoice(broken)).toBe(false);
    expect(() => saveSoundChoice(true, broken)).not.toThrow();
  });
});
