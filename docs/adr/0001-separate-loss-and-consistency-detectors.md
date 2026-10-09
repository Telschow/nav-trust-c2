# ADR 0001: Separate detectors for GNSS loss and GNSS inconsistency

Status: accepted, 2026-10-09. Decided by the maintainer; written down by Claude on their instruction.

## Context

The trust engine (issue 7) must produce GREEN / AMBER / RED with a reason code
(`GNSS_LOSS`, `INCONSISTENT_INNOVATION`, `BIAS_DRIFT`, `STALE`). The first plan was one
windowed NIS / test-ratio monitor on the estimator's innovations.

Measured on the first two recordings (`tests/replay/data`, one run each, PX4 SITL, Gazebo):

- When the receiver stops (`failure gps off`), the estimator gets no GPS measurements, so
  there are no innovations. In the 8 s around the first zone entry of the jamming run,
  `vel_ratio` stayed near 0.009 and `pos_horiz_ratio` near 0.004, with blips of at most
  0.019 and 0.015.
  The nominal run reaches `vel_ratio` 0.111 on its own.
- Signals that did change: the reported fix type (`FIX_3D` to `NO_GPS` about 1 s after the
  failure starts) and `pos_horiz_accuracy` (0.15 m to 0.53 m within 3 s).
- After a longer outage the estimator stops reporting `vel_ratio`; it must be optional.

A test-ratio monitor therefore cannot detect loss. It can only judge GPS data that exists.

## Decision

Two independent detectors feed one state machine.

1. Availability detector: fix type, time since the last valid fix, and the estimator's
   position accuracy. Produces `GNSS_LOSS` and `STALE`.
2. Consistency detector: windowed NIS / test-ratio monitor on the estimator status.
   Produces `INCONSISTENT_INNOVATION` and `BIAS_DRIFT`.

The state machine combines both, applies hysteresis, and outputs state, reason and
horizontal bound. Loss takes precedence in the reason code.

## Consequences

- NT-01 (alert after total GNSS loss) depends on the availability detector alone.
- NT-02 (no false alerts in nominal runs) is a risk for the consistency detector only.
  Its threshold must be set above the nominal ratios, so the nominal recordings bound it.
- The consistency detector cannot be validated on the jamming recording. It needs fault
  data where GPS keeps reporting wrong values: `stuck` (frozen position) runs are being
  recorded for that. `wrong` only changes the reported fix type and jamming state in PX4
  and leaves the position untouched, so it is not a drift fault.
- Measured separation between nominal and faulted ratios is not known yet.

## Open, not decided here

Thresholds, window length, hysteresis constants and the accuracy limit for AMBER vs RED.
All are proposals until measured on the recordings. Whether the estimator `flags` field
(it changed to 37 after a long outage) is a useful extra signal is untested.

## Alternatives considered

- One NIS monitor for everything: rejected, cannot see loss (evidence above).
- Fix type only: rejected, blind to a receiver that reports a good fix with a wrong
  position, which is the case the consistency detector exists for.
