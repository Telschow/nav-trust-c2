# Screen-reader pass on the approval flow (issue 206)

One manual pass with VoiceOver (macOS) or NVDA (Windows), about 15 minutes. It covers the confirm
dialog, the countdown and the two-step landing route (issue 119), which so far have only component
tests. Record what you hear, not what you expect.

## Set up

`make console`, then `make demo` and open http://127.0.0.1:8000 in Safari (VoiceOver) or Firefox
(NVDA). Turn the screen reader on, and wait for the alert: after 15 to 20 seconds `uav2` turns "Not
trusted" and a card "Land uav2 and hand over S2" appears.

## Steps

| # | Do | Expect |
|---|---|---|
| 1 | Move to the card. | It is announced as "Recommendation: Land uav2 and hand over S2". |
| 2 | Listen for the countdown for 30 seconds. | No announcement every second. A coarse "Expires in about ..." or "less than ... seconds" only when you read it. |
| 3 | Activate "Approve...". | A dialog opens, announced with its title. Focus is on Cancel, not on the confirm control. |
| 4 | Press Tab repeatedly, then Shift+Tab. | Focus cycles through the dialog's controls and wraps. It never reaches the page behind. |
| 5 | Press Escape. | The dialog closes and focus is back on "Approve...". |
| 6 | Open it again, go to "Your name (recorded with the decision)", type a name. | The field is announced with that label. |
| 7 | Find the hold-to-confirm button. | Announced with its hint about holding. Note whether you can tell it needs a press and hold. |
| 8 | Activate "Use two steps instead". | Focus moves to "Confirm landing". |
| 9 | Do nothing for 6 seconds. | The route disarms. Note exactly what is announced, if anything. |
| 10 | Use two steps again and activate "Confirm landing" within 5 seconds. | Demo mode: no command is sent, the decision is recorded. |
| 11 | After the dialog closes, note where focus is and what is announced. | Open question: where should focus land when the card disappears? |

## Record

For each step: what was announced (verbatim), pass or problem, and for a problem how bad it is
(blocks the task, makes it hard, or minor). Add the screen reader, its version, the browser and the
operating system. Post it on issue 206.

| # | Heard (verbatim) | Pass / problem | Severity | Notes |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |
| 7 | | | | |
| 8 | | | | |
| 9 | | | | |
| 10 | | | | |
| 11 | | | | |

Name the single worst problem first.
