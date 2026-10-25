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
  lastHeardAt_s: number;
}

export interface ConsoleState {
  connected: boolean;
  /** the connection dropped and no fresh snapshot has arrived since: what is on screen is old */
  resync: boolean;
  /** server_s of the latest message from the backend, to say how old the screen is */
  lastBackendAt_s: number | null;
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
  /** ids of recommendations the operator has marked "Seen" */
  seen: string[];
  /** ids of recommendations that expired while their vehicle could not be heard */
  expiredWithoutLink: string[];
  fleet: Fleet;
  doneSectors: string[]; // ids of sectors the backend says have been flown
  calibration: Calibration | null;
  log: LogEntry[];
  nextLogId: number;
}

export const initialState: ConsoleState = {
  connected: false,
  resync: false,
  lastBackendAt_s: null,
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
  seen: [],
  expiredWithoutLink: [],
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
  | { type: "decided"; decision: Decision }
  | { type: "seen"; id: string };

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
  const duration = formatDuration(change.last_report_age_s);
  const next: ConsoleState = {
    ...s,
    links: {
      ...s.links,
      [change.vehicle_id]: {
        state: change.state,
        lastHeardAt_s: change.state === "NO_LINK" ? server_s - change.last_report_age_s : server_s,
      },
    },
  };
  return change.state === "NO_LINK"
    ? withLog(next, server_s, "warn", `${change.vehicle_id} has no link: last heard ${duration} ago`)
    : withLog(next, server_s, "good", `${change.vehicle_id} link restored after ${duration}`);
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
      return { ...s, connected: action.connected, resync: action.connected ? s.resync : true };
    case "fleet":
      return { ...s, fleet: action.fleet, doneSectors: action.done };
    case "calibration":
      return { ...s, calibration: action.calibration };
    case "seen":
      return s.seen.includes(action.id) ? s : { ...s, seen: [...s.seen, action.id] };
    case "decided":
      return { ...s, decisions: { ...s.decisions, [action.decision.recommendation_id]: action.decision } };
    case "server": {
      const { event, clientNow } = action;
      const base: ConsoleState = {
        ...s,
        clockOffset: event.server_s - clientNow,
        lastBackendAt_s: event.server_s,
        resync: event.type === "state" ? false : s.resync,
      };
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
            links[v] = { state: l.state, lastHeardAt_s: snap.server_s - l.last_report_age_s };
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
            seen: [],
            expiredWithoutLink: [],
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
          // what the notice says about the link is what was true now, not when it is read later
          const lostAtExpiry = d.outcome === "EXPIRED" && rec !== undefined && isNoLink(base, rec.vehicle_id);
          return withLog(
            {
              ...base,
              decisions: { ...base.decisions, [d.recommendation_id]: { ...base.decisions[d.recommendation_id], ...d } },
              expiredWithoutLink: lostAtExpiry ? [...base.expiredWithoutLink, d.recommendation_id] : base.expiredWithoutLink,
              // an earlier "Seen" was about the open decision; the expiry is news again
              seen: d.outcome === "EXPIRED" ? base.seen.filter((id) => id !== d.recommendation_id) : base.seen,
            },
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

/** The console cannot reach the backend, or has not yet been given a fresh snapshot since it could
 * not. Every state on screen is then only the last one received. */
export function backendLost(s: ConsoleState): boolean {
  return !s.connected || s.resync;
}

/** Whether the operator has marked a recommendation seen. A re-raised recommendation is a new id,
 * so it starts unseen. */
export function isSeen(s: ConsoleState, recommendationId: string): boolean {
  return s.seen.includes(recommendationId);
}

/** Whether the vehicle of an expired recommendation could not be heard when it expired. */
export function expiredWithoutLink(s: ConsoleState, recommendationId: string): boolean {
  return s.expiredWithoutLink.includes(recommendationId);
}

export interface FleetCounts extends Record<TrustState, number> {
  /** vehicles the backend cannot hear: not counted under their last known state */
  noLink: number;
}

/** How many vehicles are in each trust state now. A vehicle with no link has no state now. */
export function trustCounts(s: ConsoleState): FleetCounts {
  const counts: FleetCounts = { GREEN: 0, AMBER: 0, RED: 0, noLink: 0 };
  for (const [id, trust] of Object.entries(s.vehicles)) {
    if (isNoLink(s, id)) counts.noLink += 1;
    else counts[trust.state] += 1;
  }
  return counts;
}

/** The decided recommendations for the "Recently decided" list: an expiry the operator has not yet
 * seen is shown pinned instead, so it is not listed twice. */
export function decidedHistory(s: ConsoleState): { rec: Recommendation; decision: Decision }[] {
  const pinned = new Set(pinnedExpired(s).map((p) => p.rec.id));
  return decidedRecommendations(s).filter((d) => !pinned.has(d.rec.id));
}

/** Recommendations that expired unanswered and that the operator has not yet marked seen, newest
 * first. They stay in view so an expiry never passes unnoticed. */
export function pinnedExpired(s: ConsoleState): { rec: Recommendation; decision: Decision }[] {
  return Object.values(s.decisions)
    .filter((d) => d.outcome === "EXPIRED" && s.recommendations[d.recommendation_id] && !s.seen.includes(d.recommendation_id))
    .sort((a, b) => b.decided_s - a.decided_s)
    .map((decision) => ({ rec: s.recommendations[decision.recommendation_id]!, decision }));
}

export interface RaisedAgain {
  /** how many times this vehicle and reason have now been put to the operator (2 = the second) */
  nth: number;
  /** server_s when the latest earlier one expired unanswered */
  previousExpiredAt_s: number;
}

/** Whether a recommendation follows earlier ones for the same vehicle and reason that expired
 * unanswered. Derived from the decisions the console holds, so a reload forgets them: a denial or
 * an approval is not a re-raise, and the first recommendation after a reload looks first-time. */
export function raisedAgain(s: ConsoleState, rec: Recommendation): RaisedAgain | null {
  const earlier = Object.values(s.recommendations).filter(
    (r) =>
      r.id !== rec.id &&
      r.vehicle_id === rec.vehicle_id &&
      r.reason === rec.reason &&
      r.created_s < rec.created_s &&
      s.decisions[r.id]?.outcome === "EXPIRED",
  );
  if (earlier.length === 0) return null;
  return {
    nth: earlier.length + 1,
    previousExpiredAt_s: Math.max(...earlier.map((r) => s.decisions[r.id]!.decided_s)),
  };
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
