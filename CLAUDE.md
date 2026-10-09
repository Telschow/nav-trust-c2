# CLAUDE.md

## Project
nav-trust-c2: human-on-the-loop mission control for a small team of simulated drones (PX4 SITL,
Gazebo, ROS 2, MAVSDK). Detects GNSS degradation, shows per-vehicle navigation trust
(GREEN/AMBER/RED + reason + position bound), recommends hold / RTL / re-task. Nothing executes
without operator approval. Search-and-rescue / area-survey framing.

## Scope guardrails (non-negotiable)
- Simulation only, unclassified, public sources. No weapons, targeting, effectors, real
  platform parameters, or swarm attack behaviours.
- Every vehicle command except PX4 internal failsafes requires a recorded operator approval.

## Layout
navtrust/ (pure Python trust engine, no sim dependency) | c2/ (allocator, recommender, policy
gate, audit log) | console/ (web UI) | sim/ (docker, survey script, later worlds) | scenarios/
(YAML) | eval/ (batch runner, metrics) | docs/product, docs/programme, docs/adr, docs/ICD.md

## Commands
- All checks without the sim: `make check` (ruff, ruff format, mypy strict, pytest)
- Unit tests only: `pytest`
- Bag replay tests (from M1b): `pytest tests/replay`
- Sim: `make sim-build`, `make sim-up`, `make fly`, `make sim-down`
- Scenarios and eval (from M1a / M3): `make scenario NAME=jamming_zone`, `make eval`; CI checks
  that the generated table matches the committed one.

## Rules
- CI must not need Gazebo: replay recorded bags.
- Metrics are measured, never typed. Targets in docs are labelled "proposal".
- MAVSDK-Python is imported as `mavsdk_grpc` (package `mavsdk-grpc`); the `mavsdk` name from v4
  is a different, native binding.
- PX4 is pinned to a `main` commit (sim/docker/Dockerfile), not a release: gz GPS failure
  injection (`failure gps off|stuck|wrong`) does not exist in v1.17.0 or v1.18.0-rc1.
- A GNSS outage longer than a few seconds makes PX4 land the vehicle ("blind land"
  failsafe). Zones in tests must be short, or the scenario must expect the landing.
- No em dashes. Lean docs. Weekly status file written by the maintainer.
- Maintainer writes docs/product/*, requirements and ADR decisions. Agents may review them.
- Ask before adding heavy dependencies or changing the ICD.
