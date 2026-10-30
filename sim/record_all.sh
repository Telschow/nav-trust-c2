#!/usr/bin/env bash
# Record every run of every scenario, each against a freshly restarted simulator with one
# vehicle. Takes about 6 to 7 minutes per run. Needs the image from `make sim-build`.
#
#   sim/record_all.sh            all scenarios
#   sim/record_all.sh stuck_position    one scenario
#   SCENARIO_DIR=scenarios/heldout OUT_DIR=eval/heldout/recordings sim/record_all.sh    held-out set
#   RESUME=1 sim/record_all.sh   skip runs that already have a recording (make record-lost-link)
#
# A run is recorded into a scratch directory and moved into place only if it succeeded, so a
# failed run never leaves a truncated file or overwrites a recording you already have.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="${IMAGE:-nav-trust-c2-sim}"
SCENARIO_DIR="${SCENARIO_DIR:-scenarios}"
OUT_DIR="${OUT_DIR:-eval/recordings}"
ONLY="${1:-}"
RESUME="${RESUME:-}"
PARTIAL="${OUT_DIR}/.partial"

docker rm -f "${IMAGE}" >/dev/null 2>&1 || true
docker run -d --name "${IMAGE}" -v "$PWD":/workspaces/nav-trust-c2 -e NUM_VEHICLES=1 "${IMAGE}" >/dev/null
mkdir -p "${OUT_DIR}"
failures=()

while read -r name runs; do
    [ -n "${ONLY}" ] && [ "${ONLY}" != "${name}" ] && continue
    for run in $(seq 1 "${runs}"); do
        final="${OUT_DIR}/${name}-${run}.jsonl"
        if [ -n "${RESUME}" ] && [ -s "${final}" ]; then
            echo "=== ${name} run ${run}/${runs} already recorded"
            continue
        fi
        echo "=== ${name} run ${run}/${runs}"
        rm -rf "${PARTIAL}"
        mkdir -p "${PARTIAL}"
        docker restart "${IMAGE}" >/dev/null
        sleep 90
        if docker exec -w /workspaces/nav-trust-c2 "${IMAGE}" \
            python -m sim.run_scenario "${name}" --run "${run}" \
            --scenarios "${SCENARIO_DIR}" --out "${PARTIAL}"; then
            mv "${PARTIAL}/${name}-${run}.jsonl" "${final}"
        else
            echo "!!! ${name} run ${run} failed"
            failures+=("${name}-${run}")
        fi
        rm -rf "${PARTIAL}"
    done
done < <(python -m sim.run_scenario --list --scenarios "${SCENARIO_DIR}")

docker stop "${IMAGE}" >/dev/null
echo "recordings written to ${OUT_DIR}"
if [ "${#failures[@]}" -gt 0 ]; then
    echo "FAILED RUNS: ${failures[*]}"
    exit 1
fi
