"""The interactive explainer (issue 186) is a static page whose numbers come from the README.

The README's first screen is generated from the results files and checked by
`test_readme_numbers.py`, so tying every figure on the explainer's evidence step to that block
keeps the explainer from quoting a number nothing checks. The page may load fonts and nothing
else from the network, so it works offline."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "docs" / "media" / "explainer.html").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
SUMMARY = README.split("<!-- summary-start -->")[1].split("<!-- summary-end -->")[0]


def tiles() -> list[tuple[str, str, str]]:
    return re.findall(r"tile\('([^']*)', '([^']*)', '([^']*)'\)", PAGE)


def test_the_evidence_step_has_its_tiles() -> None:
    assert len(tiles()) == 4


def test_every_figure_on_the_evidence_step_appears_in_the_readme_summary() -> None:
    missing = []
    for value, description, _ in tiles():
        for token in re.findall(r"\d[\d,]*(?:\.\d+)?%?", value + " " + description):
            if token not in SUMMARY:
                missing.append(token)
    assert missing == []


def test_every_source_the_evidence_step_cites_exists() -> None:
    for _, _, source in tiles():
        assert (ROOT / source).exists(), source


def test_the_page_loads_nothing_but_fonts_from_the_network() -> None:
    assert "<script src" not in PAGE
    hosts = set(re.findall(r'(?:src|href)="https?://([^/"]+)', PAGE))
    links = {"github.com", "youtu.be", "telschow.github.io"}  # outbound links, not loaded
    assert hosts - links == {"fonts.googleapis.com"}


def test_illustrated_steps_say_so_and_the_evidence_step_says_what_is_not_shown() -> None:
    assert "Illustration, not data" in PAGE
    assert "Not shown." in PAGE


def test_the_readme_links_to_the_explainer() -> None:
    assert "media/explainer.html" in SUMMARY
