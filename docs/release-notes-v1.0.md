# nav-trust-c2 v1.0.0

Simulation only. Source and results: https://github.com/Telschow/nav-trust-c2

## What it is
A mission-control console for three simulated PX4 vehicles. Two detectors judge each vehicle's
navigation. The console shows GREEN, AMBER or RED with a reason and a position error with its
measured coverage, and recommends landing a vehicle or handing its sector to another. Nothing
executes without a recorded operator approval; one gate is the only path to a command, and a test
enforces it.

## Measured (simulation, regenerated and checked by CI)
- GNSS loss detected in 1.0 to 1.4 s (12 runs); a frozen position in 3.0 to 4.5 s, above the 3 s
  proposal target; no alert in nominal runs.
- Position error within 3 m in 100% of 4,040 reports (development) and 99.72% of 5,308
  (held-out). The first version held in 30.8%.
- Held-out validation: 7 of 8 pre-declared expectations met; the unmet one is reported.
- One of three vehicles lost: 100% of the area covered with the hand-over, 87% without.
- Backend time from a RED report to a recommendation: 5 to 6 ms.

## Not shown
Real hardware or receivers; link loss; trained operators. Usability: in round 1 two participants
did not decide unaided on the first version of the console, which was then redesigned. The
redesign has not been re-tested with people yet.

## Mistakes found on the way
Listed in https://github.com/Telschow/nav-trust-c2/blob/main/docs/how-this-was-built.md,
including an invalid position bound, a wrong assumption about frozen GPS, and recordings that
leaked across runs.

## Run it
`make demo` (Python 3.12, Node 22; no simulator needed). The simulator needs Docker and about
8 GiB for the VM. Details in the README.
