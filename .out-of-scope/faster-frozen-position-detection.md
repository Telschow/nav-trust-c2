# Faster frozen-position detection

This project does not tune the consistency detector to bring the frozen-position time to detect
under the 3 s proposal.

## Why this is out of scope

A frozen position takes 3.0 to 4.5 s to detect (M-01, R7), above the 3 s proposal. M-01 is
reported as `partial`, per fault type, and that honest result stands. Trying for a faster detector
needs a fresh held-out set (the current one is used up for this version, R3), about three days of
simulator runs, and a risk of more false alerts in the nominal runs, which are at zero today. The
gain is a number closer to a target that is itself a proposal. Not worth the held-out set now.

If the 3 s target becomes a requirement, delete this file and open a new issue.

## Prior requests

- #78: "Tune frozen-position detection against a fresh held-out set (M-01, R7)"
