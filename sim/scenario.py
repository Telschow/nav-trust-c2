"""Scenario files (scenarios/*.yaml): what to fly, what fault to inject, how many recordings.

Pure Python plus PyYAML; no simulator imports, so the evaluation can read scenarios in CI.
The classes follow ADR 0002: nominal, short_outage, long_outage, stuck_position, plus wrong_fix.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CLASSES = ("nominal", "short_outage", "long_outage", "stuck_position", "wrong_fix", "link_loss")
MODES = ("off", "stuck", "wrong")  # failure modes of PX4's `failure gps`
LINK_CUT_AFTER = ("mission_start", "fault_start")


@dataclass(frozen=True)
class Survey:
    width_m: float = 600.0
    height_m: float = 100.0
    spacing_m: float = 100.0
    altitude_m: float = 30.0
    speed_m_s: float = 10.0


@dataclass(frozen=True)
class Zone:
    west: float
    south: float
    east: float
    north: float


@dataclass(frozen=True)
class Fault:
    mode: str
    zone: Zone
    latch: bool = False


@dataclass(frozen=True)
class LinkCut:
    """Cut the MAVLink link between PX4 and the scripts, both directions, for one vehicle."""

    after: str  # one of LINK_CUT_AFTER
    delay_s: float
    duration_s: float | None = None  # None: the link never comes back


@dataclass(frozen=True)
class Scenario:
    name: str
    scenario_class: str
    description: str
    expected_px4: str
    survey: Survey
    fault: Fault | None
    runs: int
    max_duration_s: float
    link_cut: LinkCut | None = None

    def recording_name(self, run: int) -> str:
        return f"{self.name}-{run}"


def parse_scenario(data: dict[str, Any]) -> Scenario:
    def need(key: str) -> Any:
        if key not in data:
            raise ValueError(f"scenario is missing {key!r}")
        return data[key]

    name = str(need("name"))
    scenario_class = str(need("class"))
    if scenario_class not in CLASSES:
        raise ValueError(f"{name}: class must be one of {CLASSES}, got {scenario_class!r}")

    survey = Survey(**{k: float(v) for k, v in data.get("survey", {}).items()})
    if min(survey.width_m, survey.height_m, survey.spacing_m, survey.speed_m_s) <= 0:
        raise ValueError(f"{name}: survey values must be > 0")

    fault: Fault | None = None
    if "fault" in data:
        f = data["fault"]
        raw_mode = f["mode"]
        # YAML 1.1 reads an unquoted `off` as the boolean False; `on` would read as True
        mode = "off" if raw_mode is False else str(raw_mode)
        if mode not in MODES:
            raise ValueError(f"{name}: fault mode must be one of {MODES}, got {mode!r}")
        zone = Zone(**{k: float(v) for k, v in f["zone"].items()})
        if zone.east <= zone.west or zone.north <= zone.south:
            raise ValueError(f"{name}: zone must have positive width and height")
        fault = Fault(mode, zone, bool(f.get("latch", False)))

    link_cut: LinkCut | None = None
    if "link_cut" in data:
        c = data["link_cut"]
        after = str(c.get("after"))
        if after not in LINK_CUT_AFTER:
            raise ValueError(f"{name}: link_cut after must be one of {LINK_CUT_AFTER}")
        if after == "fault_start" and fault is None:
            raise ValueError(f"{name}: link_cut after fault_start needs a GNSS fault")
        delay_s = float(c.get("delay_s", 0.0))
        duration_s = float(c["duration_s"]) if c.get("duration_s") is not None else None
        if delay_s < 0 or (duration_s is not None and duration_s <= 0):
            raise ValueError(f"{name}: link_cut delay_s must be >= 0 and duration_s > 0")
        link_cut = LinkCut(after, delay_s, duration_s)
    if (scenario_class == "link_loss") != (link_cut is not None):
        raise ValueError(f"{name}: only the link_loss class has a link_cut, and it needs one")
    if (scenario_class == "nominal") != (fault is None and link_cut is None):
        raise ValueError(f"{name}: only the nominal class has no fault and no link cut")

    runs = int(need("runs"))
    max_duration = float(need("max_duration_s"))
    if runs < 1 or max_duration <= 0:
        raise ValueError(f"{name}: runs must be >= 1 and max_duration_s > 0")
    return Scenario(
        name=name,
        scenario_class=scenario_class,
        description=str(need("description")).strip(),
        expected_px4=str(need("expected_px4")).strip(),
        survey=survey,
        fault=fault,
        runs=runs,
        max_duration_s=max_duration,
        link_cut=link_cut,
    )


def load_scenario(path: Path) -> Scenario:
    scenario = parse_scenario(yaml.safe_load(path.read_text(encoding="utf-8")))
    if path.stem != scenario.name:
        raise ValueError(f"{path.name}: file name must match the scenario name {scenario.name!r}")
    return scenario


def load_all(directory: Path) -> list[Scenario]:
    return [load_scenario(p) for p in sorted(directory.glob("*.yaml"))]
