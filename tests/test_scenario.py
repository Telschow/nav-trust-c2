from pathlib import Path

import pytest

from sim.scenario import load_all, load_scenario, parse_scenario

SCENARIOS = Path(__file__).parent.parent / "scenarios"


def base() -> dict[str, object]:
    return {
        "name": "x",
        "class": "nominal",
        "description": "d",
        "expected_px4": "e",
        "runs": 1,
        "max_duration_s": 10,
    }


def test_all_committed_scenarios_load_and_cover_every_class() -> None:
    scenarios = load_all(SCENARIOS)
    assert {s.scenario_class for s in scenarios} == {
        "nominal",
        "short_outage",
        "long_outage",
        "stuck_position",
        "wrong_fix",
    }
    assert (
        all(s.runs >= 2 for s in scenarios)
        and next(s for s in scenarios if s.name == "nominal").runs >= 3
    )


def test_zones_lie_on_the_survey_route() -> None:
    for s in load_all(SCENARIOS):
        if s.fault:
            z = s.fault.zone
            assert 0 <= z.west < z.east <= s.survey.width_m
            assert z.south < 0 and z.north > s.survey.height_m  # covers every lane


def test_stuck_position_is_latched_and_the_others_are_not() -> None:
    latched = {s.name: s.fault.latch for s in load_all(SCENARIOS) if s.fault}
    assert latched == {
        "short_outage": False,
        "long_outage": False,
        "stuck_position": True,
        "wrong_fix": False,
    }


def test_recording_names() -> None:
    s = load_scenario(SCENARIOS / "stuck_position.yaml")
    assert s.recording_name(2) == "stuck_position-2"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"class": "weird"}, "class must be one of"),
        ({"runs": 0}, "runs must be"),
        (
            {"fault": {"mode": "off", "zone": {"west": 0, "south": 0, "east": 10, "north": 10}}},
            "only the nominal class",
        ),
        ({"class": "stuck_position"}, "only the nominal class"),
        (
            {
                "class": "stuck_position",
                "fault": {"mode": "bogus", "zone": {"west": 0, "south": 0, "east": 1, "north": 1}},
            },
            "fault mode",
        ),
        (
            {
                "class": "stuck_position",
                "fault": {"mode": "stuck", "zone": {"west": 5, "south": 0, "east": 5, "north": 1}},
            },
            "positive width",
        ),
        ({"survey": {"width_m": 0}}, "survey values"),
    ],
)
def test_bad_scenarios_are_rejected(change: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_scenario({**base(), **change})


def test_missing_field_is_named() -> None:
    data = base()
    del data["expected_px4"]
    with pytest.raises(ValueError, match="expected_px4"):
        parse_scenario(data)


def test_file_name_must_match_scenario_name(tmp_path: Path) -> None:
    (tmp_path / "other.yaml").write_text(
        "name: x\nclass: nominal\ndescription: d\nexpected_px4: e\nruns: 1\nmax_duration_s: 5\n"
    )
    with pytest.raises(ValueError, match="file name"):
        load_scenario(tmp_path / "other.yaml")


def test_an_unquoted_off_is_read_as_the_string_off() -> None:
    """YAML turns a bare `off` into False; the loader must not reject or mangle it."""
    import yaml

    data = yaml.safe_load(
        "name: x\nclass: short_outage\ndescription: d\nexpected_px4: e\n"
        "runs: 1\nmax_duration_s: 5\n"
        "fault:\n  mode: off\n  zone: {west: 0, south: 0, east: 5, north: 5}\n"
    )
    assert data["fault"]["mode"] is False
    fault = parse_scenario(data).fault
    assert fault is not None and fault.mode == "off"


def test_record_argv_builds_the_recorder_command_for_a_fault_scenario() -> None:
    from sim.run_scenario import record_argv

    s = load_scenario(SCENARIOS / "stuck_position.yaml")
    argv = record_argv(s, 2, Path("eval/recordings"))
    assert argv[argv.index("--out") + 1] == "eval/recordings/stuck_position-2.jsonl"
    assert argv[argv.index("--zone") + 1 : argv.index("--zone") + 5] == [
        "200.0",
        "-50.0",
        "280.0",
        "150.0",
    ]
    assert argv[argv.index("--mode") + 1] == "stuck" and "--latch-fault" in argv
    assert argv[argv.index("--max-duration") + 1] == "200.0"


def test_record_argv_for_nominal_has_no_fault_arguments() -> None:
    from sim.run_scenario import record_argv

    argv = record_argv(load_scenario(SCENARIOS / "nominal.yaml"), 1, Path("x"))
    assert "--zone" not in argv and "--mode" not in argv and "--latch-fault" not in argv


def test_listing_and_bad_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    from sim.run_scenario import main

    main(["--list", "--scenarios", str(SCENARIOS)])
    lines = capsys.readouterr().out.splitlines()
    assert "nominal 4" in lines and "stuck_position 3" in lines
    with pytest.raises(SystemExit):
        main(["nope", "--scenarios", str(SCENARIOS)])
    with pytest.raises(SystemExit):
        main(["nominal", "--run", "9", "--scenarios", str(SCENARIOS)])
