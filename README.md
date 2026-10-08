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

Checks (no simulator needed):

```
pip install -e ".[dev,sim]"
make check
```

Simulator (Docker; the first image build compiles PX4, needs about 8 GiB for the Docker VM and 20 GB of disk):

```
make sim-build
make sim-up        # headless PX4 SITL + Gazebo, vehicle 1 on udp 14541
make fly           # lawnmower survey over 1 x 1 km, telemetry to logs/*.jsonl
make sim-down
```

Caveat: the Docker image and the survey flight were written against the PX4 v1.17.0 sources but
have not yet been run end to end. M0 is not done until they have.

## How this was built

_To be written by the maintainer: which parts were written by hand and which with AI assistance._

## Layout

See `CLAUDE.md`.
