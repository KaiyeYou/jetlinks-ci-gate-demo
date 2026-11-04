#!/usr/bin/env python3
"""Fail CI when a direct dependency is not declared in the allowlist."""

from __future__ import annotations

import pathlib
import sys
import xml.etree.ElementTree as ET


ROOT = pathlib.Path(__file__).resolve().parents[2]
POM = ROOT / "delivery-guard-demo" / "pom.xml"
ALLOWLIST = ROOT / "quality-policy" / "allowed-dependencies.txt"
NS = {"m": "http://maven.apache.org/POM/4.0.0"}


def load_allowlist() -> set[str]:
    return {
        line.strip()
        for line in ALLOWLIST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def direct_dependencies() -> set[str]:
    root = ET.parse(POM).getroot()
    dependencies: set[str] = set()
    for dependency in root.findall("./m:dependencies/m:dependency", NS):
        group_id = dependency.findtext("m:groupId", default="", namespaces=NS)
        artifact_id = dependency.findtext("m:artifactId", default="", namespaces=NS)
        scope = dependency.findtext("m:scope", default="compile", namespaces=NS)
        dependencies.add(f"{group_id}:{artifact_id}:{scope}")
    return dependencies


def main() -> int:
    unexpected = sorted(direct_dependencies() - load_allowlist())
    if unexpected:
        print("[ci-gate] BLOCKED: undeclared direct dependencies", file=sys.stderr)
        for dependency in unexpected:
            print(f"  - {dependency}", file=sys.stderr)
        print("Update the dependency review record before changing the allowlist.", file=sys.stderr)
        return 1
    print("[ci-gate] PASS: direct dependencies match the approved policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
