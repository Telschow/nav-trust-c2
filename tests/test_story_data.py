"""The clip's numbers come from recordings, not from the scene code (issue 184)."""

import hashlib
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("build_story", ROOT / "tools/story/build_story.py")
assert _spec is not None and _spec.loader is not None
build_story = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_story)


def test_the_clip_shows_the_distances_adr_0003_reports() -> None:
    runs = build_story.build()["runs"]
    adr = (ROOT / "docs/adr/0003-land-for-frozen-position.md").read_text()
    rows = re.finditer(r"^\| (none|LAND) \| (\d+) m", adr, re.M)
    row = {m.group(1).lower(): int(m.group(2)) for m in rows}
    assert row["none"] == runs["none"]["farthest_from_start_m"]
    assert abs(row["land"] - runs["land"]["farthest_from_start_m"]) <= 1


def test_the_land_run_is_approved_after_the_fault_and_touches_down_later() -> None:
    land = build_story.build()["runs"]["land"]
    assert land["approved_rel_s"] == 15.0
    assert land["touchdown_rel_s"] > land["approved_rel_s"]
    assert build_story.build()["runs"]["none"]["approved_rel_s"] is None


def test_each_run_records_which_file_it_came_from() -> None:
    for run in build_story.build()["runs"].values():
        path = ROOT / run["source"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == run["sha256"]
