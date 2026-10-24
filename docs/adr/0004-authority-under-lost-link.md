# ADR 0004: Authority under lost link

Status: proposed, 2026-10-24. Context and options drafted by Claude at the maintainer's
request (issue 72). The decision is the maintainer's and is left blank.

## Context

C2-01 ties every vehicle command to a recorded operator approval, except PX4's own failsafes.
That approval has to be reachable. In contested operations navigation and the C2 link can
degrade together, so the project needs a defined answer to what a vehicle may do when the
operator cannot be reached, and on whose authority.

Each vehicle is judged on three independent dimensions: navigation integrity (the trust
engine), link health (does the backend still hear the vehicle) and operator availability (can a
decision be made in time). Terms are defined in `GLOSSARY.md`.

The evidence that matters is ADR 0003. With a frozen GNSS position no PX4 failsafe fires, and
the vehicle runs away: 5320 m from its start with no action, against 450 m with LAND, which
put it on the ground 9 s after the command. HOLD and RTL ended in fast uncontrolled descents.
That is one run per action in one simulator (issue 81 adds more).

The cases, as a contingency matrix (rows are a proposal):

| Situation | Behaviour |
|---|---|
| GNSS degraded, link up | Current loop: trust state, recommendation, operator approval |
| Link up, recommendation unanswered | Expires after 60 s and is raised again; PX4 failsafes act |
| Link lost, GNSS healthy | PX4 data-link-loss failsafe |
| Link lost, position inconsistent (frozen or spoofed) | Nothing on board catches it unless a contingency does |
| Link lost, GNSS lost | PX4 failsafes (blind land) |
| Link restored | Reconcile state, show onboard actions, never replay stale decisions |

## Considered options

1. **PX4 failsafes only.** No new authority. Simple, but nothing onboard detects a frozen or
   spoofed position, so no failsafe acts in that case.
2. **Pre-authorised contingencies.** The operator approves, before the mission, a policy that
   pairs a fault and a link condition with an action. The approval is recorded in the audit log.
   The vehicle executes only within it and reports what it did when the link returns.
3. **Wait for the operator.** Recommendations expire and are raised again until the link
   returns. Unbounded exposure for fast faults. The `operator_unresponsive` scenario (issue 75)
   measures this exposure.

## Points raised in review

Not decisions. Raised on 2026-10-24 for the maintainer to accept, change or drop.

- `STALE` (the engine's own input is silent) and `NO_LINK` (the backend has not heard from the
  vehicle) stay separate. While a vehicle is `NO_LINK` no command is proposed to it, but its
  sector may still be re-assigned.
- `NO_LINK` means telemetry silence only. Cutting both directions together is a stated
  assumption; an asymmetric link is out of scope.
- A contingency counts as an approval given in advance, so every command still traces to a
  recorded approval or to PX4. The wording of the scope guardrail in `CLAUDE.md` would be
  amended when this ADR is accepted, not before.
- The only allowed action is LAND, because ADR 0003 is the only evidence for any action under a
  frozen position. A vehicle never decides anything about other vehicles.
- PX4's data-link-loss action is RTL when navigation is healthy. The onboard monitor overrides it
  to LAND on position inconsistency. The contingency's wait time must be shorter than
  `COM_DL_LOSS_T`, or RTL starts first.
- The policy is approved once per mission and referenced by the audit row's id and hash, with a
  fixed maximum age and no revocation (the link may be down when one is wanted). This is
  integrity of the record, not authentication.

## Decision

To be written by the maintainer.

## Consequences

To be written with the decision. If option 2 is accepted: new requirement IDs for link health
and contingencies (proposed as LL-01 to LL-03 in `docs/product/requirements.md`), the CONOPS
vignette C, and the `CLAUDE.md` guardrail wording.
