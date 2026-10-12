# nav-trust-c2

Human-on-the-loop mission control for a small team of simulated drones: navigation trust per
vehicle (GREEN, AMBER, RED, with a reason and a measured position error) and recommendations that
wait for an operator's approval.

<video controls preload="metadata" poster="media/overview-poster.jpg" style="width:100%">
  <source src="media/nav-trust-c2-overview.mp4" type="video/mp4">
</video>

*One minute, captioned: the replay demo from a trusted fleet to an approved, gated command. Map
tiles are left out of this recording. The [three-minute demo](https://youtu.be/L7DrhOYMQ5A) shows
the live map.*

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
