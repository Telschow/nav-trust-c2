# ADR 0002: Scenarios follow PX4's failsafe; the operator decides what comes after

Status: accepted, 2026-10-09. Decided by the maintainer; written down by Claude on their instruction.

## Context

The product recommends HOLD, RTL or re-tasking when GNSS trust drops, and nothing executes
without operator approval, except PX4's own failsafes (CLAUDE.md guardrail).

What PX4 does without GNSS (SITL, Gazebo, pinned PX4 `main` a427a2e):

- `EKF2_NOAID_TOUT` is the longest the estimator keeps a horizontal solution on inertial
  dead-reckoning: default 5 s, maximum 10 s (parameter definition in the PX4 source).
  After that the position controller falls back to `Failsafe: blind land`.
- In the one recorded long outage (`gps off`, a 300 m zone, about 30 s at 10 m/s) the
  vehicle left cruise altitude roughly 5 to 10 s after the loss and landed inside the zone.
  The two scripts' clocks in that older run were not aligned, so the delay is approximate.
  That run is not committed.
- Zones of 40 m (about 4 s) were flown through: mission finished, no failsafe.
- With `gps stuck` no failsafe fired: altitude stayed at 30.0 m for the 173 s after the fault
  in `stuck_zone-1`, while the estimated position froze and the mission stalled at waypoint 1.
  The true position was not recorded, so what the vehicle really did is unknown.

So during a pure outage there is no window in which a human can decide: the estimator
allows at most 10 s and the vehicle lands by itself.

## Decision

1. Keep PX4's failsafe behaviour as it is. Do not raise `EKF2_NOAID_TOUT` to lengthen the
   window: the maximum only doubles it, it is still too short for a human, and it makes the
   simulated vehicle less representative.
2. Build scenarios in three classes:
   - Short outage (zone crossed in about 5 s or less): trust dips to AMBER and recovers, the
     vehicle flies on. Shows detection and recovery.
   - Long outage (more than the estimator's timeout): PX4 lands the vehicle, trust goes RED
     with `GNSS_LOSS`. The operator decides what happens next.
   - Stuck position (consistency fault): no failsafe, the vehicle stays airborne, trust goes
     RED with `INCONSISTENT_INNOVATION`. The operator has time to approve an action.
3. The recommender (C2-02) follows the reason code:
   - RED with `GNSS_LOSS`: recommend re-tasking the vehicle's remaining sectors to the others
     (the vehicle is landing or has landed, so HOLD and RTL are moot), and operator-led recovery.
   - RED with `INCONSISTENT_INNOVATION`: recommend HOLD or RTL, plus re-tasking its sectors.
   - AMBER: inform; no command is recommended.
4. Ground truth position must be recorded in simulation before the evaluation harness (M3).
   "Misleading-trust epochs" and any check of the horizontal bound need the true error, which
   the current recordings cannot give.

## Consequences

- Mission completion is legitimately lower in long-outage scenarios; the metrics that matter
  there are time to detect, misleading-trust epochs, and the quality of the re-task.
- Scenario YAMLs (issue 14) must state which class they are and the expected PX4 behaviour.
- The stuck-position class is the main demonstration of human-on-the-loop; it rests on one
  recorded run.

## Open, not decided here

Exact zone sizes and speeds per class. How to obtain ground truth (Gazebo pose via `gz`
transport is the likely source). What a landed vehicle should show on the console and
whether a landed vehicle's remaining sectors are re-tasked automatically or only on approval
(approval, per the guardrail, unless changed).
