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
import { decidedHistory, decidedRecommendations, initialState, isNoLink, openRecommendations, backendLost, expiredWithoutLink, isSeen, pinnedExpired, raisedAgain, reducer, serverNow, trustCounts } from "./store";
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

describe("link health (LL-01, issue 73)", () => {
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
    expect(s.links.uav1).toEqual({ state: "NO_LINK", lastHeardAt_s: 46 });
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
    expect(s.links.uav1).toEqual({ state: "NO_LINK", lastHeardAt_s: 57.5 });
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

  it("counts a vehicle with no link as no link, not as its last known state", () => {
    const data: StateSnapshot = {
      ...snapshot,
      vehicles: { uav1: trust("uav1", "GREEN"), uav2: trust("uav2", "GREEN"), uav3: trust("uav3", "RED", "STALE") },
      links: { uav2: { vehicle_id: "uav2", state: "NO_LINK", last_report_age_s: 5 } },
    };
    const s = apply(initialState, ev({ type: "state", server_s: 50, data }));
    expect(trustCounts(s)).toEqual({ GREEN: 1, AMBER: 0, RED: 1, noLink: 1 });
  });

  it("a fresh snapshot replaces the links", () => {
    let s = apply(initialState, ev({ type: "state", server_s: 50, data: withLinks({ uav1: { vehicle_id: "uav1", state: "NO_LINK", last_report_age_s: 4 } }) }));
    s = apply(s, ev({ type: "state", server_s: 80, data: snapshot }));
    expect(s.links).toEqual({});
  });
});

describe("re-raised decisions (issue 111)", () => {
  const recAt = (id: string, created: number, vehicle = "uav2", reason: Recommendation["reason"] = "INCONSISTENT_INNOVATION"): Recommendation =>
    ({ ...rec, id, vehicle_id: vehicle, reason, created_s: created, expires_s: created + 60 });
  const decide = (s: ConsoleState, id: string, outcome: "EXPIRED" | "DENIED" | "APPROVED", at: number) =>
    apply(s, ev({ type: "decision", server_s: at, data: { recommendation_id: id, outcome, decided_s: at, operator: "o", note: "" } }));
  const raise = (s: ConsoleState, r: Recommendation) => apply(s, ev({ type: "recommendation", server_s: r.created_s, data: r }));

  it("a first recommendation for a vehicle and reason is not marked", () => {
    const s = raise(initialState, recAt("r1", 100));
    expect(raisedAgain(s, recAt("r1", 100))).toBeNull();
  });

  it("one that follows an expiry for the same vehicle and reason is raised again, with when the last expired", () => {
    let s = raise(initialState, recAt("r1", 100));
    s = decide(s, "r1", "EXPIRED", 160);
    s = raise(s, recAt("r2", 161));
    expect(raisedAgain(s, recAt("r2", 161))).toEqual({ nth: 2, previousExpiredAt_s: 160 });
  });

  it("counts every earlier expiry and reports the latest", () => {
    let s = raise(initialState, recAt("r1", 100));
    s = decide(s, "r1", "EXPIRED", 160);
    s = raise(s, recAt("r2", 161));
    s = decide(s, "r2", "EXPIRED", 221);
    s = raise(s, recAt("r3", 222));
    expect(raisedAgain(s, recAt("r3", 222))).toEqual({ nth: 3, previousExpiredAt_s: 221 });
  });

  it("an earlier denial or approval is not a re-raise", () => {
    let s = raise(initialState, recAt("r1", 100));
    s = decide(s, "r1", "DENIED", 120);
    s = raise(s, recAt("r2", 130));
    expect(raisedAgain(s, recAt("r2", 130))).toBeNull();
  });

  it("an expiry for another vehicle or another reason does not count", () => {
    let s = raise(initialState, recAt("r1", 100, "uav3"));
    s = decide(s, "r1", "EXPIRED", 160);
    s = raise(s, recAt("r2", 161, "uav2"));
    s = raise(s, recAt("r3", 162, "uav3", "GNSS_LOSS"));
    expect(raisedAgain(s, recAt("r2", 161, "uav2"))).toBeNull();
    expect(raisedAgain(s, recAt("r3", 162, "uav3", "GNSS_LOSS"))).toBeNull();
  });

  it("a fresh snapshot forgets earlier expiries", () => {
    let s = raise(initialState, recAt("r1", 100));
    s = decide(s, "r1", "EXPIRED", 160);
    s = apply(s, ev({ type: "state", server_s: 200, data: { ...snapshot, open_recommendations: [recAt("r2", 161)] } }));
    expect(raisedAgain(s, recAt("r2", 161))).toBeNull();
  });
});

describe("expired decisions stay visible until seen (issue 112)", () => {
  const exp = (s: ConsoleState, id: string, vehicle: string, created: number) => {
    const r: Recommendation = { ...rec, id, vehicle_id: vehicle, created_s: created, expires_s: created + 60 };
    let n = apply(s, ev({ type: "recommendation", server_s: created, data: r }));
    n = apply(n, ev({ type: "decision", server_s: created + 60, data: { recommendation_id: id, outcome: "EXPIRED", decided_s: created + 60, operator: "system", note: "" } }));
    return n;
  };
  const answer = (s: ConsoleState, id: string, outcome: "APPROVED" | "DENIED") =>
    apply(s, ev({ type: "decision", server_s: 150, data: { recommendation_id: id, outcome, decided_s: 150, operator: "o", note: "" } }));

  it("an expired recommendation is pinned, newest first", () => {
    let s = exp(initialState, "r1", "uav2", 100);
    s = exp(s, "r2", "uav3", 200);
    expect(pinnedExpired(s).map((p) => p.rec.id)).toEqual(["r2", "r1"]);
  });

  describe("whether the vehicle could be heard comes from the backend's record of the expiry (issues 129, 135)", () => {
    const expiry = (heard: boolean | undefined) => {
      let s = apply(initialState, ev({ type: "recommendation", data: rec }));
      const data = { recommendation_id: "r1", outcome: "EXPIRED" as const, decided_s: 160, operator: "system", note: "", ...(heard === undefined ? {} : { vehicle_heard: heard }) };
      s = apply(s, ev({ type: "decision", data }));
      return s;
    };
    const link = (s: ConsoleState, state: "LINK_OK" | "NO_LINK") =>
      apply(s, ev({ type: "link", server_s: 200, data: { vehicle_id: "uav2", state, last_report_age_s: 3 } }));

    it("an expiry the backend says was heard stays heard after the link is lost", () => {
      expect(expiredWithoutLink(link(expiry(true), "NO_LINK"), "r1")).toBe(false);
    });

    it("an expiry the backend says had no link stays so after the link returns", () => {
      expect(expiredWithoutLink(link(expiry(false), "LINK_OK"), "r1")).toBe(true);
    });

    it("an event that arrives late is judged by the backend's field, not the link state now", () => {
      const lostNow = link(apply(initialState, ev({ type: "recommendation", data: rec })), "NO_LINK");
      const s = apply(lostNow, ev({ type: "decision", data: { recommendation_id: "r1", outcome: "EXPIRED", decided_s: 160, operator: "system", note: "", vehicle_heard: true } }));
      expect(expiredWithoutLink(s, "r1")).toBe(false);
    });

    it("an older backend sends no field: treated as heard", () => {
      expect(expiredWithoutLink(expiry(undefined), "r1")).toBe(false);
    });
  });

  it("stays pinned however many other events arrive", () => {
    let s = exp(initialState, "r1", "uav2", 100);
    for (let i = 0; i < 70; i++) s = apply(s, ev({ type: "navtrust", server_s: 200 + i, data: trust("uav1", i % 2 ? "GREEN" : "AMBER", i % 2 ? null : "GNSS_LOSS") }));
    expect(pinnedExpired(s).map((p) => p.rec.id)).toEqual(["r1"]);
  });

  it("marking it seen removes the notice but keeps the decision in the history", () => {
    let s = exp(initialState, "r1", "uav2", 100);
    s = reducer(s, { type: "seen", id: "r1" });
    expect(pinnedExpired(s)).toEqual([]);
    expect(decidedRecommendations(s).map((d) => d.rec.id)).toEqual(["r1"]);
  });

  it("an unseen expiry is shown pinned, not twice: the history lists it only once seen", () => {
    let s = exp(initialState, "r1", "uav2", 100);
    expect(decidedHistory(s).map((d) => d.rec.id)).toEqual([]);
    s = reducer(s, { type: "seen", id: "r1" });
    expect(decidedHistory(s).map((d) => d.rec.id)).toEqual(["r1"]);
  });

  it("an approved or denied decision is not pinned", () => {
    let s = apply(initialState, ev({ type: "recommendation", server_s: 100, data: { ...rec, id: "a" } }));
    s = answer(s, "a", "APPROVED");
    s = apply(s, ev({ type: "recommendation", server_s: 100, data: { ...rec, id: "d" } }));
    s = answer(s, "d", "DENIED");
    expect(pinnedExpired(s)).toEqual([]);
  });

  it("a fresh snapshot starts with nothing pinned and nothing seen", () => {
    let s = exp(initialState, "r1", "uav2", 100);
    s = apply(s, ev({ type: "state", server_s: 300, data: snapshot }));
    expect(pinnedExpired(s)).toEqual([]);
    expect(s.seen).toEqual([]);
  });
});

describe("an open decision marked seen (issue 115)", () => {
  const rec2: Recommendation = { ...rec, id: "r2", created_s: 200, expires_s: 260 };
  const opened = () => apply(initialState, ev({ type: "recommendation", data: rec }));

  it("is seen once marked, and stays open", () => {
    const s = reducer(opened(), { type: "seen", id: "r1" });
    expect(isSeen(s, "r1")).toBe(true);
    expect(openRecommendations(s).map((r) => r.id)).toEqual(["r1"]);
  });

  it("starts unseen", () => {
    expect(isSeen(opened(), "r1")).toBe(false);
  });

  it("a re-raised recommendation starts unseen even if the previous one was seen", () => {
    let s = reducer(opened(), { type: "seen", id: "r1" });
    s = apply(s, ev({ type: "decision", data: { recommendation_id: "r1", outcome: "EXPIRED", decided_s: 160, operator: "system", note: "" } }));
    s = apply(s, ev({ type: "recommendation", data: rec2 }));
    expect(isSeen(s, "r2")).toBe(false);
  });

  it("approving or denying works as before after seen", () => {
    let s = reducer(opened(), { type: "seen", id: "r1" });
    s = apply(s, ev({ type: "decision", data: { recommendation_id: "r1", outcome: "APPROVED", decided_s: 120, operator: "o", note: "" } }));
    expect(openRecommendations(s)).toEqual([]);
    expect(s.decisions.r1?.outcome).toBe("APPROVED");
  });

  it("one marked seen while open still appears as an unseen expiry when it expires", () => {
    let s = reducer(opened(), { type: "seen", id: "r1" });
    s = apply(s, ev({ type: "decision", data: { recommendation_id: "r1", outcome: "EXPIRED", decided_s: 160, operator: "system", note: "" } }));
    expect(pinnedExpired(s).map((p) => p.rec.id)).toEqual(["r1"]);
    expect(isSeen(s, "r1")).toBe(false);
  });

  it("a fresh snapshot starts with nothing seen", () => {
    const s = apply(reducer(opened(), { type: "seen", id: "r1" }), ev({ type: "state", server_s: 50, data: snapshot }));
    expect(isSeen(s, "r1")).toBe(false);
  });
});

describe("losing the backend (issue 120)", () => {
  const live = () => apply(apply(initialState, ev({ type: "state", server_s: 50, data: snapshot })), ev({ type: "navtrust", server_s: 60, data: trust("uav1", "GREEN") }));
  const connected = (s: ConsoleState, on: boolean) => reducer(s, { type: "connection", connected: on });

  it("is not lost while connected and synced", () => {
    expect(backendLost(connected(live(), true))).toBe(false);
  });

  it("is lost as soon as the connection drops", () => {
    expect(backendLost(connected(live(), false))).toBe(true);
  });

  it("stays lost after the connection returns until a fresh snapshot arrives", () => {
    const back = connected(connected(live(), false), true);
    expect(backendLost(back)).toBe(true);
    expect(backendLost(apply(back, ev({ type: "state", server_s: 90, data: snapshot })))).toBe(false);
  });

  it("remembers when the backend was last heard, on the server clock", () => {
    expect(live().lastBackendAt_s).toBe(60);
  });
});

describe("recovery after an outage (issue 77)", () => {
  const summary = (superseded: string[]) =>
    ev({ type: "outage_summary", server_s: 90, data: { vehicle_id: "uav2", duration_s: 12, trust: trust("uav2", "AMBER", "STALE"), trust_changes: [{ server_s: 90, state: "AMBER", reason: "STALE" }], onboard_actions: [], superseded } });

  it("a superseded recommendation closes, is not an unseen expiry, and is listed as decided", () => {
    let s = apply(initialState, ev({ type: "recommendation", data: rec }));
    s = apply(s, ev({ type: "decision", data: { recommendation_id: "r1", outcome: "SUPERSEDED", decided_s: 90, operator: "system", note: "" } }));
    expect(openRecommendations(s)).toEqual([]);
    expect(pinnedExpired(s)).toEqual([]);
    expect(decidedHistory(s).map((d) => d.decision.outcome)).toEqual(["SUPERSEDED"]);
  });

  it("the log says the situation changed, not that an operator did it", () => {
    let s = apply(initialState, ev({ type: "recommendation", data: rec }));
    s = apply(s, ev({ type: "decision", data: { recommendation_id: "r1", outcome: "SUPERSEDED", decided_s: 90, operator: "system", note: "" } }));
    expect(s.log[0]?.text).toContain("superseded, the situation changed");
    expect(s.log[0]?.text).not.toContain("by system");
  });

  it("the summary is logged with how long the link was down and what it closed", () => {
    const s = apply(initialState, summary(["r1"]));
    const text = s.log[0]?.text ?? "";
    expect(text).toContain("uav2");
    expect(text).toContain("0:12");
    expect(text).toContain("1 decision closed");
  });

  it("says plainly when the situation had not changed", () => {
    expect(apply(initialState, summary([])).log[0]?.text).toContain("nothing closed");
  });
});
