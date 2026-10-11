# Contributing

Issues and pull requests are welcome. Keep to the project's scope, which is firm:

- Simulation only, public sources, search-and-rescue and area-survey framing. No weapons,
  targeting, effectors, real platform parameters or attack behaviours. Changes that move in that
  direction will be closed.
- Every vehicle command except PX4's own failsafes needs a recorded operator approval. The only
  path to the executor is `c2/gate.py`; a test enforces it.
- Metrics are measured, never typed. A target in a document is labelled "proposal".
- Changing the interface (`docs/ICD.md`) needs a discussion first.

Before opening a pull request, run `make check` (ruff, ruff format, mypy strict, pytest) and, for
console changes, `cd console && npm test`. CI does not need the simulator: it replays recorded
runs. If you change the trust engine or the recommender, regenerate the results tables
(`make eval`, `make eval-heldout`); CI fails when a committed table differs from the recordings.

Style: plain language, lean docs, no em dashes.
