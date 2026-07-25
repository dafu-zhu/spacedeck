"""This repo is public. Nothing from the author's private repos may enter it.

Enforced rather than reviewed by eye, because the failure mode is silent and a git
history is permanent. If a pattern below trips on legitimate content, narrow the
pattern deliberately — do not delete the check.
"""

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]

DENYLIST = {
    "private repo name": r"summer-26",
    "local username": r"dafuz(?!hu@)",
    "machine hostname": r"\bzdf\b",
    "LAN address": r"\b10\.0\.0\.\d+\b",
    "wifi SSID": r"\b603N\b",
    "alternate email": r"fxcarrypl",
    "server host": r"[Hh]etzner",
    "employer": r"\bBofA\b",
    "internship": r"\bxtech\b",
    "conference": r"\bAISTATS\b",
    "private library": r"\bfxcarry\b",
    "course codes": r"\b(finm|busn|stat3|econ)\d{3,}\b",
    "cloud folder": r"[Oo]ne[Dd]rive",
    "windows user path": r"[Cc]:\\+Users\\+",
}

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "dist", "build"}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".json", ".txt", ".yml", ".yaml", ".cfg", ".sh"}


def _tracked_text_files():
    for path in REPO.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name == "LICENSE":
            yield path


@pytest.mark.parametrize("label,pattern", sorted(DENYLIST.items()))
def test_no_private_data_in_the_repo(label, pattern):
    compiled = re.compile(pattern)
    hits = []
    for path in _tracked_text_files():
        if path.name == pathlib.Path(__file__).name:
            continue  # this file necessarily contains the patterns
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if compiled.search(line):
                hits.append(f"{path.relative_to(REPO)}:{n}: {line.strip()[:100]}")
    assert not hits, f"{label} leaked into a public repo:\n" + "\n".join(hits)


def test_the_scanner_actually_reads_files():
    """A denylist that scans nothing would pass forever."""
    assert len(list(_tracked_text_files())) > 10


def test_the_scanner_would_catch_a_plant(tmp_path, monkeypatch):
    """Guard against the checks silently going no-op."""
    compiled = re.compile(DENYLIST["private repo name"])
    assert compiled.search("this mentions summer-26 somewhere")
