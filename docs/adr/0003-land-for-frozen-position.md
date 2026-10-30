# ADR 0003: Recommend LAND for a vehicle whose GNSS position is inconsistent

Status: accepted, 2026-10-10. Decided by the maintainer; written down by Claude on their
instruction. Amends ADR 0002 (stuck-position class and recommender rule). Limits amended
2026-10-30 after the repetition in issue 81.

## Context

ADR 0002 assumed that a vehicle with a frozen GNSS position stays airborne and that the
operator has time to approve a HOLD. It noted that the true position had not been recorded.
Ground truth from Gazebo (`sim/ground_truth.py`) now exists, and it shows that assumption was
wrong. In PX4 SITL with `failure gps stuck` the reported position freezes while the vehicle
keeps flying: it believes it has not moved, so it keeps pushing toward its next waypoint and
accelerates. No PX4 failsafe fires, and nothing in the vehicle's own estimate shows it.

Runs (committed in `tests/replay/data/experiments/`, all with the fault latched, the operator
action sent 15 s after the fault, a 600 m survey route, one run each):

| Operator action | Farthest from start | Outcome |
|---|---|---|
| none | 5320 m | still flying at 28 m, speed 19 m/s at +30 s, 27 m/s at +60 s, 36 m/s at +120 s; 1359 m away at +60 s |
| LAND | 450 m | on the ground 9 s after the command, stopped, 2.9 m/s when below 3 m altitude |
| HOLD | 614 m | on the ground 38 s after the command, 420 m off the route, 31.7 m/s horizontal speed when below 3 m altitude |
| RTL | 414 m | on the ground 25 s after the command, 24.6 m/s horizontal speed when below 3 m altitude |

An earlier no-action run (not committed) reached 5.9 km. A first attempt at the HOLD and RTL
runs used a fault that cleared whenever the believed position left the zone and was
discarded as not a fair test; the RTL run in it also lost all data at 99 s.

The earlier recordings (`stuck_zone-1`) have no ground truth; what they showed (an estimated
position that froze, a stalled mission) was the estimate, not the vehicle.

## Decision

1. For RED with `INCONSISTENT_INNOVATION` the recommender suggests LAND, plus re-tasking the
   vehicle's unfinished sectors. LAND is added to the ICD proposal (`Command`), the gate, both
   executors and the console. HOLD and RTL are no longer recommended for this case.
2. A recommendation that expires unanswered is issued again while the vehicle is still RED,
   so a vehicle that keeps flying away is never left without an open recommendation. A denied
   or approved one is not repeated. The expiry is not shortened: a shorter expiry would only
   remove the operator's chance to act.
3. The console marks this recommendation as urgent ("may be flying away from where it thinks
   it is, and nothing else will stop it").
4. The stuck-position class in ADR 0002 is restated: no failsafe fires, the vehicle accelerates
   away, and the operator's window is measured in tens of seconds (about 1.4 km away after 60 s).

## Consequences

- Time matters more than ADR 0002 assumed. The 60 s expiry is long compared with how fast the
  vehicle leaves; the time from fault to RED (3.3 s in the recordings) is the part the system
  controls.
- The evaluation can now measure how wrong the position really was when the engine said
  GREEN (misleading-trust epochs), using ground truth.
- The live demo in the console PR sent HOLD to the faulted vehicle. Its flight mode was HOLD,
  but ground truth was not recorded, so it was not shown that it stopped; the experiment above
  suggests it would not have stopped safely.

## Limits, not decided here

One run per action, in one simulator, for one fault model (PX4's `stuck`, which freezes position
and velocity together). Real frozen or spoofed GNSS may behave differently. HOLD and RTL were
not tried at other delays. A landing in place can itself be unsafe (people, terrain, water);
the console states what it will do and the operator decides. Whether PX4 should be configured
to stop such a vehicle without the operator is not examined.

Amended 2026-10-30 (issue 81, accepted by the maintainer). Repeated in 52 runs over speed and
delay: LAND reached the ground 8 to 12 s after the command in every run, but touched down at
2.0 to 28.3 m/s; the 2.9 m/s above was the best case. With no action, 12 of 13 runs were still
flying after 220 s, up to 8179 m away. Distance was set mostly by the operator delay: LAND reached
258 to 443 m at a 5 s delay and 666 to 973 m at 30 s. LAND was no better than RTL on distance
(236 to 909 m). The claim that LAND stops the vehicle is withdrawn; the claim that it is the
quickest way to the ground stands. See `docs/validation/frozen-position-matrix.md`.
