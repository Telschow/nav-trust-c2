# Usability findings, October 2026

Two participants, one session each, 11 October 2026. Facilitated by the developer. This is a
first look at what people do with the console, not a measurement of rates.

## What was tested
The replay demo (`make demo`, scenario `stuck`): three drones, one of which (`uav2`) has a frozen
GPS position. A recommendation "Land and re-task uav2" appears about 15 s after the feed starts and
counts down from 60 s. Protocol v1: participants were told they supervise three drones, that a
drone only acts when they approve, and to keep an eye on the drones while thinking aloud. The
console was the version before the redesign in pull request 46.

## Who
Two students in their late twenties, no drone or operations background, acquaintances of the
facilitator. The facilitator also built the system.

## What was measured

| | P1 | P2 |
|---|---|---|
| Alert raised (backend clock) | T+315.6 s | T+269.4 s |
| Card expired unanswered | twice (60 s each) | twice (60 s each) |
| Decision | approved at T+450.5 s, 14.1 s after the third card was raised and after a hint from the facilitator (level not recorded); 134.9 s after the first alert | none; third card still open when the session ended |
| Time to notice | not recorded (no screen recording, no timeline) | not recorded |
| Understanding score (0 to 4) | not scored | not scored |
| Raw workload answers | 5, 1, 4, 5, 5, 4 | 3, 1, 2, 4, 1, 2 |

The audit database confirms both sessions: three recommendations each, no rejected decision
attempts. The workload answers were written down as single digits; the scale on the printed form
runs 0 to 100, so they are reported as given and not converted to a Raw TLX score. Confidence and
clarity ratings were not recorded.

## What they said
Both described the red drone, the sectors, the path each drone had flown, the colours, that the
map was Zurich, the speed of the drones and a possible crash of `uav2`. Neither mentioned the
decision card, its countdown or its buttons, and neither said what they were supposed to do.

## Problems

| # | Problem | Severity | Hit by | Evidence |
|---|---|---|---|---|
| 1 | The decision was not acted on. Both noticed the problem but did not connect it to an action | Blocker | 2 of 2 | Two unanswered cards each (about 2 minutes); P1 approved only after a hint |
| 2 | Participants did not understand that a decision was theirs to make | Blocker | 2 of 2 | Facilitator's account; the v1 briefing said only to keep an eye on the drones |
| 3 | Whether the "REPLAY DEMO" label, the wording "Land and re-task" or the right-hand position of the card played a part | Not tested | | No question was asked |

Not found: the card being off screen. At 1440 x 900 and 1280 x 800 the card and both buttons are
visible without scrolling (screenshots taken during the review, not in the participants' sessions).

## What changed
- Protocol v2 (pull request 45): the briefing gives a role and a goal ("you are the supervisor on
  duty ... whenever the system needs a decision from you, make it"), screen recording with the
  `T+` clock is required, and a decision made after a level 3 hint counts as failed without help.
- Console (pull request 46): a solid red "Decision required" band across the top while any
  decision waits, with the time left and a Review button; the tab title shows the count; the fleet
  becomes rows; flat surfaces and plain labels.
- A debrief question about the red band.

None of these has been re-tested with people.

## What did not change, and why
Wording such as "Land and re-task uav2", the 60 s expiry and the card's position are unchanged: the
sessions gave no evidence about them either way.

## Limits
- N is 2, convenience sample, not trained operators, with the developer as facilitator.
- A replay: recorded trust data, synthetic positions, five times faster than the flight.
- Several measures are missing (time to notice, understanding, confidence, clarity, the hint
  level); this note does not estimate them.
- The result is a first signal: 2 of 2 did not act unaided. It says nothing about the redesign.
