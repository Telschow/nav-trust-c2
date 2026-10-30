# CLAUDE.md

## Project
nav-trust-c2:
- human-on-the-loop mission control for a small team of simulated drones (PX4 SITL,
Gazebo, MAVSDK).
- Detects GNSS degradation, shows per-vehicle navigation trust
(GREEN/AMBER/RED + reason + position bound), recommends hold / RTL / re-task.
- Nothing executes without operator approval, given live or in advance (ADR 0004).
- Search-and-rescue / area-survey framing.

## Scope guardrails (non-negotiable)
- Simulation only, unclassified, public sources. No weapons, targeting, effectors, real
  platform parameters, or swarm attack behaviours.
- Every vehicle command except PX4 internal failsafes requires a recorded operator approval. A contingency the operator approved before the mission counts as that approval for the fault, link condition and action it names (LAND only), and for nothing else (ADR 0004).

## Layout
navtrust/ (pure Python trust engine, no sim dependency) | c2/ (allocator, recommender, policy
gate, audit log) | console/ (web UI) | sim/ (docker, survey script, later worlds) | scenarios/
(YAML) | eval/ (batch runner, metrics) | docs/product, docs/programme, docs/adr, docs/ICD.md, GLOSSARY.md, docs/research

## Commands
- All checks without the sim: `make check` (ruff, ruff format, mypy strict, pytest)
- Unit tests only: `pytest`
- Bag replay tests (from M1b): `pytest tests/replay`
- Console (React, TypeScript, Vite, MapLibre; Node 22+): `make console` builds it, `make demo` runs backend +
  console + replayed demo data with no simulator, `cd console && npm test` for its tests
- Usability session (issue 16): `docs/usability/` has the facilitator script, metrics and session
  sheet; `python -m eval.usability logs/usability/P1.sqlite` gives time to decision from a
  session's audit database. Session data lives in `logs/` and is never committed.
- Sim: `make sim-build`, `make sim-up`, `make fly`, `make sim-down`
- Scenarios and eval: scenario files in `scenarios/`; `make record-all` records every run with
  ground truth into `eval/recordings` (simulator, about 1.5 h); `make eval` regenerates
  `eval/results.json` and `eval/results.md`; CI fails if the committed table differs from the
  recordings. Ground truth is evaluation-only: the trust engine never sees it.
- Time from GNSS loss to descent: `python -m eval.blind_land` (reads `eval/recordings`).
- Lost link (issue 75): `make record-lost-link` records only the `link_loss` family in
  `scenarios/lost_link` into `eval/lost_link/recordings` (`make record-all` runs it after the main
  set); `make eval` also regenerates `eval/lost_link/results.md` (`python -m eval.link_loss`); CI
  fails if the committed table differs from the recordings.
- Onboard monitor (issue 76): `python -m eval.onboard_replay eval/lost_link/recordings` replays
  recordings through it (CI checks that it never acts in the nominal, jamming, stuck, wrong-fix and
  link-only recordings); `sim/record_onboard_runs.sh` records `link_and_frozen` with the monitor
  running (simulator, resumable) into `eval/lost_link/onboard`.
- Frozen-position matrix (issue 81): `sim/record_frozen_matrix.sh` (simulator, resumable),
  `python -m eval.frozen_matrix tests/replay/data/experiments/matrix`; the results note is
  `docs/validation/frozen-position-matrix.md` and a test checks it against the recordings.
- Fleet mission completion (M-04): `make record-fleet` (three vehicles, one lost, scripted
  operator; simulator, about 80 min), `make eval-fleet` writes `eval/fleet/results.md`; CI checks it.

## Rules
- CI must not need Gazebo: replay recorded bags.
- Metrics are measured, never typed. Targets in docs are labelled "proposal".
- MAVSDK-Python is imported as `mavsdk_grpc` (package `mavsdk-grpc`); the `mavsdk` name from v4
  is a different, native binding.
- PX4 is pinned to a `main` commit (sim/docker/Dockerfile), not a release: gz GPS failure
  injection (`failure gps off|stuck|wrong`) does not exist in v1.17.0 or v1.18.0-rc1.
- A GNSS loss that does not end made the simulated vehicle start a controlled descent after
  about 5 s and land about 45 s after the loss (2 of 2 runs). Six outages of 4 s caused no
  descent. Zones in tests must be short (4 s worked), or the scenario must expect the landing.
  See docs/validation/px4-lost-link-parameters.md.
- No em dashes. Lean docs. Weekly status file written by the maintainer.
- Maintainer writes docs/product/*, requirements and ADR decisions. Agents may review them.
- Console UI work follows `console/DESIGN.md` (IBM/Carbon, from VoltAgent/awesome-design-md, MIT).
  It is a marketing-site extraction: keep the tokens, but trust state colours and operator
  density come first.
- Ask before adding heavy dependencies or changing the ICD.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`Telschow/nav-trust-c2`, via `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md` plus `docs/adr/`. See `docs/agents/domain.md`.
