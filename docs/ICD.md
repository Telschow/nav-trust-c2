# Interface control document (PROPOSAL)

Status: **proposal by Claude, not reviewed.** `NavTrust` is as implemented in
`navtrust/types.py` (from the spec). `Recommendation` and `Decision` were not available
in this repository and are defined here to build the backend (issue 10); the maintainer
should confirm or replace them before they harden. Changing a message needs maintainer
approval (CLAUDE.md). The link-health messages below were approved by the maintainer on
2026-10-24 (issue 73).

All times are seconds on one clock owned by the backend. JSON field names equal the
dataclass field names; enums are their string values.

## NavTrust (vehicle trust, produced by the trust engine)
| field | type | note |
|---|---|---|
| vehicle_id | string | |
| stamp_s | float | |
| state | GREEN, AMBER, RED | |
| reason | GNSS_LOSS, INCONSISTENT_INNOVATION, BIAS_DRIFT, STALE, or null | null only in GREEN |
| horizontal_bound_m | float or `null` | GREEN: a bound calibrated against ground truth (3.0 m). Otherwise unknown: `null` in JSON (infinity in the engine) |
| confidence | float 0..1 | the share of calibration reports in which the true error stayed within `horizontal_bound_m` (0.99). 0 when the bound is unknown. Not a per-moment probability |
| headroom | float 0..1 | GREEN only (0 otherwise): how far the vehicle is from an alert. The smaller of two margins: the worst recent innovation test ratio against the estimator's own rejection gate, and how long the inputs have been silent against the stale limit. Not a probability |

`GET /calibration` serves how the bound and its coverage were obtained (counts, measured coverage
on the development and the held-out sets, source). The numbers live in `navtrust/calibration.py`
and `tests/test_calibration.py` recomputes them from the recordings. They hold for PX4 SITL in
Gazebo at 5 to 12 m/s and say nothing about other conditions.

## Recommendation (produced by the recommender, shown to the operator)
| field | type | note |
|---|---|---|
| id | string | unique |
| vehicle_id | string | vehicle the recommendation is about |
| created_s | float | |
| expires_s | float | after this it cannot be approved |
| reason | ReasonCode | the NavTrust reason that triggered it |
| command | HOLD, RTL, LAND, or null | the vehicle command to execute if approved (LAND is recommended for INCONSISTENT_INNOVATION, ADR 0003) |
| sector_moves | list of {sector_id, to_vehicle} | re-tasking to execute if approved; may be empty |
| rationale | string | one line for the operator |

A recommendation with neither a command nor sector moves is rejected.

## Decision (the operator's answer)
| field | type | note |
|---|---|---|
| recommendation_id | string | |
| outcome | APPROVED, DENIED | EXPIRED and SUPERSEDED are written by the backend, never sent by a client |
| decided_s | float | stamped by the backend |
| operator | string, not blank | a blank name is refused (422 `invalid_operator`) and the attempt is audited |
| note | string, optional | |
| vehicle_heard | boolean, EXPIRED only | whether the backend could hear the vehicle at the moment the recommendation expired; absent for every other outcome. A client of an older backend finds no field and treats it as heard |

SUPERSEDED: closed by the backend when a link returns and the vehicle's trust state or reason
is no longer what it was when the recommendation was raised (see Link health). A decision on a
superseded recommendation is refused with 410 `superseded`, like an expired one.

## Position and origin (for the map; added with the console)
`POST /positions` `{vehicle_id, lat_deg, lon_deg, alt_m}` is the latest vehicle position. It is
published on the WebSocket and kept in `/state`, but not audited (high rate). `POST /origin`
`{lat_deg, lon_deg}` is the geographic position of the sector grid's south-west corner, so the
console can place sectors, which are in metres. Every WebSocket event and the `state` message
carry `server_s`, the backend clock, for client-side expiry countdowns. `POST /source`
`{label}` names where the data comes from (`live` by default); a replay or demo feeder must set
it so the console cannot present replayed data as a live flight.

## Fleet (`GET /fleet`)
`{origin, assignment, done}`. `assignment` maps each vehicle to its sectors
(`{id, west, south, east, north}`, metres from the origin). `done` lists the ids of sectors that
have been flown: the backend marks a sector done when at least 95% of it has been passed within
half the lane spacing by a vehicle that was airborne and GREEN at the time (`c2/progress.py`;
proposals). It is derived from the positions the vehicles report, not from ground truth, and it is
not audited. The console polls it.

## Link health (is the backend hearing the vehicle)
Says nothing about navigation; it is a separate dimension from the trust state (ADR 0004,
GLOSSARY.md "No link"). It is measured on the backend's own clock from the arrival of any
`navtrust` or `position` message for the vehicle, never from `stamp_s`, which is the feed's clock.

| field | type | note |
|---|---|---|
| vehicle_id | string | |
| state | LINK_OK, NO_LINK | NO_LINK when the vehicle's last report is older than the link timeout (`--link-timeout`, default 2 s, a proposal). Exactly the timeout is still LINK_OK |
| last_report_age_s | float | see below |

- The `state` message (and `GET /state`) has `links`: vehicle id to `{vehicle_id, state,
  last_report_age_s}`, where `last_report_age_s` is the age of the vehicle's last report now. A
  vehicle never heard from has no entry. A client of an older backend finds no `links` and must
  show no link indicator.
- A `link` WebSocket event `{"type": "link", "data": {vehicle_id, state, last_report_age_s},
  "server_s": ...}` is published once per change. In an event, `last_report_age_s` is the age of
  the last report when the state changed: for NO_LINK, how long the vehicle has been silent so far;
  for LINK_OK, the length of the silence that just ended.
- While NO_LINK the vehicle's last `NavTrust` stays in `vehicles` and is only the last one
  known. The recommender hands it no work and offers it no command; a recommendation already
  open stays open while the link is down.
- Recovery (issue 77). The first `navtrust` report after an outage closes what the outage made
  stale and publishes an `outage_summary` event `{"type": "outage_summary", "data":
  {vehicle_id, duration_s, trust, trust_changes, onboard_actions, superseded}, "server_s": ...}`:
  `duration_s` is the length of the silence, `trust` the first report after it,
  `trust_changes` the `{server_s, state, reason}` changes seen since the link was lost,
  `onboard_actions` the actions the vehicle took on its own (always empty until the onboard
  monitor exists, issue 76) and `superseded` the ids of recommendations closed. A recommendation
  raised before the outage for that vehicle is closed as SUPERSEDED when its trust state or reason
  changed; one raised while the link was down is left alone. The recommender raises a new one if
  the vehicle still needs it. If a position report ends the outage, the summary waits for the
  next trust report. The same summary is an `outage_summary` audit row.

- The backend sweeps for silent vehicles every 0.5 s, so a fleet that has gone completely quiet
  is noticed.

## Command acknowledgement (issue 77)
The gate sends each approved command and waits for the vehicle to accept it: an executor call
returns when the vehicle has answered. Audit rows, per command, in order: `command_sent`
(`recommendation_id`, `action`), then `command_acknowledged`, or `command_not_acknowledged`
(also `timeout_s`; `--ack-timeout`, default 5 s, a proposal). A command never acknowledged is
audited, not resent: its approval is spent. The recommender does not repeat an answered
recommendation, so nothing is raised again automatically. The decision's `execution` reports it as
not executed with reason `not_acknowledged: ...`. An error raised by the executor itself is a
failure (`command_failed`), not a missing answer. Whether the vehicle received it anyway is unknown,
so a re-task is not rolled back.

## Onboard contingencies (issue 76, ADR 0004)
A contingency is an approval given in advance. The operator approves, before the mission, a
policy; a vehicle's onboard monitor may LAND on it when the C2 cannot be reached.

- `POST /policy` `{operator, wait_s, entries}` with `entries` a list of `{reason, link, action}`
  (`reason` a ReasonCode, `link` only `NO_LINK`, `action` only `LAND`). `wait_s` is how long the C2
  must have been silent, above 0 and below PX4's data-link-loss time (`COM_DL_LOSS_T`, 10 s in the
  simulated vehicles): a policy no vehicle would accept is refused with 422 `invalid_policy`. A
  blank operator is refused like a blank decision. It answers 201 `{audit_id, approved_s, sha256,
  max_age_s, policy}`; `sha256` is the hash of the policy as canonical JSON (sorted keys, no
  spaces) and `max_age_s` (4 h, a proposal) is how long a vehicle may rely on it. The approval is
  an audit row `policy_approved`. There is no revocation, because the link may be down when one is
  wanted. This is integrity of the record, not authentication.
- `POST /onboard-actions` `{vehicle_id, t_s, action, reason, link_down_s, policy_audit_id,
  policy_sha256}` is a vehicle saying, once its link is back, what it did on its own. `t_s` is
  the vehicle's clock. It is accepted only if that policy approval is in the audit log with the
  same hash (else 422 `unknown_policy` and a `rejected_onboard_action` row). It is audited as
  `onboard_action`, published as an `onboard_action` WebSocket event with the same fields, and
  listed in the `outage_summary` of the outage it falls in (`onboard_actions`).
- A vehicle acts only when the C2 has been silent longer than `wait_s`, its own trust state is
  RED and its reason matches an entry, its trust report is recent and the approval is not older
  than `max_age_s`; then once. The monitor reads PX4's own figures through the trust engine (ADR
  0005); its rule is not calibrated against ground truth and no result may say it is.

## Audit log
Append-only. One row per event: `t_s`, `kind` (`navtrust_change`, `recommendation`,
`decision`, `rejected_decision`, `link_change`, `outage_summary`, `command_sent`,
`command_acknowledged`, `command_not_acknowledged`, `command_executed`, `command_failed`,
`command_blocked`, `policy_approved`, `onboard_action`, `rejected_onboard_action`), `vehicle_id`, JSON `payload`. Trust is logged on
state or reason changes, not on every message. A `link_change` row has the `state`,
`previous_state`, `last_report_age_s` (as in the `link` event) and `link_timeout_s`; one row per
change.
