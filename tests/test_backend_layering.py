"""The backend and the trust engine do not depend on the simulator package (issue 177).

The backend imported a constant from the simulator package inside an endpoint, and its entry point
imported the MAVSDK executor. The limit now lives with the policy rules both sides share, and the
MAVSDK executor is registered by a launcher in the simulator package."""

import argparse
import ast
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from c2.dryrun import DryRunExecutor  # noqa: E402
from c2.fleet import FleetState  # noqa: E402
from c2.server import ExecutorFactory, build_app_from_args, parse_args  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def imported_modules(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0:
        return [node.module or ""]
    return []


def modules_importing_the_simulator() -> list[str]:
    offenders = []
    for folder in ("c2", "navtrust"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if any(n == "sim" or n.startswith("sim.") for n in imported_modules(node)):
                    offenders.append(f"{path.relative_to(ROOT)}:{getattr(node, 'lineno', 0)}")
    return offenders


def test_no_module_of_the_backend_or_the_trust_engine_imports_the_simulator_package() -> None:
    assert modules_importing_the_simulator() == []


def test_the_data_link_loss_limit_sits_with_the_policy_rules_that_must_stay_below_it() -> None:
    from c2.contingency import COM_DL_LOSS_T_S, land_on_inconsistent_position, validate_policy

    validate_policy(land_on_inconsistent_position(COM_DL_LOSS_T_S - 1), COM_DL_LOSS_T_S)
    with pytest.raises(ValueError):  # a wait at the limit would let PX4's own failsafe start first
        validate_policy(land_on_inconsistent_position(COM_DL_LOSS_T_S), COM_DL_LOSS_T_S)


def test_a_launcher_can_register_an_executor_the_backend_builds_for_its_fleet() -> None:
    built: list[FleetState] = []

    def factory(args: argparse.Namespace, fleet: FleetState) -> DryRunExecutor:
        built.append(fleet)
        return DryRunExecutor()

    executors: dict[str, ExecutorFactory] = {"fake": factory}
    args = parse_args(executors, ["--executor", "fake", "--db", ":memory:", "--console", "none"])
    app = build_app_from_args(args, executors)
    assert app is not None and len(built) == 1 and "uav1" in built[0].assignment


def test_the_plain_backend_offers_only_the_dry_run_executor() -> None:
    with pytest.raises(SystemExit):
        parse_args({}, ["--executor", "mavsdk"])
    assert parse_args({}, []).executor == "dryrun"


def test_the_simulator_launcher_registers_the_mavsdk_executor() -> None:
    pytest.importorskip("mavsdk_grpc")
    from sim.backend import mavsdk_executor
    from sim.executor import MavsdkExecutor

    executors: dict[str, ExecutorFactory] = {"mavsdk": mavsdk_executor}
    argv = ["--executor", "mavsdk", "--origin", "47.397971", "8.546164", "--db", ":memory:"]
    args = parse_args(executors, argv + ["--console", "none"])
    fleet = FleetState({})
    assert isinstance(mavsdk_executor(args, fleet), MavsdkExecutor)  # built, not connected
    assert build_app_from_args(args, executors) is not None
