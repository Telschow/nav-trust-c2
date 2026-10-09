import pytest

from sim.interference import point_in_polygon, rectangle
from sim.survey import GeoPoint, LocalPoint, geo_to_local, local_to_geo


def test_rectangle_membership() -> None:
    zone = rectangle(400, 0, 700, 1000)
    assert point_in_polygon(LocalPoint(500, 500), zone)
    assert not point_in_polygon(LocalPoint(300, 500), zone)
    assert not point_in_polygon(LocalPoint(500, 1100), zone)


def test_concave_polygon() -> None:
    # L shape: the notch at (7, 7) is outside
    shape = [
        LocalPoint(0, 0),
        LocalPoint(10, 0),
        LocalPoint(10, 5),
        LocalPoint(5, 5),
        LocalPoint(5, 10),
        LocalPoint(0, 10),
    ]
    assert point_in_polygon(LocalPoint(2, 8), shape)
    assert point_in_polygon(LocalPoint(8, 2), shape)
    assert not point_in_polygon(LocalPoint(8, 8), shape)


def test_degenerate_inputs() -> None:
    with pytest.raises(ValueError):
        point_in_polygon(LocalPoint(0, 0), [LocalPoint(0, 0), LocalPoint(1, 1)])
    with pytest.raises(ValueError):
        rectangle(5, 0, 5, 10)


def test_geo_to_local_roundtrip() -> None:
    origin = GeoPoint(47.3979711, 8.5461637)
    for east, north in [(0, 0), (800, 0), (0, 950), (-300, 420)]:
        back = geo_to_local(origin, local_to_geo(origin, LocalPoint(east, north)))
        assert back.east_m == pytest.approx(east, abs=1e-6)
        assert back.north_m == pytest.approx(north, abs=1e-6)
