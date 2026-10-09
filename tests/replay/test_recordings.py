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
    if recording.first("recording_stopped"):
        pytest.skip("deliberately stopped early")
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


# What the receiver reports a moment after a zone entry, per failure mode (PX4 gz, measured).
EXPECTED_FIX_IN_ZONE = {"off": "NO_GPS", "wrong": "FIX_2D", "stuck": None}


def test_zone_runs_change_the_fix_as_the_failure_mode_implies(recording: Recording) -> None:
    mode = recording.header["failure_mode"]
    if mode is None:
        pytest.skip("not a zone run")
    enters = recording.of("gnss_enter")
    assert enters
    gps = recording.of("gps_info")
    expected = EXPECTED_FIX_IN_ZONE[mode]
    if expected is None:
        # stuck: the receiver keeps reporting a fix; only the position is frozen
        assert {g["fix_type"] for g in gps} == {"FIX_3D"}
        return
    exits = recording.of("gnss_exit")
    assert len(enters) == len(exits)
    for enter, leave in zip(enters, exits, strict=True):
        lost = [g for g in gps if enter["t_s"] <= g["t_s"] <= enter["t_s"] + 3]
        back = [g for g in gps if leave["t_s"] <= g["t_s"] <= leave["t_s"] + 1]
        assert lost and lost[0]["fix_type"] == expected
        assert back and back[0]["fix_type"] == "FIX_3D"
