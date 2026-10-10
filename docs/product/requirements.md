# Requirements and success metrics

DRAFT written by Claude on 2026-10-10 at the maintainer's request, from the project spec
(section 3 requirements, section 1.5 metrics) and the evidence in this repository. The maintainer
owns it: edit the wording, the targets and the judgements. Targets are proposals from the spec, not
results. Status is read from `trace.csv`, which a test checks against the files it cites.

Everything here was measured in simulation (PX4 SITL in Gazebo, one vehicle model, 5 to 12 m/s,
PX4's own GPS failure model). Nothing in it says anything about real receivers or real interference.

## Requirements

| ID | Requirement | Verification | Status | What the evidence shows |
|---|---|---|---|---|
| NT-01 | The trust engine shall raise AMBER within 3 s of total GNSS loss (proposal) | replay test, `eval/` | met | 12 runs with GNSS switched off: time to detect 1.0 to 1.4 s |
| NT-02 | The trust engine shall not leave GREEN in nominal runs | replay test, `eval/` | met | 9 nominal runs, no alert after startup |
| NT-03 | The displayed bound shall contain the true position error in at least 95% of GREEN epochs | ground-truth comparison | met | Since the calibrated bound (3.0 m, claimed 99%): 100.0% of 4,040 development reports and 99.72% of 5,308 held-out reports. Before it the console's bound held in 30.8% of reports, so this requirement was **not** met until PR 37 |
| C2-01 | No vehicle command shall execute without a recorded operator approval, except PX4's own failsafes | unit tests on the gate and the audit log | met | The gate is the only path to a command, an AST test enforces that, and every outcome is audited |
| C2-02 | On RED the system shall propose re-assignment of the vehicle's remaining sectors within 2 s | integration test | partial | The recommender runs on the report that turns RED, which is tested. End-to-end latency in a live system was not measured. For a frozen position the proposal is LAND plus re-assignment |
| C2-03 | Every alert shall show a reason code an operator can act on | UI test, review checklist | partial | The console shows a plain-language reason and the exact actions, covered by component tests. The review checklist has not been done |
| UX-01 | The operator can see all vehicles' trust states without scrolling at 1080p | manual check, screenshot | partial | Measured at 1920 x 1080 with 3 vehicles: the lowest card ends at 889 of 1080 px, nothing scrolls. The spec says an operator controls 3 to 5 vehicles; five of these cards would need scrolling |

## Success metrics (spec section 1.5)

| ID | Metric | Target (proposal) | Status | Measured |
|---|---|---|---|---|
| M-01 | Time to detect | median under 3 s | partial | Median 1.25 s over all 23 fault runs, but it hides a split: GNSS off 1.2 s (12 runs), wrong fix 0.4 s (4 runs), **frozen position 3.5 s (7 runs, range 3.0 to 4.5 s), above the target** |
| M-02 | False alert rate | 0 in N nominal runs | met | 0 in 9 nominal runs. Across all 32 runs there was one false episode in 1.73 flight hours, caused by a stall of the whole simulation (held-out report) |
| M-03 | Misleading-trust epochs | under 1% | met | 0.00% (development) and 0.28% (held-out) with the calibrated bound. With the old bound most GREEN reports were misleading |
| M-04 | Mission completion | at least 90% in a single-vehicle-loss scenario | gap | Not measured. It needs a fleet scenario with an approved re-task and sector-completion tracking, which does not exist yet |
| M-05 | Operator workload proxy | alerts plus approvals per 10 minutes | partial | Interruptions per run are measured (1 for a long outage or a frozen position, 0 otherwise). Per 10 minutes is not computed, and no approvals are simulated |
| M-06 | Time to decision | report | gap | Pending the usability sessions (issue 16). The extractor `eval/usability.py` exists |

## Where the spec disagrees with itself or with what was learned

- **95% against 99%.** NT-03 asks for at least 95% coverage, section 1.5 asks for under 1% misleading
  epochs, which is 99%. The calibrated bound is 3.0 m at a claimed 99%, which meets both. A 95% bound
  would be 2.5 m.
- **The spec's CONOPS recommends "RTL via dead reckoning corridor" for a drifting vehicle.** For a
  frozen position, ground truth showed that RTL (and HOLD) end in a fast uncontrolled descent and
  only LAND stopped the vehicle safely (ADR 0003, one run each).
- **ROS 2 and uXRCE-DDS are not used.** The spec allows the fallback to MAVSDK only; recordings are
  JSON lines and not ROS 2 bags.
- **NT-01 and NT-02 numbers.** The 3 s figure is a proposal in the spec. It is met with margin in
  simulation; that is not evidence it is the right figure for an operator.

## Checking the table

`tests/test_traceability.py` fails if a row cites a file that does not exist, if a requirement
verified by test is not named in any test, or if this page omits a row of `trace.csv`.
