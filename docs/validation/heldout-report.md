# Held-out validation: report

Protocol: `heldout-protocol.md`, committed before any of these runs existed. Numbers below are
copied from `eval/heldout/results.md`, which CI regenerates from `eval/heldout/recordings`.

## What was done

18 runs in 8 scenarios, flown after the protocol was committed. The engine was not changed: the
fingerprint of the engine and recommender code in the results equals the one frozen in the protocol
(`ef6eb466...`), and `git diff` of those files against the protocol commit is empty.

## Result: 7 of 8 expectations met, E3 not met

| | Expectation | Result |
|---|---|---|
| E0 | All recordings present | met |
| E1 | Every fault run detected | met (10 of 10) |
| E2 | Time to detect at most 5 s | met |
| E3 | No false alert | **not met**: 1 episode in `wrong_fix_fast-1` |
| E4 | No second GREEN while more than 10 m off | met |
| E5 | Severity matches the class | met |
| E6 | Interruptions per run as expected | met |
| E7 | PX4 behaved as the scenario files say | met |

### The one miss (E3)

`wrong_fix_fast-1` has a 6 s AMBER episode (28.5 to 34.5 s) with no fault injected. The cause is a
hole in the data, not a judgement by the engine:

- The estimator status stream has no sample between 25.5 and 32.25 s (6.8 s). The position and
  ground-truth streams have holes at the same moment (4.2 s and 5.9 s).
- The simulation clock ran at 0.23 times real time and then caught up at about 52 times: the whole
  simulation stalled and resumed. No other recording has a hole like it (the next largest is 2.5 s).
- The engine reported `STALE` after 3 s without data, as designed, and returned to GREEN when data
  came back. Had the hole been about a second longer it would have escalated to RED.

I do not know why the simulation stalled. I was running tests on the same machine while that run
was in progress, which is a plausible cause, but I did not test it. Per the protocol the run is
**not** removed, repeated or excluded, and the engine and thresholds were not changed. The result
stands as: one false alert in 0.73 flight hours, caused by a data gap.

## Margins worth knowing

- **Slow frozen position is detected late.** `stuck_position_slow` is detected after 4.4 to 4.5 s,
  inside the 5 s limit by half a second. This is the case the protocol predicted as most at risk.
  Time to detect for a frozen position was 3.0 to 3.2 s in development (10 m/s), 3.5 to 3.7 s at
  12 m/s and 4.4 to 4.5 s at 5 m/s. Two runs per condition is too few to say how it depends on
  speed, and it is not monotonic in speed, so I draw no rule from it.
- **The error at the alert is small in every case** (at most 3.6 m), including the slowest. The
  alert comes before the position is wrong, as in development.
- **No second of misleading GREEN** in any of the 18 runs, with a 10 m threshold that sits well
  above the roughly 3 m error that even nominal runs show.

## What this shows and what it does not

It shows that, inside this simulator, the engine's behaviour held up across speeds from 5 to
12 m/s, altitudes of 20 and 40 m, zone widths from 20 to 360 m and a zone on one lane only.

It does not show anything about real receivers or real jamming or spoofing, other vehicles or
estimators, or faults that grow slowly; the fault model is PX4's, the same one used in development.
It has 18 runs and two to three per scenario, so it gives no rates. The false-alert exposure is
0.73 flight hours in this set.

## What is used up

These recordings are no longer held out for this version of the engine: I have looked at them. Any
later change to the engine changes its fingerprint, the CI check will fail until the results are
regenerated, and a fair test of the changed engine needs a new set of runs under new conditions.
