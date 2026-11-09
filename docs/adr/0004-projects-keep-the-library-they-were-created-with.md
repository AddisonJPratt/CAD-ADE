# 4. Projects keep the library they were created with; old projects stay on the geometric fallback

Date: 2026-11-08. Status: accepted. Ticket: #69.

## Context

A new project gets a copy of `library/` (helpers, `standard_parts.json`, printer profiles), and
the copy is committed with every version (`engine/versions.py: create_project`). Projects made
before #65 have a library with no `feature()`, and a design with no `feature(...)` calls, so a
face picked in Studio gets a geometric description ("Face on bracket · front") instead of a
feature name. #69 names the features in the starter designs, and asked whether opening a project
should also refresh its library copy.

## Decision

Opening a project never touches its `library/`. Projects made before #65 stay on the geometric
fallback; new projects from the starters get named faces.

- Refreshing the library names nothing on its own. Names come from `feature(...)` calls in the
  design, and an old project's design (often edited since by the user or the agent) has none.
  Naming it would mean rewriting the design, not syncing a helper file.
- The library is part of each version. A version must rebuild to the geometry it was saved with,
  and a refresh can change it: `standard_parts.json` sets hole, counterbore and insert sizes.
- A refresh on open would leave every old project unsaved the moment it opens, with a diff in
  files the user never edited.

## Consequences

- The worker already tolerates a library without the feature registry (it falls back to no
  features), so old projects keep building and picking exactly as before.
- An agent asked to name features in an old project needs `feature()` first: it brings the
  project's `library/features.py` up to date as an ordinary, reviewed change, saved as a new
  version like any other edit. Starting a fresh project from the starter is the other route.
- If library changes ever need to reach existing projects (a bug in a helper, a corrected
  standard part), that is an explicit, versioned "update library" action, not a side effect of
  opening a project.
