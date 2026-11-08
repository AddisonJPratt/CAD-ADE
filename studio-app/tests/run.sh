#!/bin/sh
set -eu
MAGIC_TEST_PROJECT=$(mktemp -d "${TMPDIR:-/tmp}/magic-cad-studio.XXXXXXXX")
export MAGIC_TEST_PROJECT
# New projects from the open screen go here, never into ~/Magic CAD Projects. Its own folder,
# not inside the test project: the home also keeps the recently-opened list, which must not
# show up as an unsaved change in a project.
MAGIC_PROJECTS_HOME=$(mktemp -d "${TMPDIR:-/tmp}/magic-cad-home.XXXXXXXX")
export MAGIC_PROJECTS_HOME
# Make mode records print results in the print log: never the repo's real prints/PRINT_LOG.md.
MAGIC_PRINT_LOG="$MAGIC_PROJECTS_HOME/PRINT_LOG.md"
export MAGIC_PRINT_LOG
trap 'rm -rf "$MAGIC_TEST_PROJECT" "$MAGIC_PROJECTS_HOME"' EXIT
../.venv/bin/python tests/setup.py
npx tsc --noEmit
npx playwright test "$@"
