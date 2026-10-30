#!/usr/bin/env bash
# Issue 76: the link_and_frozen scenario with the onboard monitor running (ADR 0004). A frozen GNSS
# position, then the link is cut 5 s after the fault (uplink only), and the vehicle lands itself
# if the monitor's rule fires. Each run gets a freshly restarted simulator with one vehicle, about
# 6 to 7 minutes. Needs the image from `make sim-build`. Recordings already made are skipped.
#
#   sim/record_onboard_runs.sh                  3 runs, wait 5 s
#   WAIT=3 RUNS=2 sim/record_onboard_runs.sh
#
# The link signal the monitor sees is the link-cut relay's state, so the result says what the
# monitor does given that cut (docs/ICD.md, Onboard contingencies).
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="${IMAGE:-nav-trust-c2-sim}"
OUT_DIR="${OUT_DIR:-eval/lost_link/onboard}"
WAIT="${WAIT:-5}"
RUNS="${RUNS:-3}"

docker rm -f "${IMAGE}" >/dev/null 2>&1 || true
docker run -d --name "${IMAGE}" -v "$PWD":/workspaces/nav-trust-c2 -e NUM_VEHICLES=1 "${IMAGE}" >/dev/null
mkdir -p "${OUT_DIR}"
failures=()

for run in $(seq 1 "${RUNS}"); do
    name="link_and_frozen_onboard-${run}"
    out="${OUT_DIR}/${name}.jsonl"
    [ -s "${out}" ] && { echo "=== ${name} already recorded"; continue; }
    echo "=== ${name}"
    docker restart "${IMAGE}" >/dev/null
    sleep 90
    if ! docker exec -w /workspaces/nav-trust-c2 "${IMAGE}" \
        python -m sim.record_run --scenario "${name}" --out "${out}" \
        --mode stuck --zone 200 -50 280 150 --latch-fault \
        --width 600 --height 100 --spacing 100 --altitude 30 --speed 10 \
        --max-duration 300 --link-cut-after fault_start --link-cut-delay 5 \
        --link-cut-direction uplink --onboard-wait "${WAIT}"; then
        echo "!!! ${name} failed"
        rm -f "${out}"
        failures+=("${name}")
    fi
done

docker stop "${IMAGE}" >/dev/null
echo "recordings written to ${OUT_DIR}"
if [ "${#failures[@]}" -gt 0 ]; then
    echo "FAILED RUNS: ${failures[*]}"
    exit 1
fi
