"""The backend and the trust engine do not depend on the simulator package (issue 177), and the
trust engine does not depend on the backend (issue 181).

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


# a lower layer never imports a higher one: the trust engine, then the backend, then the simulator
FORBIDDEN = {"navtrust": ("c2", "sim"), "c2": ("sim",)}


def layering_violations(root: Path) -> list[str]:
    offenders = []
    for folder, forbidden in FORBIDDEN.items():
        for path in sorted((root / folder).rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                for name in imported_modules(node):
                    if any(name == f or name.startswith(f + ".") for f in forbidden):
                        offenders.append(f"{path.relative_to(root)}:{getattr(node, 'lineno', 0)}")
    return offenders


def test_no_lower_layer_imports_a_higher_one() -> None:
    assert layering_violations(ROOT) == []


def test_a_violating_import_is_reported_and_a_permitted_one_is_not(tmp_path: Path) -> None:
    for folder in ("navtrust", "c2"):
        (tmp_path / folder).mkdir()
    (tmp_path / "navtrust" / "engine.py").write_text("import c2.hub\n", encoding="utf-8")
    (tmp_path / "c2" / "server.py").write_text("from sim.backend import run\n", encoding="utf-8")
    (tmp_path / "c2" / "hub.py").write_text("from navtrust.engine import X\n", encoding="utf-8")
    assert layering_violations(tmp_path) == ["navtrust/engine.py:1", "c2/server.py:1"]


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
