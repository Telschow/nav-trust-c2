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

# A recording counts as done only if it is complete: the recorder writes recording_stopped last,
# so a file cut short by a failed run or a killed script is recorded again, not skipped.
is_complete() {
    [ -s "$1" ] && grep -q '"event": "recording_stopped"' "$1"
}
