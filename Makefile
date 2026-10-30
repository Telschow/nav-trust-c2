IMAGE ?= nav-trust-c2-sim
VEHICLES ?= 1

.PHONY: scenario record-all record-lost-link eval-lost-link eval help check lint typecheck test sim-build sim-up sim-down fly fleet backend console console-dev demo

help:
	@echo "scenario    record one scenario run in the running sim: make scenario NAME=stuck_position RUN=1"
	@echo "record-all  record every run of every scenario, then the link_loss family (6 to 7 min per run, restarts the sim each run)"
	@echo "record-lost-link  only the link_loss family, scenarios/lost_link"
	@echo "eval-lost-link    regenerate eval/lost_link/results.md from its recordings"
	@echo "eval        regenerate eval/results.json and eval/results.md, and the link_loss table, from the recordings"
	@echo "check       ruff + mypy + pytest (no simulator needed)"
	@echo "sim-build   build the PX4 SITL + Gazebo image (long, first time only)"
	@echo "sim-up      start headless SITL, VEHICLES=n"
	@echo "sim-down    stop it"
	@echo "fleet       fly the survey with VEHICLES vehicles (needs sim-up VEHICLES=n)"
	@echo "console     build the operator console (needs Node 22+)"
	@echo "console-dev run the console with hot reload on :5173 (backend on :8000)"
	@echo "demo        backend + console + replayed demo data, no simulator (open :8000)"
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

console:
	cd console && npm ci && npm run build

console-dev:
	cd console && npm run dev

# The demo feed replays recorded trust data with synthetic positions; the console labels it so.
demo: console demo-run

# Same without rebuilding the console. One database per session: make demo-run DEMO_DB=logs/usability/P1.sqlite
DEMO_DB ?= logs/audit-demo.sqlite
DEMO_SCENARIO ?= stuck
demo-run:
	mkdir -p $(dir $(DEMO_DB))
	python -m c2.server --db $(DEMO_DB) --source "REPLAY DEMO" & SERVER=$$!; trap "kill $$SERVER" EXIT INT TERM; \
	sleep 3; python -m sim.demo_feed --speed 5 --scenario $(DEMO_SCENARIO)

scenario:
	docker exec -w /workspaces/nav-trust-c2 $(IMAGE) python -m sim.run_scenario $(NAME) --run $(or $(RUN),1)

record-all:
	sim/record_all.sh
	$(MAKE) record-lost-link

# The link_loss family (issue 75): link cuts, a link that flaps, an operator who never answers.
record-lost-link:
	SCENARIO_DIR=scenarios/lost_link OUT_DIR=eval/lost_link/recordings sim/record_all.sh

# Regenerate the link_loss table from its recordings; CI fails if the committed one differs.
eval-lost-link:
	python -m eval.link_loss eval/lost_link/recordings --write eval/lost_link/results.md

eval:
	python -m eval.evaluate
	$(MAKE) eval-lost-link

record-heldout:
	SCENARIO_DIR=scenarios/heldout OUT_DIR=eval/heldout/recordings sim/record_all.sh

eval-heldout:
	python -m eval.evaluate --heldout

# Fleet mission completion (M-04): three vehicles, one lost, scripted operator. About 80 minutes.
record-fleet:
	sim/record_fleet_all.sh   # OPERATOR_DELAY=<s> sets the scripted operator delay (default 15)

eval-fleet:
	python -m eval.fleet
