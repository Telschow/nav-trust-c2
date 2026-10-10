# PR/FAQ: Nav-Trust C2

DRAFT written by Claude on 2026-10-10 at the maintainer's request. It is a mock press release for a
simulation prototype, dated at the planned end of the project; nothing in it was released and no
company or customer is involved. Every figure is from this repository's measurements and says
"in simulation". `[you decide]` marks things only you can know or choose: the name, the voice, the
quotes. Rewrite it in your own words.

---

## Nav-Trust C2 shows drone operators which position they can believe

**6 December 2026 (planned).** A new open-source prototype, Nav-Trust C2, gives the operator of a
small team of survey drones something they usually do not have: a plain answer to "can I trust this
vehicle's position right now?". It was built and tested entirely in simulation.

When satellite navigation degrades, a drone's own estimator can keep reporting a position with
unwarranted confidence, and the operator reacts late or not at all. Nav-Trust C2 watches each
vehicle's navigation, marks it GREEN, AMBER or RED with a reason in plain language, shows how far the
position can be off, and recommends what to do. It never acts on its own: every command waits for
the operator's approval and is written to an audit log.

In simulation, it raised an alert a median of 1.2 seconds after satellite navigation was switched
off, with no false alerts in nine fault-free runs. For one dangerous failure, a receiver that keeps
reporting a good fix while its position freezes, the vehicle accelerates away and no failsafe fires.
Nav-Trust C2 flagged it within 3 to 4.5 seconds, while the vehicle was still within a few metres of
where it believed it was, and recommended landing it, the only action that stopped the vehicle
safely in the tests.

"`[you decide: a quote from you as the builder, or leave this out. I have not invented one.]`"

The position it displays is not the estimator's own figure, which was wrong far more often than it
claimed. It is a bound measured against the simulator's ground truth: within 3 metres in 99% of
reports, checked on a separate set of runs.

Nav-Trust C2 is an MIT-licensed prototype for PX4 in Gazebo. `make demo` runs the console without a
simulator, on recorded data, and labels it as a replay.

---

## FAQ

**Who is it for?** An operator supervising three to five small survey drones, a commander who wants
the fleet picture, and an engineer who needs to reproduce incidents. These are hypotheses; no
operator has been interviewed yet.

**Does it fly the drones?** No. The drones fly their missions and run their own failsafes. The
console recommends; the operator approves; only then does a command go out. A test enforces that
nothing else in the backend can send one.

**How does it decide a position cannot be trusted?** Two independent checks. One watches whether
GNSS is present, degraded, lost or silent. The other watches whether the data that is arriving
agrees with the vehicle's own sensors. A receiver that reports a good fix but a frozen position is
caught by the second, not the first.

**What does "within 3 metres, 99%" mean?** In 9,348 simulated reports with the vehicle marked GREEN,
the true error was within 3 metres in 99.8% of them (100.0% on the development set, 99.72% on the
held-out set). It holds for this simulator, this vehicle and 5 to 12 m/s. It says nothing else.

**What if the operator does not answer?** The recommendation expires after 60 seconds and is raised
again while the vehicle is still RED. The vehicle's own failsafes act regardless.

**Why recommend landing, not returning home?** Because it was tested. With a frozen position the
vehicle does not know where it is, so return-to-launch and hold ended in fast, uncontrolled
descents hundreds of metres off; landing stopped it. One run per action, so this shows what is
possible, not how often.

**What did you test, and what did you not?** 32 simulated runs across five kinds of scenario (one
without a fault): 14 recorded after the engine was built, and 18 in a held-out set with different
speeds and zones. Not tested:
real receivers, real interference, other vehicles, link loss, an operator under stress. One held-out
expectation was missed: a 6-second stall of the whole simulation produced one false alert, and the
report says so.

**Is it safe for real use?** No. It is a simulation prototype with no authentication, a simulator's
failure model and a handful of runs per scenario. The scope is search-and-rescue and area survey; it
has no weapons, targeting or effector logic and is not designed for any.

**What would you do next?** Track which parts of a sector are already flown, so a re-task does not
start over; measure mission completion with an operator in the loop; run it with real operators; add
link loss; test against real receivers.

**How was it built?** `docs/how-this-was-built.md`.
