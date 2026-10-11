#!/usr/bin/env bash
# Record the fleet scenarios (see sim/record_fleet.py), each on a freshly restarted simulator with
# three vehicles. About 14 minutes per run. Needs the image from `make sim-build`.
#
#   sim/record_fleet_all.sh                 all runs below
#   sim/record_fleet_all.sh loss_denied 2   one run
#   OPERATOR_DELAY=40 sim/record_fleet_all.sh   another operator delay (replaces the recordings)
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="${IMAGE:-nav-trust-c2-sim}"
OUT_DIR="${OUT_DIR:-eval/fleet/recordings}"
OPERATOR_DELAY="${OPERATOR_DELAY:-15}"  # seconds the scripted operator waits before answering
ONLY="${1:-}"
ONLY_RUN="${2:-}"

docker rm -f "${IMAGE}" >/dev/null 2>&1 || true
docker run -d --name "${IMAGE}" -v "$PWD":/workspaces/nav-trust-c2 -e NUM_VEHICLES=3 "${IMAGE}" >/dev/null
mkdir -p "${OUT_DIR}"
failures=()

# name operator runs
while read -r name operator runs; do
    [ -n "${ONLY}" ] && [ "${ONLY}" != "${name}" ] && continue
    for run in $(seq 1 "${runs}"); do
        [ -n "${ONLY_RUN}" ] && [ "${ONLY_RUN}" != "${run}" ] && continue
        echo "=== ${name} run ${run}/${runs}"
        docker restart "${IMAGE}" >/dev/null
        sleep 100
        if ! docker exec -w /workspaces/nav-trust-c2 "${IMAGE}" \
            python -m sim.record_fleet --name "${name}" --run "${run}" \
            --operator "${operator}" --operator-delay "${OPERATOR_DELAY}" --out-dir "${OUT_DIR}"; then
            echo "!!! ${name} run ${run} failed"
            failures+=("${name}-${run}")
        fi
    done
done <<LIST
loss_approved approve 3
loss_denied deny 3
LIST

docker stop "${IMAGE}" >/dev/null
if [ "${#failures[@]}" -gt 0 ]; then
    echo "failed: ${failures[*]}"
    exit 1
fi
