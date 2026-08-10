# CLAUDE.md

Repository-local guidance for day-to-day work in this repo.

## Read first

1. `PROJECT_STATUS.md` - current state, what is next, blockers.
2. `ENGINEERING_STANDARD.md` - portable workflow and coding standard.
3. `IMPLEMENTATION_STANDARDS.md` - binding contract.

`IMPLEMENTATION_STANDARDS.md` wins on any conflict.

For document ownership and map-by-question, use root `../CLAUDE.md`.

**Before building anything from `BACKLOG.md`, check `SHIPPED.md`.** The two share one letter
namespace and answer opposite questions; a letter missing from the backlog is shipped or retired,
never free. Neither doc map named `SHIPPED.md` until 2026-08-10, which left a cold start with no
route to *"is this already built?"* - the question the file exists to answer.

## What this file is (and is not)

- This is a **quick orientation** for contributors already inside the repo.
- This is **not** the product spec, architecture contract, or historical record.
- Avoid duplicating rules here that already live in `IMPLEMENTATION_STANDARDS.md`.

## Minimal repo shape

- `packages/truestill-core/` - core library and safety-critical logic.
- `packages/truestill-cli/` - `truestill` command surface.
- `packages/truestill-app/` - local web UI (`truestill-app`), imports core only.
- `docs/` - decisions, standards, backlog, and research records.

## Practical reminders

- **Inner loop: targeted tests only.** Never the full gate on an edit.
- **`make check` before every commit** - 19-33 s for 2,080 tests, which is not friction.
- **`make gate` when the diff reaches the browser.** It runs `check`, then `e2e` only if the diff
  touches `packages/truestill-app/src/` or `tests/e2e/`, and prints what decided it. The reason
  for skipping the browser lane is a command's output, never a recollection.
- The browser lane stays separate from `make check` and out of a fresh clone's path: `make check`
  is green with no browser installed. `IMPLEMENTATION_STANDARDS.md` §6.1 is the binding rule.
- `exiftool` must be installed and on PATH for metadata paths.
- Treat `docs/*-research.md` as historical records: keep findings/rejections, do not rewrite
  them into present-tense truth.
