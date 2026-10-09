"""Sanity checks on the committed recordings. These guard the data the trust-engine replay
tests (NT-01, NT-02) will rely on; they say nothing about the engine itself."""

from pathlib import Path

import pytest

from navtrust.recording import Recording, load_recording

DATA = Path(__file__).parent / "data"
FILES = sorted(DATA.glob("*.jsonl"))


def test_recordings_exist() -> None:
    assert any(f.name.startswith("nominal") for f in FILES)
    assert any(f.name.startswith("jamming_zone") for f in FILES)


@pytest.fixture(params=FILES, ids=lambda p: p.stem)
def recording(request: pytest.FixtureRequest) -> Recording:
    return load_recording(request.param)


def test_run_completed(recording: Recording) -> None:
    finished, landed = recording.first("mission_finished"), recording.first("landed")
    assert finished is not None and landed is not None
    assert landed["t_s"] > finished["t_s"]


def test_estimator_status_is_sampled_throughout(recording: Recording) -> None:
    est = recording.of("estimator_status")
    assert len(est) > 100
    # vel_ratio is absent while the estimator is not fusing GPS velocity (long outage)
    assert all(0.0 <= e["vel_ratio"] < 10 for e in est if "vel_ratio" in e)
    assert sum("vel_ratio" in e for e in est) > 0.95 * len(est)


def test_nominal_keeps_its_fix(recording: Recording) -> None:
    if recording.header["zone"] is not None:
        pytest.skip("not a nominal run")
    assert recording.of("gnss_enter") == []
    assert {g["fix_type"] for g in recording.of("gps_info")} <= {"FIX_3D"}


def test_jamming_loses_and_regains_the_fix(recording: Recording) -> None:
    if recording.header["zone"] is None:
        pytest.skip("not a jamming run")
    enters, exits = recording.of("gnss_enter"), recording.of("gnss_exit")
    assert enters and len(enters) == len(exits)
    gps = recording.of("gps_info")
    for enter, leave in zip(enters, exits, strict=True):
        lost = [g for g in gps if enter["t_s"] <= g["t_s"] <= enter["t_s"] + 3]
        back = [g for g in gps if leave["t_s"] <= g["t_s"] <= leave["t_s"] + 1]
        assert lost and lost[0]["fix_type"] == "NO_GPS"
        assert back and back[0]["fix_type"] == "FIX_3D"
