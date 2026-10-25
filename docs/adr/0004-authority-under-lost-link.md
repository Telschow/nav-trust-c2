# ADR 0004: Authority under lost link

Status: accepted, 2026-10-24. Decided by the maintainer; context and options written by
Claude on their instruction (issue 72).

## Context

C2-01 ties every vehicle command to a recorded operator approval, except PX4's own failsafes.
That approval has to be reachable. In contested operations navigation and the C2 link can
degrade together, so the project needs a defined answer to what a vehicle may do when the
operator cannot be reached, and on whose authority.

Each vehicle is judged on three independent dimensions: navigation integrity (the trust
engine), link health (does the backend still hear the vehicle) and operator availability (can a
decision be made in time). Terms are defined in `GLOSSARY.md`.

The evidence that matters is ADR 0003. With a frozen GNSS position no PX4 failsafe fires, and
the vehicle runs away: 5320 m from its start (farthest point at the 220 s cut-off) with no
action, against 450 m with LAND, which put it on the ground 9 s after the command. HOLD and RTL
reached the ground at 31.7 and 24.6 m/s horizontal speed.
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

## Decision

Option 2: pre-authorised contingencies, with PX4's own failsafes underneath. Option 1 alone
leaves a frozen or spoofed position uncaught, because PX4's position-loss failsafe fires when the
estimate becomes invalid and not when it is wrong (ADR 0003). Option 3 leaves the exposure
unbounded for fast faults, and no source in the research note uses it.

1. **A contingency is an approval given in advance.** The operator approves, before the mission,
   a policy of entries that each pair a fault reason and a link condition with an action. Every
   vehicle command still traces to a recorded approval or to a PX4 failsafe.
2. **The only action is LAND**, because ADR 0003 is the only evidence for any action under a
   frozen position. A vehicle never decides anything about other vehicles.
3. **When it acts.** Only when the link has been down longer than the policy's wait time and the
   trust reason matches an entry. Otherwise it does nothing and keeps reporting. The wait time
   must be shorter than PX4's `COM_DL_LOSS_T` (10 s in the simulated vehicles), so that the
   `COM_FAIL_ACT_T` hold and PX4's own action have not started. (Amended 2026-10-24: the first
   text said "plus any hold", about 15 s, which disagreed with the parameters note and issue 76.)
4. **PX4 underneath.** The simulated vehicles' airframe already sets the data-link-loss action to
   Return (`NAV_DLL_ACT` 2), so no parameter change is needed (see
   `docs/validation/px4-lost-link-parameters.md`). RTL while navigation is healthy was recorded in
   2 runs (`eval/lost_link/recordings/link_only-*.jsonl`, issue 97): HOLD about 12 s and RTL about 17 s
   after the cut, touchdown about 102 s after it. That is 2 runs in one simulator, not a rate. The
   onboard monitor overrides it to LAND on a position inconsistency that matches an entry. (Amended
   2026-10-24 and 2026-10-25: the first text said the action had to be set explicitly because it
   defaults to Disabled, and that RTL while healthy was unmeasured.)
5. **Recording.** The policy is approved once per mission as an audited approval. The vehicle
   accepts a policy only if it matches that audit row's id and hash, and only up to a fixed
   maximum age. There is no revocation, because the link may be down when one is wanted. This is
   integrity of the record, not authentication.
6. **While `NO_LINK`, no command is proposed to that vehicle.** Its sector may still be
   re-assigned to a reachable vehicle. `NO_LINK` means telemetry silence only; an asymmetric link
   is not modelled.
7. **After reconnection**, the vehicle reports each onboard action with time, reason and policy
   reference. Recommendations raised before the outage are closed as superseded if the situation
   changed. An approved command that was never acknowledged is audited, not resent.
8. **Guardrail wording** for the scope guardrail in `CLAUDE.md`: "Every vehicle
   command except PX4 internal failsafes requires a recorded operator approval. A contingency the
   operator approved before the mission counts as that approval for the fault, link condition and
   action it names, and for nothing else."

## Consequences

- LL-01 to LL-03 in `docs/product/requirements.md` become real requirements (issues 73, 75, 76)
  and need evidence before any "met".
- The decision rests on thin evidence: ADR 0003 is one run per action (issue 81 adds more), and
  the research note (PR 92) found no public precedent for hashed or time-limited delegated
  authority and could not reach the defence primary sources. The design is justified here, not by
  precedent.
- A forged policy file is possible in the simulator (R17). The ADR claims record integrity only.
- The simulated link is cut in both directions together (R16). Results say nothing about an
  asymmetric or delayed link.
- If issue 81 contradicts ADR 0003, items 2 and 4 are reopened.
- CONOPS vignette C, the `link_loss` scenario family and the onboard monitor follow this
  decision (issues 74 to 77).
