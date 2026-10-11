# nav-trust-c2

Human-on-the-loop mission control console for a small team of simulated drones. It detects GNSS
degradation, tells the operator how much to trust each vehicle's position, and recommends (never
executes without approval) re-tasking, hold or return-to-launch.

**Status: milestone M0 (skeleton). No trust engine, no console yet.** Results table, demo video
and the 60-second summary come with later milestones.

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

![Operator console at 1080p, live run: uav2 lost trust, decision waiting](docs/screenshots/console-1080p.jpg)

A dark operations-room console: a card per vehicle (trust state, plain-language reason, position
bound, time in state, assigned sectors, a two-minute trust strip), a map with the survey sectors
coloured by the vehicle that owns them, and a decision queue where each recommendation lists
exactly what approving will do and counts down to its expiry.

The screenshot is a **live run** of three simulated PX4 vehicles: a frozen-GPS-position fault was
injected on uav2, its trust turned RED, and the console recommends landing it and moving its sector
to uav3. Nothing has been sent yet: the decision waits for the operator. The healthy vehicles show
"within 3 m" (a bound that held in 99% of reports, measured against simulator ground truth) and
how much margin they have before an alert.

Try it without the simulator: `make demo`, then open http://127.0.0.1:8000. That replays
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
