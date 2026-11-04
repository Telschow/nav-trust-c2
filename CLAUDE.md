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
`make help` lists the targets. `tools/worktree.sh <name>` makes a ready worktree for a task.
- `make eval-all` is the one command that refreshes every committed eval table. Run it after
  editing a file the engine fingerprint covers (`navtrust/*.py`, `c2/recommender.py`,
  `c2/allocator.py`, `c2/fleet.py`, `c2/messages.py`). CI fails if a table differs from its
  recordings or carries an old fingerprint. `make eval-fleet` does the same for
  `eval/fleet/results.md`.
- Ground truth is evaluation-only: the trust engine never sees it. Session data in `logs/` is never
  committed.
- Simulator recording scripts (`sim/record_*.sh`, `make record-*`) are resumable, run one at a time
  and refuse to start on a busy machine.
- No make target for these, run them as modules: `python -m eval.usability logs/usability/P1.sqlite`
  (time to decision from a session), `python -m eval.blind_land` (GNSS loss to descent, from
  `eval/recordings`), `python -m eval.onboard_replay eval/lost_link/recordings` (CI checks the
  onboard monitor never acts in the nominal, jamming, stuck, wrong-fix and link-only recordings),
  `python -m eval.frozen_matrix tests/replay/data/experiments/matrix` (a test checks
  `docs/validation/frozen-position-matrix.md` against it), `python -m eval.land_diagnosis
  tests/replay/data/experiments/land-diagnosis`.
- Simulator scripts with no make target: `sim/record_onboard_runs.sh` (`link_and_frozen` with the
  monitor running, into `eval/lost_link/onboard`), `sim/record_frozen_matrix.sh`,
  `sim/record_land_diagnosis.sh`. `make record-fleet` (three vehicles, one lost, scripted operator;
  about 80 min) is not in `make help`.

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
