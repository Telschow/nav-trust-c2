# Requirements and success metrics

Written by Claude on 2026-10-10 at the maintainer's request, from the project spec
(section 3 requirements, section 1.5 metrics) and the evidence in this repository. Targets are
proposals from the spec, not results. Status is read from `trace.csv`, which a test checks against the files it cites.

Everything here was measured in simulation (PX4 SITL in Gazebo, one vehicle model, 5 to 12 m/s,
PX4's own GPS failure model). Nothing in it says anything about real receivers or real interference.

## Requirements

| ID | Requirement | Verification | Status | What the evidence shows |
|---|---|---|---|---|
| NT-01 | The trust engine shall raise AMBER within 3 s of total GNSS loss (proposal) | replay test, `eval/` | met | 12 runs with GNSS switched off: time to detect 1.0 to 1.4 s |
| NT-02 | The trust engine shall not leave GREEN in nominal runs | replay test, `eval/` | met | 9 nominal runs, no alert after startup |
| NT-03 | The displayed bound shall contain the true position error in at least 95% of GREEN epochs | ground-truth comparison | met | Since the calibrated bound (3.0 m, claimed 99%): 100.0% of 4,040 development reports and 99.72% of 5,308 held-out reports. Before it the console's bound held in 30.8% of reports, so this requirement was **not** met until PR 37 |
| C2-01 | No vehicle command shall execute without a recorded operator approval, except PX4's own failsafes | unit tests on the gate and the audit log | met | The gate is the only path to a command, an AST test enforces that, and every outcome is audited |
| C2-02 | On RED the system shall propose re-assignment of the vehicle's remaining sectors within 2 s | integration test | met | Measured in 6 live three-vehicle runs: 5 to 6 ms from the backend receiving the RED report to the recommendation (`eval/fleet/results.md`). The engine's report interval (2 Hz, up to 0.5 s by design) and delivery to the console are not included. For a frozen position the proposal is LAND plus re-assignment |
| C2-03 | Every alert shall show a reason code an operator can act on | UI test, review checklist | partial | Review done (`docs/validation/c2-03-review.md`) and tested for every recommendation the recommender can make; one gap fixed. Whether an operator acts on it is not shown: round 1 participants did not act unaided; round 2 pending |
| UX-01 | The operator can see all vehicles' trust states without scrolling at 1080p | manual check, screenshot | met | Measured at 1920 x 1080 with 5 vehicles and the decision band showing: each row is 189 px and the fleet panel does not scroll. The spec says 3 to 5 vehicles |
| LL-01 | A vehicle whose reports have stopped for longer than the link timeout shall be shown as NO LINK, with its last trust state marked as last known and its age (proposal, M5a, issue 73) | unit and component tests with a fake clock | met | Covered by tests: the hub marks a vehicle NO_LINK after 2 s of silence (a proposal) and restores it on the next report, each change audited once; the server sweeps on a timer; the console row shows a No link badge, Last known, Last heard, and not current for the bound, time in state and margin; the header counts it separately; the map tag shows NO LINK and the age on a second line and the row loses its red tint. Looked at in a browser with the replay demo and the feed stopped: `docs/screenshots/no-link.png`. Known gaps, not part of this requirement: a decision for a no-link vehicle can still be approved without a warning (issue 128), the expired notice uses the link state now (issue 129), a map tag can cover a sector label (issue 130). Simulation only |
| LL-02 | With the link down, a vehicle shall act only within a contingency policy the operator approved before the mission, and only with LAND (proposal, M5b, issue 76, ADR 0004) | unit tests and the `link_and_frozen` scenario | gap | Not built. ADR 0004 accepted 2026-10-24. Proposed by Claude |
| LL-03 | Every vehicle action shall be recorded with the authority it ran under: live approval, contingency or PX4 failsafe (proposal, M5b, issue 75) | audit log check in the eval table | gap | Not built. Proposed by Claude on 2026-10-24 |

## Success metrics (spec section 1.5)

| ID | Metric | Target (proposal) | Status | Measured |
|---|---|---|---|---|
| M-01 | Time to detect | median under 3 s | partial | Median 1.25 s over all 23 fault runs, but it hides a split: GNSS off 1.2 s (12 runs), wrong fix 0.4 s (4 runs), **frozen position 3.5 s (7 runs, range 3.0 to 4.5 s), above the target** |
| M-02 | False alert rate | 0 in N nominal runs | met | 0 in 9 nominal runs. Across all 32 runs there was one false episode in 1.73 flight hours, caused by a stall of the whole simulation (held-out report) |
| M-03 | Misleading-trust epochs | under 1% | met | 0.00% (development) and 0.28% (held-out) with the calibrated bound. With the old bound most GREEN reports were misleading |
| M-04 | Mission completion | at least 90% in a single-vehicle-loss scenario | met | Simulation, three vehicles, one lost (a long GNSS outage that makes PX4 land it), scripted operator approving after 15 s: 100% of the area covered in 3 of 3 runs. With the operator denying: 87% in 3 of 3 runs (the lost vehicle's sector 62%), so the re-task is what meets the target. One loss pattern, few runs, scripted operator (`eval/fleet/results.md`) |
| M-05 | Operator workload proxy | alerts plus approvals per 10 minutes | met | Reported: single-vehicle runs 3.07 interruptions per 10 min (frozen position) and 6.91 (long outage) of flight, 0 in nominal; fleet runs 1.9 (approved) and 2.8 (denied) alerts plus decisions per 10 min. The operator is scripted, so this counts the system's demands, not a person's effort |
| M-06 | Time to decision | report | partial | Round 1, protocol v1, N=2 (`docs/usability/findings-2026-10.md`): P1 approved 134.9 s after the first alert and only after a hint; P2 did not decide. Redesign and protocol v2 not yet re-tested |

## Where the spec disagrees with itself or with what was learned

- **95% against 99%.** NT-03 asks for at least 95% coverage, section 1.5 asks for under 1% misleading
  epochs, which is 99%. The calibrated bound is 3.0 m at a claimed 99%, which meets both. A 95% bound
  would be 2.5 m.
- **The spec's CONOPS recommends "RTL via dead reckoning corridor" for a drifting vehicle.** For a
  frozen position, ground truth showed that RTL (and HOLD) reached the ground at 24.6 (31.7) m/s horizontal speed and
  only LAND stopped the vehicle safely (ADR 0003, one run each).
- **ROS 2 and uXRCE-DDS are not used.** The spec allows the fallback to MAVSDK only; recordings are
  JSON lines and not ROS 2 bags.
- **NT-01 and NT-02 numbers.** The 3 s figure is a proposal in the spec. It is met with margin in
  simulation; that is not evidence it is the right figure for an operator.

## Proposal: M-01 per fault type

M-01 is a single median under 3 s, which hides a split (see the M-01 row). A proposal for the
maintainer to accept: state the target per fault type, because a frozen position is inherently
slower to confirm than a total GNSS loss. For example, GNSS off and wrong fix under 3 s, frozen
position under 5 s (the limit the held-out protocol already used), each with its run count.
Tuning the detector is a separate, optional follow-up (issue 78).

## Checking the table

`tests/test_traceability.py` fails if a row cites a file that does not exist, if a requirement
verified by test is not named in any test, or if this page omits a row of `trace.csv`.
