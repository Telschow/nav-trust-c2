import pytest

from navtrust import NavTrust, ReasonCode, TrustState


def make(**overrides: object) -> NavTrust:
    base: dict[str, object] = {
        "vehicle_id": "uav1",
        "stamp_s": 0.0,
        "state": TrustState.GREEN,
        "reason": None,
        "horizontal_bound_m": 2.0,
        "confidence": 0.95,
    }
    base.update(overrides)
    return NavTrust(**base)  # type: ignore[arg-type]


def test_valid_message() -> None:
    msg = make(state=TrustState.RED, reason=ReasonCode.GNSS_LOSS)
    assert msg.state is TrustState.RED
    assert msg.reason is ReasonCode.GNSS_LOSS


@pytest.mark.parametrize("bad", [{"horizontal_bound_m": -1.0}, {"confidence": 1.5}])
def test_rejects_out_of_range_values(bad: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        make(**bad)


def test_state_names_match_icd() -> None:
    assert [s.value for s in TrustState] == ["GREEN", "AMBER", "RED"]
    assert {r.value for r in ReasonCode} == {
        "GNSS_LOSS",
        "INCONSISTENT_INNOVATION",
        "BIAS_DRIFT",
        "STALE",
    }
