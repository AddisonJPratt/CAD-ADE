#!/bin/sh
set -eu
MAGIC_TEST_PROJECT=$(mktemp -d "${TMPDIR:-/tmp}/magic-cad-studio.XXXXXXXX")
export MAGIC_TEST_PROJECT
trap 'rm -rf "$MAGIC_TEST_PROJECT"' EXIT
../.venv/bin/python tests/setup.py
npx tsc --noEmit
npx playwright test "$@"
