# PX4 SITL + Gazebo (gz, headless) + MAVSDK-Python. Linux host recommended.
#
# Why not px4io/px4-dev: per the PX4 docs it is the NuttX build image and has no Gazebo;
# a px4-sim image is announced there but not published, so we install Gazebo through
# PX4's own Tools/setup/ubuntu.sh at a pinned PX4 commit.
FROM ubuntu:26.04

# PX4 main commit, not a release: GPS failure injection for Gazebo (gz) exists only on main
# (v1.17.0 and v1.18.0-rc1 do not handle it, the command times out). Move to the first
# release tag that contains gz_bridge failure_injection::process_gnss once one exists.
ARG PX4_REF=a427a2e3feee2d5bbcf286feabaea0adc92554d5
# Compile jobs. Low default: Docker Desktop VMs often have ~4 GB and gcc gets OOM-killed.
ARG BUILD_JOBS=2

ENV DEBIAN_FRONTEND=noninteractive \
    RUNS_IN_DOCKER=true \
    PX4_DIR=/opt/PX4-Autopilot

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git sudo wget lsb-release gnupg make python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN git init "${PX4_DIR}" \
    && git -C "${PX4_DIR}" remote add origin https://github.com/PX4/PX4-Autopilot.git \
    && git -C "${PX4_DIR}" fetch --depth 1 origin "${PX4_REF}" \
    && git -C "${PX4_DIR}" checkout --quiet FETCH_HEAD \
    && git -C "${PX4_DIR}" submodule update --init --recursive --depth 1

WORKDIR ${PX4_DIR}
# --no-nuttx: skip the ARM toolchain, we only need the simulation target.
RUN bash Tools/setup/ubuntu.sh --no-nuttx \
    && rm -rf /var/lib/apt/lists/*
RUN make -j"${BUILD_JOBS}" px4_sitl_default

# Project tooling lives in its own venv so it never touches PX4's system Python packages.
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir "mavsdk-grpc==4.0.5" "fastapi>=0.115" "uvicorn[standard]>=0.30" "httpx>=0.27" "pyyaml>=6"
ENV PATH=/opt/venv/bin:${PATH}

COPY sim/docker/run_sitl.sh /usr/local/bin/run_sitl.sh
RUN chmod +x /usr/local/bin/run_sitl.sh

WORKDIR /workspaces/nav-trust-c2
CMD ["run_sitl.sh"]
