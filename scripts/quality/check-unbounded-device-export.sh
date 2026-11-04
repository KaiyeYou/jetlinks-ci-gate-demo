#!/bin/sh
set -eu

repo_root=$(git rev-parse --show-toplevel)
controller="$repo_root/jetlinks-manager/device-manager/src/main/java/org/jetlinks/community/device/web/DeviceInstanceController.java"

if grep -Fq 'parameter.setPaging(false);' "$controller"; then
    echo "[ci-gate] BLOCKED: device export disables paging and can query an unbounded result set" >&2
    echo "  file: $controller" >&2
    echo "  required: enable paging and enforce DeviceExportPolicy" >&2
    exit 1
fi

if ! grep -Fq 'DeviceExportPolicy.requireAllowed(parameter.getPageSize())' "$controller"; then
    echo "[ci-gate] BLOCKED: device export does not enforce the shared export policy" >&2
    exit 1
fi

echo "[ci-gate] PASS: device export is bounded by DeviceExportPolicy"
