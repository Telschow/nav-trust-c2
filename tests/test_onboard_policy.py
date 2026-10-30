"""Issue 76, ADR 0004 items 1, 3 and 5: the contingency policy an operator approved before the
mission, and when the vehicle may rely on it."""

from typing import Any

import pytest

from sim.failsafe_params import COM_DL_LOSS_T_S
from sim.onboard_policy import Policy, PolicyRejected, load_policy, policy_sha256

LAND_ON_FROZEN: dict[str, Any] = {
    "entries": [{"reason": "INCONSISTENT_INNOVATION", "link": "NO_LINK", "action": "LAND"}],
    "wait_s": 5.0,
}
MAX_AGE_S = 4 * 3600.0


def approval(policy: dict[str, Any] | None = None, **over: Any) -> dict[str, Any]:
    policy = policy or LAND_ON_FROZEN
    record = {
        "audit_id": 7,
        "approved_s": 1000.0,
        "sha256": policy_sha256(policy),
        "policy": policy,
    }
    return {**record, **over}


def load(record: dict[str, Any], now_s: float = 1100.0) -> Policy:
    return load_policy(record, now_s=now_s, max_age_s=MAX_AGE_S)


def test_an_approved_policy_loads_with_its_audit_reference() -> None:
    policy = load(approval())
    assert policy.audit_id == 7 and policy.sha256 == policy_sha256(LAND_ON_FROZEN)
    assert policy.wait_s == 5.0


def test_a_matching_entry_is_found_only_for_its_reason_and_link_condition() -> None:
    policy = load(approval())
    assert policy.matches("INCONSISTENT_INNOVATION", "NO_LINK") is not None
    assert policy.matches("GNSS_LOSS", "NO_LINK") is None  # no entry: no action
    assert policy.matches("INCONSISTENT_INNOVATION", "LINK_OK") is None
    assert policy.matches(None, "NO_LINK") is None


def test_a_policy_with_no_entries_never_matches() -> None:
    policy = load(approval({"entries": [], "wait_s": 5.0}))
    assert policy.matches("INCONSISTENT_INNOVATION", "NO_LINK") is None


def test_the_hash_is_independent_of_key_order_and_layout() -> None:
    reordered = {
        "wait_s": 5.0,
        "entries": [{"action": "LAND", "link": "NO_LINK", "reason": "INCONSISTENT_INNOVATION"}],
    }
    assert policy_sha256(reordered) == policy_sha256(LAND_ON_FROZEN)


@pytest.mark.parametrize(
    ("record", "why"),
    [
        (approval(sha256="0" * 64), "hash"),  # no matching approval record
        (
            approval(
                policy={**LAND_ON_FROZEN, "wait_s": 6.0}, sha256=policy_sha256(LAND_ON_FROZEN)
            ),
            "hash",
        ),
        (approval(approved_s=1100.0 - MAX_AGE_S - 1), "expired"),
        (approval(approved_s=2000.0), "future"),  # approved after now: the clocks disagree
    ],
)
def test_a_policy_that_does_not_match_its_approval_or_is_too_old_is_refused(
    record: dict[str, Any], why: str
) -> None:
    with pytest.raises(PolicyRejected) as err:
        load(record)
    assert why in str(err.value)


def test_a_missing_approval_record_is_refused() -> None:
    with pytest.raises(PolicyRejected):
        load({"policy": LAND_ON_FROZEN})


@pytest.mark.parametrize("action", ["HOLD", "RTL", "land", "DISARM"])
def test_only_land_is_a_valid_action(action: str) -> None:
    policy = {
        "entries": [{"reason": "INCONSISTENT_INNOVATION", "link": "NO_LINK", "action": action}],
        "wait_s": 5.0,
    }
    with pytest.raises(PolicyRejected, match="LAND"):
        load(approval(policy))


@pytest.mark.parametrize("wait_s", [COM_DL_LOSS_T_S, COM_DL_LOSS_T_S + 5, 0, -1])
def test_the_wait_must_be_positive_and_shorter_than_px4s_data_link_loss_time(wait_s: float) -> None:
    with pytest.raises(PolicyRejected, match="wait"):
        load(approval({**LAND_ON_FROZEN, "wait_s": wait_s}))


def test_an_unknown_reason_or_link_condition_is_refused() -> None:
    bad = {"entries": [{"reason": "MOON", "link": "NO_LINK", "action": "LAND"}], "wait_s": 5.0}
    with pytest.raises(PolicyRejected):
        load(approval(bad))
    bad = {"entries": [{"reason": "STALE", "link": "SOMETIMES", "action": "LAND"}], "wait_s": 5.0}
    with pytest.raises(PolicyRejected):
        load(approval(bad))


def test_the_policy_ages_with_the_vehicles_own_clock_and_expires() -> None:
    policy = load(approval(), now_s=1100.0)  # approved 100 s before it was loaded
    assert policy.valid_at(local_s=50.0, loaded_local_s=50.0)
    assert policy.valid_at(local_s=50.0 + MAX_AGE_S - 101.0, loaded_local_s=50.0)
    assert not policy.valid_at(local_s=50.0 + MAX_AGE_S, loaded_local_s=50.0)
