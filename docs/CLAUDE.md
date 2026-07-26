# CLAUDE.md

Guidance for working in this repository.

## Read first (the two-document contract)

At the start of every session, read both:

1. [`docs/ENGINEERING_STANDARD.md`](ENGINEERING_STANDARD.md) - the portable canon (workflow,
   research order, code standard).
2. [`docs/IMPLEMENTATION_STANDARDS.md`](IMPLEMENTATION_STANDARDS.md) - the binding, repo-specific
   contract (product invariants, architecture, data, process, quality gates).

**`IMPLEMENTATION_STANDARDS.md` wins on any conflict** - with each other, and with the notes
below (which are a quick summary, not the contract).

## What this is

A media library organizer: analyse files, derive a folder label from each file's own
metadata, and place them into `<Label>/YYYY/MM/`. Built to organize a Google Photos
export before it is pushed to long-term storage.

## Non-negotiable design rules

1. **Never hard-code the set of category folders.** Labels are *derived* from evidence.
   If a new source needs supporting, add a row to `NAME_PATTERNS` in `categorize.py` or
   let the `software`/`device` rules derive it. Do not reintroduce a `Category` enum.
2. **Never consult filesystem mtime for dating.** Google's export zips carry the
   download time, not the capture time. Metadata first, filename convention second,
   `Undated/` third. Dates are never guessed.
3. **Never overwrite.** Collisions are resolved by content hash: identical is a skipped
   duplicate, different is written with a numeric suffix.
4. **Dry run is the default.** Planning is pure and touches nothing; `execute(apply=True)`
   is the only code path that writes.
5. **Rule order is load-bearing.** Screenshot and messenger rules run *before* device
   metadata, because screenshots and messenger files often carry device tags that would
   otherwise misfile them. Tests pin this; do not reorder without updating them.

## Layout

A uv workspace of three packages: the core library, the CLI, and the local web UI. The UI
package sits *beside* the core and depends only on it - never on the CLI.

```
packages/
├── truestill-core/src/truestill_core/   # the library (importable, typed, py.typed)
│   ├── models.py       dataclasses + enums; Category is a plain str label, by design
│   ├── exif.py         batched exiftool JSON reads (no per-file process spawn)
│   ├── dates.py        capture-date resolution and filename date conventions
│   ├── categorize.py   the ordered rule chain; NAME_PATTERNS is the extension point
│   ├── naming.py       the YYYYMMDD_HHMMSS_<original> copy filename
│   ├── hashing.py      SHA-256 (content) + dHash (perceptual)
│   ├── scan.py         concurrent hashing pass with the byte-size pre-filter
│   ├── dedup.py        two-tier duplicate index (exact skip, perceptual keep+flag)
│   ├── catalog.py      SQLite state; schema versioned via PRAGMA user_version
│   ├── drive.py        drive identity marker (+ legacy-name compatibility)
│   ├── layout.py       the destination folder LayoutTemplate and its presets
│   ├── migrate.py      crash-safe, journalled re-layout of an existing drive
│   ├── reclaim.py      verify-gated source deletion (opt-in, journalled)
│   ├── verify.py       re-hash a connected drive's copies against the catalog
│   ├── events.py       pure camera-event clustering (no I/O)
│   ├── event_review.py the interactive event naming/merge/split stage
│   ├── takeout.py      Google Takeout sidecar parsing and date rescue
│   ├── progress.py     the ProgressCallback seam shared by CLI and app
│   ├── destinations/   pluggable Destination backends (local, rclone)
│   └── organizer.py    pure planning, then opt-in execution
├── truestill-cli/src/truestill_cli/     # the `truestill` command (thin wrapper over the core)
│   ├── cli.py          argparse entry point and the decision report
│   ├── events_review.py terminal prompts for the event stage
│   └── __main__.py     python -m truestill_cli
└── truestill-app/src/truestill_app/     # the `truestill-app` local web UI (Starlette)
    ├── server.py       the application factory: routes, SSE, static, token guard
    ├── service.py      the bridge to truestill-core (imports core only, never the CLI)
    ├── security.py     localhost token guard (X-Truestill-Token / ?token=)
    ├── jobs.py         background job registry for long-running runs
    ├── templates/      server-rendered HTML (no bundler, no npm)
    └── static/         tokens.css + app.css + vanilla-JS app.js
```

Shared ruff/mypy/pytest config lives in the virtual workspace root `pyproject.toml`.

## Conventions

Matches the house style used in `~/ad/application/nexdue`: uv + hatchling, ruff
(line-length 100, double quotes), mypy with `disallow_untyped_defs`, pytest, and a
`Makefile` wrapping `uv run`. `make check` runs across all workspace members.

Run `make check` before considering work done.

## External dependency

`exiftool` (Ubuntu: `libimage-exiftool-perl`) must be on PATH. It is the *only* metadata
reader: a Python EXIF library would cover photos only and would not see video container
tags or the vendor MakerNotes the screenshot rule depends on.

Runtime Python dependencies are deliberately minimal and must justify themselves against
the stdlib - `imagehash` + `pillow` + `pillow-heif` in `truestill-core` (perceptual hashing
needs image decoding, which the stdlib cannot do), and `starlette` + `uvicorn` in
`truestill-app`. `truestill-cli` adds none. The authoritative inventory, with the reasoning
for each, is `IMPLEMENTATION_STANDARDS.md` §7.
