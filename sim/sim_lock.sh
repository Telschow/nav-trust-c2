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
