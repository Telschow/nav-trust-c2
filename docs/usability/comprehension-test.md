# Explainer comprehension test (issue 188)

Does a person outside drones and navigation understand [the explainer](../media/explainer.html)
without help? 2 to 3 participants, one at a time, about 15 minutes each. You observe and record;
you do not explain. It tests the explainer, not the participant. With 2 to 3 people you find
problems, not rates: report each person, say N, do not average.

**Pass bar (proposal):** 2 of 3 say, in substance, "the drone thinks it is somewhere it is not, and
a person must approve what to do". If the bar is not met, say so plainly in the findings.

## Before

- Participants work outside drones and navigation and have not seen the explainer. Pilot once with
  someone who will not take part; that run is not data.
- Open the explainer full screen on a laptop. Do not open the README or the video.
- Consent as in `facilitator-script.md`, Phase 0. Codes C1, C2, C3. No names. Session data stays
  out of the repository, as with the usability sessions.

## Script

Say once: "This is a short explainer. Please go through it at your own pace and think aloud. I will
not answer questions, because I want to see what the page does by itself. It is not a test of you."

Give about 20 seconds per step before the first prompt, and say nothing else. Then at each step ask
only "What do you think is going on?" if they are silent for 20 seconds.

Watch and note, with the step number:

- where they stall or go back;
- a word they stumble on or ask about, verbatim;
- Step 2 (spot the liar): did they find the stopped dot, how long it took, and whether the game
  felt too easy, too hard or about right in their words;
- Step 4: did they press approve or deny, and what they said it would do.

## Questions (after the last step, in this order)

1. "In your own words, what is the problem?"
2. "What does the person in this story do, and why can the system not just act?"
3. "What was the picture of the tunnel for?"
4. "Which part, if any, did you not understand?"
5. "Was there a word you would change?"

Write answers word for word. Do not confirm or correct them. Score Q1 and Q2 afterwards:

| Pass | A summary like |
|---|---|
| Yes | Says the drone's position is wrong (or frozen, or not where it thinks) **and** that a person approves the action. |
| Partly | Gets one of the two. |
| No | Neither, or describes something else (for example weather, crashes, GPS signal strength only). |

## Sheet (one per participant)

Code: C__  Date: ______  Consent: [ ] yes  Recording: [ ] yes [ ] no  Pilot: [ ]

| Step | Stalled or went back? | Words they stumbled on (verbatim) |
|---|---|---|
| 1 Your phone | | |
| 2 Spot the liar (found it? after __ s; too easy / right / too hard) | | |
| 3 What it sees | | |
| 4 You decide (approve / deny / neither; what they said it does) | | |
| 5 Evidence | | |

Q1 answer: ______________________________________________ Pass: yes / partly / no
Q2 answer: ______________________________________________ Pass: yes / partly / no
Q3 answer: ______________________________________________
Q4 answer: ______________________________________________
Q5 answer: ______________________________________________

## Findings note

One section per participant, then: how many met the bar (of N), where people stalled, the words
that failed, and the changes to make to the explainer and the video opener. State what was not
shown. Commit it as `docs/usability/findings-comprehension-<month>.md`, without session data.
