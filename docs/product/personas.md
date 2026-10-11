# Personas

These are **hypotheses**, not research: no operator has been interviewed. The usability sessions (issue 16) are the first contact with real people, and they will test the operator persona only. Rewrite anything that does not match what you believe about these people.

## 1. Operator (controls 3 to 5 vehicles)

- **Goal.** Finish the survey safely and cover the area.
- **Pain.** Cannot see how good each vehicle's navigation is. Alarms arrive without reasons. When a
  vehicle's position is wrong, nothing on the screen says so.
- **What the console gives them.** A card per vehicle with a trust state shown as colour, icon and
  words; the reason in plain language; how far the position can be off (3 m, calibrated in
  simulation) and how close the vehicle is to being flagged; a decision queue that says what
  approving will do and when it expires; an activity log.
- **How we would know it helps.** Time to notice and time to decision, whether they understand
  what their decision did, and perceived workload. Not measured yet (`docs/usability/`).
- **Status.** Supported by the console. Tested on nobody.

## 2. Mission commander

- **Goal.** Know coverage and risk at a glance.
- **Pain.** No consolidated trust picture across vehicles.
- **What the console gives them.** A fleet summary in the header (how many vehicles are trusted,
  degraded or not trusted) and a map with the survey sectors coloured by the vehicle that owns them.
- **What it does not give them.** A coverage figure in the console, or a mission-level risk view. Area covered is
  measured offline, per run and for the fleet after a re-task (`eval/fleet/results.md`, M-04), but
  not shown in the console. **Partly supported.**

## 3. Maintainer and test engineer

- **Goal.** Reproduce and analyse incidents.
- **Pain.** No structured record of navigation events and decisions.
- **What they get.** An append-only audit log of every trust change, recommendation, decision and
  command outcome (SQLite); recordings with ground truth that replay through the trust engine in CI
  without a simulator; scenario files; a results table that CI regenerates and checks; a held-out
  validation procedure with its expectations written first.
- **Status.** Well supported. This is the persona the project serves best.

## What these personas do not cover

Anyone outside a simulated search-and-rescue or area-survey setting; people who supervise more than
five vehicles; anyone with a real flight authority to consider. The scope guardrails apply: no
weapons, targeting or effectors.
