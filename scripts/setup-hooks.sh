#!/bin/sh
set -eu

repo_root=$(git rev-parse --show-toplevel)
git config core.hooksPath .githooks

echo "Pre-commit hook enabled for: $repo_root"
echo "Run 'git config --get core.hooksPath' to verify the setting."
