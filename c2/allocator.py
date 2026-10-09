"""Sector allocation for a survey area. Pure Python, no simulator dependency.

The area is split into equal strips (sectors) stacked northwards. Each vehicle gets one
sector to start with. When a vehicle can no longer be trusted, `reassign` hands its
unfinished sectors to the remaining vehicles.

Granularity is the sector: a sector counts as done only when the caller says so, so a
partly flown sector is flown again in full by its new vehicle. That is conservative, not
optimal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Position = tuple[float, float]  # east, north in metres from the area origin


@dataclass(frozen=True)
class Sector:
    id: str
    west: float
    south: float
    east: float
    north: float

    def __post_init__(self) -> None:
        if self.east <= self.west or self.north <= self.south:
            raise ValueError(f"sector {self.id} must have positive width and height")

    @property
    def center(self) -> Position:
        return ((self.west + self.east) / 2, (self.south + self.north) / 2)

    @property
    def area(self) -> float:
        return (self.east - self.west) * (self.north - self.south)


Assignment = dict[str, list[Sector]]


def split_area(width_m: float, height_m: float, n_sectors: int) -> list[Sector]:
    """Equal strips, south to north, ids S1..Sn. Origin is the south-west corner."""
    if width_m <= 0 or height_m <= 0 or n_sectors < 1:
        raise ValueError("width, height must be > 0 and n_sectors >= 1")
    step = height_m / n_sectors
    return [
        Sector(
            f"S{i + 1}", 0.0, i * step, width_m, (i + 1) * step if i < n_sectors - 1 else height_m
        )
        for i in range(n_sectors)
    ]


def assign(sectors: list[Sector], vehicle_ids: list[str]) -> Assignment:
    """Initial assignment: sectors and vehicles in order, one sector each.

    Requires as many sectors as vehicles; extra sectors are not assigned here, use reassign
    semantics if you need them spread.
    """
    if len(sectors) != len(vehicle_ids):
        raise ValueError("assign needs exactly one sector per vehicle")
    if len(set(vehicle_ids)) != len(vehicle_ids):
        raise ValueError("vehicle ids must be unique")
    return {v: [s] for v, s in zip(sorted(vehicle_ids), sectors, strict=True)}


def workload(sectors: list[Sector]) -> float:
    return sum(s.area for s in sectors)


def reassign(
    assignment: Assignment,
    lost_vehicle: str,
    done_sector_ids: set[str],
    positions: dict[str, Position],
    available: list[str] | None = None,
) -> Assignment:
    """Move the lost vehicle's unfinished sectors to other vehicles.

    Each sector goes to the available vehicle with the least workload so far; ties go to the
    vehicle nearest to the sector centre. The lost vehicle keeps only its finished sectors.
    Returns a new assignment; the input is not modified.

    available: vehicles allowed to take work (default: every other vehicle). Pass a narrower
    list to exclude vehicles that are themselves not trusted.
    """
    if lost_vehicle not in assignment:
        raise KeyError(f"unknown vehicle {lost_vehicle!r}")
    takers = [
        v for v in (available if available is not None else list(assignment)) if v != lost_vehicle
    ]
    unknown = [v for v in takers if v not in assignment]
    if unknown:
        raise KeyError(f"unknown vehicle(s) {unknown}")
    if not takers:
        raise ValueError("no vehicle available to take over")
    missing = [v for v in takers if v not in positions]
    if missing:
        raise KeyError(f"no position for {missing}")

    result: Assignment = {v: list(s) for v, s in assignment.items()}
    orphaned = [s for s in assignment[lost_vehicle] if s.id not in done_sector_ids]
    result[lost_vehicle] = [s for s in assignment[lost_vehicle] if s.id in done_sector_ids]

    for sector in sorted(orphaned, key=lambda s: s.id):
        pending = {
            v: workload([s for s in result[v] if s.id not in done_sector_ids]) for v in takers
        }
        best = min(
            takers,
            key=lambda v: (pending[v], math.dist(positions[v], sector.center), v),
        )
        result[best].append(sector)
    return result
