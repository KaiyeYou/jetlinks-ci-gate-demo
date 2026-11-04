#!/usr/bin/env python3
"""Fast, deterministic checks for staged Git content.

The demo intentionally uses only Python's standard library so every developer
can run the hook without an IDE plugin. A production repository can replace or
extend this check with Gitleaks while keeping the same hook contract.
"""

from __future__ import annotations

import re
import subprocess
import sys


MAX_STAGED_FILE_BYTES = 5 * 1024 * 1024
SECRET_PATTERN = re.compile(
    r"(?i)(?:password|passwd|token|secret|access[_-]?key|mqtt[_-]?key)"
    r"\s*[:=]\s*['\"]?([A-Za-z0-9_+/=-]{20,})"
)
SAFE_MARKERS = ("${", "example", "placeholder", "changeme", "replace_me")


def git(*args: str, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )


def staged_paths() -> list[str]:
    result = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", text=False)
    return [
        raw.decode("utf-8", errors="surrogateescape")
        for raw in result.stdout.split(b"\0")
        if raw
    ]


def oversized_files(paths: list[str]) -> list[tuple[str, int]]:
    failures: list[tuple[str, int]] = []
    for path in paths:
        result = git("cat-file", "-s", f":{path}")
        size = int(result.stdout.strip())
        if size > MAX_STAGED_FILE_BYTES:
            failures.append((path, size))
    return failures


def staged_secret_lines() -> list[str]:
    result = git("diff", "--cached", "--unified=0", "--diff-filter=ACMR")
    failures: list[str] = []
    current_file = "unknown"
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        candidate = line[1:].strip()
        lowered = candidate.lower()
        if any(marker in lowered for marker in SAFE_MARKERS):
            continue
        if SECRET_PATTERN.search(candidate):
            failures.append(f"{current_file}: {candidate[:120]}")
    return failures


def main() -> int:
    paths = staged_paths()
    large = oversized_files(paths)
    secrets = staged_secret_lines()

    if not large and not secrets:
        print("[pre-commit] PASS: no secrets or oversized staged files")
        return 0

    print("[pre-commit] BLOCKED: staged content violates repository policy", file=sys.stderr)
    for path, size in large:
        print(f"  - oversized file: {path} ({size / 1024 / 1024:.1f} MiB)", file=sys.stderr)
    for finding in secrets:
        print(f"  - possible secret: {finding}", file=sys.stderr)
    print("Remove the sensitive content, stage the fix, and commit again.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
