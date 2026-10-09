import pytest

from c2.allocator import Sector, assign, reassign, split_area, workload

POS = {"uav1": (0.0, 0.0), "uav2": (0.0, 5.0), "uav3": (0.0, 10.0)}


def three() -> tuple[list[Sector], dict[str, list[Sector]]]:
    sectors = split_area(1000, 900, 3)
    return sectors, assign(sectors, ["uav3", "uav1", "uav2"])


def test_split_covers_the_area_exactly_once() -> None:
    sectors = split_area(1000, 1000, 3)
    assert [s.id for s in sectors] == ["S1", "S2", "S3"]
    assert sectors[0].south == 0 and sectors[-1].north == 1000
    assert all(a.north == b.south for a, b in zip(sectors, sectors[1:], strict=False))
    assert sum(s.area for s in sectors) == pytest.approx(1000 * 1000)


def test_assign_gives_each_vehicle_one_sector_in_id_order() -> None:
    _, a = three()
    assert [(v, [s.id for s in secs]) for v, secs in sorted(a.items())] == [
        ("uav1", ["S1"]),
        ("uav2", ["S2"]),
        ("uav3", ["S3"]),
    ]


def test_assign_needs_matching_counts_and_unique_ids() -> None:
    with pytest.raises(ValueError):
        assign(split_area(10, 10, 3), ["a", "b"])
    with pytest.raises(ValueError):
        assign(split_area(10, 10, 2), ["a", "a"])


def test_reassign_moves_unfinished_sectors_and_keeps_finished_ones() -> None:
    _, a = three()
    out = reassign(a, "uav2", done_sector_ids=set(), positions=POS)
    assert out["uav2"] == []
    moved = [s.id for v in ("uav1", "uav3") for s in out[v] if s.id == "S2"]
    assert moved == ["S2"]
    done = reassign(a, "uav2", done_sector_ids={"S2"}, positions=POS)
    assert [s.id for s in done["uav2"]] == ["S2"] and done["uav1"] == a["uav1"]


def test_reassign_does_not_modify_its_input() -> None:
    _, a = three()
    before = {v: list(s) for v, s in a.items()}
    reassign(a, "uav1", set(), POS)
    assert a == before


def test_reassign_balances_load_then_prefers_the_nearest_vehicle() -> None:
    sectors = split_area(1000, 1000, 4)  # 250 m strips; S1 centre is at north 125 m
    a = {"uav1": [sectors[0], sectors[3]], "uav2": [sectors[1]], "uav3": [sectors[2]]}
    out = reassign(a, "uav1", set(), POS)
    # S1: uav2 and uav3 have equal load; uav3 (north 10 m) is nearer to 125 m than uav2 (5 m)
    assert [s.id for s in out["uav3"]] == ["S3", "S1"]
    # S4: uav3 now has more work than uav2, so load beats distance
    assert [s.id for s in out["uav2"]] == ["S2", "S4"]
    assert workload(out["uav2"]) == workload(out["uav3"])


def test_reassign_can_exclude_untrusted_vehicles() -> None:
    _, a = three()
    out = reassign(a, "uav2", set(), POS, available=["uav3"])
    assert [s.id for s in out["uav3"]] == ["S3", "S2"]
    assert out["uav1"] == a["uav1"]


def test_reassign_error_cases() -> None:
    _, a = three()
    with pytest.raises(KeyError):
        reassign(a, "ghost", set(), POS)
    with pytest.raises(ValueError):
        reassign({"uav1": a["uav1"]}, "uav1", set(), POS)
    with pytest.raises(KeyError):
        reassign(a, "uav1", set(), {"uav2": (0.0, 0.0)})
    with pytest.raises(KeyError):
        reassign(a, "uav1", set(), POS, available=["uav9"])


def test_sector_validation() -> None:
    with pytest.raises(ValueError):
        Sector("X", 5, 0, 5, 10)
