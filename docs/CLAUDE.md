# CLAUDE.md

Guidance for working in this repository.

## Read first

Start with [`PROJECT_STATUS.md`](PROJECT_STATUS.md) - where the project stands and what
ships next. Then the contract:

1. [`docs/ENGINEERING_STANDARD.md`](ENGINEERING_STANDARD.md) - the portable canon (workflow,
   research order, code standard).
2. [`docs/IMPLEMENTATION_STANDARDS.md`](IMPLEMENTATION_STANDARDS.md) - the binding, repo-specific
   contract (product invariants, architecture, data, process, quality gates).

**`IMPLEMENTATION_STANDARDS.md` wins on any conflict** - with each other, and with the notes
below (which are a quick summary, not the contract).

Settled product stances live in [`DECISIONS.md`](DECISIONS.md); approved-but-unbuilt work in
[`BACKLOG.md`](BACKLOG.md). The root [`../CLAUDE.md`](../CLAUDE.md) carries the full document map.

## What this is

**Truestill** - a local-first media organizer, de-duplicator and backup pipeline. It analyses
a photo/video library, derives a folder label from each file's own metadata, and places copies
into a `<Label>/YYYY/MM/` tree. Originally built to rescue a Google Photos Takeout export
(where capture dates survive only in JSON sidecars), but nothing in it is Google-specific.

Beyond organizing, it owns the whole custody story: content-addressed drive identity, an
offline catalog of which drive holds which copy, re-hash verification, 3-2-1 backup to a
second drive, crash-safe re-layout, and verify-gated reclaim of source files that are
provably backed up.

Two front-ends over one core library:

- **`truestill`** - the CLI (organize, ingest, drives, where, verify, status, config,
  reclaim, migrate-layout).
- **`truestill-app`** - a local web UI on `127.0.0.1`, token-authenticated, server-rendered,
  no bundler. Co-equal with the CLI, not a replacement.

Your files never leave your machine. No accounts, no telemetry - permanently (`DECISIONS.md` D1).

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
