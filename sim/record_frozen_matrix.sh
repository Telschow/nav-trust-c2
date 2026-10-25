#!/usr/bin/env bash
# Frozen-position experiment of ADR 0003, repeated over actions, cruise speeds and operator delays
# (issue 81). Each run gets a freshly restarted simulator with one vehicle, so it takes about 6 to
# 7 minutes. The default grid is 4 actions x 2 speeds x 2 delays x 3 runs = 48 runs, about 5 hours.
# Needs the image from `make sim-build`. Runs already recorded are skipped, so it can be restarted.
#
#   sim/record_frozen_matrix.sh
#   SPEEDS="5 12" DELAYS="5 30" RUNS=3 ACTIONS="none land hold rtl" sim/record_frozen_matrix.sh
#   RUNS=1 SPEEDS=10 DELAYS=15 sim/record_frozen_matrix.sh    smallest useful batch, 4 runs
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="${IMAGE:-nav-trust-c2-sim}"
OUT_DIR="${OUT_DIR:-tests/replay/data/experiments/matrix}"
ACTIONS="${ACTIONS:-none land hold rtl}"
SPEEDS="${SPEEDS:-5 12}"
DELAYS="${DELAYS:-5 30}"
RUNS="${RUNS:-3}"
MAX_DURATION="${MAX_DURATION:-220}"

docker rm -f "${IMAGE}" >/dev/null 2>&1 || true
docker run -d --name "${IMAGE}" -v "$PWD":/workspaces/nav-trust-c2 -e NUM_VEHICLES=1 "${IMAGE}" >/dev/null
mkdir -p "${OUT_DIR}"
failures=()

for action in ${ACTIONS}; do
    for speed in ${SPEEDS}; do
        for delay in ${DELAYS}; do
            for run in $(seq 1 "${RUNS}"); do
                name="stuck-${action}-v${speed}-d${delay}-${run}"
                out="${OUT_DIR}/${name}.jsonl"
                [ -s "${out}" ] && { echo "=== ${name} already recorded"; continue; }
                echo "=== ${name}"
                operator=()
                [ "${action}" != "none" ] && operator=(--operator-action "${action}" --operator-delay "${delay}")
                docker restart "${IMAGE}" >/dev/null
                sleep 90
                if ! docker exec -w /workspaces/nav-trust-c2 "${IMAGE}" \
                    python -m sim.record_run --scenario "${name}" --out "${out}" \
                    --mode stuck --zone 200 -50 280 150 --latch-fault \
                    --width 600 --height 100 --spacing 100 --altitude 30 --speed "${speed}" \
                    --max-duration "${MAX_DURATION}" ${operator[@]+"${operator[@]}"}; then
                    echo "!!! ${name} failed"
                    rm -f "${out}"
                    failures+=("${name}")
                fi
            done
        done
    done
done

docker stop "${IMAGE}" >/dev/null
echo "recordings written to ${OUT_DIR}"
if [ "${#failures[@]}" -gt 0 ]; then
    echo "FAILED RUNS: ${failures[*]}"
    exit 1
fi
