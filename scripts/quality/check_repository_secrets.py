#!/usr/bin/env python3
"""Repeat the repository's fast secret rule in CI over all tracked text files."""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys


DEFAULT_ROOT = pathlib.Path(__file__).resolve().parents[2]
MAX_TEXT_BYTES = 2 * 1024 * 1024
SECRET_PATTERN = re.compile(
    r"(?i)(?:password|passwd|token|secret|access[_-]?key|mqtt[_-]?key)"
    r"\s*[:=]\s*['\"]?([A-Za-z0-9_+/=-]{20,})"
)
SAFE_MARKERS = ("${", "example", "placeholder", "changeme", "replace_me")


def tracked_files(root: pathlib.Path) -> list[pathlib.Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    )
    return [
        root / raw.decode("utf-8", errors="surrogateescape")
        for raw in result.stdout.split(b"\0")
        if raw
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=DEFAULT_ROOT,
        help="Git worktree to scan (defaults to this repository)",
    )
    return parser.parse_args()


def main() -> int:
    root = parse_args().root.resolve()
    findings: list[str] = []
    for path in tracked_files(root):
        if not path.is_file() or path.stat().st_size > MAX_TEXT_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            if any(marker in lowered for marker in SAFE_MARKERS):
                continue
            if SECRET_PATTERN.search(line):
                findings.append(f"{path.relative_to(root)}:{number}")

    if findings:
        print("[secret-scan] BLOCKED: possible credentials in tracked files", file=sys.stderr)
        for finding in findings:
            print(f"  - {finding}", file=sys.stderr)
        return 1

    print("[secret-scan] PASS: no matching credentials in tracked text files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
