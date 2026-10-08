IMAGE ?= nav-trust-c2-sim
VEHICLES ?= 1

.PHONY: help check lint typecheck test sim-build sim-up sim-down fly

help:
	@echo "check       ruff + mypy + pytest (no simulator needed)"
	@echo "sim-build   build the PX4 SITL + Gazebo image (long, first time only)"
	@echo "sim-up      start headless SITL, VEHICLES=n (Linux host, host networking)"
	@echo "sim-down    stop it"
	@echo "fly         fly the 1 x 1 km survey against vehicle 1 (needs sim-up)"

check: lint typecheck test

lint:
	ruff check .
	ruff format --check .

typecheck:
	mypy

test:
	pytest

sim-build:
	docker build -f sim/docker/Dockerfile -t $(IMAGE) .

# Host networking: PX4 sends MAVLink to 127.0.0.1:14540+i, so MAVSDK must share the namespace.
sim-up:
	docker run -d --rm --name $(IMAGE) --network host -e NUM_VEHICLES=$(VEHICLES) $(IMAGE)

sim-down:
	docker stop $(IMAGE)

fly:
	python -m sim.fly_survey
