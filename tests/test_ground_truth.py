import asyncio
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mavsdk_grpc")

from sim.fly_survey import JsonlLog  # noqa: E402
from sim.ground_truth import gz_command, log_ground_truth, parse_poses  # noqa: E402


def message(sec: int, nsec: int, poses: dict[str, tuple[float, float, float]]) -> str:
    return json.dumps(
        {
            "header": {"stamp": {"sec": str(sec), "nsec": nsec}},
            "pose": [
                {"name": n, "id": i, "position": {"x": x, "y": y, "z": z}}
                for i, (n, (x, y, z)) in enumerate(poses.items())
            ],
        }
    )


def test_parse_keeps_only_vehicle_models_and_reads_the_sim_time() -> None:
    line = message(
        111,
        624_000_000,
        {
            "x500_2": (0.0, 5.0, -0.013),
            "base_link": (1, 2, 3),
            "x500_1": (10.5, 20.5, 30.0),
            "ground_plane": (0, 0, 0),
        },
    )
    sim_s, poses = parse_poses(line)
    assert sim_s == pytest.approx(111.624)
    assert poses == {"uav2": (0.0, 5.0, -0.013), "uav1": (10.5, 20.5, 30.0)}


def test_parse_tolerates_a_missing_header_and_rejects_garbage() -> None:
    assert parse_poses('{"pose": []}') == (0.0, {})
    with pytest.raises(ValueError):
        parse_poses("not json")


def test_gz_command_reads_the_dynamic_pose_topic_as_json() -> None:
    cmd = gz_command()
    assert cmd[:2] == ["gz", "topic"] and "--json-output" in cmd
    assert "/world/default/dynamic_pose/info" in cmd


def test_logging_downsamples_by_sim_time_and_skips_bad_lines(tmp_path: Path) -> None:
    lines = [
        message(10, 0, {"x500_1": (1.0, 2.0, 3.0)}),
        "{ broken",
        message(10, 200_000_000, {"x500_1": (9.0, 9.0, 9.0)}),  # within 0.5 s: dropped
        message(10, 600_000_000, {"x500_1": (4.0, 5.0, 6.0)}),
        message(11, 200_000_000, {"x500_2": (0.0, 5.0, 0.0)}),  # not a requested vehicle
    ]
    script = "import sys\nfor l in sys.argv[1:]:\n    print(l)\n"
    log = JsonlLog(tmp_path / "t.jsonl")
    asyncio.run(log_ground_truth(log, ["uav1"], 0.5, [sys.executable, "-c", script, *lines]))
    log.close()
    rows = [json.loads(r) for r in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert [(r["event"], r["east_m"], r["north_m"], r["alt_m"]) for r in rows] == [
        ("truth", 1.0, 2.0, 3.0),
        ("truth", 4.0, 5.0, 6.0),
    ]
    assert rows[0]["vehicle"] == "uav1" and rows[1]["sim_s"] == pytest.approx(10.6)
