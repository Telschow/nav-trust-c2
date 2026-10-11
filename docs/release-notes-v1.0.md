# nav-trust-c2 v1.0 release notes (draft, not tagged)

Tag after usability round 2 and the demo video. Simulation only.

## What it is
A mission-control console for three simulated PX4 vehicles. Two detectors judge each vehicle's
navigation; the console shows GREEN, AMBER or RED with a reason and a position error with its
measured coverage; it recommends landing or re-tasking a sector, and nothing executes without a
recorded operator approval.

## Measured (all in simulation, regenerated and checked by CI)
- GNSS loss detected in 1.0 to 1.4 s (12 runs), a frozen position in 3.0 to 4.5 s, no alert in
  nominal runs.
- Position error within 3 m in 100% of 4,040 reports (development) and 99.72% of 5,308 (held-out).
- Held-out validation: 7 of 8 pre-declared expectations met; the unmet one is reported.
- One of three vehicles lost: 100% of the area covered with the re-task, 87% without.
- Backend time from a RED report to a recommendation: 5 to 6 ms.

## Not shown
Real hardware or receivers; link loss; trained operators; a usability result for the redesigned
console (round 1: 2 of 2 participants did not decide unaided on the first version).

## Mistakes found along the way
Listed in `docs/how-this-was-built.md`, including an invalid position bound, a wrong assumption
about frozen GPS, and recordings that leaked across runs.

## Upgrade notes
First release. Python 3.12, Node 22, Docker for the simulator image.
