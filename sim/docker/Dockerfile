# PX4 SITL + Gazebo (gz, headless) + MAVSDK-Python. Linux host recommended.
#
# Why not px4io/px4-dev: per the PX4 docs it is the NuttX build image and has no Gazebo;
# a px4-sim image is announced there but not published, so we install Gazebo through
# PX4's own Tools/setup/ubuntu.sh at a pinned PX4 tag.
FROM ubuntu:24.04

ARG PX4_VERSION=v1.17.0

ENV DEBIAN_FRONTEND=noninteractive \
    RUNS_IN_DOCKER=true \
    PX4_DIR=/opt/PX4-Autopilot

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git sudo wget lsb-release gnupg make python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${PX4_VERSION}" --recurse-submodules --shallow-submodules \
        https://github.com/PX4/PX4-Autopilot.git "${PX4_DIR}"

WORKDIR ${PX4_DIR}
# --no-nuttx: skip the ARM toolchain, we only need the simulation target.
RUN bash Tools/setup/ubuntu.sh --no-nuttx \
    && rm -rf /var/lib/apt/lists/*
RUN make px4_sitl_default

# Project tooling lives in its own venv so it never touches PX4's system Python packages.
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir "mavsdk-grpc==4.0.5"
ENV PATH=/opt/venv/bin:${PATH}

COPY sim/docker/run_sitl.sh /usr/local/bin/run_sitl.sh
RUN chmod +x /usr/local/bin/run_sitl.sh

WORKDIR /workspaces/nav-trust-c2
CMD ["run_sitl.sh"]
