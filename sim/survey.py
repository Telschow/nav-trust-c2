"""Lawnmower (boustrophedon) survey geometry. Pure functions, no simulator dependency."""

from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_M = 6_371_008.8  # IUGG mean radius; flat-earth error is negligible at 1 km scale


@dataclass(frozen=True)
class LocalPoint:
    """Offset from the area origin: east and north in metres."""

    east_m: float
    north_m: float


@dataclass(frozen=True)
class GeoPoint:
    lat_deg: float
    lon_deg: float


def lawnmower(width_m: float, height_m: float, spacing_m: float) -> list[LocalPoint]:
    """Waypoints covering a width x height rectangle, origin at its south-west corner.

    Lanes run east-west and are stacked northwards. The lane count is chosen so that the
    actual spacing is height / ceil(height / spacing), i.e. never larger than requested,
    and the last lane lies exactly on the north edge. Direction alternates per lane.
    """
    if width_m <= 0 or height_m <= 0 or spacing_m <= 0:
        raise ValueError("width_m, height_m and spacing_m must be > 0")

    intervals = math.ceil(height_m / spacing_m)
    step = height_m / intervals
    points: list[LocalPoint] = []
    for lane in range(intervals + 1):
        north = lane * step
        west, east = LocalPoint(0.0, north), LocalPoint(width_m, north)
        points.extend((west, east) if lane % 2 == 0 else (east, west))
    return points


def lawnmower_rect(
    west_m: float, south_m: float, east_m: float, north_m: float, spacing_m: float
) -> list[LocalPoint]:
    """Lawnmower over an arbitrary rectangle, in the same frame as the area origin."""
    return [
        LocalPoint(west_m + p.east_m, south_m + p.north_m)
        for p in lawnmower(east_m - west_m, north_m - south_m, spacing_m)
    ]


def local_to_geo(origin: GeoPoint, point: LocalPoint) -> GeoPoint:
    """Convert a local east/north offset to latitude/longitude (small-area approximation)."""
    lat = origin.lat_deg + math.degrees(point.north_m / EARTH_RADIUS_M)
    lon = origin.lon_deg + math.degrees(
        point.east_m / (EARTH_RADIUS_M * math.cos(math.radians(origin.lat_deg)))
    )
    return GeoPoint(lat, lon)


def geo_to_local(origin: GeoPoint, point: GeoPoint) -> LocalPoint:
    """Inverse of local_to_geo: latitude/longitude to east/north metres from the origin."""
    north = math.radians(point.lat_deg - origin.lat_deg) * EARTH_RADIUS_M
    east = (
        math.radians(point.lon_deg - origin.lon_deg)
        * EARTH_RADIUS_M
        * math.cos(math.radians(origin.lat_deg))
    )
    return LocalPoint(east, north)


def path_length_m(points: list[LocalPoint]) -> float:
    return sum(
        math.hypot(b.east_m - a.east_m, b.north_m - a.north_m)
        for a, b in zip(points, points[1:], strict=False)
    )
