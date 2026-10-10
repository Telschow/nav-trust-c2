# Usability session: facilitator script

Session length: about 35 minutes per participant. Plan for 2 to 3 participants, one at a time.
You observe and record; you do not teach, defend or explain the console during the session.

What this tests: whether a person who has never seen the console can notice that a drone's
navigation can no longer be trusted, understand what is being recommended, and decide, within the
time the recommendation allows. It tests the console, not the participant.

What it cannot show: with 2 to 3 people you will find usability problems, not measure rates. Report
what each person did, say N, and do not average.

## Before the first session

1. Pilot once with someone who will not take part, to time it and catch breakages. That run is not
   data.
2. Build the console once: `make console`. Check that the two commands in "Setting up each
   session" start without errors and that the alert appears.
3. Pick the screen: 1920 x 1080, browser full screen, no other windows. The map needs internet
   (OpenStreetMap tiles).
4. Print the observation sheet (`session-sheet.md`) and the questionnaire page, one each per
   participant. Decide who will hold the stopwatch if you are not alone; otherwise use the screen
   recording and the console's `T+` clock instead (below).
5. Decide whether to screen-record (with sound, for the think-aloud). Only with consent.
6. Read the metrics definitions in `metrics.md` once, so you know what you are listening for.

## Setting up each session (5 minutes before)

Terminal A, the backend, with a fresh database for this participant (P1, P2, P3):

```
python -m c2.server --db logs/usability/P1.sqlite --source "REPLAY DEMO"
```

Open http://127.0.0.1:8000 in the browser, full screen. It shows `REPLAY DEMO`, the `T+` clock and
"Waiting for vehicles to report their navigation trust...". Leave it like that.

Terminal B, ready but **not started** (you start it at the end of the briefing, Phase 1):

```
python -m sim.demo_feed --speed 5
```

Restart terminal A with a new database name for every participant: the backend keeps state, and
an approved recommendation changes which drone owns which sector.

The `T+` clock in the header is the backend clock. When you write down a time during the session,
write what `T+` shows. Everything the system logs uses the same clock, so your notes line up with
it exactly.

Which scenario: the default (`stuck`) has one alert. Two others exist, added to the feed command:
`--scenario outage` (drone `uav3` loses GNSS and is landed by PX4; the card offers only to move its
sector, with no command) and `--scenario both` (the two together, so two cards are open at once).
Use `stuck` for every participant unless you have a reason to compare; do not mix scenarios between
participants and then compare their times. Note that the demo compresses time five-fold: in
`outage` the drone is AMBER for only about a second before it turns RED, so a participant may never
see AMBER.

In `both`, the urgent card ("Land and re-task uav2", with the red warning) appears second, below
the routine re-task, because the list is ordered oldest first. Watch which one the participant
takes first and write it down; that ordering is a known open question, not something to hide.

What will happen, so you are not surprised: once the feed starts, the three drones appear. About 15
to 20 seconds later drone `uav2` turns "Not trusted" and a card appears on the right: "Land and
re-task uav2", with a 60 second countdown. If nobody answers, it expires and the same
recommendation appears again. Approving it moves sector S2 from `uav2` to `uav1` on the map.

## Phase 0: welcome and consent (3 minutes)

Say, in your own words, covering every point:

> Thank you for helping. I am testing a screen that helps someone supervise three small survey
> drones, not testing you. There are no wrong answers, and I cannot be disappointed by anything you
> do. Everything is simulated: no real drone is involved and nothing you click can cause harm.
>
> I will ask you to think aloud: say what you are looking at, what you think it means and what you
> are about to do, even if it feels obvious. I will mostly stay quiet. If I do not answer a
> question it is because I am trying not to influence you, not because I am ignoring you.
>
> I will note what you do and how long things take. [If recording: With your permission I will
> record the screen and your voice, so I do not have to rely on my notes. The recording stays on my
> computer, is used only to write up this study, and is deleted afterwards.] Your name will not
> appear anywhere. You will be "P1" (or P2, P3).
>
> You can stop at any time, for any reason, without saying why. Is that all right?

Wait for a clear yes. If anyone says no to recording, do not record, and do not ask twice. Write the
participant code, date and consent (yes/no, recording yes/no) on the sheet. Do not write names.

(This is a plain statement, not legal advice. If your university or employer requires a formal
ethics process or a signed form for studies with people, follow that instead.)

## Phase 1: briefing and free monitoring (5 minutes)

Give the briefing, exactly once. Do not add detail if asked ("that is part of what I am looking
at").

> Imagine you supervise three drones that are searching an area. This screen tells you how far you
> can trust each drone's position. The system can recommend actions. A drone only does something
> when you approve it; if you do nothing, nothing happens except what the drone does on its own.
> Please keep thinking aloud. For the next few minutes your job is just to keep an eye on the
> drones. I will not tell you when anything happens.

Then start the feed in terminal B and start your session notes. Write down the `T+` shown in the
header at that moment: the alert comes about 15 to 20 seconds later.

Watch, and note without helping:
- what they look at first, and in what order;
- the moment they first notice drone `uav2` has a problem: the `T+` and their exact words
  (this is "time to notice");
- anything they misread aloud.

Silence rules:
- 20 seconds of silence: say "What are you looking at now?"
- That is the only prompt in this phase.

## Phase 2: the decision (as long as it takes, at most 5 minutes)

Do not give an instruction. When they have noticed the card, they will often start deciding by
themselves. If they say they have noticed something but ask what to do:

> What would you do if I were not here?

If they ask what a word means ("bound", "re-task"): "What do you think it means?" Record the word.

Record, with `T+`:
- when they first read the "If you approve" list aloud or point at it;
- when they open the confirmation dialog;
- what they decide (approve, deny, or let it expire) and the stated reason;
- every question they ask, verbatim;
- every hint you give (see below) with its level;
- any slip: clicking the wrong thing, closing something, reading the countdown wrongly.

If the 60 second countdown ends without a decision, do not intervene. Note it. The card reappears
by design; let them continue.

Hint levels (use the lowest that unblocks them, log each one):
- Level 1, after 60 seconds of silence or confusion: "What are you thinking right now?"
- Level 2, only after 90 seconds with no progress: point at a region without naming it: "Is there
  anything on the right-hand side you have not looked at yet?"
- Level 3, only if they are stuck for 3 minutes or distressed: tell them what the card is for, and
  mark the task as "failed without help".

Stop this phase when they have approved or denied, or after 5 minutes.

## Phase 3: what happened? (3 minutes)

Ask these in order. Do not confirm or correct the answers; just thank them. Write the answers
down word for word, then score them afterwards using the rubric in `metrics.md`.

1. "In your own words, what did your decision do?" (If they let it expire: "What happened when the
   time ran out?")
2. "Where is sector S2 now, and which drone is flying it?"
3. "Can you trust `uav2`'s position now? How do you know?"
4. "What did the dashed ring around `uav2` on the map mean to you?"

## Phase 4: questionnaire (4 minutes)

Hand over the printed questionnaire (it is at the end of `session-sheet.md`) and leave them alone
to fill it in: six workload scales, then three short ratings. Say only:

> Please answer for the whole time you were supervising the drones, from the first minute until
> your decision.

Do not look over their shoulder, and do not discuss the answers until they hand it back.

## Phase 5: debrief (5 minutes)

Ask, and listen. Write down exact words.

1. "What was the most confusing part?"
2. "Was anything missing, anything you wanted to know and could not find?"
3. "What does 'position bound: unknown' mean to you?"
4. "Did you notice the label in the top right, next to the clock?" If yes: "What does it say?
   What did you take it to mean?" (Tests whether the replay marker is understood.)
5. "If you could change one thing first, what would it be?"
6. "Would you want this screen if you really had to supervise drones? Why or why not?"

Close: thank them, say what happens next (a short write-up with no names), and delete or hand
over anything they asked about. Do not tell them what the "right" answer was unless they ask; if
they ask, say that approving the recommendation is the safe choice here, and why (the drone's
position is frozen and it may be flying away, which only landing stops: ADR 0003).

## Immediately after each session (5 minutes)

- Stop both terminals (Ctrl-C). Check `logs/usability/P<n>.sqlite` exists.
- Run `python -m eval.usability logs/usability/P<n>.sqlite` and copy the time to decision onto the
  sheet.
- Fill the gaps in your notes while you remember them, mark the top three problems you saw, and
  save the recording as `P<n>` with no personal information in the file name.

## Rules for you

- Neutral wording only: "What do you expect to happen?", not "Did you see the red button?".
- Never say "good", "right" or "wrong". "Thank you" is fine.
- Do not explain the interface, even when you wince. Write down where you wanted to.
- If something breaks (the feed stops, the map does not load), say "That is a fault in my setup",
  fix it, and write down what happened. Discard the session if it affected the task.
- Never promise that a problem will be fixed.
