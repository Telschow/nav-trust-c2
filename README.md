# nav-trust-c2

[![CI](https://github.com/Telschow/nav-trust-c2/actions/workflows/ci.yml/badge.svg)](https://github.com/Telschow/nav-trust-c2/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Telschow/nav-trust-c2/actions/workflows/codeql.yml/badge.svg)](https://github.com/Telschow/nav-trust-c2/actions/workflows/codeql.yml)
[![Docs](https://github.com/Telschow/nav-trust-c2/actions/workflows/pages.yml/badge.svg)](https://telschow.github.io/nav-trust-c2/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Does the operator know which drone's position to trust, and what to do about it?**

<!-- summary-start -->
## In 60 seconds

**Problem.** A drone that loses GNSS, or whose position has frozen, keeps flying on a position
that is wrong. A person supervising several drones has to learn which one, how wrong, and what to
do, and no vehicle may be commanded without that person's approval.

**What it does.** Two independent detectors watch each simulated vehicle (GNSS availability, and
agreement with the vehicle's own sensors). The console shows per vehicle a trust state (GREEN,
AMBER, RED), the reason, and a position error with its measured coverage. It recommends landing,
re-tasking a lost vehicle's sector, and nothing else. Nothing executes without a recorded
operator approval; one gate is the only path to a command, and a test enforces it.

**Evidence, all in simulation (PX4 SITL and Gazebo, ground truth from the simulator).**
- GNSS loss was detected in 1.0 to 1.4 s in 12 runs; a frozen position in 3.0 to 4.5 s. No alert
  in 9 nominal runs.
- The displayed bound, within 3 m, held in 100% of 4,040 reports on the data it was tuned on and
  in 99.72% of 5,308 reports on an independent set. The first version, taken from the
  estimator's own accuracy figure, held in 30.8%.
- A frozen GPS position does not stall the vehicle, it flies away (5.3 km in one run). Only
  LAND ended the flight in a controlled stop, so that is what is recommended.
- With one of three vehicles lost, the area covered was 100% when the operator approved the
  re-task and 87% when the operator denied it (3 runs each, scripted operator).
- Held-out validation: 7 of 8 pre-declared expectations met. The one that was not is reported,
  not excluded: [docs/validation/heldout-report.md](docs/validation/heldout-report.md).

**What is not shown.** Real hardware, real interference, or a usability result: two people did not
act on the decision unaided, the console was then redesigned, and that has not been re-tested
([findings](docs/usability/findings-2026-10.md)). Targets in the documents are proposals.

**How it was built, including the mistakes:** [docs/how-this-was-built.md](docs/how-this-was-built.md).
<!-- summary-end -->

## Scope and ethics guardrails

- Simulation only. Unclassified, public sources only.
- Mission framing is search-and-rescue and area survey.
- No weapons, no targeting, no effectors, no real platform parameters, no swarm attack behaviour.
- The operator always approves vehicle commands. Only PX4's own failsafes act without approval.

## Non-goals

Real hardware flight, swarming algorithms, computer vision, learned components, datalink
encryption modelling, any targeting or effector logic.

## Quick start

Checks (no simulator needed). Python 3.12; Node 22 or newer only for the console:

```
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,sim,c2]"
make check
```

The console demo (no simulator, no Docker): `make demo`, then open http://127.0.0.1:8000. About 15
seconds after it starts, uav2 turns RED and a decision appears. Other scenarios:
`make demo-run DEMO_SCENARIO=outage` (a vehicle loses GNSS and PX4 lands it) or `both` (two
alerts at once). Stop it with Ctrl-C. Details under "Operator console" below.

Simulator (Docker; the first image build compiles PX4, needs about 8 GiB for the Docker VM and 20 GB of disk):

```
make sim-build
make sim-up        # headless PX4 SITL + Gazebo, vehicle 1 on udp 14541
make fly           # lawnmower survey over 1 x 1 km, telemetry to logs/*.jsonl
make sim-down
```

The image pins PX4 to a `main` commit (see `sim/docker/Dockerfile`), not a release, because GPS
failure injection for Gazebo does not exist in v1.17.0. All recordings were made with it.

## Operator console

![Operator console at 1080p, replay demo: uav2 lost trust, decision waiting](docs/screenshots/console-1080p.jpg)

A dark operations console: a row per vehicle (trust state as a shape, a word and a colour,
plain-language reason, position error, time in state, assigned and flown sectors, margin to alert,
a two-minute trust strip), a map with the survey sectors coloured by the vehicle that owns them,
and a decision queue where each recommendation lists exactly what approving will do and counts
down to its expiry. While any decision waits, a red band across the top names the most urgent one
and the time left.

The screenshot is the **replay demo** (`make demo`: recorded trust data from a simulated frozen
GPS position, synthetic positions, labelled `REPLAY DEMO` in the header). uav2 turned RED, a red
band across the top says a decision is required, and the console recommends landing uav2 and
moving its sector to uav1. Nothing has been sent: the decision waits for the operator. The
healthy vehicles show "within 3 m" (a bound that held in 99% of reports, measured against
simulator ground truth) and their margin before an alert. The three-vehicle runs with live PX4
vehicles are in [eval/fleet/results.md](eval/fleet/results.md).

Run the same thing yourself without the simulator: `make demo`, then open http://127.0.0.1:8000. That replays
**recorded** trust data with **synthetic** positions, and the console says `REPLAY DEMO` in the
header whenever the data is not live. Map tiles are OpenStreetMap (internet needed; attribution
is shown on the map). The tiles come from OpenStreetMap's public server, whose
[tile usage policy](https://operations.osmfoundation.org/policies/tiles/) allows light use such
as this demo and not bulk or production use. For anything heavier, point the map style in
`console/src/components/MapView.tsx` at your own tile source.

## Results

The evaluation (time to detect, false alerts, time spent GREEN while the position was actually
wrong, error at the alert, mission completion, operator interruptions) is generated from
recorded simulator runs with ground truth: [eval/results.md](eval/results.md). CI recomputes it
and fails if it differs. The scenarios are in [scenarios/](scenarios/); `make record-all`
re-records them (simulator needed, about 1.5 hours) and `make eval` regenerates the table.

Fleet-level mission completion (three vehicles, one lost, a scripted operator) is in
[eval/fleet/results.md](eval/fleet/results.md): in simulation the re-task brought the area covered
from 87% to 100%. `make record-fleet` re-records it (about 80 minutes) and `make eval-fleet`
regenerates the table.

## How this was built

This project (including its code, tests and documentation) was supported by different local and cloud-hosted LLMs. Every design & architecture decision, the scope and goals of the project and its requirements and limitations was defined by me (aka the maintainer). You can find further information in 
[docs/how-this-was-built.md](docs/how-this-was-built.md).

## Acknowledgements

Built on [PX4](https://px4.io) (BSD-3), [Gazebo](https://gazebosim.org), [MAVSDK](https://mavsdk.mavlink.io),
[MapLibre GL JS](https://maplibre.org) (BSD-3), map data from
[OpenStreetMap contributors](https://www.openstreetmap.org/copyright) (ODbL) and the IBM Plex
fonts (SIL Open Font License 1.1). `console/DESIGN.md` is adapted from
[VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) (MIT).

## Layout

See `CLAUDE.md`.
