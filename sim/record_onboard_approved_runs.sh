#!/usr/bin/env bash
# Issue 76: link_and_frozen with the onboard monitor under a policy the operator approved at the
# backend (ADR 0004 handoff), not the experiment's own. Per run: a freshly restarted simulator, a
# backend inside the container, a policy approved for mission m1 and uav1, the vehicle pulls it
# before launch, and after the link is back the monitor reports to the backend. The backend's
# audit log is kept next to the recording so the run shows which approval authorised the LAND.
# About 6 to 7 minutes a run. Needs the image from `make sim-build`. Recordings already made are
# skipped.
#
#   sim/record_onboard_approved_runs.sh                 3 runs, wait 5 s
#   WAIT=3 RUNS=2 sim/record_onboard_approved_runs.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=sim/sim_lock.sh
source sim/sim_lock.sh

IMAGE="${IMAGE:-nav-trust-c2-sim}"
OUT_DIR="${OUT_DIR:-eval/lost_link/onboard-approved}"
WAIT="${WAIT:-5}"
RUNS="${RUNS:-3}"
MAX_DURATION="${MAX_DURATION:-300}"
MISSION="${MISSION:-m1}"
PORT=8765
BACKEND="http://127.0.0.1:${PORT}"
IN="docker exec -w /workspaces/nav-trust-c2 ${IMAGE}"

docker rm -f "${IMAGE}" >/dev/null 2>&1 || true
docker run -d --name "${IMAGE}" -v "$PWD":/workspaces/nav-trust-c2 -e NUM_VEHICLES=1 "${IMAGE}" >/dev/null
mkdir -p "${OUT_DIR}"
failures=()

for run in $(seq 1 "${RUNS}"); do
    name="link_and_frozen_onboard_approved-${run}"
    out="${OUT_DIR}/${name}.jsonl"
    db="${OUT_DIR}/${name}.audit.sqlite"
    is_complete "${out}" && { echo "=== ${name} already recorded"; continue; }
    echo "=== ${name}"
    rm -f "${db}"
    docker restart "${IMAGE}" >/dev/null
    wait_for_sim 1
    docker exec -d -w /workspaces/nav-trust-c2 "${IMAGE}" \
        python -m c2.server --db "${db}" --port "${PORT}" --vehicles 1
    sleep 5
    if ! docker exec -i -w /workspaces/nav-trust-c2 "${IMAGE}" python - <<PY
import httpx
r = httpx.post("${BACKEND}/policy", json={
    "entries": [{"reason": "INCONSISTENT_INNOVATION", "link": "NO_LINK", "action": "LAND"}],
    "wait_s": ${WAIT}, "mission_id": "${MISSION}", "vehicles": ["uav1"],
    "operator": "recording script",
})
r.raise_for_status()
print("policy approved, audit id", r.json()["audit_id"])
PY
    then
        echo "!!! ${name}: the backend did not take the policy"
        failures+=("${name}")
        continue
    fi
    if record_one "${name}" "${out}" "${MAX_DURATION}" \
        ${IN} python -m sim.record_run --scenario "${name}" --out "${out}.partial" \
        --mode stuck --zone 200 -50 280 150 --latch-fault \
        --width 600 --height 100 --spacing 100 --altitude 30 --speed 10 \
        --max-duration "${MAX_DURATION}" --link-cut-after fault_start --link-cut-delay 5 \
        --link-cut-direction uplink --link-cut-duration 60 \
        --onboard-backend "${BACKEND}" --onboard-mission "${MISSION}"; then
        ${IN} python -m c2.audit_verify "${db}" || failures+=("${name}: audit_verify")
    fi
done

docker stop "${IMAGE}" >/dev/null
echo "recordings written to ${OUT_DIR}"
report_outcome
