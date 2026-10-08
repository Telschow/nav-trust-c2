#!/usr/bin/env bash
# Start NUM_VEHICLES PX4 SITL instances (x500) against one headless Gazebo world.
#
# Mirrors the multi-vehicle recipe in the PX4 docs: instance 1 starts the Gazebo server,
# later instances attach in standalone mode. Instance i exposes MAVLink for MAVSDK on
# UDP 14540+i (see ROMFS/px4fmu_common/init.d-posix/px4-rc.mavlink).
#
# Env: NUM_VEHICLES (default 1), SPAWN_SPACING_M (default 5), PX4_DIR, PX4_GZ_WORLD,
#      PX4_HOME_LAT / PX4_HOME_LON / PX4_HOME_ALT (all three or none).
set -euo pipefail

NUM_VEHICLES="${NUM_VEHICLES:-1}"
SPAWN_SPACING_M="${SPAWN_SPACING_M:-5}"
PX4_DIR="${PX4_DIR:-/opt/PX4-Autopilot}"
PX4_BIN="${PX4_DIR}/build/px4_sitl_default/bin/px4"
LOG_DIR="${LOG_DIR:-/tmp/px4-logs}"

export HEADLESS=1
export GZ_IP=127.0.0.1
export PX4_SIM_MODEL=gz_x500
export PX4_SYS_AUTOSTART=4001

mkdir -p "${LOG_DIR}"
pids=()
cleanup() {
    for pid in "${pids[@]}"; do kill "${pid}" 2>/dev/null || true; done
    pkill -f "gz sim" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for i in $(seq 1 "${NUM_VEHICLES}"); do
    if [ "${i}" -eq 1 ]; then
        "${PX4_BIN}" -d -i 1 >"${LOG_DIR}/px4_1.log" 2>&1 &
        pids+=("$!")
        echo "waiting for the Gazebo world"
        for _ in $(seq 1 60); do
            gz topic -l 2>/dev/null | grep -q "^/world/.*/clock" && break
            sleep 1
        done
    else
        y=$(( (i - 1) * SPAWN_SPACING_M ))
        PX4_GZ_STANDALONE=1 PX4_GZ_MODEL_POSE="0,${y}" \
            "${PX4_BIN}" -d -i "${i}" >"${LOG_DIR}/px4_${i}.log" 2>&1 &
        pids+=("$!")
    fi
    echo "started vehicle ${i}: MAVSDK address udpin://0.0.0.0:$((14540 + i)), log ${LOG_DIR}/px4_${i}.log"
done

wait
