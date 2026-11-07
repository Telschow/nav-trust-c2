"""The command endings the console recognises are the ones the backend and the ICD name.

The list is kept in three places (c2/hub.py, console/src/store.ts, docs/ICD.md). A new ending
added to one and not the others would be hidden by the console, so this fails instead.
"""

import re
from pathlib import Path

from c2.hub import _COMMAND_ENDINGS

ROOT = Path(__file__).resolve().parent.parent


def test_the_console_recognises_exactly_the_backends_command_endings() -> None:
    source = (ROOT / "console/src/store.ts").read_text()
    match = re.search(r"const COMMAND_ENDINGS = \[(.*?)\]", source, re.DOTALL)
    assert match is not None, "COMMAND_ENDINGS not found in console/src/store.ts"
    assert tuple(re.findall(r'"(\w+)"', match.group(1))) == _COMMAND_ENDINGS


def test_the_icd_names_every_command_ending() -> None:
    icd = (ROOT / "docs/ICD.md").read_text()
    assert [kind for kind in _COMMAND_ENDINGS if f"`{kind}`" not in icd] == []
