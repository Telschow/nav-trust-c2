# Usability round 2: the lost-link card (issues 16 and 82)

An addition to `facilitator-script.md`, run in the same session after Phase 3. It tests what the
console shows when a vehicle's reports stop and come back. Same rules: neutral wording, no
teaching, hint levels logged, N stated.

## What the console shows today

- A vehicle with no link shows "No link", its state as "Last known", and "Margin to alert: not
  current, no link". The map says "No link: position and state are last known, not current".
- A recommendation for a vehicle with no link says "uavN has no link. This command may not reach
  it."
- When the link returns, the log gets one line: "uavN link was down 12 s: nothing closed" (or "1
  decision closed" when a recommendation was superseded).
- A superseded recommendation is shown as "Superseded".

## Not shown, so not tested

- **Onboard actions and their authority.** The data carries them, but no console screen shows
  them. Issue 82 lists them; that part waits for a screen.
- **A demo scenario that drops a vehicle's reports.** `sim.demo_feed` has `stuck`, `outage` (GNSS
  loss) and `both`. None cuts a link, so there is nothing to show a participant until a `link`
  scenario exists, or a recorded lost-link run is replayed.

## Script (about 5 minutes, once a scenario exists)

Do not say what will happen. At the moment a vehicle shows "No link", start the notes and ask only
"What are you looking at now?" after 20 seconds of silence.

Ask in order, and write the answers word for word:

1. "What do you think has happened to that drone?"
2. "Is what the screen shows about it true now? How do you know?"
3. (If a recommendation for it is open) "Would you approve this now? Why or why not?"
4. After the link returns: "What changed while it was away? Where did you find out?"
5. "Was there anything you wanted to know and could not find?"

Score nothing. Note: did they read "Last known" as "not current", did they approve a command to a
vehicle with no link and what they said it would do, did they find the log line.

## Sheet additions

| Moment | T+ | Their words |
|---|---|---|
| Vehicle shows "No link" | | |
| First remark about it | | |
| Read "Last known" or the margin as not current? | | |
| Decision on a command to it (if offered) | | |
| Link returns | | |
| Found out what changed (where, how long) | | |
