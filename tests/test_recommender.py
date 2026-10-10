import pytest

from c2.allocator import assign, split_area
from c2.fleet import FleetState
from c2.messages import Command
from c2.recommender import Recommender, RecommenderConfig
from navtrust.types import NavTrust, ReasonCode, TrustState

POS = {"uav1": (0.0, 0.0), "uav2": (0.0, 5.0), "uav3": (0.0, 10.0)}


class Clock:
    t = 50.0

    def __call__(self) -> float:
        return self.t


def fleet() -> FleetState:
    return FleetState(
        assign(split_area(1000, 900, 3), ["uav1", "uav2", "uav3"]), positions=dict(POS)
    )


def msg(v: str, state: TrustState, reason: ReasonCode | None = None, t: float = 0.0) -> NavTrust:
    return NavTrust(v, t, state, reason, 0.15 if state is TrustState.GREEN else float("inf"), 1.0)


def green(r: Recommender, f: FleetState, *vs: str) -> None:
    for v in vs:
        assert r.observe(msg(v, TrustState.GREEN), f) == []


def make() -> tuple[Recommender, FleetState, Clock]:
    clock = Clock()
    r = Recommender(clock, RecommenderConfig(ttl_s=60.0))
    f = fleet()
    green(r, f, "uav1", "uav2", "uav3")
    return r, f, clock


def test_amber_recommends_nothing() -> None:
    r, f, _ = make()
    assert r.observe(msg("uav2", TrustState.AMBER, ReasonCode.GNSS_LOSS), f) == []


def test_red_gnss_loss_retasks_without_a_vehicle_command() -> None:
    r, f, clock = make()
    [rec] = r.observe(msg("uav2", TrustState.RED, ReasonCode.GNSS_LOSS), f)
    assert rec.command is None and rec.vehicle_id == "uav2" and rec.reason is ReasonCode.GNSS_LOSS
    assert [m.sector_id for m in rec.sector_moves] == ["S2"]
    assert rec.sector_moves[0].to_vehicle in {"uav1", "uav3"}
    assert (rec.created_s, rec.expires_s) == (clock.t, clock.t + 60.0)
    assert "uav2" in rec.rationale and "S2" in rec.rationale


def test_red_inconsistency_lands_and_retasks() -> None:
    r, f, _ = make()
    [rec] = r.observe(msg("uav3", TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION), f)
    assert rec.command is Command.LAND
    assert [m.sector_id for m in rec.sector_moves] == ["S3"]


def test_stale_is_treated_like_loss() -> None:
    r, f, _ = make()
    [rec] = r.observe(msg("uav1", TrustState.RED, ReasonCode.STALE), f)
    assert rec.command is None and [m.sector_id for m in rec.sector_moves] == ["S1"]


def test_one_recommendation_per_episode_and_a_new_one_after_recovery() -> None:
    r, f, _ = make()
    red = msg("uav2", TrustState.RED, ReasonCode.GNSS_LOSS)
    assert len(r.observe(red, f)) == 1
    assert r.observe(red, f) == []
    assert r.observe(msg("uav2", TrustState.AMBER, ReasonCode.GNSS_LOSS), f) == []
    assert r.observe(red, f) == []  # still the same episode: never went GREEN
    green(r, f, "uav2")
    assert len(r.observe(red, f)) == 1


def test_a_changed_reason_during_red_is_a_new_recommendation() -> None:
    r, f, _ = make()
    assert len(r.observe(msg("uav2", TrustState.RED, ReasonCode.GNSS_LOSS), f)) == 1
    [second] = r.observe(msg("uav2", TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION), f)
    assert second.command is Command.LAND


def test_untrusted_vehicles_do_not_take_work() -> None:
    r, f, _ = make()
    r.observe(msg("uav1", TrustState.AMBER, ReasonCode.GNSS_LOSS), f)
    [rec] = r.observe(msg("uav2", TrustState.RED, ReasonCode.GNSS_LOSS), f)
    assert [m.to_vehicle for m in rec.sector_moves] == ["uav3"]


def test_nobody_available_means_no_loss_recommendation_but_still_a_land() -> None:
    r, f, _ = make()
    r.observe(msg("uav1", TrustState.RED, ReasonCode.GNSS_LOSS), f)  # moves S1 away first
    r.observe(msg("uav3", TrustState.AMBER, ReasonCode.GNSS_LOSS), f)
    assert r.observe(msg("uav2", TrustState.RED, ReasonCode.GNSS_LOSS), f) == []
    [land] = r.observe(msg("uav2", TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION), f)
    assert land.command is Command.LAND and land.sector_moves == ()


def test_finished_sectors_are_not_moved() -> None:
    r, f, _ = make()
    f.done_sector_ids.add("S2")
    assert r.observe(msg("uav2", TrustState.RED, ReasonCode.GNSS_LOSS), f) == []
    [land] = r.observe(msg("uav2", TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION), f)
    assert land.command is Command.LAND and land.sector_moves == ()


def test_ids_are_unique() -> None:
    r, f, _ = make()
    a = r.observe(msg("uav1", TrustState.RED, ReasonCode.GNSS_LOSS), f)[0]
    b = r.observe(msg("uav2", TrustState.RED, ReasonCode.GNSS_LOSS), f)[0]
    assert a.id != b.id


def test_config_validation() -> None:
    with pytest.raises(ValueError):
        RecommenderConfig(ttl_s=0)


def test_an_unanswered_recommendation_is_issued_again_while_the_vehicle_is_still_red() -> None:
    from c2.messages import Decision, Outcome

    r, f, _ = make()
    red = msg("uav2", TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION)
    [first] = r.observe(red, f)
    assert r.observe(red, f) == []
    r.on_decision(Decision(first.id, Outcome.EXPIRED, 120.0, "system"), "uav2")
    [again] = r.observe(red, f)
    assert again.id != first.id and again.command is Command.LAND


def test_a_denied_or_approved_recommendation_is_not_repeated() -> None:
    from c2.messages import Decision, Outcome

    r, f, _ = make()
    red = msg("uav2", TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION)
    [rec] = r.observe(red, f)
    for outcome in (Outcome.DENIED, Outcome.APPROVED):
        r.on_decision(Decision(rec.id, outcome, 60.0, "daniel"), "uav2")
        assert r.observe(red, f) == []
