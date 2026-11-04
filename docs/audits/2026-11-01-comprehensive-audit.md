# Comprehensive audit, 2026-11-01

## 1. Commit and scope

- Commit: `56e6aee9fbaad86ea473a26a1cd19fc94bf0d817` (`main`, merge of PR #155). Working tree clean.
- Scope: trust engine, C2 backend, policy gate, audit log, onboard monitor, console, scenarios,
  eval, docs, CI and supply chain. Read-only: no code changed, no simulator run, held-out data
  not touched.
- Method: an independent source audit with executed probes against the backend (a throwaway
  script, not committed), plus a lead review that re-read the P2 code paths and the issue backlog.
  Part of the work was done by AI agents (Claude Code); every claim cites file and line.

## 2. Executive summary

The central safety claim holds. No code path sends a vehicle command around the policy gate: the
gate executes once, only for an approved decision, and audits every outcome; an unacknowledged
command is audited, not resent; approvals live in memory and cannot be replayed after a restart;
experiment scripts that bypass the gate are labelled as such; the onboard monitor only ever lands
and only when all ADR 0004 conditions hold. The trust engine never sees ground truth. The
held-out validation was handled honestly.

The gaps (all P2 or lower) are in what can be put in front of the operator (`POST /recommendations`
accepts any recommendation, #157), what the backend accepts from a vehicle (an onboard report is
checked for policy hash but not policy scope, #158), and what the audit log can prove after a
restart (#159). The ADR 0004 record chain from operator approval to vehicle is not wired end to
end (#76).

## 3. Readiness

| Dimension | Assessment |
|---|---|
| Technical correctness | Strong on the gate and trust engine; one likely reason-precedence issue (#160, needs an ADR 0001 decision). |
| Architecture | Clean layering (`navtrust/` pure, `c2/` domain, `sim/` adapters). Authority logic (proposal, decision, execution, provenance) is spread across hub, gate, server and recommender. |
| Experimental validity | Pre-declared held-out set, 7 of 8 expectations met and the miss reported. Coverage figures rest on correlated 2 Hz samples (NTC-18). |
| Tests and CI | `make check` green with CI extras (532 passed, 8 skipped); console 162 tests; one test needs the `sim` extra unannounced. |
| Security | Loopback binding, same-origin and anti-rebinding checks, `yaml.safe_load`, no pickle, no secrets. No authentication by design (documented). `ci.yml` lacks `permissions`; actions pinned by tag. |
| Product maturity | Strongest of the three: PRFAQ, CONOPS, requirements, ICD, ADRs, risk log, milestones. |
| Documentation | Very good; README numbers typed by hand (they match today); "not built" wording lags the onboard code. |
| Usability | Honest: the first sessions did not support an unaided decision; redesigned; not re-tested (#82, #16). |
| Visual quality | Real demo video, screenshots and GIF exist; README first screen does not show them; no vertical cut. |
| Portfolio readiness | High. The human-authority boundary is the most legible story in the portfolio. |

## 4. Subsystem inventory

Appendix section (b).

## 5. Strengths worth preserving

Appendix section (c) and the "Not a defect" entries NTC-19 to NTC-24.

## 6 to 10. Findings register

| ID | Sev | Class | Finding | Issue |
|---|---|---|---|---|
| NTC-01 | P2 | Confirmed gap | `POST /recommendations` lets a local client propose any command, TTL and vehicle; not in ICD; source not audited | #157 |
| NTC-02 | P2 | Confirmed defect | Onboard action report accepted without checking it is within the cited policy | #158 |
| NTC-03 | P2 | Confirmed gap | Audit log cannot tie command to approval across restarts (ids and clock restart) | #159 |
| NTC-04 | P2 | Confirmed gap (documented) | ADR 0004 record chain not wired; only an experiment approval reaches a vehicle; no mission binding | #76 (comment) |
| NTC-05 | P2 | Likely issue | DEGRADED fix plus inconsistency gives RED with reason GNSS_LOSS, so no LAND is recommended | #160 (decision) |
| NTC-06 | P2 | Confirmed defect | Onboard runner loses a report on POST failure; logs the action before `land()` returns | #158 |
| NTC-07 | P2 | Likely issue | 5 s acknowledgement timeout against measured re-task times up to 4.7 s | #77 (comment) |
| NTC-08 | P3 | Confirmed gap | Sector moves not re-checked at execution time | none (low risk, note for #157 design) |
| NTC-09 | P3 | Confirmed gap | Console signs decisions as "operator" by default | none (usability round #82 should decide) |
| NTC-10 | P3 | Confirmed gap | Command outcomes not published on the WebSocket | #161 |
| NTC-11 | P3 | Confirmed gap | Confirm dialog stays open after expiry or a decision elsewhere | #161 |
| NTC-12 | P3 | Likely issue | Dialog without focus trap; countdown inside a live region | #119 (comment) |
| NTC-13 | P3 | Confirmed defect | NaN in a trust report breaks every later console snapshot | #161 |
| NTC-14 | P3 | Confirmed defect | One test needs the `sim` extra without saying so | #163 |
| NTC-15 | P3 | Confirmed gap | `ci.yml` has no `permissions`; tag-pinned actions; base image and Gazebo float | #163 |
| NTC-16 | P3 | Confirmed gap | README and ICD say "not built" for code that exists | #162 |
| NTC-17 | P3 | Confirmed gap | README headline numbers typed, unchecked | #162 |
| NTC-18 | P3 | Strategic opportunity | Report coverage per flight and per speed with an interval | none yet; fold into the next calibration change |
| NTC-19 to NTC-24 | n/a | Not a defect | Approved command still dispatched during NO_LINK (by design, console warns); experiment harness bypasses labelled; gate idempotent; same-origin policy adequate on loopback; ground truth isolated; usability audit DB claim checked | none |

Severity rationale: C2-01 is not violated by any finding, so none is P0 or P1. NTC-01 and NTC-02
rank first because they weaken what the audit log can prove about authority, which is the
product's core claim.

## 11. Documentation inconsistencies

NTC-16, NTC-17; `docs/how-this-was-built.md` facts table is a 2026-10-10 snapshot and says so.

## 12. Product and usability

The product framing is the strongest in the portfolio. The open question that matters most is
the human one: the usability round showed operators did not act on the decision unaided, the
console was redesigned (#110 spec, #111 to #120 done), and that redesign has not been tested
(#82). Until it is, the README must keep saying so.

## 13. Visual and portfolio presentation

Existing: YouTube demo, `docs/media/nav-trust-c2-overview.mp4`, poster, `docs/screenshots/`.
Gap: README first screen shows text and a diagram; no 9:16 cut; repository homepage empty.
Workstream: #164.

## 14. Prioritised recommendations

1. #157 (P2, S). 2. #158 (P2, M). 3. #159 (P2, M). 4. #160 decision (maintainer). 5. #162 (P2, S to M).
6. #164 (P2, M, after #162). 7. #161 (P3, M). 8. #163 (P3, S). Existing: #76 record chain, #77, #82
usability re-test, #119.

Do not build: authentication or multi-operator roles (out of scope, documented), new vehicle
actions beyond LAND for pre-authorisation, real-hardware paths.

## 15. Existing issue mapping

| Issue | State before | Audit view | Action |
|---|---|---|---|
| #76 Onboard monitor | Open | Decision logic implemented and replay-tested; record chain to vehicle missing; live sim evidence (`eval/lost_link/onboard`) not recorded | Comment (NTC-04); defects split to #158 |
| #77 Reconnection and acknowledgement | Open | Acknowledgement timeout exists; fleet recordings predate it | Comment (NTC-07) |
| #119 AT route to approve | Open | Focus trap and live-region issues belong here | Comment (NTC-12) |
| #110 Console spec | Open | Child issues #111 to #120 closed | No change; maintainer check in #137 |
| #82, #16 Usability | Open | Redesign untested; most important human-factors gap | No change |
| #75, #71, #78, #79, #83, #19, #137 | Open | Consistent with HEAD | No change |

## 16. New issues

Parent #156; children #157 to #164.

## 17. Dependency graph

```
#160 (decision) ──> ADR 0001 amendment ──> engine and recommender tests
#76 record-chain decision ──> integration test POST /policy -> vehicle -> /onboard-actions
#162 ──> #164
#157, #158, #159, #161, #163 independent (an Authority module, appendix (e), would host #157, #159, #161)
```

## 18. Quality gates

Before promoting "every command has a recorded operator approval" in public material: #157,
#158 and #159 closed. Before claiming the console supports an unaided decision: #82 done.

## 19. Unverified

Whether `mavsdk_server` can still deliver a command after the gate cancels the gRPC call at the
timeout (needs the simulator). Branch protection. Behaviour with an asymmetric link (out of scope).

## 20. Handoff

Start with #157 (tdd). Run `make check` with `pip install -e ".[dev,sim,c2]"` and
`cd console && npm test`. Respect CLAUDE.md: ask before changing the ICD; `docs/product/*` and
ADR decisions are maintainer-written.

---

## Appendix: independent source audit (verbatim)

### nav-trust-c2: independent source-level audit

Commit audited: `56e6aee9fbaad86ea473a26a1cd19fc94bf0d817`. Read-only. No simulator was run, no
held-out recording was touched or regenerated, nothing was committed. Probes ran against the
in-process FastAPI app with an in-memory audit log and the dry-run executor
(`probe.py`, next to this file).

## (a) Check results

| Command | Result |
|---|---|
| `python3 -m venv /tmp/ntc-venv && pip install -e ".[dev,c2]"` then `ruff check .` | All checks passed |
| `ruff format --check .` | 161 files already formatted |
| `mypy` (strict, `pyproject.toml` file list) | Success: no issues found in 117 source files |
| `pytest` without the `sim` extra | **1 failed, 491 passed, 17 skipped**, 1 warning (see NTC-14) |
| `pip install mavsdk-grpc==4.0.5` (the `sim` extra CI uses), then `make check` | **rc 0: 532 passed, 8 skipped**, 1 warning (Starlette `httpx` deprecation) |
| Skips with the full extras (`pytest -rs`) | 8, all in `tests/replay/test_recordings.py` (`deliberately stopped early` 1, `not a nominal run` 3, `not a zone run` 4): data-dependent parametrisation, not missing deps |
| Console, copied to `/tmp/ntc-console`: `npm ci` | rc 0 |
| `npm run typecheck` (tsc 7.0.2) | rc 0 |
| `npm test` (vitest 5.0.5) | **6 files, 162 tests passed** |
| `npm audit --omit=dev` | found 0 vulnerabilities |
| `git grep -nE '(ghp_|gho_|github_pat_|AKIA|BEGIN .*PRIVATE|api[_-]?key|secret|token|/Users/|/home/[a-z])'` | No secrets and no personal paths. Only hits are `id-token: write` in `pages.yml` and the word "token" in design docs |

Failing test without the `sim` extra:
`tests/test_onboard_run.py::test_the_monitor_lands_the_vehicle_itself_and_reports_only_once_the_link_is_back`,
`assert (0 == 1)` at `tests/test_onboard_run.py:124`, caused by
`ModuleNotFoundError: No module named 'mavsdk_grpc'` raised inside the task at `sim/onboard_run.py:71`.

## (b) Subsystem inventory

| Subsystem | Status | Evidence |
|---|---|---|
| Trust engine (availability + consistency detectors, GREEN/AMBER/RED, reason, calibrated GREEN bound, headroom) | Implemented | `navtrust/engine.py`, `availability.py`, `consistency.py`, `calibration.py` |
| `BIAS_DRIFT` reason | Planned (enum only) | `navtrust/consistency.py:9` "Not implemented: BIAS_DRIFT" |
| Recommender (LAND + re-task for INCONSISTENT_INNOVATION, re-task for GNSS_LOSS/STALE, 60 s TTL, re-raise on expiry, NO_LINK suppression) | Implemented | `c2/recommender.py` |
| Hub (trust, link health, recommendations, decisions, expiry, outage reconcile, pub/sub) | Implemented | `c2/hub.py` |
| Policy gate + acknowledgement timeout | Implemented | `c2/gate.py` |
| Append-only audit log (SQLite triggers) | Implemented | `c2/audit.py:19-22` |
| HTTP/WebSocket API with same-origin and anti-rebinding checks | Implemented, no authentication by design | `c2/server.py:5-8`, `101-119` |
| MAVSDK executor (HOLD, RTL, LAND, re-task via mission upload) | Implemented, sim only | `sim/executor.py` |
| Contingency policy approval (`POST /policy`) and onboard report (`POST /onboard-actions`) | Implemented at the backend | `c2/hub.py:203-255`, `c2/server.py:197-218` |
| Onboard monitor decision logic | Implemented, tested on replays | `sim/onboard_monitor.py`, `eval/onboard_replay.py` |
| Delivery of an operator-approved policy to a vehicle | **Not built**: only an experiment approval (audit id 0) is ever loaded | `sim/record_run.py:234-251`, NTC-04 |
| Onboard monitor live simulator evidence | Not recorded: `eval/lost_link/onboard` does not exist | `ls eval/lost_link` gives `recordings results.md` |
| Console (React, MapLibre, approval with hold-to-confirm for LAND) | Implemented | `console/src` |
| Console policy approval UI | Not built | no `policy` reference in `console/src` |
| Asymmetric or delayed link, real radios, authentication | Out of scope (ADR 0004 R16, R17; risks R12) | `docs/adr/0004-authority-under-lost-link.md` |

## (c) Verified strengths

- Single command path in `c2/`. `CommandGate` holds the executor privately; it runs only with an
  APPROVED decision and only once (`c2/gate.py:66-74`, `_executed` set before any await at line
  74). An AST test enforces that no other `c2/` module calls an executor method
  (`tests/test_gate.py:160`).
- Every outcome is audited: `command_sent`, `command_acknowledged` / `command_not_acknowledged`,
  `command_executed`, `command_failed`, `command_blocked` (`c2/gate.py:107-152`). A command never
  acknowledged is audited and not resent (`c2/gate.py:99-102`), as ADR 0004 item 7 requires.
- `asyncio.wait` instead of `wait_for` so an executor's own `TimeoutError` is a failure, not
  silence (`c2/gate.py:131-132`).
- Decision validation is strict and audited when rejected: outcome must be APPROVED or DENIED,
  operator must be non-blank, expired and superseded are 410 (`c2/hub.py:257-291`). `decide`
  sweeps before checking, so an expired recommendation cannot be approved.
- Same-origin enforcement covers HTTP and the WebSocket handshake, rejects `Origin: null`, and
  blocks DNS rebinding by refusing dotted non-IP Host names (`c2/server.py:89-119`, `331-333`).
  Probe: cross-origin POST 403, `Host: attacker.example` 403, `Origin: null` 403.
- Default bind `127.0.0.1` (`c2/server.py:367`); no `0.0.0.0` HTTP bind anywhere (`git grep`
  hits are only MAVLink `udpin://`). YAML uses `yaml.safe_load` (`sim/scenario.py:159`); no pickle,
  no `eval`, no `shell=True`.
- Onboard monitor acts only when all of: C2 heard before, silent longer than `wait_s`, own state RED,
  reason matches a `NO_LINK` entry, trust report fresh, policy young enough; and only once
  (`sim/onboard_monitor.py:62-83`). `validate_policy` allows only `LAND` and `NO_LINK` and
  `0 < wait_s < COM_DL_LOSS_T` (`c2/contingency.py:35-48`), shared by backend and vehicle. This
  matches ADR 0004 items 1 to 3.
- Ground truth isolation is structural: the engine API takes only fix type, accuracy and two
  test ratios (`navtrust/engine.py:75-86`), and `navtrust/replay.py:17,56` feeds only
  `gps_info` and `estimator_status` records. No module in `navtrust/`, `c2/` or the onboard
  monitor reads a ground-truth field (`git grep -niE "ground_truth|truth|gz_pose"`: comments only).
- Calibration numbers are recomputed from recordings by `tests/test_calibration.py`, eval tables
  are regenerated and diffed in CI, and the held-out protocol was frozen before data; the
  held-out report records its own miss (E3) and the later fingerprint change honestly
  (`docs/validation/heldout-report.md`, addendum).
- Console: hold-to-confirm for LAND with keyboard support (Space/Enter keydown/keyup, release on
  blur), focus on Cancel for LAND, `role="dialog"` + `aria-modal`, a status live region for the
  hold, a no-link warning, buttons disabled while the backend is lost, and a full re-sync from
  the backend snapshot on reconnect (`console/src/store.ts:179-207`).
- Usability evidence is reported conservatively (N=2, failed task reported, "not re-tested").

## (d) Findings

Severity: P0 safety/authority bypass, P1 serious, P2 should fix, P3 minor.

### NTC-01 `POST /recommendations` lets any local client create a recommendation outside the recommender's rules
- Classification: Confirmed gap. Severity: P2. Confidence: high.
- Where: `c2/server.py:257-266`, `c2/messages.py:45-49` and `106-116`, `c2/hub.py:194-201`.
- Evidence:
  ```python
  @app.post("/recommendations", status_code=201)
  async def post_recommendation(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
      try:
          rec = recommendation_from_dict(body)
          hub.add_recommendation(rec)
  ```
  The only checks are `expires_s > created_s` and "command or sector moves". Client supplies
  `id`, `created_s`, `expires_s`, `vehicle_id`, `command`, `sector_moves`.
- Observed (probe 1 and 2): a recommendation posted with `expires_s: 1e12` for never-seen
  `uav9` was approved an hour later and executed (`actions: ['LAND uav9']`). A LAND recommendation
  for a vehicle already NO_LINK is accepted. The `recommendation` audit row does not say whether
  the recommender or an external client created it. The endpoint is not in `docs/ICD.md`
  (sections at lines 29-56 describe the Recommendation as "produced by the recommender").
- Expected: ADR 0004 table "Expires after 60 s" and item 6 "While NO_LINK, no command is proposed
  to that vehicle" hold for every recommendation, and the audit says who proposed it.
- C2-01 is not bypassed: an operator approval is still required. The gap is in what can be put in
  front of the operator and what the audit can prove about provenance.
- Verify: `python -I probe.py` (probes 1 and 2).
- Fix: remove the endpoint from the production app (keep it behind a test-only flag), or make the
  hub stamp `created_s`/`expires_s` itself, cap TTL, reject unknown vehicles and NO_LINK commands,
  and add `"source": "recommender" | "external"` to the audit payload.
- Acceptance: a test that a posted recommendation with `expires_s` beyond `now + ttl` or for a
  NO_LINK vehicle is refused, and that every `recommendation` audit row has a source.

### NTC-02 Backend accepts an onboard action that the cited policy does not authorise
- Classification: Confirmed defect. Severity: P2. Confidence: high.
- Where: `c2/hub.py:234-255`, check at `238-243`.
- Evidence:
  ```python
  approved = [
      e
      for e in self._audit.events("policy_approved")
      if e.id == report.get("policy_audit_id")
      and e.payload["sha256"] == report.get("policy_sha256")
  ]
  ```
  Only id and hash are compared. `action`, `reason` and `link_down_s` versus the policy's
  entries and `wait_s` are not checked, nor whether the policy was older than `max_age_s`.
- Observed (probe 3): report `{"action": "RTL", "reason": "GNSS_LOSS", "link_down_s": 0.1}`
  citing a policy that only allows `INCONSISTENT_INNOVATION / NO_LINK / LAND` with `wait_s` 5
  returned 204 and was audited as `onboard_action` (not `rejected_onboard_action`). It also calls
  `_note_report(vehicle_id)` (line 252), so a report can flip a vehicle's link state to LINK_OK.
- Expected: ADR 0004 item 8: a contingency counts "for the fault, link condition and action it
  names, and for nothing else". LL-03 wants every action recorded with the authority it ran under;
  an `onboard_action` row should mean "within the policy".
- Verify: probe 3.
- Fix: reuse `sim/onboard_policy.Policy.matches` (or a shared function in `c2/contingency.py`)
  to check `(reason, "NO_LINK", action)` and `link_down_s > wait_s`; audit a mismatch as
  `rejected_onboard_action` with `rejected_because: outside_policy` (keep the record: the vehicle
  did act).
- Acceptance: tests for wrong action, wrong reason, `link_down_s <= wait_s`, each producing a
  `rejected_onboard_action` row and no link-state change.

### NTC-03 Audit log cannot tie a command to its approval across backend restarts
- Classification: Confirmed gap. Severity: P2. Confidence: high.
- Where: `c2/server.py:366` (`--db` default `logs/audit.sqlite`), `405-407` (clock restarts at 0),
  `c2/recommender.py:112` (ids restart at `rec-<vehicle>-1`), `c2/audit.py:42-52` (no session
  column, no start row).
- Evidence:
  ```python
  start = time.monotonic()
  clock = lambda: time.monotonic() - start  # noqa: E731
  hub = Hub(AuditLog(args.db), clock, link_timeout_s=args.link_timeout)
  ```
- Observed: two Hub sessions on the same SQLite file produce
  `[(6, 5.0, 'rec-uav2-1'), (12, 5.0, 'rec-uav2-1')]`: identical recommendation id and identical
  `t_s`. `command_sent` rows join to decisions only by `recommendation_id`, so the join is
  ambiguous. `DuplicateRecommendation` (`c2/hub.py:195-196`) only checks memory.
- Expected: the audit can prove which operator decision authorised which command.
- Mitigation in place: `make demo-run` recommends one DB per session; `eval.usability` reads one.
- Verify: script in this audit's transcript (two `Hub(AuditLog(db), ...)` instances on one file).
- Fix: write a `session_started` row with a random session id and wall-clock time at startup,
  include the session id in recommendation ids (or in every row), and store `decision_audit_id`
  in `command_sent` payloads.
- Acceptance: test that two sessions on one DB yield distinct recommendation ids and that each
  `command_sent` row references the audit id of its `decision` row.

### NTC-04 ADR 0004 record chain is not wired end to end; the only onboard policy is an experiment's own
- Classification: Confirmed gap (acknowledged in docs). Severity: P2. Confidence: high.
- Where: `sim/record_run.py:234-251`, `sim/onboard_run.py:35-41` (`experiment_approval`),
  `sim/onboard_policy.py:55-82`, `c2/hub.py:203-232`.
- Evidence: the only caller of `load_policy` outside tests and eval is
  `sim/record_run.py:236`, with `approval = experiment_approval(args.onboard_wait)` (audit id 0,
  `approved_s = time.time()`), and `now_s=approval["approved_s"]`, so age is always 0.
  `hub.approve_policy` stamps `approved_s` on the backend's run-relative clock
  (`now = self._clock()`, `c2/hub.py:218`), a different clock domain from `time.time()`.
  Nothing transfers a `POST /policy` result to a vehicle; the console has no policy UI. The
  policy record carries no vehicle or mission binding, so within 4 h any approval is reusable by
  any vehicle and any mission (ADR 0004 item 5: "approved once per mission").
- Observed vs expected: ADR 0004 item 5 says "The vehicle accepts a policy only if it matches that
  audit row's id and hash". Today the vehicle only checks that a payload matches its own hash,
  which anyone can compute (the docstring says so, `sim/onboard_policy.py:8`).
- This is honest in docs (`docs/product/requirements.md:22` LL-02 "gap, Not built"), but the code
  has more than "not built" suggests, and README line 83 says "planned ... not built".
- Fix: define the hand-off (backend serves the approval; vehicle stores `audit_id`, `sha256`,
  wall-clock `approved_utc`, `mission_id`, `vehicle_ids`); make `approve_policy` stamp wall time;
  check mission binding in `load_policy`.
- Acceptance: an integration test from `POST /policy` to `load_policy` to `POST /onboard-actions`
  accepted, and a policy from a different mission refused.

### NTC-05 Reason precedence hides a position inconsistency when the fix is only degraded
- Classification: Likely issue (design consequence of ADR 0001). Severity: P2. Confidence: medium.
- Where: `navtrust/engine.py:124-140`, `c2/recommender.py:97-99`, `sim/onboard_monitor.py:72`.
- Evidence:
  ```python
  state = max((s for s, _ in findings), key=_RANK.__getitem__)
  order = [ReasonCode.GNSS_LOSS, ReasonCode.STALE, ReasonCode.INCONSISTENT_INNOVATION]
  reason = min((r for _, r in findings), key=order.index)
  ```
- Observed (pure-Python run of `TrustEngine`, `FIX_2D` plus ratios at 2.0 from t = 3 s):
  `5.0 RED GNSS_LOSS DEGRADED INCONSISTENT`. The state is RED only because of the consistency
  detector, but the reason is `GNSS_LOSS`. Consequences: the recommender proposes no LAND
  (`wants_land` only for INCONSISTENT_INNOVATION), the onboard contingency does not match, and
  PX4's position-loss failsafe has no reason to fire while a 2D fix is still reported.
- Expected: the reason should explain the state. ADR 0001 says "Loss takes precedence in the
  reason code", which was written when DEGRADED could only produce AMBER; a degraded-plus-
  inconsistent case was not recorded (ADR 0001 notes `wrong` changes only the fix type).
- Verify: script in transcript; no recording covers it.
- Fix (maintainer decision, ADR amendment): take the reason from the finding that set the worst
  state, or carry both reasons; add an engine test for DEGRADED + INCONSISTENT.
- Acceptance: test that DEGRADED + INCONSISTENT yields RED with `INCONSISTENT_INNOVATION` (or a
  documented combined reason) and that the recommender proposes LAND.

### NTC-06 Onboard runner: report failure loses the record, and the action is logged before the command result
- Classification: Confirmed defect (code reading). Severity: P2. Confidence: high for the
  ordering, medium for impact (no simulator run).
- Where: `sim/onboard_run.py:86-105`.
- Evidence:
  ```python
  unreported = monitor.take_unreported()
  if unreported:
      await report(unreported)
  ...
  write("onboard_action", vehicle_clock_s=fields.pop("t_s"), **fields)
  await drone.action.land()
  ```
  `take_unreported` empties the list before the POST; `report_actions` calls
  `raise_for_status()`; nothing catches, so a 5xx, a timeout, or a 422 `unknown_policy` (which an
  audit-id-0 experiment approval will always get from a real backend) ends `decide()` and, via
  `asyncio.gather`, the whole monitor, and the action is never reported. `land()` errors (e.g.
  command denied) likewise kill the monitor, after the log already says `onboard_action`, with no
  acknowledged/failed outcome recorded (unlike the gate).
- Expected: ADR 0004 item 7: "After reconnection, the vehicle reports each onboard action".
- Fix: re-queue on failure and retry with backoff; record `onboard_command_acknowledged` /
  `onboard_command_failed` after `land()`; catch per-task errors so a stream failure does not
  silently end the monitor.
- Acceptance: unit test with a fake backend returning 500 then 204: the action is reported once;
  test with a fake `land()` raising: outcome logged, monitor still running.

### NTC-07 Re-task acknowledgement timeout sits just above measured re-task time
- Classification: Likely issue. Severity: P2. Confidence: medium.
- Where: `c2/server.py:376-381` (`--ack-timeout` default 5.0), `c2/gate.py:131-141`,
  `sim/executor.py:58-80`, `eval/fleet/results.md` per-run table.
- Evidence: measured decision to re-task 2.3, 4.7 and 2.7 s (`loss_approved-1..3`). Those
  recordings contain `command_executed` but no `command_sent` rows
  (`grep -o '"kind": *"command_[a-z_]*"' eval/fleet/recordings/loss_approved-*.jsonl`), so they
  predate the acknowledgement timeout. The re-task call (download, upload, start for up to two
  vehicles) runs inside one 5 s window and is cancelled at the limit.
- Risk: a slightly slower run is audited `command_not_acknowledged`, the fleet plan is not rolled
  back (by design), and a mission may have been uploaded but not started.
- Fix: per-vehicle send and acknowledgement in `retask`, or a separate, measured timeout for
  re-task; re-record the fleet set with the gate as it is now.
- Acceptance: fleet recordings with `command_sent`/`command_acknowledged` rows, and a documented
  re-task latency distribution against the timeout.

### NTC-08 Gate applies a recommendation's sector moves without re-checking them at approval time
- Classification: Likely issue. Severity: P3. Confidence: medium.
- Where: `c2/gate.py:91-98`, `c2/fleet.py:22-36`.
- Evidence: `self._fleet.apply_moves([(m.sector_id, m.to_vehicle) for m in rec.sector_moves])`
  moves a sector from whoever owns it now, and `changed` uses `rec.vehicle_id`, not the actual
  previous owner. The taker's trust and link are not rechecked; moves were computed up to 60 s
  earlier (`c2/recommender.py:122-143` requires GREEN and reachable only at creation).
- Expected: the operator approves what the card showed; if the premise changed, block or supersede.
- Fix: in the gate, refuse (`command_blocked`, `stale_moves`) when a sector's owner is no longer
  `rec.vehicle_id` or the taker is not GREEN and reachable.
- Acceptance: test with two overlapping recommendations; the second is blocked.

### NTC-09 Console attributes decisions to a generic "operator" by default
- Classification: Confirmed gap. Severity: P3. Confidence: high.
- Where: `console/src/App.tsx:18-24`, `73`; `console/src/components/ConfirmDialog.tsx:61`.
- Evidence: `return localStorage.getItem(OPERATOR_KEY) ?? "operator";` and
  `postDecision(rec.id, outcome, operator.trim() || "operator")`. Deny is sent from the card
  without the dialog, so it is always under the stored or default name.
- Expected: C2-01 "a decision is only an operator approval if it names the operator"
  (`c2/hub.py:271`). "operator" is a placeholder, not a name. (No authentication is documented, R12.)
- Fix: start empty, require a name once per session before any decision, reject the literal
  `operator` at the hub, show the name in the header.
- Acceptance: component test that Approve and Deny are disabled until a name is set.

### NTC-10 Command outcomes are not published; other consoles never learn whether an approval executed
- Classification: Confirmed gap. Severity: P3. Confidence: high.
- Where: `c2/gate.py:107-152` uses `self._hub.audit.append` only; `Hub._publish`
  (`c2/hub.py:117-120`) is never called for command rows; `execution` exists only in the HTTP
  response (`c2/server.py:280-286`).
- Observed: a second console (or the same one after reconnect, since the snapshot holds only
  open recommendations, `c2/hub.py:428-432`) shows "Approved by X" with no executed / not
  acknowledged / failed line (`console/src/components/RecommendationCard.tsx:188-194`).
- Fix: publish a `command` event per audit row and include recent command outcomes in `/state`.
- Acceptance: WebSocket test that a `command_not_acknowledged` reaches a second subscriber.

### NTC-11 Confirm dialog stays open after its recommendation expires, is superseded or decided elsewhere
- Classification: Confirmed gap (UI consistency). Severity: P3. Confidence: high.
- Where: `console/src/App.tsx:39`, `219-231`; `setConfirming(null)` only at lines 75, 85, 228.
- Evidence: `confirming` is a snapshot; no effect closes it when the id leaves `open`.
  `canConfirm` (`ConfirmDialog.tsx:61`) does not check expiry.
- Impact: the backend refuses (410/409) so nothing unsafe executes; the operator holds for 1.5 s
  and then gets an error toast.
- Fix: close or disable the dialog when `!open.some(r => r.id === confirming.id)` and show why.
- Acceptance: component test that expiry while the dialog is open disables confirm.

### NTC-12 Approval dialog has no focus trap or focus return; decisions live region announces the countdown
- Classification: Likely issue (accessibility). Severity: P3. Confidence: medium (not tested with
  a screen reader).
- Where: `console/src/components/ConfirmDialog.tsx:68-74` and `79` (no Tab handling, no `inert`
  on the background, focus not restored on close; `grep -n "Tab\|inert"` finds nothing);
  `console/src/App.tsx:169` `aria-live="polite"` wraps the cards whose text
  `Expires in ...` changes every tick (`console/src/components/RecommendationCard.tsx:77`).
  `DecisionBanner.tsx:24-25` deliberately keeps its countdown out of the alert region, so the
  panel contradicts the banner's own rule.
- Fix: trap Tab inside the dialog (or `inert` the rest), restore focus to the Approve button;
  move the countdown out of the live region or mark it `aria-hidden` with a coarse sr-only text.
- Acceptance: component tests for Tab cycling and focus return; manual check with a screen reader.

### NTC-13 NaN in a trust report breaks the console's WebSocket snapshot
- Classification: Confirmed defect. Severity: P3. Confidence: high.
- Where: `c2/messages.py:78-88` (`float(bound)` accepts NaN; `stamp_s` likewise),
  `navtrust/types.py:35-36` (`nan < 0` is false), `c2/server.py:341-345` (`send_json`).
- Observed: posting `"horizontal_bound_m": NaN` returns 204; `GET /state` renders it as `null`,
  but the WebSocket snapshot contains the literal `NaN` ("ws contains NaN: True"). The console's
  `JSON.parse` fails and the message is dropped silently (`console/src/api.ts:25-30`), so every
  later `state` snapshot is lost while that vehicle's value persists. `alt_m` on `/positions`
  has the same gap (`c2/hub.py:159-160` checks lat/lon only).
- Fix: reject non-finite numbers in `navtrust_from_dict` and `ingest_position`; send WebSocket
  JSON with `allow_nan=False`.
- Acceptance: tests that NaN/Infinity inputs return 422.

### NTC-14 One test needs the `sim` extra but does not say so
- Classification: Confirmed defect (test hygiene). Severity: P3. Confidence: high.
- Where: `sim/onboard_run.py:71` (lazy `from sim.record_run import parse_estimator_status`, which
  imports `mavsdk_grpc`), `tests/test_onboard_run.py:99-130`.
- Observed: without `mavsdk-grpc` the import fails inside a task, the exception is swallowed
  ("Task exception was never retrieved") and the test fails on `assert drone.landed == 1`.
  CLAUDE.md's `make check` "without the sim" suggests it should pass. CI installs `.[dev,sim,c2]`
  so CI is green. The module docstring "NOT SHOWN BY ANY TEST HERE" (`sim/onboard_run.py:9`) is
  also stale: this test runs `run_monitor` with a fake drone.
- Fix: move `parse_estimator_status` to a module without the MAVSDK import, or
  `pytest.importorskip("mavsdk_grpc")`.
- Acceptance: `pip install -e ".[dev,c2]" && pytest` passes.

### NTC-15 Workflow hardening: `ci.yml` has no `permissions` block; actions in `ci.yml` and `codeql.yml` are pinned by tag
- Classification: Confirmed gap. Severity: P3. Confidence: high.
- Where: `.github/workflows/ci.yml` (no `permissions:`; `uses: actions/checkout@v7` lines 12, 34,
  51; `actions/setup-python@v7.1.0` lines 13, 52; `actions/setup-node@v7` line 35),
  `.github/workflows/codeql.yml:23-27` (`@v7`, `@v4`). `pages.yml` is pinned by SHA and scopes
  permissions, so the repo already has the pattern. No `pull_request_target` anywhere. Dependabot
  covers pip, npm, actions and docker.
- Also: `sim/docker/Dockerfile:6` `FROM ubuntu:24.04` (tag, not digest); line 36 installs
  `fastapi>=0.115`, `uvicorn[standard]>=0.30` etc. unpinned; Gazebo comes from PX4's
  `Tools/setup/ubuntu.sh` apt install at build time, so its version floats while PX4 is pinned
  (`PX4_REF=a427a2e3...`, line 11). Python extras in `pyproject.toml` are ranges with no lock file.
- Fix: `permissions: contents: read` at the top of `ci.yml`; pin actions by SHA with a version
  comment; record the Gazebo package versions in recording headers or pin them.
- Acceptance: all `uses:` lines are 40-hex SHAs; recordings carry the gz version.

### NTC-16 Docs lag the code on contingencies and on C2-01's wording
- Classification: Confirmed gap (docs). Severity: P3. Confidence: high.
- Where: `README.md:82-83` ("A contingency approved before the mission is planned (ADR 0004, not
  built)"); `docs/product/requirements.md:17` (C2-01 "met", wording still "except PX4's own
  failsafes", while the onboard LAND is neither a gate command nor a PX4 failsafe), lines 22-23
  (LL-02, LL-03 "Not built"); `docs/ICD.md:101` ("always empty until the onboard monitor exists").
  The backend endpoints, policy validation and monitor exist (issue 76).
- Note: `docs/product/*` is maintainer-owned per CLAUDE.md; this is a report, not an edit request
  for agents.
- Fix: maintainer updates LL-02 to "partial" with what exists and what is missing (NTC-04), and
  C2-01 to the ADR 0004 item 8 wording.

### NTC-17 README headline numbers are typed, not generated
- Classification: Confirmed gap. Severity: P3. Confidence: high.
- Where: `README.md:23-34` (for example "detected in 1.0 to 1.4 s in 12 runs", "99.72% of 5,308",
  "100% ... 87%"). No test reads `README.md` (`grep -rn README tests/` has no hits).
- Observed: the numbers do match `eval/results.md`, `eval/heldout/results.md` and
  `eval/fleet/results.md` today (checked by hand: 5 + 7 loss runs, TTD 1.0 to 1.4 s; 7 frozen
  runs, 3.0 to 4.5 s; 4 + 5 nominal runs). But nothing keeps them in sync, against the rule
  "Metrics are measured, never typed".
- Fix: generate the summary block between the existing `<!-- summary-start -->` markers from the
  results JSON, or add a test that checks each quoted number.

### NTC-18 Calibration claim of 0.99 coverage rests on strongly correlated samples
- Classification: Strategic opportunity. Severity: P3. Confidence: medium.
- Where: `navtrust/calibration.py:37-45`, `eval/heldout/results.md` (nominal_fast 99.4%,
  stuck_position_slow 99.3%).
- Evidence: bound 3.0 m chosen where the development maximum was 2.9 m (`eval/results.md`,
  nominal runs 2.8 to 2.9 m); 4,040 and 5,308 reports at 2 Hz from 14 and 18 flights, so the
  effective sample size is much smaller than the report count. The console shows
  `confidence = 0.99` as if it were a per-report probability. Error grows with speed and the
  12 m/s held-out runs are where the misses are.
- Docs are already careful ("Simulation only", "the claim"). The opportunity is to report coverage
  per flight and per speed with an interval, and to state the claim as "held in N of M flights".
- Acceptance: `GET /calibration` and the docs carry per-speed coverage and a flight-level interval.

### NTC-19 Approving a pre-outage command while the vehicle is NO_LINK still dispatches it
- Classification: Not a defect (by design), residual risk noted. Severity: n/a. Confidence: high.
- Where: `c2/hub.py:257-291` and `c2/gate.py:63-121` do not check link state; probe 2 shows
  `LAND uav1` dispatched while `uav1` is NO_LINK.
- Why it is acceptable: ADR 0004 item 6 restricts *proposing* (the recommender complies,
  `c2/recommender.py:99`), item 7 says an unacknowledged command is audited, not resent, and the
  console warns (`console/src/language.ts:122-127`). With the modelled symmetric link the
  executor fails or times out and nothing is replayed. Residual: with an asymmetric link (R16, not
  modelled) the command could arrive. Worth an ADR line if asymmetric links come into scope.

### NTC-20 Experiment harness sends commands outside the gate
- Classification: Not a defect. Confidence: high.
- Where: `sim/record_run.py:60-77` (`operator_action_after_fault`, docstring: "bypasses the console
  and the gate on purpose, so it is only for recorded experiments"), `sim/onboard_run.py:103`
  (onboard LAND under ADR 0004), `sim/fly_survey.py:189-200` (arm, mission upload and start: the
  mission launch, before any recommendation), `sim/failsafe_params.py:27-28` (parameter setup).
  The gate's AST test covers only `c2/` (`tests/test_gate.py:160-174`).
- All are labelled in recording headers (`sim/record_run.py:129-141`). Opportunity: extend the
  architecture test with an allow-list of vehicle-command call sites in `sim/`, so a new one
  cannot appear unnoticed.

### NTC-21 Gate idempotency, replay and double-submit
- Classification: Not a defect. Confidence: high.
- `_executed` is added before the first await (`c2/gate.py:74`); a second `decide` for the same id
  raises `AlreadyDecided` (`c2/hub.py:277-283`); the console disables confirm while busy
  (`ConfirmDialog.tsx:61`). Decisions and `_executed` are in memory, so a restart cannot replay an
  old approval from the audit log (the restart problem is attribution, NTC-03, not replay).

### NTC-22 Same-origin policy allows any loopback origin on any port
- Classification: Not a defect (documented trade-off). Confidence: high.
- Where: `c2/server.py:117` `if _is_loopback(source[0]) or source == target:`. Needed for the
  Vite dev server on :5173. Any other web app served from localhost on the operator machine can
  approve commands. Probe 6: `Origin: http://localhost:5555` gets 200. Acceptable for a
  localhost-only, unauthenticated simulation tool (risk R12); restrict to an explicit allow-list if
  the backend is ever shown on a shared machine.

### NTC-23 Ground truth never reaches the trust engine
- Classification: Not a defect. Confidence: high. See strengths. Opportunity: add an AST test that
  `navtrust/` and `sim/onboard_*.py` import nothing from `sim.ground_truth` or `eval`, to make the
  structural guarantee explicit.

### NTC-24 Usability "audit database confirms both sessions"
- Classification: Unverified. Confidence: n/a. `docs/usability/findings-2026-10.md` cites audit
  DBs under `logs/`, which are git-ignored by policy (`.gitignore` `logs/`). Claims are modest and
  internally consistent; they cannot be checked from the repository.

## (e) Architecture candidates

Hot spots from `git log -100 --name-only`: `console/src/components/components.test.tsx` (15),
`console/src/store.test.ts` (12), `store.ts` (11), `App.tsx` (10), `RecommendationCard.tsx` (8),
`MapView.tsx` (8), `sim/record_run.py` (6), `docs/ICD.md` (5), `c2/hub.py` and `c2/server.py` (4).

1. **Authority module behind one seam. Strong.** The command-authority invariants are spread over
   four modules: TTL and NO_LINK suppression in the recommender, decision lifecycle in the hub,
   once-only execution in the gate, and an HTTP adapter (`POST /recommendations`) that skips the
   first set (NTC-01). The hub's interface is wide (447 lines: link health, outages, policy,
   onboard reports, pub/sub). A deeper `Authority` module with a small interface (`propose`,
   `decide`, `execute`, `record_onboard`) owning ids, clocks, session and audit provenance would
   give locality to every C2-01 rule and let NTC-01, 03, 08 and 10 be fixed in one place.
2. **One contingency module used by both ends. Strong.** The policy shape is in
   `c2/contingency.py`, loading in `sim/onboard_policy.py`, the rule in `sim/onboard_monitor.py`,
   wiring in `sim/onboard_run.py`, and backend acceptance in `c2/hub.py`. The backend check is
   shallower than the vehicle's (NTC-02). Moving `Policy.matches` and an `authorises(policy,
   report)` function into `c2/contingency.py` gives leverage: one function decides "within the
   policy" for the vehicle, the backend and the eval.
3. **Experiment harness versus product seam. Worth exploring.** `sim/record_run.py` (393 lines,
   a hot spot) composes the survey, injector, link-cut relay, ground truth, onboard monitor and a
   gate-bypassing operator. The "experiment only" boundary is a docstring. An `ExperimentActions`
   adapter as the only non-gate command path in `sim/`, enforced by the AST test (NTC-20), would
   make the seam real.
4. **Backend-derived action availability for the console. Speculative.** The console recomputes
   "actionable" from expiry, link state and connection (`store.ts`, `App.tsx`), and the dialog
   holds a stale snapshot (NTC-11). A backend field per open recommendation (`actionable`,
   `blocked_because`) would move that logic behind the API and shrink the most-churned files.

## (f) Open questions

1. Does cancelling a MAVSDK gRPC call at the acknowledgement timeout (`c2/gate.py:133-134`) stop
   `mavsdk_server` from completing a command or mission upload later? Not verifiable without a
   simulator; it decides whether "audited, not resent" also means "not delivered late".
2. Should the reason precedence for DEGRADED + INCONSISTENT (NTC-05) be an ADR 0001 amendment?
3. Is `POST /recommendations` needed outside tests?
4. How is a backend-approved policy meant to reach a vehicle, on which clock is its age measured,
   and is it bound to one mission and a set of vehicles (NTC-04)?
5. Will the fleet set be re-recorded with the current gate so acknowledgement timing is measured
   (NTC-07)?
6. Should a policy with no entries (accepted: probe 4 returns 201) or entries with extra keys
   (accepted, 201) be refused as malformed? Harmless today because only `action` is read and
   only `LAND` is valid.
