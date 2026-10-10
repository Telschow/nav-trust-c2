#!/usr/bin/env bash
# Record every run of every scenario, each against a freshly restarted simulator with one
# vehicle. Takes about 6 to 7 minutes per run. Needs the image from `make sim-build`.
#
#   sim/record_all.sh            all scenarios
#   sim/record_all.sh stuck_position    one scenario
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="${IMAGE:-nav-trust-c2-sim}"
ONLY="${1:-}"

docker rm -f "${IMAGE}" >/dev/null 2>&1 || true
docker run -d --name "${IMAGE}" -v "$PWD":/workspaces/nav-trust-c2 -e NUM_VEHICLES=1 "${IMAGE}" >/dev/null
mkdir -p eval/recordings
failures=()

while read -r name runs; do
    [ -n "${ONLY}" ] && [ "${ONLY}" != "${name}" ] && continue
    for run in $(seq 1 "${runs}"); do
        echo "=== ${name} run ${run}/${runs}"
        docker restart "${IMAGE}" >/dev/null
        sleep 90
        if ! docker exec -w /workspaces/nav-trust-c2 "${IMAGE}" \
            python -m sim.run_scenario "${name}" --run "${run}"; then
            echo "!!! ${name} run ${run} failed"
            failures+=("${name}-${run}")
        fi
    done
done < <(python -m sim.run_scenario --list)

docker stop "${IMAGE}" >/dev/null
echo "recordings written to eval/recordings"
if [ "${#failures[@]}" -gt 0 ]; then
    echo "FAILED RUNS: ${failures[*]}"
    exit 1
fi
