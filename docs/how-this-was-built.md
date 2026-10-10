# How this was built

DRAFT written by Claude on 2026-10-10 at the maintainer's request, for the maintainer to edit and
publish. Facts about the repository come from git and are marked as a snapshot; the decision log is
reconstructed from the working sessions, not from the repository, so check it before publishing.
`[you decide]` marks what only the maintainer can state.

## In short

The maintainer planned the project over about three weeks at one to two hours a day (their account),
and made every product and technical decision. The code, tests and most documents were written by
an AI coding agent, Claude Code, working in the maintainer's repository: it proposed options and
a recommendation at each decision point, the maintainer chose, and the maintainer merged every pull
request. The product documents in `docs/product/` were also drafted by the agent, at the
maintainer's request, as drafts for the maintainer to rewrite; the project's own spec had asked for
the maintainer to write them. `[you decide]` how much of them you rewrote, and say so here.

## Tools and models

Claude Code (Anthropic's command-line coding agent), running in the VS Code extension, with the
model Claude Sonnet 5.5 (`claude-sonnet-5-5`). Every agent commit carries
`Co-Authored-By: Claude Sonnet 5.5`. PX4 SITL with Gazebo for simulation, MAVSDK for vehicle
control, FastAPI for the backend, React, TypeScript and MapLibre for the console, GitHub Actions
for CI. ROS 2 was in the original spec and is not used.

## Who did what

| | Maintainer | Agent |
|---|---|---|
| Direction | Every product and technical decision (below); scope and ethics guardrails; what to build next | Options with evidence and a recommendation each time |
| Code and tests | Reviewed and merged the pull requests `[you decide: how closely you read them]` | Wrote all of it |
| Simulation and measurement | Ran the machine and fixed the environment (Docker memory and disk) | Ran the experiments and wrote the harness; reported numbers from the data |
| Product docs | Owns them | First drafts, at the maintainer's request |
| Usability sessions | Plans and runs them | Wrote the kit and the extractor |
| Weekly status, risk log | Owns them | Drafts |

## Facts from git (snapshot of 2026-10-10)

| | |
|---|---|
| Repository history | 8 to 10 October 2026 (the planning before it is not in the repository) |
| Non-merge commits on `main` | 27, all authored by the agent |
| Merge commits on `main` | 18, all by the maintainer |
| Pull requests | 17 merged, 2 open when this was written |
| Issues | 14 closed, 5 open |
| Python / TypeScript / YAML / Markdown lines | about 6,900 / 1,700 / 160 / 1,200 (before these docs; excludes dependencies) |
| Tests | 269 Python, 23 console; CI runs lint, types and tests with no simulator |
| Recordings | 32 simulated runs with ground truth, with a results table CI regenerates |
| Architecture decision records | 3, each recorded on the maintainer's instruction |

Reproduce: `git log --no-merges --format=%an | sort | uniq -c`, `gh pr list --state all`.

## The decisions, and who made them

At each point below the agent laid out options. The maintainer decided. In every case but one the
maintainer chose the option the agent recommended; the one exception is marked. `[you decide]`
whether to keep this table, and whether it is complete.

| Decision | Agent recommended | Maintainer chose |
|---|---|---|
| How to get a base branch for the first pull request | Create `main`, rebase | Same |
| Recording format | JSON lines, not ROS 2 bags | Agreed |
| Structure of the trust engine (ADR 0001) | Separate loss and consistency detectors, from the recordings | Recorded it |
| How scenarios treat PX4's failsafe (ADR 0002) | Follow the failsafe; three scenario classes | Recorded it |
| Console technology | React, TypeScript, Vite, MapLibre | Same |
| Map tiles | The agent suggested a plain grid might look cleaner and avoid tile terms | **OpenStreetMap** (different) |
| Source of the interface definitions | The agent's proposal, to be reviewed | Same |
| PX4 version for GPS failure injection | Pin an unreleased `main` commit | Same |
| Action for a frozen GNSS position | LAND, after ground truth contradicted HOLD | Same (ADR 0003) |
| Held-out validation and a second demo scenario | Do both | Yes |
| Queue order | Urgent first | Yes |
| What the position bound and `confidence` mean | A calibrated bound with its coverage, plus a headroom indicator | Yes |

## What went wrong, and how it was found

A public list. Each row is a mistake in the agent's work, found by the method in the third column.

| # | What went wrong | How it was found | Where fixed |
|---|---|---|---|
| 1 | Issue 5 was written from PX4's `main` documentation, which does not match the pinned v1.17.0: GPS failure injection for Gazebo did not exist there | The injection command timed out | PR 22 pinned a `main` commit |
| 2 | Two wrong diagnoses of a silent failure injector (a shared UDP port, then a silent loop) before the real one: it crashed on the timeout | Reading the full output | PR 22 |
| 3 | The escalation timer counted the 2 s recovery hold as outage time, so a 4 s outage went RED | A test I wrote passed by 0.02 s, which looked wrong | PR 27 |
| 4 | Assumed a vehicle with a frozen GPS position stalls in place, and recommended HOLD | Ground truth showed it flies away at up to 36 m/s | PR 32, ADR 0003 |
| 5 | Told the maintainer a faulted vehicle was "in HOLD", which was true of its mode but not shown to have stopped it | Same experiment | PR 32 |
| 6 | The first HOLD and RTL experiment was unfair: the injector cleared the fault whenever the believed position left the zone | Reading the trace | PR 32 (redone with a latched fault) |
| 7 | A check I added to stop a hang crashed the recorder when PX4 landed a vehicle by design, and aborted the whole batch | The first long-outage run | PR 33 |
| 8 | A bare `off` in YAML is read as `False` | A test | PR 33 |
| 9 | Matching ground truth to the nearest sample added up to 5 m of false error at 10 m/s | The nominal runs showed an error floor | PR 33 (interpolation) |
| 10 | Briefly took a recording still being written for a failed run | Checking the batch log | not committed |
| 11 | "Closes #X and #Y" closes only the first issue; five finished issues stayed open | Reading the issue list | closed by hand |
| 12 | An unanswered recommendation was never marked expired in a live session, so ADR 0003's re-issue never happened; my earlier test hid it by calling `GET /state` | Running the usability flow end to end | PR 34 |
| 13 | The console clock read `T+NaN:NaN` at the start of every session | Same | PR 34 |
| 14 | The console's map worker failed to load, its container collapsed to zero height, and the server had no WebSocket library | Looking at screenshots | PR 31 |
| 15 | The held-out report quoted the development set's flight hours | Re-reading the totals before opening the PR | PR 35 |
| 16 | The displayed position bound (about 0.15 m) was the estimator's own figure and held in 30.8% of reports; spec requirement NT-03 was not met. I had called it "not validated" earlier but still displayed it | Measuring it against ground truth | PR 37 |
| 17 | Wrote that the 3 m nominal error was "roughly 0.3 s of lag"; a time-shift analysis refuted it | Checking before building a confidence on it | PR 37 |
| 18 | 4,073 files of `console/node_modules` committed by `git add -A` on a branch with an old `.gitignore`; CI passed regardless | Counting lines in the repository | PR 38 (untracked; still in history) |

The pattern: the agent's own checks (tests, the type checker, CI) passed in most of these. What
found the problems was running the system, measuring it against ground truth, and reading the
numbers back. `[you decide]` whether to say what you would do differently next time.

## What the agent could not do or did not verify

- It cannot tell how closely each pull request was read; that is the maintainer's to state.
- Everything was measured in simulation. No real receiver, no real interference, no operator under
  stress. The usability sessions have not happened.
- Several results rest on few runs (2 to 4 per scenario, one run per action in ADR 0003).
- The held-out set is no longer held out for this version of the engine.
