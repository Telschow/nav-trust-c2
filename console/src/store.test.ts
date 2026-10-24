import { describe, expect, it } from "vitest";
import {
  actionsOf,
  calibrationText,
  contextNote,
  formatBound,
  formatDuration,
  formatPercent,
  headroomLevel,
  reasonText,
  titleOf,
  urgencyNote,
} from "./language";
import { decidedRecommendations, initialState, isNoLink, openRecommendations, reducer, serverNow } from "./store";
import type { ConsoleState } from "./store";
import type { NavTrust, Recommendation, ServerEvent, StateSnapshot } from "./types";

const trust = (v: string, state: NavTrust["state"], reason: NavTrust["reason"] = null): NavTrust => ({
  vehicle_id: v, stamp_s: 1, state, reason, horizontal_bound_m: state === "GREEN" ? 3 : null, confidence: state === "GREEN" ? 0.99 : 0, headroom: state === "GREEN" ? 0.9 : 0,
});
const rec: Recommendation = {
  id: "r1", vehicle_id: "uav2", created_s: 100, expires_s: 160, reason: "INCONSISTENT_INNOVATION",
  command: "HOLD", sector_moves: [{ sector_id: "S2", to_vehicle: "uav3" }], rationale: "x",
};
const ev = (e: Omit<ServerEvent, "server_s"> & { server_s?: number }): ServerEvent =>
  ({ server_s: 10, ...e }) as ServerEvent;
const apply = (s: ConsoleState, e: ServerEvent, clientNow = 0) =>
  reducer(s, { type: "server", event: e, clientNow });

const snapshot: StateSnapshot = {
  server_s: 50, source: "live", origin: { lat_deg: 47, lon_deg: 8 }, positions: {},
  vehicles: { uav1: trust("uav1", "GREEN") }, open_recommendations: [rec],
};

describe("reducer", () => {
  it("loads a snapshot and derives the clock offset", () => {
    const s = apply(initialState, ev({ type: "state", server_s: 50, data: snapshot }), 20);
    expect(s.vehicles.uav1?.state).toBe("GREEN");
    expect(openRecommendations(s).map((r) => r.id)).toEqual(["r1"]);
    expect(serverNow(s, 25)).toBe(55);
    expect(s.stateSince.uav1).toBe(50);
  });

  it("logs and timestamps only real changes of state or reason", () => {
    let s = apply(initialState, ev({ type: "state", server_s: 50, data: snapshot }));
    s = apply(s, ev({ type: "navtrust", server_s: 60, data: trust("uav1", "GREEN") }));
    expect(s.log).toHaveLength(0);
    expect(s.stateSince.uav1).toBe(50);
    s = apply(s, ev({ type: "navtrust", server_s: 70, data: trust("uav1", "AMBER", "GNSS_LOSS") }));
    expect(s.stateSince.uav1).toBe(70);
    expect(s.log[0]?.text).toContain("uav1 is now AMBER");
    s = apply(s, ev({ type: "navtrust", server_s: 80, data: trust("uav1", "RED", "GNSS_LOSS") }));
    expect(s.log).toHaveLength(2);
    s = apply(s, ev({ type: "navtrust", server_s: 85, data: trust("uav1", "RED", "STALE") }));
    expect(s.stateSince.uav1).toBe(80); // reason changed, state did not
    expect(s.log).toHaveLength(3);
  });

  it("closes a recommendation when its decision arrives", () => {
    let s = apply(initialState, ev({ type: "recommendation", data: rec }));
    expect(openRecommendations(s)).toHaveLength(1);
    s = apply(s, ev({ type: "decision", data: { recommendation_id: "r1", outcome: "APPROVED", decided_s: 12, operator: "daniel", note: "" } }));
    expect(openRecommendations(s)).toHaveLength(0);
    expect(decidedRecommendations(s)[0]?.decision.operator).toBe("daniel");
    expect(s.log[0]?.text).toContain("approved by daniel");
  });

  it("keeps the execution result the console got from its own POST", () => {
    let s = apply(initialState, ev({ type: "recommendation", data: rec }));
    s = reducer(s, { type: "decided", decision: { recommendation_id: "r1", outcome: "APPROVED", decided_s: 12, operator: "daniel", note: "", execution: { executed: true, reason: null, actions: ["HOLD uav2"] } } });
    s = apply(s, ev({ type: "decision", data: { recommendation_id: "r1", outcome: "APPROVED", decided_s: 12, operator: "daniel", note: "" } }));
    expect(s.decisions.r1?.execution?.actions).toEqual(["HOLD uav2"]);
  });

  it("caps trails and the activity log, and skips repeated positions", () => {
    let s = initialState;
    for (let i = 0; i < 400; i++) {
      s = apply(s, ev({ type: "position", data: { vehicle_id: "uav1", lat_deg: 47 + i * 1e-5, lon_deg: 8, alt_m: 30, stamp_s: i } }));
    }
    expect(s.trails.uav1).toHaveLength(150);
    const same = { vehicle_id: "uav1", lat_deg: 47.0039, lon_deg: 8, alt_m: 30, stamp_s: 999 };
    const before = s.trails.uav1!.length;
    s = apply(s, ev({ type: "position", data: same }));
    s = apply(s, ev({ type: "position", data: same }));
    expect(s.trails.uav1!.length).toBe(Math.min(150, before + 1));
    for (let i = 0; i < 200; i++) s = apply(s, ev({ type: "recommendation", data: { ...rec, id: `r${i}` } }));
    expect(s.log).toHaveLength(60);
  });

  it("a fresh snapshot replaces vehicle data but keeps nothing stale", () => {
    let s = apply(initialState, ev({ type: "navtrust", data: trust("ghost", "RED", "STALE") }));
    s = apply(s, ev({ type: "state", server_s: 50, data: snapshot }));
    expect(Object.keys(s.vehicles)).toEqual(["uav1"]);
  });
});

describe("language", () => {
  it("formats bounds, durations and reasons", () => {
    expect(formatBound(null)).toBe("unknown");
    expect(formatBound(3)).toBe("within 3 m");
    expect(formatBound(2.46)).toBe("within 2.5 m");
    expect(formatPercent(0.99)).toBe("99%");
    expect(formatPercent(0.9972, 1)).toBe("99.7%");
    expect(headroomLevel(0.9)).toBe("ample");
    expect(headroomLevel(0.4)).toBe("shrinking");
    expect(headroomLevel(0.1)).toBe("low");
    expect(formatDuration(75)).toBe("1:15");
    expect(formatDuration(3725)).toBe("1:02:05");
    expect(formatDuration(-3)).toBe("0:00");
    expect(reasonText(null)).toBe("Navigation consistent");
    expect(reasonText("STALE")).toBe("No recent navigation data");
  });

  it("describes exactly what approving will do", () => {
    expect(actionsOf(rec)).toEqual(["Hold uav2 in place", "Move sector S2 from uav2 to uav3"]);
    expect(titleOf(rec)).toBe("Hold uav2 and hand over S2");
    expect(titleOf({ ...rec, command: null })).toBe("Hand over S2 from uav2");
    expect(actionsOf({ ...rec, command: "RTL", sector_moves: [] })).toEqual(["Send uav2 back to its launch point"]);
    expect(actionsOf({ ...rec, command: "LAND", sector_moves: [] })).toEqual(["Land uav2 where it is"]);
    expect(titleOf({ ...rec, command: "LAND" })).toBe("Land uav2 and hand over S2");
    expect(titleOf({ ...rec, sector_moves: [] })).toBe("Hold uav2");
  });
});

describe("urgency", () => {
  it("warns only when a frozen-position vehicle is to be landed", () => {
    expect(urgencyNote({ ...rec, command: "LAND" })).toContain("flying away");
    expect(urgencyNote({ ...rec, command: "HOLD" })).toBeNull();
    expect(urgencyNote({ ...rec, command: "LAND", reason: "GNSS_LOSS" })).toBeNull();
  });
});

describe("queue order", () => {
  const routine: Recommendation = { ...rec, id: "routine", vehicle_id: "uav3", reason: "GNSS_LOSS", command: null, created_s: 100 };
  const urgent: Recommendation = { ...rec, id: "urgent", command: "LAND", created_s: 110 };
  const commanded: Recommendation = { ...rec, id: "rtl", command: "RTL", reason: "GNSS_LOSS", created_s: 105 };

  it("puts the urgent card first even though it arrived last", () => {
    let s = apply(initialState, ev({ type: "recommendation", data: routine }));
    s = apply(s, ev({ type: "recommendation", data: urgent }));
    expect(openRecommendations(s).map((r) => r.id)).toEqual(["urgent", "routine"]);
  });

  it("orders urgent, then commanded, then re-task only, each oldest first", () => {
    let s = initialState;
    for (const r of [routine, commanded, urgent, { ...routine, id: "routine2", created_s: 120 }]) {
      s = apply(s, ev({ type: "recommendation", data: r }));
    }
    expect(openRecommendations(s).map((r) => r.id)).toEqual(["urgent", "rtl", "routine", "routine2"]);
  });
});

describe("calibration text", () => {
  it("states the coverage, both data sets and that it is simulation only", () => {
    const text = calibrationText({
      bound_m: 3, coverage: 0.99, development_reports: 4040, development_coverage: 1,
      heldout_reports: 5308, heldout_coverage: 0.9972, source: "PX4 SITL in Gazebo",
    });
    expect(text).toContain("within 3 m");
    expect(text).toContain("100.0% of 4,040");
    expect(text).toContain("99.7% of 5,308");
    expect(text).toContain("Simulation only");
  });
});

describe("fleet action", () => {
  it("keeps the assignment and which sectors are done", () => {
    const next = reducer(initialState, { type: "fleet", fleet: { uav1: [] }, done: ["S1"] });
    expect(next.doneSectors).toEqual(["S1"]);
    expect(next.fleet).toEqual({ uav1: [] });
  });
});

describe("C2-03: every recommendation the recommender can make is readable and actionable", () => {
  // the combinations c2/recommender.py produces (ADR 0002 and 0003)
  const make = (reason: Recommendation["reason"], command: Recommendation["command"]): Recommendation => ({
    id: "r", vehicle_id: "uav2", created_s: 0, expires_s: 60, reason, command,
    sector_moves: [{ sector_id: "S2", to_vehicle: "uav1" }], rationale: "",
  });
  const combos = [
    make("GNSS_LOSS", null),
    make("STALE", null),
    make("INCONSISTENT_INNOVATION", "LAND"),
  ];

  it("names the vehicle in the title and in every action, and shows no internal code", () => {
    for (const rec of combos) {
      expect(titleOf(rec)).toContain("uav2");
      expect(actionsOf(rec).length).toBeGreaterThan(0);
      for (const a of actionsOf(rec)) expect(a).toMatch(/uav\d/);
      for (const text of [reasonText(rec.reason), titleOf(rec), ...actionsOf(rec)]) {
        expect(text).not.toMatch(/[A-Z]+_[A-Z_]+/);
      }
    }
  });

  it("gives each reason its own wording", () => {
    const texts = combos.map((r) => reasonText(r.reason));
    expect(new Set(texts).size).toBe(texts.length);
  });

  it("says that nothing is sent to the vehicle when there is no command, and warns when landing is urgent", () => {
    expect(contextNote(combos[0]!)).toContain("failsafe");
    expect(contextNote(combos[1]!)).toContain("stopped reporting");
    expect(contextNote(combos[2]!)).toBeNull();
    expect(urgencyNote(combos[2]!)).not.toBeNull();
    expect(urgencyNote(combos[0]!)).toBeNull();
  });
});

describe("link health (issue 73)", () => {
  const withLinks = (links: NonNullable<StateSnapshot["links"]>): StateSnapshot => ({ ...snapshot, links });

  it("loads each vehicle's link from the snapshot and works out when it was last heard", () => {
    const s = apply(
      initialState,
      ev({
        type: "state",
        server_s: 50,
        data: withLinks({
          uav1: { vehicle_id: "uav1", state: "NO_LINK", last_report_age_s: 4 },
          uav2: { vehicle_id: "uav2", state: "LINK_OK", last_report_age_s: 0.5 },
        }),
      }),
    );
    expect(s.links.uav1).toEqual({ state: "NO_LINK", lastHeard_s: 46 });
    expect(s.links.uav2?.state).toBe("LINK_OK");
    expect(isNoLink(s, "uav1")).toBe(true);
    expect(isNoLink(s, "uav2")).toBe(false);
  });

  it("an older backend that sends no links shows no link problem for anyone", () => {
    const s = apply(initialState, ev({ type: "state", server_s: 50, data: snapshot }));
    expect(s.links).toEqual({});
    expect(isNoLink(s, "uav1")).toBe(false);
  });

  it("a vehicle going quiet is NO_LINK, dated from the age the backend reports, and is logged", () => {
    let s = apply(initialState, ev({ type: "state", server_s: 50, data: snapshot }));
    s = apply(
      s,
      ev({ type: "link", server_s: 60, data: { vehicle_id: "uav1", state: "NO_LINK", last_report_age_s: 2.5 } }),
    );
    expect(s.links.uav1).toEqual({ state: "NO_LINK", lastHeard_s: 57.5 });
    expect(s.log[0]?.tone).toBe("warn");
    expect(s.log[0]?.text).toContain("uav1 has no link");
  });

  it("the next report restores the link and the log says how long it was silent", () => {
    let s = apply(initialState, ev({ type: "state", server_s: 50, data: snapshot }));
    s = apply(s, ev({ type: "link", server_s: 60, data: { vehicle_id: "uav1", state: "NO_LINK", last_report_age_s: 2.5 } }));
    s = apply(s, ev({ type: "link", server_s: 72, data: { vehicle_id: "uav1", state: "LINK_OK", last_report_age_s: 14 } }));
    expect(s.links.uav1?.state).toBe("LINK_OK");
    expect(isNoLink(s, "uav1")).toBe(false);
    expect(s.log[0]?.tone).toBe("good");
    expect(s.log[0]?.text).toContain("uav1 link restored after 0:14");
  });

  it("the last trust state is kept while the link is down, to be shown as last known", () => {
    let s = apply(initialState, ev({ type: "state", server_s: 50, data: snapshot }));
    s = apply(s, ev({ type: "link", server_s: 60, data: { vehicle_id: "uav1", state: "NO_LINK", last_report_age_s: 2.5 } }));
    expect(s.vehicles.uav1?.state).toBe("GREEN");
  });

  it("a fresh snapshot replaces the links", () => {
    let s = apply(initialState, ev({ type: "state", server_s: 50, data: withLinks({ uav1: { vehicle_id: "uav1", state: "NO_LINK", last_report_age_s: 4 } }) }));
    s = apply(s, ev({ type: "state", server_s: 80, data: snapshot }));
    expect(s.links).toEqual({});
  });
});
