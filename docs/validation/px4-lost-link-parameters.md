# PX4 lost-link parameters and the time to a GNSS-loss descent

Prepared by Claude on 2026-10-24 for issue 91, from PX4's source at the commit the simulator is
pinned to (`a427a2e`, `sim/docker/Dockerfile`) and from the committed recordings. Simulation only.

## Parameters at the pinned commit

Read from PX4's files at that commit, not from a running vehicle (see the limits below).

| Parameter | Value in the simulated vehicle | Where it comes from |
|---|---|---|
| `NAV_DLL_ACT` | 2, Return mode | `param set-default` in `ROMFS/px4fmu_common/init.d-posix/airframes/4001_gz_x500`, the airframe `sim/docker/run_sitl.sh` starts. The global default is 0, Disabled |
| `COM_DL_LOSS_T` | 10 s (range 5 to 300) | global default in `docs/public/config/failsafe/parameters.json` |
| `COM_FAIL_ACT_T` | 5.0 s | global default, same file. PX4 holds this long before it enters a failsafe |
| `COM_GNSSLOSS_ACT` | 0, Warning | global default, same file |
| `SYS_HAS_NUM_GNSS` | 0, no receiver count required | global default, same file |
| `EKF2_NOAID_TOUT` | 5 s | global default, same file: maximum inertial dead-reckoning time |
| `MPC_LAND_SPEED` | 0.7 m/s | global default, same file |

Neither the airframe file nor `rc.mc_defaults` sets any of these except `NAV_DLL_ACT`. The mode
numbers are from `src/modules/commander/failsafe/failsafe.h` at the same commit.

So at this commit the simulated vehicles already return home on a lost data link, after
`COM_DL_LOSS_T` plus the `COM_FAIL_ACT_T` hold, about 15 s. Issue 74 needs no parameter change to
get RTL; it needs a link-cut hook and a recording that shows the setting.

## Time from GNSS loss to descent, from the recordings

`python -m eval.blind_land` measures it from ground-truth altitude (`eval/blind_land.py`, tested
in `tests/test_blind_land.py`). Rows are GNSS-off outages; each short-outage run has two zones.

| Recording | GNSS back after (s) | Descended | Onset (s) | Touchdown (s) |
|---|---|---|---|---|
| long_outage-1 | never | yes | 5.2 | 45.2 |
| long_outage-2 | never | yes | 5.5 | 45.0 |
| short_outage-1 (two zones) | 4.0 | no | none | none |
| short_outage-2 (two zones) | 4.0 | no | none | none |
| short_outage-3 (two zones) | 4.0 and 4.1 | no | none | none |

- With GNSS gone for good, the vehicle began a steady descent about 5 s after the loss in 2 of 2
  runs, at about 0.74 m/s, and was on the ground about 45 s after the loss.
- In 6 of 6 outages of 4 s, the vehicle did not descend.
- So the reaction starts between 4 s (no reaction, 6 of 6) and 5.2 s (reaction, 2 of 2). That is
  consistent with `EKF2_NOAID_TOUT` (5 s), and the descent rate is close to `MPC_LAND_SPEED`
  (0.7 m/s). Consistent is not shown: the recordings carry no flight-mode events and there are no
  PX4 logs, so which mechanism acted is not established.

## What this changes (proposals for the maintainer)

- **`CLAUDE.md` and CONOPS vignette A** say "a few seconds" and "the timing was not measured
  exactly". Measured: no reaction at 4 s, descent from about 5 s, touchdown about 45 s after the
  loss, in this simulator.
- **ADR 0004, "link lost, GNSS lost".** The GNSS-driven descent starts about 5 s in, before the
  data-link-loss failsafe can act (10 s plus a 5 s hold). In that row the vehicle is already
  landing when the link failsafe would start.
- **ADR 0004, wait time.** The contingency wait time must be shorter than the 15 s before RTL
  starts, and arguably shorter than the 10 s before the hold.
- **Issue 74.** Record `NAV_DLL_ACT` and `COM_DL_LOSS_T` in each lost-link recording's header, so
  the setting is evidence and not an assumption.

## Limits

- The parameter values are read from source files. A stored parameter file or a later startup
  script could override a default. To confirm in a running vehicle, run `param show NAV_DLL_ACT`
  (and the others) in the SITL shell; no simulator was available for this note.
- Two long outages, one vehicle model, 10 m/s, 30 m altitude, PX4's own `gps off` failure model.
  Counts, not rates.
- `SYS_HAS_NUM_GNSS` and `COM_GNSSLOSS_ACT` were not found to be overridden. The recordings show
  one GNSS stream per vehicle (`gps_info`), so PX4's two-receiver check probably cannot act, but
  the Gazebo model's receiver count was not checked.
