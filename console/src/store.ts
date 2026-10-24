import { actionsOf, formatDuration, reasonText, titleOf, urgencyRank } from "./language";
import type {
  Calibration,
  Decision,
  Fleet,
  LinkState,
  LinkStatus,
  NavTrust,
  Origin,
  Position,
  Recommendation,
  ServerEvent,
  TrustState,
} from "./types";

const TRAIL_POINTS = 150;
const HISTORY_POINTS = 240;
const LOG_ENTRIES = 60;

export interface HistoryPoint {
  server_s: number;
  state: TrustState;
}

export interface LogEntry {
  id: number;
  server_s: number;
  tone: "info" | "good" | "warn" | "bad";
  text: string;
}

export interface LinkInfo {
  state: LinkState;
  /** server_s of the vehicle's last report, so "last heard" can keep counting on the server clock */
  lastHeard_s: number;
}

export interface ConsoleState {
  connected: boolean;
  /** server clock minus client clock (seconds); null until the first message */
  clockOffset: number | null;
  source: string;
  origin: Origin | null;
  vehicles: Record<string, NavTrust>;
  links: Record<string, LinkInfo>;
  positions: Record<string, Position>;
  trails: Record<string, [number, number][]>; // [lon, lat]
  history: Record<string, HistoryPoint[]>;
  stateSince: Record<string, number>; // server_s when the state last changed
  recommendations: Record<string, Recommendation>;
  decisions: Record<string, Decision>;
  fleet: Fleet;
  doneSectors: string[]; // ids of sectors the backend says have been flown
  calibration: Calibration | null;
  log: LogEntry[];
  nextLogId: number;
}

export const initialState: ConsoleState = {
  connected: false,
  clockOffset: null,
  source: "live",
  origin: null,
  vehicles: {},
  links: {},
  positions: {},
  trails: {},
  history: {},
  stateSince: {},
  recommendations: {},
  decisions: {},
  fleet: {},
  doneSectors: [],
  calibration: null,
  log: [],
  nextLogId: 1,
};

export type Action =
  | { type: "connection"; connected: boolean }
  | { type: "server"; event: ServerEvent; clientNow: number }
  | { type: "fleet"; fleet: Fleet; done: string[] }
  | { type: "calibration"; calibration: Calibration }
  | { type: "decided"; decision: Decision };

function withLog(
  s: ConsoleState,
  server_s: number,
  tone: LogEntry["tone"],
  text: string,
): ConsoleState {
  const entry: LogEntry = { id: s.nextLogId, server_s, tone, text };
  return { ...s, log: [entry, ...s.log].slice(0, LOG_ENTRIES), nextLogId: s.nextLogId + 1 };
}

function applyTrust(s: ConsoleState, msg: NavTrust, server_s: number): ConsoleState {
  const previous = s.vehicles[msg.vehicle_id];
  const stateChanged = !previous || previous.state !== msg.state;
  const reasonChanged = !previous || previous.reason !== msg.reason;
  const history = [...(s.history[msg.vehicle_id] ?? []), { server_s, state: msg.state }].slice(
    -HISTORY_POINTS,
  );
  let next: ConsoleState = {
    ...s,
    vehicles: { ...s.vehicles, [msg.vehicle_id]: msg },
    history: { ...s.history, [msg.vehicle_id]: history },
    stateSince: stateChanged
      ? { ...s.stateSince, [msg.vehicle_id]: server_s }
      : s.stateSince,
  };
  if (previous && (stateChanged || reasonChanged)) {
    const tone = msg.state === "GREEN" ? "good" : msg.state === "AMBER" ? "warn" : "bad";
    next = withLog(next, server_s, tone, `${msg.vehicle_id} is now ${msg.state}: ${reasonText(msg.reason)}`);
  }
  return next;
}

function applyLink(s: ConsoleState, change: LinkStatus, server_s: number): ConsoleState {
  const silent = formatDuration(change.last_report_age_s);
  const next: ConsoleState = {
    ...s,
    links: {
      ...s.links,
      [change.vehicle_id]: {
        state: change.state,
        lastHeard_s: change.state === "NO_LINK" ? server_s - change.last_report_age_s : server_s,
      },
    },
  };
  return change.state === "NO_LINK"
    ? withLog(next, server_s, "warn", `${change.vehicle_id} has no link: last heard ${silent} ago`)
    : withLog(next, server_s, "good", `${change.vehicle_id} link restored after ${silent}`);
}

function applyPosition(s: ConsoleState, pos: Position): ConsoleState {
  const trail = s.trails[pos.vehicle_id] ?? [];
  const last = trail[trail.length - 1];
  const moved = !last || last[0] !== pos.lon_deg || last[1] !== pos.lat_deg;
  return {
    ...s,
    positions: { ...s.positions, [pos.vehicle_id]: pos },
    trails: moved
      ? { ...s.trails, [pos.vehicle_id]: [...trail, [pos.lon_deg, pos.lat_deg] as [number, number]].slice(-TRAIL_POINTS) }
      : s.trails,
  };
}

export function reducer(s: ConsoleState, action: Action): ConsoleState {
  switch (action.type) {
    case "connection":
      return { ...s, connected: action.connected };
    case "fleet":
      return { ...s, fleet: action.fleet, doneSectors: action.done };
    case "calibration":
      return { ...s, calibration: action.calibration };
    case "decided":
      return { ...s, decisions: { ...s.decisions, [action.decision.recommendation_id]: action.decision } };
    case "server": {
      const { event, clientNow } = action;
      const base: ConsoleState = { ...s, clockOffset: event.server_s - clientNow };
      switch (event.type) {
        case "state": {
          const snap = event.data;
          const recs: Record<string, Recommendation> = {};
          for (const r of snap.open_recommendations) recs[r.id] = r;
          const stateSince: Record<string, number> = {};
          const history: Record<string, HistoryPoint[]> = {};
          for (const [v, t] of Object.entries(snap.vehicles)) {
            stateSince[v] = snap.server_s;
            history[v] = [{ server_s: snap.server_s, state: t.state }];
          }
          const links: Record<string, LinkInfo> = {};
          for (const [v, l] of Object.entries(snap.links ?? {})) {
            links[v] = { state: l.state, lastHeard_s: snap.server_s - l.last_report_age_s };
          }
          return {
            ...base,
            source: snap.source,
            origin: snap.origin,
            vehicles: snap.vehicles,
            links,
            positions: snap.positions,
            trails: {},
            history,
            stateSince,
            recommendations: recs,
            decisions: {},
          };
        }
        case "navtrust":
          return applyTrust(base, event.data, event.server_s);
        case "position":
          return applyPosition(base, event.data);
        case "link":
          return applyLink(base, event.data, event.server_s);
        case "origin":
          return { ...base, origin: event.data };
        case "source":
          return { ...base, source: event.data.label };
        case "recommendation": {
          const rec = event.data;
          const next = { ...base, recommendations: { ...base.recommendations, [rec.id]: rec } };
          return withLog(next, event.server_s, "warn", `Recommendation for ${rec.vehicle_id}: ${actionsOf(rec).join("; ")}`);
        }
        case "decision": {
          const d = event.data;
          const rec = base.recommendations[d.recommendation_id];
          const tone = d.outcome === "APPROVED" ? "good" : d.outcome === "DENIED" ? "info" : "warn";
          const what = rec ? titleOf(rec) : d.recommendation_id;
          const who = d.outcome === "EXPIRED" ? "expired unanswered" : `${d.outcome.toLowerCase()} by ${d.operator}`;
          return withLog(
            { ...base, decisions: { ...base.decisions, [d.recommendation_id]: { ...base.decisions[d.recommendation_id], ...d } } },
            event.server_s,
            tone,
            `${what}: ${who}`,
          );
        }
      }
    }
  }
}

/** The backend has not heard from this vehicle: its trust state is only the last one known. */
export function isNoLink(s: ConsoleState, vehicleId: string): boolean {
  return s.links[vehicleId]?.state === "NO_LINK";
}

/** Recommendations still waiting for an answer: most urgent first, then oldest first. */
export function openRecommendations(s: ConsoleState): Recommendation[] {
  return Object.values(s.recommendations)
    .filter((r) => !s.decisions[r.id])
    .sort((a, b) => urgencyRank(a) - urgencyRank(b) || a.created_s - b.created_s);
}

/** Decided recommendations, newest decision first. */
export function decidedRecommendations(s: ConsoleState): { rec: Recommendation; decision: Decision }[] {
  return Object.values(s.decisions)
    .filter((d) => s.recommendations[d.recommendation_id])
    .sort((a, b) => b.decided_s - a.decided_s)
    .map((decision) => ({ rec: s.recommendations[decision.recommendation_id]!, decision }));
}

export function serverNow(s: ConsoleState, clientNow: number): number | null {
  return s.clockOffset === null ? null : clientNow + s.clockOffset;
}
