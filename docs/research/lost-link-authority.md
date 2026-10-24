# Research: authority under lost link

First pass 2026-10-24, extended the same day with defence primary sources. All sources accessed 2026-10-24. Public, unclassified, non-weapon material only. Quotes are from the owner's page or file; anything not read from the owner is listed under gaps and not used.

## Question

What do public defence and uncrewed-systems practice say a vehicle may do on its own when the C2 link is lost (possibly with degraded navigation), and how is that authority granted, bounded, recorded and reconciled while a human stays on the loop?

## Short answer

- Every source read treats the lost-link action as decided before flight and run onboard: PX4 and ArduPilot parameters, the FAA/DoD air traffic procedure, SORA contingency procedures, the NASA study. This is option 2 in spirit. The autopilots as shipped are option 1. No source uses option 3.
- The US procedure that DoD air traffic facilities apply says the lost-link procedure is "programmed into the flight management system", is looked up from the airworthiness certificate or the authorisation, and is not decided at the time of loss. That is a pre-authorisation recorded in a document the controller can retrieve.
- PX4 does not catch a plausible but wrong position. Its "blind land" is a last-resort in the position controller that fires when the velocity estimate is not finite. It does not fire for a frozen fix. PX4's data-link action is `Disabled` by default, so the ADR's "PX4 data-link-loss failsafe" row holds only if the simulation sets it.
- After the link returns, ArduPilot stays in the failsafe mode, and PX4 Hold clears only on a mode change. Nothing replays old commands.
- Defence sources add little beyond the civil ones that could be read. DoDD 3000.09, the STANAGs, and Army and Air Force lost-link documents returned HTTP 403 and are not used.
- No public source describes how delegated authority is hashed, bounded in age, or audited. ADR 0004's mechanism has no public precedent found.

## Findings

### 1. Autopilot failsafes: what runs with no operator

- PX4 data link loss fires when the connection to the last MAVLink ground station is lost. `COM_DL_LOSS_T` is the threshold: "After this amount of seconds without datalink, the GCS connection lost mode triggers", default 10, min 5, max 300. `NAV_DLL_ACT` selects the action, default 0 (Disabled), with Hold, Return, Land, Terminate and Disarm as the other values. [PX4 commander_params.yaml, main](https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/src/modules/commander/commander_params.yaml); [PX4 safety docs](https://docs.px4.io/main/en/config/safety.html), both 2026-10-24. These are values on `main`, not on the repo's pinned commit.
- `COM_DLL_EXCEPT` (default 0) lists modes in which GCS loss is ignored. Source: the failsafe is also skipped when the intended mode is Land or Precision Land, or the vehicle is disarmed. [failsafe.cpp, main](https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/src/modules/commander/failsafe/failsafe.cpp), 2026-10-24.
- PX4 orders actions "in increasing severity" and "If multiple failsafes are triggered, the more severe action is taken." By default most failsafes enter Hold "for COM_FAIL_ACT_T seconds" first; `COM_FAIL_ACT_T` default 5.0 s, range 0 to 25. [PX4 safety docs](https://docs.px4.io/main/en/config/safety.html); [yaml](https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/src/modules/commander/commander_params.yaml), 2026-10-24. Whether that hold applies to the data-link failsafe was not confirmed.
- PX4 position loss fires "if the position estimate becomes invalid", falling back Return, Land, then Descend. `COM_POS_FS_ACT` default 0 (Descend). Low accuracy (`COM_POS_FS_EPH`, default 5.0 m) uses `COM_POS_LOW_ACT`, default 3 (Return), and "is only executed if the vehicle is in auto mission or auto loiter mode". Same sources. A frozen fix that stays valid and accurate triggers neither, matching ADR 0003.
- PX4 GNSS loss: `COM_GNSSLOSS_ACT` default 0 (Warning); 1 Return, 2 Land, 3 Terminate. The docs tie detection to fix count and two-receiver divergence. `SYS_HAS_NUM_GNSS` is referenced there but its default was not found in the file read. Same sources.
- "Blind land" is confirmed in PX4 source. In the multicopter position controller, if the horizontal velocity estimate is not finite the failsafe setpoint is "descend with land speed since we can't stop" at `MPC_LAND_SPEED`, with the warning "Failsafe: blind land". If the vertical velocity is invalid it does an "emergency descend". [MulticopterPositionControl.cpp, main](https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/src/modules/mc_pos_control/MulticopterPositionControl.cpp), 2026-10-24. The only timeout in that file is a 200 ms fallback to the last setpoint. The file does not say how long a GNSS outage lasts before the velocity estimate goes invalid; that comes from the estimator and is not shown in the PX4 docs read. The CLAUDE.md figure ("a few seconds") is therefore not confirmed from an owner source.
- PX4 `NAV_RCL_ACT` text: "If Hold cannot be entered (e.g. without a valid position estimate), the normal failsafe takes over". Same yaml.
- PX4 clear conditions in source: Hold, Return and Land for GCS loss and GNSS loss clear on mode change or disarm; Terminate never clears; low-accuracy actions clear when the condition clears. [failsafe.cpp](https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/src/modules/commander/failsafe/failsafe.cpp), 2026-10-24. `checkFailsafe()` was not in the fetched text, so the exact return-of-link behaviour is partly unverified.
- ArduPilot GCS failsafe fires with no heartbeat for `FS_GCS_TIMEOUT` (default 5 s); actions include RTL (Land if GPS unusable), SmartRTL, Land, DO_LAND_START, Brake, or continue the mission via `FS_OPTIONS`. It never fires if no GCS has ever connected. "If the GCS reconnects, the copter stays in the failsafe mode." [ArduPilot GCS failsafe](https://ardupilot.org/copter/docs/gcs-failsafe.html), 2026-10-24.
- MAVLink leaves heartbeat-loss behaviour undefined; it suggests 1 Hz and "four or five messages are not received". [MAVLink heartbeat service](https://mavlink.io/en/services/heartbeat.html), 2026-10-24.

### 2. Pre-planned lost-link procedures

- SORA 2.5 main body (JARUS, 13.05.2024): abnormal situations call for contingency procedures that "should return the operation to a controlled state and allow the return to using standard operating procedures or allow the safe cessation of the flight". Loss of control is where the outcome "highly relies on providence" or "could not be handled by a contingency procedure"; emergency procedures follow, and "may be supported by automated features of the UAS". [SORA 2.5 main body, sections 2.3.1 and 2.3.2](http://jarus-rpas.org/wp-content/uploads/2024/06/SORA-v2.5-Main-Body-Release-JAR_doc_25.pdf), 2026-10-24.
- SORA 2.5 Annex I defines lost link as "loss of command and control link contact with the UA such that the remote pilot can no longer intervene in the UA's flight control". [Annex I](http://jarus-rpas.org/wp-content/uploads/2024/06/SORA-v2.5-Annex-I-Release.JAR_doc_30pdf.pdf), 2026-10-24.
- EASA means of compliance for OSO 6 (SAIL III, Issue 1, 18 December 2023, marked "Proposed"): link degradation is conveyed to the remote pilot; "When a certain level of degraded conditions ... to be defined by the applicant, is reached, the C2 Link should be declared lost. The operator should have procedures in place to manage the loss". One example: on C2 loss the mission is interrupted by a return-to-home mode, and a footnote says return home with no pilot monitoring "needs to be shared before the mission(s) with all other actors involved". [EASA MOC to OSO#6-01](https://www.easa.europa.eu/en/downloads/139100/en), 2026-10-24.
- EASA SORA slides (6 March 2023): contingency volume depends on "reaction time" and "time to execute contingency manoeuvres". [EASA slides](https://www.easa.europa.eu/it/downloads/137614/en), 2026-10-24.
- FAA notice N JO 7110.724 (effective 11 October 2016, cancellation date 27 April 2017, so a superseded text), applying to "Department of Defense (DOD) air traffic facilities": "Lost link procedures are programmed into the flight management system and associated with the flight plan being flown." The controller determines the procedure "as outlined in the Special Airworthiness Certificate or Certificate of Waiver or Authorization (COA)". The procedure "should, at a minimum, include lost link route of flight, lost link orbit points, lost link altitudes, communications procedures and preplanned flight termination points". It defines lost link as loss of either uplink or downlink, and "In the event positive link cannot be established, flight termination must be implemented." It records the event by advising the Front Line Manager "so the event can be documented". [FAA N JO 7110.724](https://www.faa.gov/documentLibrary/media/Notice/N_JO_7110.724_5-2-9_UAS_Lost_Link.pdf), 2026-10-24. Note that the notice treats a downlink-only fault as lost link; the repo models a symmetric link.
- NASA Ames: lost-link procedures are "a set of rules and/or route(s) that would be programmed into the UA" and run automatically "after internal systems confirm the loss of link". Design aspects: predictability, robustness ("without being over-prescriptive"), survivability. The event has a decision time, a declared state (T0), a first segment continuing the route, a second segment, re-establishment (T2) and recovery (T3). After T2, "the RP and ATC need to coordinate actions to return the UA to its nominal flight plan". ICAO RPASP-16/WP-15 decision times of 30 s (terminal) and 240 s (en route) are for large crewed-airspace aircraft and do not transfer to a small SAR drone. [Sakakeeny et al., NTRS 20240007906](https://ntrs.nasa.gov/api/citations/20240007906/downloads/Initial_Assessment_of_LC2L_Procedures.pdf), 2026-10-24.
- UK CAA CAP3154 (September 2025 consultation): its Lost C2 Link chapter only says a separate consultation is planned; examples say a review would define how the pilot knows the link is lost and the wait before return home. [CAP3154](https://www.caa.co.uk/publication/download/26093), 2026-10-24. It is explicitly not acceptable means of compliance.

### 3. Delegation, recording and audit

- In the US procedure the delegation is the approved authorisation itself (certificate or COA), looked up at the time of loss. Event documentation is by the controller. No revocation in flight is described. [FAA N JO 7110.724](https://www.faa.gov/documentLibrary/media/Notice/N_JO_7110.724_5-2-9_UAS_Lost_Link.pdf), 2026-10-24.
- CAP3154 proposal 1.2: "A periodic log should be maintained showing which connections are active and the status of all connections in the C2 Link." This is link-performance logging, not an authority record. [CAP3154](https://www.caa.co.uk/publication/download/26093), 2026-10-24.
- No source read describes integrity protection, hashing or maximum age of a delegated authority.

## What defence sources add beyond civil ones

Little that could be read. The one defence-applicable document read, the FAA notice for DoD air traffic facilities, is civil airspace procedure and shows the same pre-programmed, pre-authorised pattern. Everything that would carry defence-specific content was not readable: DoDD 3000.09 (HTTP 403), NATO STANAG 4586 Edition 4 (HTTP 403 from nso.nato.int), STANAG 4671 or AEP-4671 (not located), US Army sUAS airspace handbook, DAFMAN 11-501 and AFMAN 11-202V3 (HTTP 403). Search snippets suggest the Army handbook recommends preprogrammed return-to-home and lost-link reports, and the Air Force documents require lost-link logging and a link status display, but those are secondary relays and are not used as evidence. No UK MoD or DSTAN lost-link text was found in public search. Conclusion: no defence-specific finding is claimed; these are open gaps, not evidence of absence.

## Comparison with ADR 0004

| Option | What the sources do |
|---|---|
| 1. PX4 failsafes only | Shipped default. But PX4's data-link action defaults to Disabled, blind land fires on an invalid velocity estimate and not on a frozen fix, and low-accuracy actions apply only in auto mission or loiter. No source gives a mechanism for a plausible wrong position. |
| 2. Pre-authorised contingencies | Matches SORA contingency procedures, the FAA/DoD lost-link procedure tied to the authorisation, and NASA. Authority is granted before flight in a retrievable document. Public sources are silent on an onboard monitor that overrides an autopilot action. |
| 3. Wait for the operator | No source uses it. FAA text: "In the event positive link cannot be established, flight termination must be implemented", i.e. the vehicle acts without the operator. |

Review points in the ADR:

- STALE versus NO_LINK separate: consistent with EASA ("declared lost" at a level the applicant defines) and NASA (a decision time before the state is declared).
- NO_LINK as telemetry silence only: the FAA text counts uplink-only or downlink-only failure as lost link. The repo's symmetric assumption is stated and out of scope; the sources do not support it as general.
- Contingency as advance approval: the same shape as a COA or SORA authorisation. The CLAUDE.md wording change remains a project matter.
- LAND only: SORA examples also list return home; EASA's note says unmonitored return home must be shared in advance with others. LAND-only is narrower than practice and is supported by ADR 0003, not contradicted.
- Wait shorter than `COM_DL_LOSS_T`: default is 10 s (min 5), and PX4 may add a `COM_FAIL_ACT_T` Hold (default 5.0 s) before the action. The comparison should be with the full time to PX4's action, and `NAV_DLL_ACT` must be set for PX4 to act at all.
- Approve once, id and hash, max age, no revocation: no public analogue. The FAA/COA model also has no in-flight revocation.

## Gaps and not verified

- DoDD 3000.09, NATO STANAG 4586 Ed. 4, STANAG 4671 and AEP-4671, STANAG 4703: HTTP 403 or not located. Not used. The 3000.09 phrase "appropriate levels of human judgment" is only seen in a search snippet.
- Army sUAS handbook, DAFMAN 11-501, AFMAN 11-202V3, Navy and MIL-HDBK-516 or DoD UAS roadmap text: 403 or not found.
- UK MoD / DSTAN lost-link text: none found.
- ICAO Doc 10019 and the ICAO working paper: HTTP 403 or certificate errors. Only the NASA description of the working paper was read.
- RTCA DO-400 and DO-365: paywalled; the RTCA page had no scope text. DO-400 is known here only through the NASA paper.
- FAA Part 108 text: not read. FAA JO 7110.65 current paragraph: only the 2016 notice read.
- PX4: values are from `main`, not the pinned commit; `SYS_HAS_NUM_GNSS` default not found; time from GNSS outage to invalid velocity estimate not found; return-of-link clearing in `checkFailsafe()` not read; whether `COM_FAIL_ACT_T` applies to data link loss not confirmed.
- No public source found on audit of delegated authority, onboard override of an autopilot failsafe, or plausibility monitoring as a failsafe trigger.

## Suggestions for the maintainer (proposals, not decisions)

1. Check what the simulation sets for `NAV_DLL_ACT`, `COM_DL_LOSS_T`, `COM_FAIL_ACT_T`, `COM_GNSSLOSS_ACT` at the pinned commit. If `NAV_DLL_ACT` is the default (Disabled), the matrix row "Link lost, GNSS healthy: PX4 data-link-loss failsafe" is wrong as written.
2. Reword the "Link lost, GNSS lost" row: blind land is a position-controller reaction to an invalid velocity estimate, not a configured failsafe. Measure the outage-to-landing time in the repo's recordings rather than quoting "a few seconds".
3. Express the wait-time constraint against the full time to PX4's action (loss time plus any Hold), and tie the contingency's own decision time and execution time to figures measured in issue 81, as SORA and NASA frame them.
4. Consider whether a downlink-only or uplink-only fault belongs in the "out of scope" list with the reason, since FAA text treats either as lost link.
5. State in the ADR that the contingency is the equivalent of an authorisation looked up at the time of loss (COA or SORA pattern), and that its integrity hash and maximum age have no public precedent found.
6. Say what happens after LAND when the link returns: both autopilots stay in the failsafe state until a human acts, which fits "never replay stale decisions".
7. Obtain DoDD 3000.09, STANAG 4586/4671/4703, DO-400 and ICAO Doc 10019 from the owner by another route (library or the maintainer's access) before citing them.
