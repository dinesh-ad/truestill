# CLAUDE.md

Repository-local guidance for day-to-day work in this repo.

## Read first

1. `PROJECT_STATUS.md` - current state, what is next, blockers.
2. `ENGINEERING_STANDARD.md` - portable workflow and coding standard.
3. `IMPLEMENTATION_STANDARDS.md` - binding contract.

`IMPLEMENTATION_STANDARDS.md` wins on any conflict.

For document ownership and map-by-question, use root `../CLAUDE.md`.

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

- Run `make check` before considering work done.
- Browser lane is explicit (`make e2e`), separate from `make check`.
- `exiftool` must be installed and on PATH for metadata paths.
- Treat `docs/*-research.md` as historical records: keep findings/rejections, do not rewrite
  them into present-tense truth.
