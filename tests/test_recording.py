import json
from pathlib import Path

import pytest

from navtrust.recording import load_recording


def write(path: Path, records: list[dict[str, object]]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


HEADER = {"t_s": 0.0, "event": "header", "schema": 1, "scenario": "x"}


def test_loads_header_and_filters_events(tmp_path: Path) -> None:
    rec = load_recording(
        write(
            tmp_path / "a.jsonl",
            [
                HEADER,
                {"t_s": 1.0, "event": "estimator_status", "vel_ratio": 0.1},
                {"t_s": 2.0, "event": "gps_info", "fix_type": "FIX_3D"},
                {"t_s": 3.0, "event": "estimator_status", "vel_ratio": 0.2},
            ],
        )
    )
    assert rec.header["scenario"] == "x"
    assert [r["vel_ratio"] for r in rec.of("estimator_status")] == [0.1, 0.2]
    first = rec.first("gps_info")
    assert first is not None and first["fix_type"] == "FIX_3D"
    assert rec.first("landed") is None


@pytest.mark.parametrize(
    "records",
    [
        [{"t_s": 0.0, "event": "position"}],
        [{**HEADER, "schema": 99}],
        [HEADER, {"t_s": 5.0, "event": "a"}, {"t_s": 4.0, "event": "b"}],
    ],
)
def test_rejects_bad_files(tmp_path: Path, records: list[dict[str, object]]) -> None:
    with pytest.raises(ValueError):
        load_recording(write(tmp_path / "bad.jsonl", records))
