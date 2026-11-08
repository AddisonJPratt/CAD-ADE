#!/bin/sh
set -eu
MAGIC_TEST_PROJECT=$(mktemp -d "${TMPDIR:-/tmp}/magic-cad-studio.XXXXXXXX")
export MAGIC_TEST_PROJECT
# New projects from the open screen go here, never into ~/Magic CAD Projects.
MAGIC_PROJECTS_HOME=$(mktemp -d "${TMPDIR:-/tmp}/magic-cad-home.XXXXXXXX")
export MAGIC_PROJECTS_HOME
trap 'rm -rf "$MAGIC_TEST_PROJECT" "${MAGIC_PROJECTS_HOME:-}"' EXIT
../.venv/bin/python tests/setup.py
npx tsc --noEmit
npx playwright test "$@"
