# nav-trust-c2

Human-on-the-loop mission control for a small team of simulated drones: navigation trust per
vehicle (GREEN, AMBER, RED, with a reason and a measured position error) and recommendations that
wait for an operator's approval.

![Operator console at 1080p, replay demo](screenshots/console-1080p.jpg)

{%
  include-markdown "../README.md"
  start="<!-- summary-start -->"
  end="<!-- summary-end -->"
%}

Source, tests and the results tables are in the
[repository](https://github.com/Telschow/nav-trust-c2). The measured results are regenerated and
checked by CI: [development set](https://github.com/Telschow/nav-trust-c2/blob/main/eval/results.md),
[held-out set](https://github.com/Telschow/nav-trust-c2/blob/main/eval/heldout/results.md),
[fleet runs](https://github.com/Telschow/nav-trust-c2/blob/main/eval/fleet/results.md).
