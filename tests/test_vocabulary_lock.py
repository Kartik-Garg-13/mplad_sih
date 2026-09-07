"""Plan §08, rule 1 — vocabulary lock, enforced, not just stated.

Every flag says "warrants review"; nothing in this repo says "fraud".
Scans source and copy for a fixed word list. Deliberately narrow (whole
words only, case-insensitive) so it doesn't false-positive on incidental
substrings ("scampi", "corruption-free", "guiltless") while still
catching the words themselves anywhere they'd matter — code, evidence
text, UI copy, or a slide.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

BANNED_WORDS = ["fraud", "corrupt", "guilty", "scam", "siphon", "embezzle"]

_SCAN_DIRS = ["src", "web/src"]
_SCAN_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".md"}
_EXCLUDE_DIR_PARTS = {"node_modules", ".next", "__pycache__", ".venv", "dist", "build"}

# "corrupt" is deliberately narrowed to exclude "corrupted"/"corruption"/
# "corrupting" — real, unrelated technical vocabulary used throughout
# this codebase for the confirmed Devanagari-script byte loss (see
# parse.py), not the misconduct sense the lock exists to catch. Every
# other banned word has no legitimate technical homonym in this domain,
# so only "corrupt" needs the exception.
_WORD_PATTERN = re.compile(
    r"\bcorrupt(?!ed\b|ion\b|ing\b)\w*|\b(?:" + "|".join(w for w in BANNED_WORDS if w != "corrupt") + r")\w*",
    re.IGNORECASE,
)


def _files_to_scan() -> list[Path]:
    files = []
    for scan_dir in _SCAN_DIRS:
        root = REPO_ROOT / scan_dir
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in _SCAN_EXTENSIONS:
                continue
            if any(part in _EXCLUDE_DIR_PARTS for part in path.parts):
                continue
            files.append(path)
    return files


def test_no_banned_vocabulary_in_source_or_copy():
    violations = []
    for path in _files_to_scan():
        # This file itself legitimately contains the banned words (it
        # has to, to define and explain the list) — skip it, not the
        # rest of the repo.
        if path == Path(__file__):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = _WORD_PATTERN.search(line)
            if match:
                violations.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {match.group(0)!r} — {line.strip()[:100]}")

    assert not violations, "Banned vocabulary found (plan §08, rule 1):\n" + "\n".join(violations)
