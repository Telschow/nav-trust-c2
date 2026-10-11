# Risks, assumptions, issues, dependencies (RAID)

Prepared by Claude on 2026-10-10 from the repository history and measurements, at the
maintainer's request. Ratings (H, M, L) are a suggestion, not a measurement. Each row points at
the evidence.

## Risks

| ID | Risk | Likelihood / impact | What reduces it | Evidence |
|---|---|---|---|---|
| R1 | All results come from one simulator and PX4's own GPS failure model; none says anything about real receivers, jamming or spoofing | H / H | Say so wherever results appear; claim nothing beyond the simulator | `eval/results.md` limits; ADR 0003 limits |
| R2 | Few runs per scenario (2 to 4); no rates can be estimated | H / M | Report counts and bounds, never rates; more runs if a claim needs one | `eval/results.md`, `eval/heldout/results.md` |
| R3 | The engine was developed and evaluated on the same kinds of fault; the held-out set is now used up for this version | M / M | Treat any engine change as a new iteration; record a new held-out set under new conditions | `docs/validation/heldout-report.md` |
| R4 | The displayed position bound is not a valid bound: in GREEN the console shows about 0.15 m but the true error was within it in only 30.8% of 4,040 simulated reports (median 0.57 m, 95th percentile 2.4 m, max 2.9 m) | H / H | Mitigated 2026-10-10: replaced by a calibrated 3 m bound with its coverage (99%), held in 100% of 4,040 development and 99.72% of 5,308 held-out GREEN reports | measurement of 2026-10-10 over `eval/recordings` |
| R5 | The recommendation for a frozen GPS position (LAND) rests on one clean run per action in one simulator | M / H | More runs and other delays before any stronger claim; the console states what it will do and the operator decides | ADR 0003, `tests/replay/data/experiments` |
| R6 | A frozen position makes the vehicle run away within tens of seconds and nothing else stops it; the operator window is short | M / H | Time to detect is about 3 to 4.5 s; urgent-first queue; re-issue on expiry | ADR 0003 |
| R7 | Detection can be late for slow flight: the frozen-position case at 5 m/s was detected after 4.4 to 4.5 s against a 5 s limit | M / M | Watch it in any further runs; no tuning on the held-out set | `docs/validation/heldout-report.md` |
| R8 | Simulation hosts stall or run out of resources (memory, disk), which cost days of work and produced one false alert in the held-out run | M / M | Record resource needs (8 GiB VM, 30 GB disk); do not run other work during recordings | held-out E3, Docker disk and memory incidents |
| R9 | The GPS failure injection exists only on an unreleased PX4 `main` commit | M / M | The commit is pinned; move to a release tag that contains the feature once one exists and re-run the evaluation | `sim/docker/Dockerfile` |
| R10 | Product documents and the requirements table are not written, so no claim of "meets requirement X" can be made | H / H | Write issue 1; put the requirement text and targets in the repository | issue 1 |
| R11 | Usability evidence will be 2 to 3 people, a convenience sample, on a replay, with the developer as facilitator | H / M | State N; report each person; do not generalise | `docs/usability/metrics.md` |
| R12 | The backend has no authentication; the operator name is typed by the user | L / M | Bind to localhost only; note it wherever the console is shown | `c2/server.py` |
| R13 | The map uses OpenStreetMap tiles, whose policy allows light use only | L / L | Fine for a demo; switch provider or self-host before any wider use | `console/src/components/MapView.tsx` |
| R14 | Re-tasking restarts the receiving vehicle from the first waypoint of every sector it holds (sector completion is not tracked), so approved re-tasks waste flown work | M / M | Mitigated 2026-10-10: the backend tracks sector completion from trusted positions (`c2/progress.py`) and the executor keeps the unflown part of a vehicle's mission (`sim/executor.py`); measured in `eval/fleet/results.md` | `c2/progress.py`; `sim/executor.py` |
| R15 | The remaining work (usability sessions, video, writing) depends on people's time, not on engineering | H / M | Book participants this week | issues 16, 17 |

## Assumptions

| ID | Assumption | If it is wrong |
|---|---|---|
| A1 | PX4's `gps stuck` is a fair stand-in for a frozen GNSS position | The runaway behaviour and the LAND finding may not carry over |
| A2 | Ground truth: vehicle 1 spawns at the Gazebo world origin, the origin of the sector grid | Every truth-based metric would be offset |
| A3 | A recommendation window of 60 s is workable for an operator | Re-issue on expiry hides a window that is too short; the usability session should probe it |
| A4 | The 10 m threshold for "GREEN while wrong" is a sensible line | A proposal; it sits above the roughly 3 m error that every flight shows |

## Issues (happened, being handled)

| ID | Issue | Status |
|---|---|---|
| I1 | Held-out expectation E3 not met: one `STALE` episode in `wrong_fix_fast-1`, caused by a 6.8 s stall of the whole simulation | Reported, not excluded; see the held-out report |
| I2 | Product docs v1 (issue 1) and weekly status files not written | Open, maintainer |
| I3 | `confidence` in the ICD has no defined meaning | Open, decision pending |
| I4 | `BIAS_DRIFT` is not produced: there is no gradual-drift fault to develop it against | Accepted for v1; state as a non-goal |
| I5 | Several issues stayed open after their work merged because "Closes #X and #Y" closes only the first | Fixed; one `Closes` per issue from now on |

## Dependencies

| ID | Dependency | Owner |
|---|---|---|
| D1 | 2 to 3 usability participants, a pilot person, and consent | maintainer |
| D2 | A machine that can run PX4, Gazebo and Docker (8 GiB for the Docker VM, 30 GB of disk) | maintainer |
| D3 | The spec's requirement text and numeric targets (NT-01, NT-02, C2-01 to C2-03, UX-01) in the repository | maintainer |
| D4 | Internet access for map tiles during any demo | maintainer |
