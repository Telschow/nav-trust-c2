"""A vehicle the backend cannot hear is not asked to take work, and is offered no command."""

from c2.allocator import assign, split_area
from c2.audit import AuditLog
from c2.fleet import FleetState
from c2.hub import Hub
from c2.messages import Command
from c2.recommender import Recommender
from navtrust.types import NavTrust, ReasonCode, TrustState

POS = {"uav1": (0.0, 0.0), "uav2": (0.0, 5.0), "uav3": (0.0, 10.0)}


def fleet() -> FleetState:
    return FleetState(
        assign(split_area(1000, 900, 3), ["uav1", "uav2", "uav3"]), positions=dict(POS)
    )


def msg(v: str, state: TrustState, reason: ReasonCode | None = None) -> NavTrust:
    return NavTrust(v, 0.0, state, reason, 0.15 if state is TrustState.GREEN else float("inf"), 1.0)


def make(no_link: set[str]) -> tuple[Recommender, FleetState]:
    """Three GREEN vehicles; `no_link` names those the backend currently cannot hear."""
    r = Recommender(lambda: 50.0, link_ok=lambda v: v not in no_link)
    f = fleet()
    for v in POS:
        assert r.observe(msg(v, TrustState.GREEN), f) == []
    return r, f


def test_a_vehicle_with_no_link_is_never_chosen_to_take_over_a_sector() -> None:
    r, f = make(no_link={"uav2"})
    [rec] = r.observe(msg("uav1", TrustState.RED, ReasonCode.GNSS_LOSS), f)
    assert [m.to_vehicle for m in rec.sector_moves] == ["uav3"]


def test_when_every_possible_taker_has_no_link_there_is_nothing_to_recommend() -> None:
    r, f = make(no_link={"uav2", "uav3"})
    assert r.observe(msg("uav1", TrustState.RED, ReasonCode.GNSS_LOSS), f) == []


def test_a_vehicle_whose_own_link_is_down_is_offered_no_command_but_its_sector_can_move() -> None:
    # Forward-looking: the server ingests a vehicle's report before the recommender sees it, so a
    # vehicle that is reporting is reachable. This rule matters once a recommendation can be
    # raised for a vehicle without a report from it (for example on a link-loss trigger).
    r, f = make(no_link={"uav3"})
    [rec] = r.observe(msg("uav3", TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION), f)
    assert rec.command is None
    assert [m.sector_id for m in rec.sector_moves] == ["S3"]
    assert Command.LAND.value not in rec.rationale


def test_with_its_link_up_the_same_vehicle_is_still_told_to_land() -> None:
    r, f = make(no_link=set())
    [rec] = r.observe(msg("uav3", TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION), f)
    assert rec.command is Command.LAND


def test_no_link_and_nobody_to_take_the_sector_means_no_recommendation() -> None:
    r, f = make(no_link={"uav1", "uav2", "uav3"})
    assert r.observe(msg("uav3", TrustState.RED, ReasonCode.INCONSISTENT_INNOVATION), f) == []


def test_the_recommender_follows_the_hubs_view_of_the_link() -> None:
    clock = [100.0]
    hub = Hub(AuditLog(), lambda: clock[0], link_timeout_s=2.0)
    # the hub's clock makes uav2 silent; the recommender's own clock only dates its output
    recommender = Recommender(lambda: 50.0, link_ok=hub.is_reachable)
    f = fleet()
    for v in POS:
        hub.ingest_navtrust(msg(v, TrustState.GREEN))
        recommender.observe(msg(v, TrustState.GREEN), f)
    clock[0] = 103.0  # uav2 falls silent; the others keep reporting
    for v in ("uav1", "uav3"):
        hub.ingest_navtrust(msg(v, TrustState.GREEN))
    red = msg("uav1", TrustState.RED, ReasonCode.GNSS_LOSS)
    hub.ingest_navtrust(red)
    [rec] = recommender.observe(red, f)
    assert [m.to_vehicle for m in rec.sector_moves] == ["uav3"]
