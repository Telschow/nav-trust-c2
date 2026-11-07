# Sourced by the simulator recording scripts (sim/record_*.sh).
#
# They all restart the one container named by $IMAGE, so two of them running at once kill each
# other's simulator and slow it down: runs fail with "Address in use", "Busy" or "Socket closed",
# and runs that survive have a simulation clock out of step with the wall clock. Run them one at
# a time. The lock is a directory because mkdir is atomic (macOS has no flock).
LOCK="${TMPDIR:-/tmp}/nav-trust-c2-sim.lock"
if ! mkdir "${LOCK}" 2>/dev/null; then
    echo "Another simulator recording script is running (lock: ${LOCK})." >&2
    echo "Run them one at a time. If none is running, remove the lock: rmdir ${LOCK}" >&2
    exit 2
fi
trap 'rmdir "${LOCK}" 2>/dev/null' EXIT

# The machine must be quiet too: another container using many cores starved the simulator and
# gave runs with no ground truth (issue 176). SIM_PREFLIGHT=off records anyway; the limits are
# SIM_MAX_OTHER_CPU (percent of a core) and SIM_MAX_LOAD (see sim/preflight.py).
python3 -m sim.preflight || exit 3

# A recording counts as done only if it is complete (see sim/recording_check.py): it ends the way
# a finished run does and carries ground truth if it was meant to. A file cut short by a failed run
# or a killed script, or one whose Gazebo stream gave nothing, is recorded again, not skipped.
is_complete() {
    python3 -m sim.recording_check "$1" 2>/dev/null
}

# The recorder sometimes writes a complete recording and then does not exit (issue 178). It gets
# its maximum duration plus RECORDER_MARGIN seconds (default 180, a proposal: the connect, takeoff
# and shutdown around the flight are not measured). At the limit a complete partial file is kept
# and the recorder ended; an incomplete one is discarded (sim/finish_recording.py).
#
#   record_one NAME OUT MAX_DURATION COMMAND...    COMMAND writes OUT.partial
#
# Call it as `record_one ... || true` (or in an `if`): it returns 1 on a failed run, which `set -e`
# would turn into an exit. Returns 0 if a recording was kept. Otherwise it adds NAME to `failures` and returns 1. A rescued
# run is added to `rescued` and reported by `report_outcome`. The caller sets `failures=()` and IMAGE.
rescued=()
record_one() {
    local name="$1" out="$2" max="$3" rc=0
    shift 3
    python3 -m sim.finish_recording --partial "${out}.partial" --final "${out}" \
        --limit $((max + ${RECORDER_MARGIN:-180})) \
        --stop "docker exec ${IMAGE} pkill -9 -f sim.record_run" -- "$@" || rc=$?
    case "${rc}" in  # 10 is RESCUED_EXIT_CODE in sim/finish_recording.py
        0) ;;
        10) rescued+=("${name}") ;;
        *)
            echo "!!! ${name} failed"
            failures+=("${name}")
            return 1
            ;;
    esac
}

# The end of every script: say which runs were rescued and which failed, and exit 1 on a failure.
report_outcome() {
    if [ "${#rescued[@]}" -gt 0 ]; then
        echo "RESCUED RUNS (the recorder did not exit, the recording was complete): ${rescued[*]}"
    fi
    if [ "${#failures[@]}" -gt 0 ]; then
        echo "FAILED RUNS: ${failures[*]}"
        exit 1
    fi
}

# After `docker restart "${IMAGE}"`: wait until the simulator is ready (sim/wait_ready.py) instead
# of sleeping a fixed time. If it is not ready within SIM_READY_LIMIT seconds (default 240, a
# proposal), print the container's last log lines and stop the script with exit code 4 (the lock
# is released by the EXIT trap above).
#
#   wait_for_sim VEHICLES
wait_for_sim() {
    if ! docker exec -w /workspaces/nav-trust-c2 "${IMAGE}" \
        python -m sim.wait_ready --vehicles "$1" --limit "${SIM_READY_LIMIT:-240}"; then
        echo "!!! the simulator was not ready; the last lines of its log:" >&2
        docker logs --tail 30 "${IMAGE}" >&2 || true
        exit 4
    fi
}
