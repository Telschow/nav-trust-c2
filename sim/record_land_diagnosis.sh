#!/usr/bin/env bash
# Issue 141: the LAND cells of the frozen-position matrix (issue 81) again, with PX4's flight mode
# recorded, to see what PX4 does between the LAND command and the ground. Each run gets a freshly
# restarted simulator with one vehicle, about 6 to 7 minutes. The default grid is 2 speeds x 2
# delays x 3 runs = 12 runs. Needs the image from `make sim-build`. Runs already recorded are
# skipped, so it can be restarted.
#
#   sim/record_land_diagnosis.sh
#   SPEEDS="5" DELAYS="5" RUNS=2 sim/record_land_diagnosis.sh
#
# Summary: python -m eval.land_diagnosis tests/replay/data/experiments/land-diagnosis
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="${IMAGE:-nav-trust-c2-sim}"
OUT_DIR="${OUT_DIR:-tests/replay/data/experiments/land-diagnosis}"
SPEEDS="${SPEEDS:-5 12}"
DELAYS="${DELAYS:-5 30}"
RUNS="${RUNS:-3}"
MAX_DURATION="${MAX_DURATION:-220}"

docker rm -f "${IMAGE}" >/dev/null 2>&1 || true
docker run -d --name "${IMAGE}" -v "$PWD":/workspaces/nav-trust-c2 -e NUM_VEHICLES=1 "${IMAGE}" >/dev/null
mkdir -p "${OUT_DIR}"
failures=()

for speed in ${SPEEDS}; do
    for delay in ${DELAYS}; do
        for run in $(seq 1 "${RUNS}"); do
            name="stuck-land-v${speed}-d${delay}-${run}"
            out="${OUT_DIR}/${name}.jsonl"
            [ -s "${out}" ] && { echo "=== ${name} already recorded"; continue; }
            echo "=== ${name}"
            docker restart "${IMAGE}" >/dev/null
            sleep 90
            if ! docker exec -w /workspaces/nav-trust-c2 "${IMAGE}" \
                python -m sim.record_run --scenario "${name}" --out "${out}" \
                --mode stuck --zone 200 -50 280 150 --latch-fault \
                --width 600 --height 100 --spacing 100 --altitude 30 --speed "${speed}" \
                --max-duration "${MAX_DURATION}" --log-flight-mode \
                --operator-action land --operator-delay "${delay}"; then
                echo "!!! ${name} failed"
                rm -f "${out}"
                failures+=("${name}")
            fi
        done
    done
done

docker stop "${IMAGE}" >/dev/null
echo "recordings written to ${OUT_DIR}"
if [ "${#failures[@]}" -gt 0 ]; then
    echo "FAILED RUNS: ${failures[*]}"
    exit 1
fi
