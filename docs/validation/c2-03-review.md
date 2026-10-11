# C2-03 review: can an operator act on the reason shown?

Requirement C2-03: every alert shall show a reason an operator can act on. This is the review
checklist the requirements table asked for. It was done by the agent that wrote the console, so
it is not independent; the usability sessions are the independent check (see the last section).

The checks below are enforced by `console/src/store.test.ts` ("C2-03") for every recommendation
the recommender can make (ADR 0002 and 0003).

## What the recommender can raise

| Trust state and reason | Recommendation | Card title | Reason shown | Extra text |
|---|---|---|---|---|
| RED, GNSS_LOSS | re-task only | "Re-task uav2" | GNSS signal lost or degraded | "No command is sent to uav2: its own failsafe is acting." |
| RED, STALE | re-task only | "Re-task uav2" | No recent navigation data | "No command is sent to uav2: it has stopped reporting." |
| RED, INCONSISTENT_INNOVATION | LAND and re-task | "Land and re-task uav2" | GNSS position disagrees with the vehicle's own sensors | "This vehicle may be flying away from where it thinks it is, and nothing else will stop it." |
| AMBER, any | none by design (ADR 0002) | none | shown in the fleet row | none |

## Checklist

| # | Question | Result |
|---|---|---|
| 1 | Is a reason shown for every alert, in words and not as a code? | Yes. Tested: no internal code (for example `GNSS_LOSS`) appears in a title, reason or action |
| 2 | Does each reason have its own wording? | Yes. Tested |
| 3 | Does the card say exactly what approving will do, naming the vehicle? | Yes, one line per action. Tested |
| 4 | Does it say what happens to the vehicle itself when no command is sent? | Not before this review. Added: the note in the table above |
| 5 | Is the time left to decide shown, and is an expired card unusable? | Yes. Tested |
| 6 | Is a dangerous wait called out? | Yes, for the frozen position (LAND). Not for loss or stale, where a failsafe is acting or data is gone |
| 7 | Can the operator tell why nothing is recommended for AMBER? | Partly. The row shows the state and reason, and the margin to alert; nothing says that no action is expected |
| 8 | Is every reason label one the system can actually produce? | No. `BIAS_DRIFT` has a label but no detector or recommendation uses it |
| 9 | Is the vocabulary understood by someone who has never seen the console? | Not shown. "Re-task" is jargon; no participant was asked about it |

## Findings

1. Fixed: a re-task-only card left the operator to guess what happens to the vehicle (4).
2. Open: AMBER gives no sign that no action is expected (7). Not changed, to keep the console as
   the round 2 sessions will see it.
3. Open: `BIAS_DRIFT` is a dead label (8).
4. Open: "re-task" as a title word (9). Round 2 should ask what participants take it to mean.

## Why the status stays "partial"

The text content passes. But "an operator can act on" is a claim about people, and in round 1
neither participant acted on a card unaided (`docs/usability/findings-2026-10.md`). That was about
noticing and understanding that a decision was theirs, not about the reason code, but the
requirement is not shown as met until round 2 on the redesign.
