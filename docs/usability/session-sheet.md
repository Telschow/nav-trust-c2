# Observation sheet: one per participant

Participant code: P__    Date: ________    Facilitator: ________    Pilot (not counted): [ ]

Consent given: [ ] yes    Recording consent: [ ] yes  [ ] no        Technical problems: ______________

## Timeline (write the `T+` shown in the header)

| T+ | What happened (their words in quotes) | Hint level (1, 2, 3) or slip |
|---|---|---|
| | Feed started | |
| | | |
| | | |
| | | |
| | | |
| | | |
| | | |
| | | |
| | | |
| | | |

Key moments (fill from the timeline):

| Moment | T+ |
|---|---|
| Feed started | |
| First verbal sign that uav2 has a problem (exact words below) | |
| Alert card appeared (from the audit log, `raised_s`) | |
| Read the "If you approve" list aloud or pointed at it | |
| Opened the confirmation dialog | |
| Decided | |

Exact words when they first noticed: ____________________________________________________

Decision: [ ] approved  [ ] denied  [ ] let it expire    Reason in their words: ______________

Did the countdown run out? [ ] no  [ ] yes, how many times: __

## After the session (from the log)

`python -m eval.usability logs/usability/P__.sqlite`

Time to decision: ______ s     Time to notice (= first verbal sign minus alert time): ______ s

Rejected decision attempts (for example acting on an expired card): ____

## Phase 3 answers (word for word) and score

| Question | Answer | Point (0/1) |
|---|---|---|
| Q1 What did your decision do? | | |
| Q1 (second point) what happened to the sector | | |
| Q2 Where is S2 now, who flies it? | | |
| Q3 Can you trust uav2's position now? How do you know? | | |
| Q4 What did the dashed ring mean? (not scored) | | n/a |

Understanding score (0 to 4): ____

## Debrief (word for word)

1. Most confusing: ______________________________________________________________
2. Missing: ______________________________________________________________________
3. What "position bound: unknown" means to them: _____________________________________
4. Noticed the label in the top right? What did they take it to mean: ____________________
5. First thing they would change: __________________________________________________
6. Would they want it, why: _______________________________________________________

## Hints and slips

Hints given: level 1 x __   level 2 x __   level 3 x __
Slips: ________________________________________________________________________________

## Problems seen in this session

| # | Problem (what happened, where on the screen) | Blocker / Major / Minor |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |

---

# Questionnaire (hand this page to the participant)

Participant code: P__

Please answer for the whole time you were supervising the drones, from the first minute until your
decision. Mark each line with a cross at the point that matches your experience.

```
Mental demand: How mentally demanding was the task?
Very low |----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----| Very high

Physical demand: How physically demanding was the task?
Very low |----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----| Very high

Temporal demand: How hurried or rushed was the pace of the task?
Very low |----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----| Very high

Performance: How successful were you in accomplishing what you were asked to do?
Perfect  |----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----| Failure

Effort: How hard did you have to work to accomplish your level of performance?
Very low |----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----| Very high

Frustration: How insecure, discouraged, irritated, stressed and annoyed were you?
Very low |----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----| Very high
```

Circle one number, 1 = strongly disagree, 5 = strongly agree.

"I was confident in the decision I made."            1   2   3   4   5

"It was clear to me what approving would do."         1   2   3   4   5

---

## Scoring the questionnaire (facilitator)

Each line has 20 equal intervals. Read the cross as a value from 0 (left end) to 100 (right end),
to the nearest 5. Raw TLX is the mean of the six values.

| Mental | Physical | Temporal | Performance | Effort | Frustration | Raw TLX (mean) | Confident | Clear |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |
