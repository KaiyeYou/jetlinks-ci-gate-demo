#!/bin/sh
set -eu

repo_root=$(git rev-parse --show-toplevel)

echo "== 1/3 Unit tests =="
if [ -n "${MAVEN_REPO_LOCAL:-}" ]; then
    mvn -Dmaven.repo.local="$MAVEN_REPO_LOCAL" \
        -f "$repo_root/delivery-guard-demo/pom.xml" \
        --batch-mode test
else
    mvn -f "$repo_root/delivery-guard-demo/pom.xml" --batch-mode test
fi

echo "== 2/3 Export safety policy =="
"$repo_root/scripts/quality/check-unbounded-device-export.sh"

echo "== 3/3 Dependency admission policy =="
python3 "$repo_root/scripts/quality/check_dependency_policy.py"

echo "[ci-gate] PASS: all merge requirements are satisfied"
