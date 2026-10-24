export type TrustState = "GREEN" | "AMBER" | "RED";
export type Reason = "GNSS_LOSS" | "INCONSISTENT_INNOVATION" | "BIAS_DRIFT" | "STALE";

export interface NavTrust {
  vehicle_id: string;
  stamp_s: number;
  state: TrustState;
  reason: Reason | null;
  horizontal_bound_m: number | null; // null = unknown
  /** share of calibration reports in which the true error stayed within the bound; 0 if unknown */
  confidence: number;
  /** 0..1, how far a GREEN vehicle is from an alert; 0 outside GREEN */
  headroom: number;
}

/** How the displayed position bound was obtained (GET /calibration). */
export interface Calibration {
  bound_m: number;
  coverage: number;
  development_reports: number;
  development_coverage: number;
  heldout_reports: number;
  heldout_coverage: number;
  source: string;
}

export interface SectorMove {
  sector_id: string;
  to_vehicle: string;
}

export interface Recommendation {
  id: string;
  vehicle_id: string;
  created_s: number;
  expires_s: number;
  reason: Reason;
  command: "HOLD" | "RTL" | "LAND" | null;
  sector_moves: SectorMove[];
  rationale: string;
}

export type Outcome = "APPROVED" | "DENIED" | "EXPIRED";

export interface Decision {
  recommendation_id: string;
  outcome: Outcome;
  decided_s: number;
  operator: string;
  note: string;
  execution?: { executed: boolean; reason: string | null; actions: string[] };
}

export interface Position {
  vehicle_id: string;
  lat_deg: number;
  lon_deg: number;
  alt_m: number;
  stamp_s: number;
}

/** Whether the backend is hearing a vehicle. Says nothing about its navigation. */
export type LinkState = "LINK_OK" | "NO_LINK";

/** A link change (`link` event) or one entry of the snapshot's `links`. `last_report_age_s` is
 * how old the vehicle's last report was when the state changed; in the snapshot, its live age. */
export interface LinkStatus {
  vehicle_id: string;
  state: LinkState;
  last_report_age_s: number;
}

export interface Origin {
  lat_deg: number;
  lon_deg: number;
}

export interface Sector {
  id: string;
  west: number;
  south: number;
  east: number;
  north: number;
}

export type Fleet = Record<string, Sector[]>;

/** Messages from the backend WebSocket. `server_s` is the backend clock. */
export type ServerEvent =
  | { type: "state"; server_s: number; data: StateSnapshot }
  | { type: "navtrust"; server_s: number; data: NavTrust }
  | { type: "position"; server_s: number; data: Position }
  | { type: "recommendation"; server_s: number; data: Recommendation }
  | { type: "decision"; server_s: number; data: Decision }
  | { type: "link"; server_s: number; data: LinkStatus }
  | { type: "origin"; server_s: number; data: Origin }
  | { type: "source"; server_s: number; data: { label: string } };

export interface StateSnapshot {
  server_s: number;
  source: string;
  origin: Origin | null;
  positions: Record<string, Position>;
  vehicles: Record<string, NavTrust>;
  /** absent from an older backend: treat as "no link problem known" */
  links?: Record<string, LinkStatus>;
  open_recommendations: Recommendation[];
}
