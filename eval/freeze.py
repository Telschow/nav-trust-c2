"""A fingerprint of the code under evaluation, so "the thresholds were frozen" is checkable.

The fingerprint covers the trust engine and everything the recommender uses; it does not cover the
evaluation harness (that is versioned by git and a changed harness changes the committed results).
Results record it. If it changes, the committed results are stale and CI fails until they are
regenerated, so a change to the engine can never hide behind old numbers.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = (
    "navtrust/*.py",
    "c2/recommender.py",
    "c2/allocator.py",
    "c2/fleet.py",
    "c2/messages.py",
)


def fingerprinted_files(root: Path = ROOT) -> list[Path]:
    files: set[Path] = set()
    for pattern in PATTERNS:
        files.update(root.glob(pattern))
    return sorted(files)


def engine_fingerprint(root: Path = ROOT) -> str:
    digest = hashlib.sha256()
    for path in fingerprinted_files(root):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
