"""No em dash anywhere in the repository (issue 174; CLAUDE.md: "No em dashes").

The rule used to be checked by hand in every code review. Tracked text files are scanned; the
character is written as an escape here so that this file passes its own check."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EM_DASH = chr(0x2014)  # not a literal: a formatter may rewrite an escape into the character
# generated or vendored text: not ours to word
EXCLUDED_NAMES = {"package-lock.json"}


def tracked_files(root: Path) -> list[Path]:
    listing = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True, check=True
    ).stdout
    return [root / name for name in listing.split("\0") if name]


def text_of(path: Path) -> str | None:
    """The file as text, or None for a binary one (a NUL byte, or not UTF-8)."""
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def find_em_dashes(files: list[Path], root: Path) -> list[str]:
    """`path:line` for every line of every text file that holds an em dash. All tracked files are
    read, Makefile and Dockerfile included, not a list of suffixes."""
    found: list[str] = []
    for path in files:
        if path.name in EXCLUDED_NAMES or not path.is_file():
            continue
        text = text_of(path)
        for number, line in enumerate((text or "").splitlines(), 1):
            if EM_DASH in line:
                found.append(f"{path.relative_to(root)}:{number}")
    return found


def test_no_tracked_text_file_has_an_em_dash() -> None:
    assert find_em_dashes(tracked_files(ROOT), ROOT) == []


def test_the_checker_catches_an_em_dash_and_names_the_line(tmp_path: Path) -> None:
    bad = tmp_path / "notes.md"
    bad.write_text(f"fine\nnot {EM_DASH} fine\n", encoding="utf-8")
    (tmp_path / "ok.py").write_text("x = 1  # a hyphen - is fine\n", encoding="utf-8")
    assert find_em_dashes([bad, tmp_path / "ok.py"], tmp_path) == ["notes.md:2"]


def test_generated_and_binary_files_are_not_scanned(tmp_path: Path) -> None:
    lock = tmp_path / "package-lock.json"
    lock.write_text(f'{{"a": "{EM_DASH}"}}\n', encoding="utf-8")
    image = tmp_path / "shot.png"
    image.write_bytes(b"\x89PNG\0" + EM_DASH.encode("utf-8"))
    assert find_em_dashes([lock, image], tmp_path) == []


def test_a_file_with_no_suffix_is_scanned_too(tmp_path: Path) -> None:
    makefile = tmp_path / "Makefile"
    makefile.write_text(f'help:\n\t@echo "a {EM_DASH} b"\n', encoding="utf-8")
    assert find_em_dashes([makefile], tmp_path) == ["Makefile:2"]
