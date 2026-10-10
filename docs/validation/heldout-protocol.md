# Held-out validation protocol

Written and committed before any held-out recording exists. Check the git history: this file,
`eval/expectations.py`, `scenarios/heldout/` and the fingerprint below come first;
`eval/heldout/recordings` is added afterwards.

## Question

The trust engine and its thresholds were developed on the recordings in `tests/replay/data` and
tuned by looking at them. The development evaluation (`eval/results.md`) was recorded afterwards
with the engine unchanged, but it uses the same speed (10 m/s), altitude (30 m) and zone sizes as
development. Does the engine still behave as expected under conditions it was not developed for?

## What is different in the held-out set

| | Development | Held-out |
|---|---|---|
| Speed | 10 m/s | 12 m/s (PX4's default limit) and 5 m/s |
| Altitude | 30 m | 40 m and 20 m |
| Zone width | 40 m, 80 m, 300 m | 20 m, 50 m, 60 m, 100 m, 360 m |
| Zone position | 200 to 450 m east, crossing both lanes | 80 to 460 m east, one scenario crossing only the return lane |
| Survey | 600 x 100 m | 600 x 100 m and 300 x 100 m |

18 runs in 8 scenarios (`scenarios/heldout/`): nominal_fast (3), nominal_slow (2),
short_outage_fast (3), short_outage_slow (2), long_outage_fast (2), stuck_position_fast (2),
stuck_position_slow (2), wrong_fix_fast (2).

## What is the same, so what this cannot show

Same simulator (PX4 SITL, Gazebo), same vehicle model, same GPS failure model (PX4's `off`,
`stuck` and `wrong`), same estimator. The faults are therefore the same *kinds* as in
development. This tests generalisation across flight conditions inside one simulator. It says
nothing about real receivers, real jamming, spoofing, other vehicles or other estimators. With 18
runs it cannot give rates.

## What is frozen

The trust engine and everything the recommender uses are fixed. Their fingerprint (sha256 over
`navtrust/*.py`, `c2/recommender.py`, `c2/allocator.py`, `c2/fleet.py`, `c2/messages.py`, see
`eval/freeze.py`) is:

```
ef6eb4666b2557353b09c4ab996bcd61722ce038164051f61e86ec490b6ae308
```

Every results file records the fingerprint it was computed with. If a held-out result carries a
different fingerprint, the engine changed after this protocol and the set is no longer held out for
that version; the report must say so.

## Expectations

Defined as code in `eval/expectations.py` so that "met" cannot be redefined after the fact. The
numbers come from the development results with a margin and are proposals, not requirements (the
spec's NT-01 and NT-02 values are not in this repository).

| | Expectation |
|---|---|
| E0 | Every scenario has all its recordings |
| E1 | Every fault run is detected |
| E2 | Time to detect is at most 5 s in every fault run (development maximum: 3.2 s) |
| E3 | No false alert in any run |
| E4 | No second in which the engine said GREEN while the true position was more than 10 m off |
| E5 | Severity matches the class: nominal stays GREEN; short outage and wrong fix reach AMBER only; a long outage reaches RED within 10 s (development: 6.4 s); a frozen position reaches RED |
| E6 | Operator interruptions per run: 1 for a long outage or a frozen position, otherwise 0 |
| E7 | PX4 behaved as the scenario file says (missions finish except for a long outage and a frozen position) |

E7 is about the simulator, not the engine; if it fails, the scenario assumption was wrong.

### Where I expect trouble

Stated in advance so that a failure is not a surprise being explained away:
- **stuck_position_slow** is the most likely to miss E2. At 5 m/s the position error grows more
  slowly, and the consistency detector only fires when the estimator's own gate is crossed.
- **short_outage_slow** crosses only one lane and lasts 20 m at 5 m/s; the recovery hold might
  interact with it.
- 12 m/s may not be reached if PX4 caps the speed; a lower real speed is not a failure but should
  be visible in the runs.

## What happens if an expectation is not met

It is reported as not met, with the runs that missed it, in `eval/heldout/results.md`. The engine
and its thresholds are **not** changed to make it pass. If a change is made later for a good
reason, that is a new development iteration: it changes the fingerprint, and the held-out set is
then partly used up, which the next report states.

## How to reproduce

```
make record-heldout    # simulator needed, about 2 hours
make eval-heldout      # writes eval/heldout/results.json and results.md
```

CI recomputes the tables from the recordings and fails if the committed ones differ.
