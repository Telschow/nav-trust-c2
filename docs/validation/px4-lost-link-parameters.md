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
  runs and was on the ground about 45 s after the loss. It came down from 30 m in about 40 s
  (touchdown minus onset in the table), a rate close to `MPC_LAND_SPEED`.
- In all six outages of 4.0 to 4.1 s, the vehicle did not descend.
- These are different tests, so they do not bracket a threshold: a 4 s outage that ended without a
  reaction, and a loss that never ended with a reaction at about 5 s. A 5 s dead-reckoning limit
  (`EKF2_NOAID_TOUT`) would fit both. Fitting is not shown: the recordings carry no flight-mode
  events and there are no PX4 logs, so which mechanism acted is not established. "Blind land" is
  the repo's name for this reaction (`CLAUDE.md`); this note measures the descent and does not
  identify the mechanism.

## What this changes (proposals for the maintainer)

- **`CLAUDE.md` and CONOPS vignette A** say "a few seconds" and "the timing was not measured
  exactly". Measured: no reaction at 4 s, descent from about 5 s, touchdown about 45 s after the
  loss, in this simulator.
- **ADR 0004, "link lost, GNSS lost".** If both fail, the GNSS-driven descent would be expected
  to start about 5 s in, before PX4's data-link-loss action (10 s plus a 5 s hold). This is an
  inference: no recording has both faults, so issue 75's `link_and_gnss_loss` is the test.
- **ADR 0004, wait time.** The contingency wait time must be shorter than the 15 s before RTL
  starts, and arguably shorter than the 10 s before the hold.
- **Issue 74** (PX4 data-link-loss failsafe, the telemetry link in the glossary). Record
  `NAV_DLL_ACT` and `COM_DL_LOSS_T` in each lost-link recording's header, so the setting is
  evidence and not an assumption. Issue 74 should start from the table above.

## Limits

- The parameter values are read from source files. A stored parameter file or a later startup
  script could override a default. To confirm in a running vehicle, run `param show NAV_DLL_ACT`
  (and the others) in the SITL shell; no simulator was available for this note.
- Two long outages, one vehicle model, 10 m/s, 30 m altitude, PX4's own `gps off` failure model.
  Counts, not rates.
- `SYS_HAS_NUM_GNSS` and `COM_GNSSLOSS_ACT` were not found to be overridden. The recordings show
  one GNSS stream per vehicle (`gps_info`), so PX4's two-receiver check probably cannot act, but
  the Gazebo model's receiver count was not checked.

## Cutting the link in the simulator (issue 74)

`sim/link_cut.py` puts a small UDP relay between PX4 and the scripts for one vehicle and drops
datagrams on a schedule from a scenario file (`link_cut:` with `after`, `delay_s`, optional
`duration_s` and `direction`). MAVSDK presents itself to PX4 as a ground station, so a silent
MAVSDK link should be a lost link to PX4's data-link-loss failsafe.

- **Ports.** For instance 1 PX4 sends to 14541 from 14581; with a cut, the relay takes 14541 and
  the scripts listen on 14641 (`relay_ports`). Only `sim.record_run` is relayed.
- **Direction.** `both` drops everything, as the issue asks, but then MAVSDK's telemetry stops
  too: the recorder would not see PX4's mode change or the landing. `uplink` drops only what the
  scripts send to PX4, so PX4 loses its ground station while the recording keeps hearing the
  vehicle. The two baseline scenarios use `uplink` for that reason. Choose `both` for a run that
  models the backend's own view (issue 75).
- **Parameters.** On a run with a cut the recorder sets `NAV_DLL_ACT` and `COM_DL_LOSS_T`, reads
  them back and writes a `failsafe_params` event, so the setting is evidence in the recording.
  It also writes a `flight_mode` event on every mode change, plus `link_cut` and `link_restore`.
- **Scenarios.** `scenarios/lost_link/link_only.yaml` (healthy GNSS) and `link_and_frozen.yaml`
  (the frozen position of `stuck_position`, link cut 5 s later, no onboard monitor). They are in
  their own folder, so `make eval` ignores them until issue 75 adds recordings and a table.
- **Recording them** (simulator, about 6 to 7 minutes per run):
  `SCENARIO_DIR=scenarios/lost_link OUT_DIR=eval/lost_link/recordings sim/record_all.sh`, then
  `python -m eval.link_cut_timing` prints the mode changes and touchdown, in seconds after the
  cut, from the recordings.

What no test here shows, and a simulator run must: that PX4 really declares the data link lost
when only the relayed link goes quiet (PX4 has a second MAVLink instance for a ground station on
18571; nothing should be attached to it), that telemetry keeps flowing during an `uplink` cut,
and that the run ends when the vehicle lands. The contingency wait-time rule for issue 76
(wait shorter than `COM_DL_LOSS_T` plus the hold) should import `COM_DL_LOSS_T_S` from
`sim/failsafe_params.py`.
