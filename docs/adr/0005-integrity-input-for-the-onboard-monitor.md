# ADR 0005: Where the onboard monitor gets its integrity input

Status: proposed, 2026-10-25. Context and options written by Claude on the maintainer's instruction.
The decision is the maintainer's to write. No code is written until it is.

## Context

Issue 76 puts the trust engine on the vehicle side of the link, so that a vehicle can act on a
pre-authorised contingency (ADR 0004) when no operator can be reached. Issue 71 and contested-nav
issue 164 describe that monitor as consuming an integrity record from contested-nav. This ADR asks
what that means in practice, because the two projects do not currently exchange anything.

**What the trust engine reads today, checked in `navtrust/engine.py`.** `update_fix(t_s, fix_type)`
takes the receiver's fix type. `update_estimator(t_s, pos_horiz_accuracy_m, pos_horiz_ratio,
vel_ratio)` takes PX4's estimator figures: an accuracy value and the innovation test ratios, where
1.0 is the point at which the estimator itself rejects a measurement. These come from PX4's EKF2
over MAVLink. The engine reports GREEN, AMBER or RED with a reason, and in GREEN a position bound
whose coverage was measured against ground truth (`navtrust/calibration.py`). The estimator's own
accuracy figure is deliberately not used as the bound.

**What contested-nav emits today, checked in its ADR-0035 and `navkit.integrity`.** The ESKF
runner returns, after a whole run, one `IntegrityStatus` per epoch in the trajectory metadata
(schema version 1), and `write_csv` can save them. A record holds the time, the position, the
claimed horizontal and vertical standard deviations, a NIS state (`ok`, `diverging` or `unknown`),
a `monitored` flag, the seconds since the last accepted GNSS fix, the enabled aiding sources, and
`usable` with a reason code. `usable` is false whenever vision is on, because no vision
configuration has passed the calibration gate (ADR-0036). The NIS state says only that innovations
are not being persistently rejected; a filter that is confidently wrong can report `ok`. The record
is synthetic evidence, not field evidence. The runner is a batch run over a whole recording. There
is no streaming interface.

**What is therefore missing.** The simulated vehicles do not run contested-nav's filter, and
contested-nav's filter does not run in the loop. A record in the contested-nav schema does not
exist at flight time in the simulator. The README says the two projects share no code, and
contested-nav keeps its runtime to NumPy, matplotlib and PyYAML (constraint S1).

**What would be lost by getting this wrong.** The idea that authority follows calibration is the
bridge between the two projects. If the input is a replayed file, the simulator evidence looks
end to end without being so, and a reader, including a defence reviewer, will ask which estimator
the vehicle was really flying on.

## Options

(a) **A schema contract, with a replayed or synthetic source in the simulator.** The trust side
defines its own small input type for the fields it needs, documented in `docs/ICD.md`, and accepts
records in the contested-nav schema as JSON or CSV. Tests and scenarios feed it from files that
contested-nav produced or from a synthetic source. No code is shared. In the simulator the vehicle
still flies on EKF2, and the integrity input is injected, so the scenario results say what the
monitor does given such a record, not that a real estimator produced it. This must be stated in
every result that uses it.

(b) **Run contested-nav's filter on the companion computer, fed by the vehicle's sensors.** The
record is then produced where the monitor runs. This is the only option that is end to end. It
needs a streaming interface in contested-nav that does not exist, a dependency or vendored copy
between the repositories, a second estimator beside EKF2 and a decision about which one the
autopilot flies on. It is the largest change and ends the statement that the two share no code.

(c) **Derive the integrity inputs from what PX4 already provides, inside `navtrust`.** The
monitor applies the same idea, that authority needs a calibrated claim, to the EKF2 innovation test
ratios and the engine's calibrated bound. No record crosses between the projects. The simulator
evidence is real, because the inputs are real. The contested-nav contribution becomes the rule and
the evidence for it, not a data feed. EKF2 test ratios are not the NIS of contested-nav, so the
semantics differ and must be named as different.

(d) **Do nothing new.** Issue 76 consumes the existing trust state and calibrated bound only, with
no integrity record. The cross-repository link stays a statement about method. This is the
smallest change, and it leaves issue 164 and contested-nav issue 166 without a consumer in this
project.

## Decision

To be written by the maintainer.

## Consequences to weigh

- **Contested-nav issue 166** adds a dead-reckoning horizon to the record as schema version 2,
  with its own ADR. If the choice is (c) or (d), that field has no consumer here, and its
  priority should be reconsidered.
- **Issue 76** specifies a process that reads the local MAVLink stream. Options (a) and (c) fit
  that; (b) changes it.
- **Evidence wording.** Under (a), every result must say the integrity input was injected. Under
  (c), the results can say they used PX4's own figures.
- **The `usable` rule** in contested-nav is about aiding configuration and the NIS state. Whatever
  is chosen, the trust side needs its own statement of when a position may be believed, and that
  statement needs its own calibration evidence, as the bound has.
- **What this ADR does not decide:** the contingency policy itself (ADR 0004), the alert limits for
  a horizon, or whether vision is ever enabled (ADR-0036).
