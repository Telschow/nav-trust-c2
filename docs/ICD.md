# Interface control document (PROPOSAL)

Status: **proposal by Claude, not reviewed.** `NavTrust` is as implemented in
`navtrust/types.py` (from the spec). `Recommendation` and `Decision` were not available
in this repository and are defined here to build the backend (issue 10); the maintainer
should confirm or replace them before they harden. Changing a message needs maintainer
approval (CLAUDE.md).

All times are seconds on one clock owned by the backend. JSON field names equal the
dataclass field names; enums are their string values.

## NavTrust (vehicle trust, produced by the trust engine)
| field | type | note |
|---|---|---|
| vehicle_id | string | |
| stamp_s | float | |
| state | GREEN, AMBER, RED | |
| reason | GNSS_LOSS, INCONSISTENT_INNOVATION, BIAS_DRIFT, STALE, or null | null only in GREEN |
| horizontal_bound_m | float or `null` | JSON has no infinity: unknown is `null` (the engine gives it outside GREEN) |
| confidence | float 0..1 | ordinal placeholder, meaning undefined (see ADR/PR 27) |

## Recommendation (produced by the recommender, shown to the operator)
| field | type | note |
|---|---|---|
| id | string | unique |
| vehicle_id | string | vehicle the recommendation is about |
| created_s | float | |
| expires_s | float | after this it cannot be approved |
| reason | ReasonCode | the NavTrust reason that triggered it |
| command | HOLD, RTL, or null | the vehicle command to execute if approved |
| sector_moves | list of {sector_id, to_vehicle} | re-tasking to execute if approved; may be empty |
| rationale | string | one line for the operator |

A recommendation with neither a command nor sector moves is rejected.

## Decision (the operator's answer)
| field | type | note |
|---|---|---|
| recommendation_id | string | |
| outcome | APPROVED, DENIED | EXPIRED is written by the backend, never sent by a client |
| decided_s | float | stamped by the backend |
| operator | string | |
| note | string, optional | |

## Position and origin (for the map; added with the console)
`POST /positions` `{vehicle_id, lat_deg, lon_deg, alt_m}` is the latest vehicle position. It is
published on the WebSocket and kept in `/state`, but not audited (high rate). `POST /origin`
`{lat_deg, lon_deg}` is the geographic position of the sector grid's south-west corner, so the
console can place sectors, which are in metres. Every WebSocket event and the `state` message
carry `server_s`, the backend clock, for client-side expiry countdowns. `POST /source`
`{label}` names where the data comes from (`live` by default); a replay or demo feeder must set
it so the console cannot present replayed data as a live flight.

## Audit log
Append-only. One row per event: `t_s`, `kind` (`navtrust_change`, `recommendation`,
`decision`, `rejected_decision`), `vehicle_id`, JSON `payload`. Trust is logged on state or
reason changes, not on every message.
