import json

import pytest

pytest.importorskip("mavsdk_grpc")

from sim.record_run import build_header, parse_args, parse_estimator_status  # noqa: E402


def test_estimator_status_keeps_known_fields_and_drops_nulls() -> None:
    msg = json.dumps(
        {
            "message_id": 230,
            "vel_ratio": 0.01,
            "pos_horiz_ratio": 0.004,
            "hagl_ratio": None,
            "tas_ratio": None,
            "time_usec": 5,
            "flags": 959,
        }
    )
    assert parse_estimator_status(msg) == {
        "vel_ratio": 0.01,
        "pos_horiz_ratio": 0.004,
        "flags": 959,
    }


def test_header_without_zone() -> None:
    header = build_header(parse_args(["--scenario", "nominal"]))
    assert header["zone"] is None and header["failure_mode"] is None
    assert header["survey"]["width_m"] == 1000.0


def test_header_with_zone_and_default_output_path() -> None:
    args = parse_args(["--scenario", "jamming_zone", "--zone", "400", "-50", "440", "300"])
    assert args.out == "tests/replay/data/jamming_zone.jsonl"
    header = build_header(args)
    assert header["zone"] == {"west": 400.0, "south": -50.0, "east": 440.0, "north": 300.0}
    assert header["failure_mode"] == "off"
