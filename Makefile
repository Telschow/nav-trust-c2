IMAGE ?= nav-trust-c2-sim
VEHICLES ?= 1

.PHONY: help check lint typecheck test sim-build sim-up sim-down fly fleet backend

help:
	@echo "check       ruff + mypy + pytest (no simulator needed)"
	@echo "sim-build   build the PX4 SITL + Gazebo image (long, first time only)"
	@echo "sim-up      start headless SITL, VEHICLES=n"
	@echo "sim-down    stop it"
	@echo "fleet       fly the survey with VEHICLES vehicles (needs sim-up VEHICLES=n)"
	@echo "backend     run the C2 backend on localhost:8000 (needs the c2 extra)"
	@echo "fly         fly the 1 x 1 km survey against vehicle 1 inside the container (needs sim-up)"

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

# PX4 sends MAVLink to 127.0.0.1:14540+i inside the container, so MAVSDK runs there too
# (works on macOS Docker Desktop, where --network host does not reach the Mac).
sim-up:
	docker run -d --rm --name $(IMAGE) -v "$(CURDIR)":/workspaces/nav-trust-c2 \
		-e NUM_VEHICLES=$(VEHICLES) $(IMAGE)

sim-down:
	docker stop $(IMAGE)

# Extra flags go through ARGS, e.g. make fly ARGS="--width 100 --height 100"
fly:
	docker exec -w /workspaces/nav-trust-c2 $(IMAGE) python -m sim.fly_survey $(ARGS)

# Extra flags go through ARGS, e.g. make fleet ARGS="--width 300 --height 300"
fleet:
	docker exec -w /workspaces/nav-trust-c2 $(IMAGE) python -m sim.fly_fleet --vehicles $(VEHICLES) $(ARGS)

backend:
	python -m c2.server
