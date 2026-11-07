# Explainer brief: the picture and the real terms

For the interactive explainer ([explainer.html](explainer.html)) and the video opener (#189). A
draft for the maintainer to edit. The picture is a metaphor; the project's vocabulary is in
[GLOSSARY.md](../../GLOSSARY.md), and the metaphor terms stay out of it.

## The explainer's steps

1. **Your phone.** A blue dot in a tunnel stops while the van keeps moving.
2. **Spot the liar.** Three drones as dots; one has stopped. Tap the one you can no longer trust.
3. **What it sees.** The system compares each position with the vehicle's own sensors and says why.
4. **You decide.** One recommendation, and nothing moves until a person approves or denies it.
5. **Evidence.** Measured results, each with its source.

## Picture to term

| In the explainer | Real term | Note |
|---|---|---|
| Blue dot | Reported position | What the vehicle says, not where it is. |
| Circle around the dot | Position bound | Shown with its measured coverage. Unknown outside GREEN. |
| Tunnel | GNSS loss, or Frozen position | The tunnel stands for both. In the tunnel the dot greys out on real phones; on a drone it stays confident. |
| Dot stops while the vehicle moves | Position inconsistency | The engine cannot tell frozen from spoofed, and the simulator does not model spoofing. |
| Dashed line from dot to true place | The gap between reported and true position | Ground truth exists only in the evaluation, never in the trust engine. |
| Dispatcher | Operator | Not authenticated; the name is a typed label (Operator name). |
| "Land uav2?" card | Recommendation | Never executes by itself. |
| Hold to approve | Approval | A recorded operator decision. Spent once used. |
| Approved, then land and re-task | Command gate | Approval, then the one gate that is the only path to a command. |
| "Nothing was sent" after Deny | A denied recommendation | The vehicle keeps flying on its own. |

Every metaphor the explainer or the opener uses must have a row. A new picture gets its row first.

## Honesty rules

1. An illustration carries no numbers and is labelled "Illustration, not data".
2. Every figure shown next to one is cited to a committed result file, and says it is simulation.
3. The picture may exaggerate to teach, and says so. Real phones often grey the dot out when the
   signal drops, so the user notices. A drone's position can stay confident and wrong, which is the
   point of the exaggeration.
4. The explainer never says the system detects spoofing, protects a real vehicle, or has been
   tested on hardware. What is not shown is stated in the README.
5. A changed wording is checked against the comprehension test ([#188](https://github.com/Telschow/nav-trust-c2/issues/188)) before the video uses it.
