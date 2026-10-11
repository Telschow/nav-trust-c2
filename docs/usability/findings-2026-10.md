# Usability findings, October 2026

Round 1: two participants, one session each, 11 October 2026, facilitated by the developer. This
is a first look at what people do with the console, not a measurement of rates. Round 2 (2 to 3
more participants, on the redesign) is planned and not yet done.

## What was tested
The replay demo (`make demo`, scenario `stuck`): three drones, one of which (`uav2`) has a frozen
GPS position. A recommendation "Land and re-task uav2" appears about 15 s after the feed starts and
counts down from 60 s. Protocol v1: participants were told they supervise three drones, that a
drone only acts when they approve, and to keep an eye on the drones while thinking aloud. The
console was the version before the redesign in pull request 46.

## Who
Two students in their late twenties, no drone or operations background, acquaintances of the
facilitator. The facilitator also built the system. Both agreed to be recorded. The recordings are
not published and nothing here carries a name or a video; quotes are paraphrases written down by
the facilitator, not verbatim.

## What was measured

| | P1 | P2 |
|---|---|---|
| Alert raised (backend clock) | T+315.6 s | T+269.4 s |
| Card expired unanswered | twice (60 s each) | twice (60 s each) |
| Hint from the facilitator | shortly before the second card expired (about T+430): "you needed to make a decision, as you see on the right side of the screen" (level 3 in the script: it says what is expected and where) | none recorded |
| Decision | approved at T+450.5 s, 14.1 s after the third card was raised and after the level 3 hint; 134.9 s after the first alert. Counts as failed without help | none; third card still open when the session ended |
| Time to notice | about 3 to 5 s after `uav2` turned red (facilitator's recollection, not verified, not separated by participant) | see P1 |
| Raw workload, 0 to 100 (see below) | 75.0 | 29.2 |
| Confidence and clarity ratings | not filled in | not filled in |
| Understanding score (0 to 4) | not scored | not scored |

The audit database confirms both sessions: three recommendations each, no rejected decision
attempts.

**Workload.** The participants answered the six scales on a 1 to 5 scale, which the facilitator
mapped linearly to 0 to 100 (1 = 0, 2 = 25, 3 = 50, 4 = 75, 5 = 100). This is coarser than the
21-step form in the kit, so the scores are not comparable with published TLX values.

| | Mental | Physical | Temporal | Performance (100 = failure) | Effort | Frustration | Mean |
|---|---|---|---|---|---|---|---|
| P1 | 100 | 0 | 75 | 100 | 100 | 75 | 75.0 |
| P2 | 50 | 0 | 25 | 75 | 0 | 25 | 29.2 |

P1, who needed the hint and approved, rated the task more demanding and their own performance as
a failure. With two people this is a description, not a result.

## What they said
Both described the red drone, the sectors, the path each drone had flown, the colours, that the
map was Zurich, the speed of the drones and a possible crash of `uav2`. Neither mentioned the
decision card, its countdown or its buttons, and neither said what they were supposed to do.
After the approval, a participant said (paraphrase) that `uav1` and `uav2` were now in sector S2:
half right, since `uav1` flies S2, but `uav2` does not. Neither participant noticed the
`REPLAY DEMO` label in the header.

## Problems

| # | Problem | Severity | Hit by | Evidence |
|---|---|---|---|---|
| 1 | The decision was not acted on. Both noticed the problem within seconds (estimate) but did not connect it to an action | Blocker | 2 of 2 | Two unanswered cards each (about 2 minutes); P1 approved only after a level 3 hint |
| 2 | Participants did not understand that a decision was theirs to make | Blocker | 2 of 2 | Facilitator's account; the v1 briefing said only to keep an eye on the drones |
| 3 | A participant misread the outcome of the decision (who flies S2) | Minor | at least 1 of 2 | Paraphrase above |
| 4 | The `REPLAY DEMO` label was not noticed | Minor | 2 of 2 | Debrief. It is therefore unlikely to explain problems 1 and 2 |
| 5 | The wording "Land and re-task" and the right-hand position of the card as causes | Not tested | | No question was asked |

Not found: the card being off screen. At 1440 x 900 and 1280 x 800 the card and both buttons are
visible without scrolling (screenshots taken during the review, not in the participants' sessions).

## What changed
- Protocol v2 (pull request 45): the briefing gives a role and a goal ("you are the supervisor on
  duty ... whenever the system needs a decision from you, make it"), screen recording with the
  `T+` clock is required, and a decision made after a level 3 hint counts as failed without help.
- Console (pull request 46 and 55): a solid red "Decision required" band across the top while any
  decision waits, with the time left and a Review button; the tab title shows the count; the fleet
  becomes rows; flat surfaces and plain labels.
- A debrief question about the red band.

None of these has been re-tested with people.

## What did not change, and why
Wording such as "Land and re-task uav2", the 60 s expiry and the card's position are unchanged: the
sessions gave no evidence about them either way.

## Round 2 (planned)
Two to three new participants with the same background, protocol v2 and the redesigned console.
Screen recording with the `T+` clock on every session, hint levels logged with their time, the
printed 0 to 100 line used for the workload scales, and the two 1 to 5 ratings filled in. The
question is whether a participant decides without a hint.

## Limits
- N is 2, convenience sample, not trained operators, with the developer as facilitator.
- A replay: recorded trust data, synthetic positions, five times faster than the flight.
- Several measures are missing (understanding score, confidence, clarity, exact times), and the
  time to notice is a recollection; this note does not estimate beyond that.
- The result is a first signal: 2 of 2 did not act unaided. It says nothing about the redesign.
