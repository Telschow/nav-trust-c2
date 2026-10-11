import pytest

from c2.allocator import Sector
from c2.progress import SectorProgress, geo_to_local
from sim.survey import GeoPoint, LocalPoint
from sim.survey import geo_to_local as sim_geo_to_local

S1 = Sector("S1", 0.0, 0.0, 600.0, 100.0)
S2 = Sector("S2", 0.0, 100.0, 600.0, 200.0)


def fly_lane(p: SectorProgress, north: float, trusted: bool = True, alt: float = 30.0) -> set[str]:
    done: set[str] = set()
    for east in range(0, 601, 5):
        done |= p.observe((float(east), north), alt, trusted)
    return done


def test_one_lane_is_not_a_sector() -> None:
    p = SectorProgress([S1])
    assert fly_lane(p, 0.0) == set()
    assert 0.4 < p.fraction("S1") < 0.6


def test_both_lanes_finish_the_sector_once() -> None:
    p = SectorProgress([S1, S2])
    fly_lane(p, 0.0)
    assert fly_lane(p, 100.0) == {"S1"}  # the lane on the shared edge also covers half of S2
    assert fly_lane(p, 100.0) == set()  # reported once
    assert p.done == {"S1"}


def test_untrusted_or_grounded_positions_cover_nothing() -> None:
    p = SectorProgress([S1])
    fly_lane(p, 0.0, trusted=False)
    fly_lane(p, 100.0, alt=1.0)
    assert p.fraction("S1") == 0.0


def test_position_far_from_every_sector_is_ignored() -> None:
    p = SectorProgress([S1])
    assert p.observe((5000.0, 5000.0), 30.0, True) == set()
    assert p.fraction("S1") == 0.0


def test_bad_settings_are_rejected() -> None:
    with pytest.raises(ValueError):
        SectorProgress([S1], done_fraction=0.0)


def test_conversion_matches_the_simulator_package() -> None:
    origin = GeoPoint(47.397971, 8.546164)
    here = GeoPoint(47.399, 8.548)
    e, n = geo_to_local(origin.lat_deg, origin.lon_deg, here.lat_deg, here.lon_deg)
    expected: LocalPoint = sim_geo_to_local(origin, here)
    assert (e, n) == pytest.approx((expected.east_m, expected.north_m))
