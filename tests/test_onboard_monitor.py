"""Issue 76, ADR 0004 item 3: the vehicle acts only when the link has been down longer than the
policy's wait time, the trust reason matches an entry and the policy is still valid."""

from navtrust.types import NavTrust, ReasonCode, TrustState
from sim.onboard_monitor import OnboardMonitor
from sim.onboard_policy import load_policy, policy_sha256

POLICY_DOC = {
    "entries": [{"reason": "INCONSISTENT_INNOVATION", "link": "NO_LINK", "action": "LAND"}],
    "wait_s": 5.0,
}
MAX_AGE_S = 3600.0


def policy(max_age_s: float = MAX_AGE_S):  # type: ignore[no-untyped-def]
    record = {
        "audit_id": 7,
        "approved_s": 100.0,
        "sha256": policy_sha256(POLICY_DOC),
        "policy": POLICY_DOC,
    }
    return load_policy(record, now_s=110.0, max_age_s=max_age_s)


def trust(t: float, state: TrustState, reason: ReasonCode | None) -> NavTrust:
    bound = 0.15 if state is TrustState.GREEN else float("inf")
    return NavTrust("uav1", t, state, reason, bound, 1.0)


FROZEN = (TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION)


def monitor(**kw: float) -> OnboardMonitor:
    return OnboardMonitor("uav1", policy(**kw), started_s=0.0)


def frozen_with_link_lost_at(m: OnboardMonitor, lost_at: float) -> None:
    """C2 is heard until `lost_at`; trust is RED for a frozen position from 3 s before it."""
    for t in range(0, int(lost_at) + 1):
        m.c2_heard(float(t))
        m.trust(
            float(t),
            trust(float(t), *FROZEN)
            if t >= lost_at - 3
            else trust(float(t), TrustState.GREEN, None),
        )


def feed_until(m: OnboardMonitor, start: float, end: float):  # type: ignore[no-untyped-def]
    for t10 in range(int(start * 10), int(end * 10) + 1):
        t = t10 / 10
        m.trust(t, trust(t, *FROZEN))
        action = m.poll(t)
        if action is not None:
            return action
    return None


def test_it_acts_once_the_link_has_been_down_longer_than_the_wait() -> None:
    m = monitor()
    frozen_with_link_lost_at(m, 20.0)
    action = feed_until(m, 20.1, 40.0)
    assert action is not None and action.action == "LAND"
    assert 25.0 < action.t_s <= 25.2  # last heard at 20 s, wait 5 s
    assert action.reason == "INCONSISTENT_INNOVATION" and action.vehicle_id == "uav1"
    assert (action.policy_audit_id, action.policy_sha256) == (7, policy_sha256(POLICY_DOC))
    assert 5.0 < action.link_down_s <= 5.2


def test_it_does_nothing_while_the_link_is_up_even_if_the_position_is_inconsistent() -> None:
    m = monitor()
    for t in range(0, 60):
        m.c2_heard(float(t))
        m.trust(float(t), trust(float(t), *FROZEN))
        assert m.poll(float(t)) is None


def test_a_link_drop_shorter_than_the_wait_does_nothing_and_resets() -> None:
    m = monitor()
    frozen_with_link_lost_at(m, 20.0)
    assert feed_until(m, 20.1, 24.0) is None  # down for 4 s
    m.c2_heard(24.5)
    assert feed_until(m, 24.6, 29.0) is None  # a new drop starts from the last contact


def test_no_matching_entry_means_no_action() -> None:
    m = monitor()
    frozen_with_link_lost_at(m, 20.0)
    for t10 in range(201, 600):
        t = t10 / 10
        m.trust(t, trust(t, TrustState.RED, ReasonCode.GNSS_LOSS))  # not in the policy
        assert m.poll(t) is None


def test_amber_is_not_enough() -> None:
    m = monitor()
    frozen_with_link_lost_at(m, 20.0)
    for t10 in range(201, 600):
        t = t10 / 10
        m.trust(t, trust(t, TrustState.AMBER, ReasonCode.INCONSISTENT_INNOVATION))
        assert m.poll(t) is None


def test_an_expired_policy_means_no_action() -> None:
    m = monitor(
        max_age_s=100.0 + 30.0
    )  # 10 s old at load; expires 120 s later on the vehicle clock
    frozen_with_link_lost_at(m, 200.0)
    assert feed_until(m, 200.1, 230.0) is None


def test_it_acts_once_and_remembers_what_it_did_until_it_is_reported() -> None:
    m = monitor()
    frozen_with_link_lost_at(m, 20.0)
    action = feed_until(m, 20.1, 40.0)
    assert action is not None
    assert feed_until(m, action.t_s + 0.1, action.t_s + 30.0) is None  # never repeats
    assert m.take_unreported() == [action]
    assert m.take_unreported() == []


def test_stale_trust_is_not_acted_on() -> None:
    m = monitor()
    frozen_with_link_lost_at(m, 20.0)
    m.trust(21.0, trust(21.0, *FROZEN))
    assert m.poll(30.0) is None  # the last report is 9 s old: the engine has gone quiet


def test_before_any_trust_report_it_does_nothing() -> None:
    m = monitor()
    assert m.poll(100.0) is None
