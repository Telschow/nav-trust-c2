# Research: authority under lost link

Prepared 2026-10-24 for ADR 0004. All sources accessed 2026-10-24. Public, unclassified, non-weapon material only. Quotes are from the owner's page or file; anything not fetched is listed under gaps.

## Question

What do public defence and uncrewed-systems practice say a vehicle may do on its own when the C2 link is lost (possibly with degraded navigation), and how is that authority granted, bounded, recorded and reconciled while a human stays on the loop?

## Short answer

- Every source reached treats lost-link behaviour as something decided before flight and carried out onboard, not something the operator decides at the moment of loss. This is option 2 in spirit; PX4 and ArduPilot are option 1 as shipped.
- Autopilot failsafes are blunt: a timer, then one configured action (hold, return, land, disarm, terminate). They key on link silence or position-estimate validity, not on position plausibility.
- Aviation guidance (EASA/JARUS SORA, ICAO, RTCA, NASA) sizes the pre-planned action by a decision time plus time to execute, and stresses predictability to others over cleverness.
- After recovery, both autopilots stay in the failsafe state; the operator takes the vehicle back explicitly. Nothing replays old commands.
- Recording and auditing of delegated authority is thinly covered in public sources. The only direct hit is a CAA proposal for a periodic link-status log. ADR 0004's id-and-hash approval row has no public precedent to copy, and none to contradict.
- Not verified: DoDD 3000.09 text, RTCA DO-400 text, STANAG documents, PX4 "blind land" behaviour.

## Findings

### 1. Autopilot failsafes: what runs with no operator

- PX4 data link loss fires "if the connection to the last MAVLink ground station like QGroundControl is lost". `COM_DL_LOSS_T` is the time after loss before it triggers; `NAV_DLL_ACT` selects "Disabled, Hold mode, Return mode, Land mode, Disarm, Terminate". [PX4 safety docs](https://docs.px4.io/main/en/config/safety.html), 2026-10-24.
- PX4 orders failsafe actions "in increasing severity" (warning, hold, return, land, disarm, terminate) and "If multiple failsafes are triggered, the more severe action is taken." Same page. This supports ADR 0004's rule that the contingency's LAND overrides RTL, but only if the project's monitor is the thing raising the severity; PX4 itself does not know the position is inconsistent.
- PX4 position loss fires when "the position estimate becomes invalid", with fallback Return, then Land, then Descend if no position estimate exists. Same page. A frozen but "valid" fix does not meet this, which matches ADR 0003.
- PX4 v1.18 adds a GNSS check failsafe (fix count below `SYS_HAS_NUM_GNSS`, or divergence between two receivers) with `COM_GNSSLOSS_ACT`, default warning only. Same page. Needs two receivers; the repo's simulated vehicle should be checked for this (see suggestions).
- PX4 source: GCS-loss failsafe is skipped when the user's intended mode is Land or Precision Land, or the vehicle is disarmed; Hold clears on mode change or disarm, Terminate never clears. [failsafe.cpp, main](https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/src/modules/commander/failsafe/failsafe.cpp), 2026-10-24. No explicit return-of-link clearing for the GCS failsafe appeared in that file; `checkFailsafe()` was not in the fetched text. Treat reconnection behaviour in PX4 as partly unverified.
- ArduPilot GCS failsafe fires when no heartbeat arrives for `FS_GCS_TIMEOUT` seconds (default 5). Actions: RTL (Land if GPS unusable), SmartRTL, Land, DO_LAND_START mission sequence, Brake, or continue the mission via `FS_OPTIONS`. It never fires if no GCS has ever connected. [ArduPilot GCS failsafe](https://ardupilot.org/copter/docs/gcs-failsafe.html), 2026-10-24.
- ArduPilot after recovery: "If the GCS reconnects, the copter stays in the failsafe mode"; the pilot must change mode. Same page.
- MAVLink does not define the response to heartbeat loss. It suggests 1 Hz heartbeats and treating a peer as disconnected after "four or five messages are not received", and says the rate and tolerance are "not defined by MAVLink". [MAVLink heartbeat service](https://mavlink.io/en/services/heartbeat.html), 2026-10-24. So `NO_LINK` timing is the project's to define.

### 2. Pre-planned lost-link procedures in aviation

- EASA SORA 2.5 training slides separate normal operation, an abnormal situation handled by "contingency procedures (return home, manual control, land on a pre-determined site etc.)", and an emergency (loss of control of the operation) handled by emergency procedures ("land asap or activation of FTS") plus an emergency response plan. [EASA SORA slides, dated 6 March 2023](https://www.easa.europa.eu/it/downloads/137614/en), 2026-10-24. A pre-approved LAND on a detected fault fits the contingency tier; the slides are a presentation, not the final text.
- Same slides: the contingency volume depends on "reaction time" and "time to execute contingency manoeuvres". The wait time before acting is therefore part of the safety case, which bears on the ADR's wait-time versus `COM_DL_LOSS_T` point.
- NASA Ames describes lost C2 link procedures as "a set of rules and/or route(s) that would be programmed into the UA", executed automatically "after internal systems confirm the loss of link". It names three design aspects: predictability, robustness ("without being over-prescriptive"), and survivability. [Sakakeeny et al., NTRS 20240007906](https://ntrs.nasa.gov/api/citations/20240007906/downloads/Initial_Assessment_of_LC2L_Procedures.pdf), 2026-10-24.
- Same paper: it breaks the event into a decision time, a declared lost state (T0), a first segment that continues the current route so others can react, a second segment, link re-establishment (T2) and recovery to normal (T3). It reports ICAO RPASP-16/WP-15 decision times of 30 s in terminal and 240 s en route airspace. These are manned-airspace values for large aircraft and are not transferable to a small SAR drone.
- Same paper: after the link returns, "the RP and ATC need to coordinate actions to return the UA to its nominal flight plan". Reconnection is a coordinated, human step.
- RTCA DO-400 (2023) is described in the NASA paper as guidance by phase of flight with actions for the UA, remote pilot and ATC. The standard itself is paywalled and was not read.
- UK CAA CAP3154 (consultation, September 2025) has a Lost C2 Link chapter that only says a separate consultation is planned. Its use cases say a formal review would define how the pilot knows the link is lost and how long the system waits "before the UA returns to home (Lost C2 Link timer)". One example specifies "RTH upon link loss". [CAP3154](https://www.caa.co.uk/publication/download/26093), 2026-10-24. It states it is not acceptable means of compliance.
- FAA: proposed Part 108 is reported to require lost-link procedures (section 108.165(d)). The only evidence found was secondary search summaries, so no claim is made; the Federal Register text was not read.

### 3. Delegation, pre-authorisation and recording

- The aviation sources above treat the lost-link action as part of the approved operation (the SORA application, the flight plan, the programmed route), which is pre-authorisation by construction. None of the fetched documents describes revoking it in flight.
- CAP3154 proposal 1.2: "A periodic log should be maintained showing which connections are active and the status of all connections in the C2 Link". [CAP3154](https://www.caa.co.uk/publication/download/26093), 2026-10-24. This is link-performance logging for SORA OSO 6, not an authority record.
- No fetched source describes how delegated authority is cryptographically bound, hashed or audited. The project's design here is its own.
- DoD Directive 3000.09 (2023) is the usual cite for "appropriate levels of human judgment". Its PDF returned HTTP 403 and was not read; a search snippet quoted the phrase but that is a secondary relay and is not used as evidence here.

## Comparison with ADR 0004

| Option | What the sources do |
|---|---|
| 1. PX4 failsafes only | This is the shipped default in PX4 and ArduPilot, and in aviation a pre-programmed action is the norm. The sources give no mechanism for catching a plausible-but-wrong position. PX4's GNSS check needs two receivers. |
| 2. Pre-authorised contingencies | Matches the contingency tier of SORA and the programmed lost-link procedures in NASA/ICAO/RTCA. The authority is granted in the approved operation before flight. Public sources are silent on a project-specific onboard monitor that overrides the autopilot's action. |
| 3. Wait for the operator | No source reached uses this as the lost-link policy. All assume the vehicle acts without the link. NASA treats the loss as a state where the pilot "will be unable to upload data". |

Review points in the ADR:

- STALE versus NO_LINK separate: consistent with NASA's view that degradation is gradual and "loss" is a declared state after a decision time. MAVLink leaves the timeout to the integrator.
- NO_LINK as telemetry silence only: ArduPilot and PX4 also key on missing heartbeat from the GCS, a one-way observation. The sources do not discuss asymmetric links.
- Contingency as advance approval: aviation practice supports pre-approval of the lost-link action. The CLAUDE.md wording change is a project matter.
- LAND only: SORA lists land at a predetermined site as one contingency, return home as another. The aviation default is return or land, so limiting to LAND is narrower than practice, justified by ADR 0003 and not contradicted by the sources.
- Wait time shorter than `COM_DL_LOSS_T`: PX4 acts at `COM_DL_LOSS_T` with `NAV_DLL_ACT`. The ordering requirement is correct in principle. Also relevant: PX4 skips the data-link failsafe when the intended mode is already Land.
- Approve once, id and hash, max age, no revocation: no public analogue found. NASA's T0 to T3 sequence shows reconciliation as a human step, which fits "never replay stale decisions".

## Gaps and not verified

- DoDD 3000.09, STANAG 4586/4671/4703, JARUS SORA 2.5 main body, ICAO Doc 10019, RTCA DO-400, FAA Part 108 text: not fetched (HTTP 403, certificate error, paywall or not located). Nothing from them is asserted.
- PX4 parameter defaults for `COM_DL_LOSS_T`, `NAV_DLL_ACT`, `COM_GNSSLOSS_ACT`: the parameter reference page was too large to reach them and the Commander yaml fetch did not contain them. Read them from the pinned commit before quoting numbers.
- PX4 "blind land" (GNSS outage) is cited in CLAUDE.md but was not found in the safety docs text read. Verify in the pinned source.
- PX4 behaviour when the GCS link returns during a data-link failsafe: partly unverified (see section 1).
- No public source found on audit of delegated authority, onboard override of an autopilot failsafe, or position-plausibility monitoring as a failsafe trigger.
- SORA slides are 2023 presentation material, not the published standard.

## Suggestions for the maintainer (proposals, not decisions)

1. Read `COM_DL_LOSS_T`, `NAV_DLL_ACT`, and the clear conditions in the pinned PX4 commit, and put the numbers into the ADR with the commit id.
2. Check whether the simulated vehicle has two GNSS receivers; if not, PX4's GNSS check failsafe is not an alternative to the contingency and the ADR can say so.
3. State the contingency's decision time and time to execute explicitly, as SORA and NASA do, and tie them to a measured figure from issue 81 rather than the aviation values.
4. Say what the vehicle does after LAND completes and the link returns: PX4 and ArduPilot stay in the failsafe state until the operator changes mode, which matches "never replay stale decisions".
5. Consider recording link status periodically, not only at contingency use, to match the CAA's log proposal in a different domain.
6. Note in the ADR that the "approve once, hash, no revocation" mechanism is project-specific, with no public precedent found.
7. Obtain DoDD 3000.09, DO-400 and the SORA 2.5 main body from the owner before citing them.
