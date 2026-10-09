import math

import pytest

from sim.survey import GeoPoint, LocalPoint, lawnmower, local_to_geo, path_length_m


def haversine_m(a: GeoPoint, b: GeoPoint) -> float:
    r = 6_371_008.8
    p1, p2 = math.radians(a.lat_deg), math.radians(b.lat_deg)
    dphi = p2 - p1
    dlmb = math.radians(b.lon_deg - a.lon_deg)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def test_lane_count_and_bounds() -> None:
    pts = lawnmower(1000, 1000, 100)
    assert len(pts) == 2 * 11
    assert min(p.east_m for p in pts) == 0
    assert max(p.east_m for p in pts) == 1000
    assert min(p.north_m for p in pts) == 0
    assert max(p.north_m for p in pts) == pytest.approx(1000)


def test_lanes_alternate_direction_and_connect() -> None:
    pts = lawnmower(1000, 300, 100)
    # lane 0 west->east, lane 1 east->west: consecutive lanes share an east/west end
    assert (pts[0].east_m, pts[1].east_m) == (0, 1000)
    assert (pts[2].east_m, pts[3].east_m) == (1000, 0)
    assert pts[1].east_m == pts[2].east_m


def test_spacing_never_exceeds_request() -> None:
    pts = lawnmower(500, 250, 100)  # 250 / 100 is not an integer
    norths = sorted({p.north_m for p in pts})
    gaps = [b - a for a, b in zip(norths, norths[1:], strict=False)]
    assert all(g <= 100 + 1e-9 for g in gaps)
    assert norths[-1] == pytest.approx(250)


def test_path_length() -> None:
    pts = lawnmower(1000, 200, 100)  # 3 lanes of 1000 m plus 2 turns of 100 m
    assert path_length_m(pts) == pytest.approx(3 * 1000 + 2 * 100)


@pytest.mark.parametrize("args", [(0, 100, 10), (100, -1, 10), (100, 100, 0)])
def test_invalid_inputs(args: tuple[float, float, float]) -> None:
    with pytest.raises(ValueError):
        lawnmower(*args)


def test_local_to_geo_matches_haversine() -> None:
    origin = GeoPoint(48.0, 11.0)
    for east, north in [(1000, 0), (0, 1000), (1000, 1000)]:
        geo = local_to_geo(origin, LocalPoint(east, north))
        expected = math.hypot(east, north)
        assert haversine_m(origin, geo) == pytest.approx(expected, rel=2e-3)


def test_local_to_geo_origin_is_identity() -> None:
    origin = GeoPoint(48.0, 11.0)
    assert local_to_geo(origin, LocalPoint(0, 0)) == origin


def test_lawnmower_rect_is_the_origin_lawnmower_shifted() -> None:
    from sim.survey import lawnmower_rect

    base = lawnmower(1000, 300, 100)
    shifted = lawnmower_rect(0, 600, 1000, 900, 100)
    assert len(shifted) == len(base)
    assert all(
        (s.east_m, s.north_m) == (b.east_m, b.north_m + 600)
        for s, b in zip(shifted, base, strict=True)
    )
