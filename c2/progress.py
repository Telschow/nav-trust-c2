"""Which sectors have been flown, from the positions vehicles report. Pure Python.

A sector is done when at least `done_fraction` of its grid cells have been passed within
`swath_half_width_m` by a vehicle that was airborne and trusted (GREEN) at the time. A position
reported while the vehicle was not GREEN proves nothing about where it was, so it covers nothing.
The tracker sees the vehicle's own reported position, not the truth; the evaluation checks it
against ground truth (eval/fleet.py).

The numbers are proposals: half the lane spacing is a swath that covers an area exactly when
every lane is flown, and 95% leaves room for the corners and for the edges of the swath.
"""

from __future__ import annotations

import math

from c2.allocator import Position, Sector

EARTH_RADIUS_M = 6_371_008.8  # same value as sim.survey; a test compares the two conversions


def geo_to_local(
    origin_lat_deg: float, origin_lon_deg: float, lat_deg: float, lon_deg: float
) -> Position:
    """East, north in metres from the origin (small-area approximation)."""
    north = math.radians(lat_deg - origin_lat_deg) * EARTH_RADIUS_M
    east = (
        math.radians(lon_deg - origin_lon_deg)
        * EARTH_RADIUS_M
        * math.cos(math.radians(origin_lat_deg))
    )
    return east, north


class SectorProgress:
    def __init__(
        self,
        sectors: list[Sector],
        *,
        cell_m: float = 10.0,
        swath_half_width_m: float = 50.0,
        done_fraction: float = 0.95,
        min_altitude_m: float = 5.0,
    ) -> None:
        if cell_m <= 0 or swath_half_width_m <= 0 or not 0 < done_fraction <= 1:
            raise ValueError("cell_m and swath_half_width_m must be > 0, done_fraction in (0, 1]")
        self._swath = swath_half_width_m
        self._fraction = done_fraction
        self._min_alt = min_altitude_m
        self._sectors = {s.id: s for s in sectors}
        self._cells: dict[str, list[tuple[float, float]]] = {}
        self._covered: dict[str, set[int]] = {}
        for s in sectors:
            cols = max(1, round((s.east - s.west) / cell_m))
            rows = max(1, round((s.north - s.south) / cell_m))
            w, h = (s.east - s.west) / cols, (s.north - s.south) / rows
            self._cells[s.id] = [
                (s.west + (i + 0.5) * w, s.south + (j + 0.5) * h)
                for i in range(cols)
                for j in range(rows)
            ]
            self._covered[s.id] = set()
        self._done: set[str] = set()

    @property
    def done(self) -> set[str]:
        return set(self._done)

    def fraction(self, sector_id: str) -> float:
        return len(self._covered[sector_id]) / len(self._cells[sector_id])

    def observe(self, position: Position, altitude_m: float, trusted: bool) -> set[str]:
        """Feed one reported position; returns the sectors that this report completed."""
        if not trusted or altitude_m < self._min_alt:
            return set()
        east, north = position
        finished: set[str] = set()
        for sid, cells in self._cells.items():
            if sid in self._done:
                continue
            s = self._sectors[sid]
            if not (
                s.west - self._swath <= east <= s.east + self._swath
                and s.south - self._swath <= north <= s.north + self._swath
            ):
                continue
            covered = self._covered[sid]
            for k, (cx, cy) in enumerate(cells):
                if math.hypot(cx - east, cy - north) <= self._swath:
                    covered.add(k)
            if len(covered) / len(cells) >= self._fraction:
                self._done.add(sid)
                finished.add(sid)
        return finished
