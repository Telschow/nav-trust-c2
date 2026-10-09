"""What the C2 knows about the fleet's work: who flies which sectors, what is done, where
each vehicle is. Pure Python."""

from __future__ import annotations

from dataclasses import dataclass, field

from c2.allocator import Assignment, Position, Sector


@dataclass
class FleetState:
    assignment: Assignment
    done_sector_ids: set[str] = field(default_factory=set)
    positions: dict[str, Position] = field(default_factory=dict)

    def sectors_of(self, vehicle_id: str) -> list[Sector]:
        return list(self.assignment.get(vehicle_id, []))

    def unfinished_of(self, vehicle_id: str) -> list[Sector]:
        return [s for s in self.sectors_of(vehicle_id) if s.id not in self.done_sector_ids]

    def apply_moves(self, moves: list[tuple[str, str]]) -> None:
        """Move sectors (sector_id, to_vehicle). Unknown sectors or vehicles raise KeyError and
        change nothing."""
        owners = {s.id: (v, s) for v, secs in self.assignment.items() for s in secs}
        for sector_id, to_vehicle in moves:
            if sector_id not in owners:
                raise KeyError(f"unknown sector {sector_id!r}")
            if to_vehicle not in self.assignment:
                raise KeyError(f"unknown vehicle {to_vehicle!r}")
        for sector_id, to_vehicle in moves:
            owner, sector = owners[sector_id]
            self.assignment[owner].remove(sector)
            self.assignment[to_vehicle].append(sector)
            owners[sector_id] = (to_vehicle, sector)
