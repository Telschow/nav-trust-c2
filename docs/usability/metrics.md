# Usability session: metrics and reporting

Companion to `facilitator-script.md`. Issue 16 asks for time to decision and a workload proxy; the
other measures below are what you need to interpret those two honestly.

## Measures

| Measure | Definition | How you get it |
|---|---|---|
| Time to notice | From the alert appearing to the participant first saying that `uav2` has a problem | Alert time: `raised_s` in the audit log. Participant time: the `T+` you wrote down, or read from the screen recording. Subtract. |
| Time to decision | From the recommendation being raised to the participant approving or denying it | `python -m eval.usability logs/usability/P<n>.sqlite` (no stopwatch needed). Blank if they never answered, or if it expired. |
| Decision | Approve, deny, or let it expire; and the reason in their words | Your sheet |
| Understanding | 0 to 4 points, scored from the Phase 3 answers with the rubric below | Your sheet, scored after the session |
| Assists | Number of hints given, by level (1, 2, 3) | Your sheet |
| Slips | Wrong clicks, misread countdown, closed dialog by accident | Your sheet |
| Workload | Raw TLX: the mean of six 0 to 100 scales | Questionnaire |
| Confidence, clarity | Two 1 to 5 ratings | Questionnaire |
| Problems | Each usability problem seen, with who hit it and how severe | Your sheet, section "Problems" |

Time to notice, time to decision and workload are the headline numbers. Everything else explains
them.

## Understanding rubric (Phase 3)

One point each, from the participant's own words, without prompting:

1. They say the drone is landed or stopped (Q1, if they approved), or that nothing was sent and the
   drone was left alone (Q1, if they denied or let it expire).
2. They say a sector was handed to another drone (Q1), or that the sector stays with `uav2` if they
   did not approve.
3. They name where sector S2 is now and who flies it (Q2). In the demo this is `uav1` after an
   approval; check the screen at that moment rather than trusting this note.
4. They say `uav2`'s position still cannot be trusted and point to why (Q3): the red state, "unknown"
   position error, or the reason text.

Score 0 to 4. A participant who lets the card expire can still score all four; the rubric asks
whether they understood what happened, not whether they approved.

Q4 (the dashed ring) is not scored. Note whether they read it as "do not rely on this position".

## Workload questionnaire (Raw TLX)

Six scales as in NASA-TLX (Hart and Staveland, 1988), each marked on a line from 0 to 100 in steps
of 5, answered for the whole supervising period. The raw (unweighted) mean of the six is the Raw
TLX score. The paired-comparison weighting step of the full method is not used.

| Scale | Question | Low end | High end |
|---|---|---|---|
| Mental demand | How mentally demanding was the task? | Very low | Very high |
| Physical demand | How physically demanding was the task? | Very low | Very high |
| Temporal demand | How hurried or rushed was the pace of the task? | Very low | Very high |
| Performance | How successful were you in accomplishing what you were asked to do? | Perfect | Failure |
| Effort | How hard did you have to work to accomplish your level of performance? | Very low | Very high |
| Frustration | How insecure, discouraged, irritated, stressed and annoyed were you? | Very low | Very high |

Physical demand is close to zero on a screen task; it stays in so that scores remain comparable
with other studies. Do not read a score as good or bad on its own: there is no cut-off, and with
three people you have nothing to compare it with except the other two and your own expectations.

Two further ratings, 1 (strongly disagree) to 5 (strongly agree):
- "I was confident in the decision I made."
- "It was clear to me what approving would do."

## Problems: severity

Use these three levels and say so in the write-up; they are this project's own, not a standard.

- **Blocker**: the participant could not complete the step, or ended up with a wrong understanding
  of what the system did or what was recommended, without noticing.
- **Major**: it cost the participant more than about 30 seconds, needed a hint, or caused a wrong
  action they then had to recover from.
- **Minor**: they commented, hesitated or were briefly confused, with no consequence.

Count how many of the participants hit each problem. Fix in this order: blockers, then majors by
count, then stop. Fixing the top three is enough for issue 16.

## Reporting rules (N is 2 to 3)

- State N at the top: "3 participants", how you found them, and that the facilitator is also the
  developer.
- Show each participant's numbers in a table. Do not report a mean or a percentage of three
  people; write "2 of 3".
- Say what was measured and what was not. For example "time to decision was 11, 19 and 41 s" is
  fine; "operators decide in about 20 s" is not.
- Quote, do not paraphrase, for anything that is about what someone understood.
- Report problems you found even if you already know how to fix them, and say what you changed.
  Say plainly that a fix was not re-tested if you did not run another participant.

Limits to repeat in every write-up:
- Convenience sample, not trained operators.
- A replay: the trust data is recorded, the positions are synthetic, and only one event happens
  (by default a drone whose GPS position freezes). Participants know it is a simulation. The demo
  runs five times faster than the flight it was recorded from, so the time pressure is not the real
  one and times to notice and decide are not transferable to a live flight.
- The first alert is a surprise only once per person; there is no learning-effect measurement.
- The facilitator built the system, which affects what participants say and what you notice.

## Data handling

- Participants are P1, P2, P3. No names in notes, file names, recordings' names or the audit
  database (ask participants to type their code in the "your name" box if they open the dialog).
- Everything for a session lives under `logs/`, which is git-ignored. Do not commit recordings,
  sheets or databases. Commit only the findings note, which has the table of values and quotes
  without names.
- Delete recordings after the findings note is written, as you told the participants.

## Findings note: template

```
# Usability session findings

Date, N, how participants were found, who facilitated.

## What was tested
The console in replay-demo mode, one scenario, tasks (monitor, decide, explain), questionnaire.

## What was measured
| Participant | Time to notice, s | Time to decision, s | Decision | Understanding, 0-4 | Assists | Raw TLX | Confidence | Clarity |

## Problems
| # | Problem | Severity | Hit by | Evidence (quote or observation) | What changed |

## What changed
Links to the changes, and which were not re-tested.

## What did not change, and why

## Limits
```
