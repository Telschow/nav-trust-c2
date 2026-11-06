# Gradual GNSS drift

This project does not detect a slow, gradual position offset, and does not plan to build the
simulator injection that a detector would need.

## Why this is out of scope

`BIAS_DRIFT` is a reserved reason code in `navtrust/types.py` that is never produced. PX4's GPS
failure model on the pinned commit offers `off`, `stuck` and `wrong` only, so there is no gradual
fault to develop a detector against, and no ground truth for what such a detector should find.
Building one means a custom injection shim in the simulator, then a detector, then a held-out
recording: a new milestone (M6), not a spike. The project's claims rest on lost link and frozen
position (ADR 0003, ADR 0004). The README says what is not shown, and a slow drift is on that list.

If a future PX4 release adds a drift fault, or the project takes on M6, delete this file and open
a new issue.

## Prior requests

- #83: "[M6] Feasibility spike: can the simulator inject gradual GNSS drift?"
