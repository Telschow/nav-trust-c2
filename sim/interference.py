"""Interference zone geometry. Pure functions, no simulator dependency."""

from __future__ import annotations

from sim.survey import LocalPoint


def point_in_polygon(point: LocalPoint, polygon: list[LocalPoint]) -> bool:
    """Ray casting. Points exactly on an edge count as inside only on some edges; callers
    that need a margin should buffer the polygon."""
    if len(polygon) < 3:
        raise ValueError("polygon needs at least 3 vertices")
    inside = False
    j = len(polygon) - 1
    for i, a in enumerate(polygon):
        b = polygon[j]
        if (a.north_m > point.north_m) != (b.north_m > point.north_m):
            east_at = (b.east_m - a.east_m) * (point.north_m - a.north_m) / (
                b.north_m - a.north_m
            ) + a.east_m
            if point.east_m < east_at:
                inside = not inside
        j = i
    return inside


def rectangle(west_m: float, south_m: float, east_m: float, north_m: float) -> list[LocalPoint]:
    if east_m <= west_m or north_m <= south_m:
        raise ValueError("rectangle must have positive width and height")
    return [
        LocalPoint(west_m, south_m),
        LocalPoint(east_m, south_m),
        LocalPoint(east_m, north_m),
        LocalPoint(west_m, north_m),
    ]
