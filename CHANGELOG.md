# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to adhere to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **In-place organize (`organize --in-place`)** for libraries that live on the drive itself -
  a pendrive or external HDD with no staging space to copy into. Files are moved by **atomic
  rename**: no bytes are rewritten, there is no instant at which the content does not exist,
  and the content hash is unchanged because the inode is. Plain `--move` now takes the same
  fast path automatically wherever the filesystem allows; `--in-place` additionally *requires*
  it, refusing a cross-device destination rather than quietly consuming space the user said
  they did not have. `--apply` needs a typed `move` confirmation, and the run reports its
  mechanism split ("3 moved by rename · 1 copied across devices").
- **`truestill undo-organize`** - reverse an in-place run, restoring every file to its exact
  prior path. Preview by default, `--apply` to move; `--list` shows recorded runs, and
  `--source-root`/`--dest-root` handle a drive that has remounted elsewhere. It ships *with*
  the feature rather than after it: a rename cannot lose bytes, so what is at risk is the
  *arrangement* of a library whose owner, by definition of this feature, has no second copy.
- Catalog **schema v10**: `inplace_runs` + `inplace_moves`, a **reversible** journal (where
  each file moved) rather than an audit one (what was destroyed).

### Added
- **`docs/PERFORMANCE.md`** - the measured baseline per pipeline stage, the two known scaling
  limits with their thresholds, and a list of things a future optimizer should **not** "improve"
  (the size pre-filter above all). It carries one binding rule, referenced from the quality
  gates: every new pipeline stage declares its complexity in *n*, and anything worse than
  O(n log n) must justify itself.
- **A runtime alarm on the one known O(n²).** Perceptual dedup's linear scan is 0.7s at 2,275
  images and deliberately left alone; the first index to pass 10,000 now logs one line saying
  so, rather than leaving the trigger in a document nobody reads.

### Fixed
- **`reclaim` can no longer delete the only copy of a file organized in place.** Such a file
  is both the source and the drive copy - one inode - so reclaim's re-verify gate was
  satisfied by the file checking against itself, and it would have deleted content with no
  backup anywhere. Those files are now excluded, and the count is reported rather than
  silently dropped.

### Changed
- **Takeout metadata baking is ~27x faster.** Writing a rescued date or location into an
  organized copy spawned one `exiftool` process per file - **254.9 ms/file** measured, almost
  all of it process startup, which is about **7 hours** for a 100,000-file Takeout and 5
  minutes for a 1,200-file one. Writes are now batched (100 files per process, staged and
  baked a chunk at a time): **9.3 ms/file**, staging copy included, or ~15.6 min at 100k.
  The originals are still never touched - the batch bakes staged copies - and a process that
  dies mid-batch is **detected**, with every unconfirmed file reported failed rather than
  counted as organized.
- **The custody strip stopped doing 13x more work than it displays.** "Safe in N places" was
  building and sorting every at-risk row and then taking its length; it now counts. 224 ms →
  17.5 ms at 100,000 files, on a query that runs after every operation and on every load.
- **Renamed the project `vaeon` → `truestill`.** Distributions are now `truestill-core`,
  `truestill-cli` and `truestill-app`; the import packages are `truestill_core`,
  `truestill_cli` and `truestill_app`; the console commands are `truestill` and
  `truestill-app`; the app's auth header is `X-Truestill-Token`. The repository moved to
  `github.com/dinesh-ad/truestill`.
- Drive markers are now written as `.truestill-drive.json`. **Drives initialised before the
  rename keep working**: `.vaeon-drive.json` is still read, its `uuid`/`label`/`created` are
  preserved verbatim (the uuid is the catalog's foreign key, so re-minting would orphan every
  recorded copy), and the old file is never deleted. Reads never write; upgrading is explicit
  via `truestill drives --migrate-marker ROOT`. Precedence when both exist: the canonical
  file wins. See `IMPLEMENTATION_STANDARDS.md` §3.1.

### Added
- Drive identity, offline catalog & verify: a `.vaeon-drive.json` marker (truestill-minted `uuid4`,
  never the mount path) identifies each backup drive. Catalog schema v6 adds a `drives` table and
  a per-(content, drive) `file_copies` location table (with a per-copy `copy_sha256`, since a
  baked copy is not byte-identical to its source). `truestill drives` (list/`--init`),
  `truestill where <term>` (which drive is a file on, fully offline), `truestill verify <path>` (re-hash a
  connected drive's copies → verified/MISSING/MISMATCH, read-only, worker-pool), and
  `truestill status` (single-copy 3-2-1 nudge). Scoped to local destinations. See
  `docs/drive-identity-research.md`.
- Google Takeout Rescue Mode (`truestill ingest --takeout <dir>`): matches each media file to its
  JSON sidecar (all naming variants -- classic, `supplemental-metadata`, truncated, `-edited`,
  relocated `(n)`), recovers `photoTakenTime`/GPS/description into the existing dating and dedup
  pipeline, bakes rescued metadata into the organized copy losslessly via exiftool (source
  untouched; catalog stores both source and post-write copy hashes), collapses album duplicate
  copies while recording album membership, and prints an honest end-of-run rescue report.
  Timezone-aware (`--tz ±HH:MM`, single UTC->local conversion), `--prefer-takeout-dates` for
  libraries fixed inside Google Photos, `--map-albums` to name Camera events after their album.
  See `docs/takeout-format.md`. Catalog schema v5.
- CLI restructured into subcommands (`truestill organize`, `truestill ingest`).
- Event layer (`--events`, opt-in, Camera-only): adaptive log-scale temporal-gap clustering
  with GPS-jump reinforcement proposes events for the user to name or skip (never
  auto-named). Named events become `Camera/YYYY/MM/YYYYMMDD_<slug>/`, consolidated under the
  start month across month boundaries. Cluster identity is the hash of member SHA-256s, so
  names and skips are remembered (schema v4) and re-proposed only when membership changes.
  Sensitivity default (4.0) tuned so multi-day trips stay whole; see `scripts/tune_events.py`.
- Filename convention: organized copies are named `YYYYMMDD_HHMMSS_<original>` (date-only
  when the time is unknown) from the same date evidence used for placement. The prefix is
  suppressed only when that exact stamp already appears in the name, so date-embedded names
  (screenshots) are not double-dated and re-runs never stack a prefix; any mismatch keeps
  the authoritative metadata prefix. Originals are never renamed; the catalog records the
  original name alongside the new one. Disable with `--no-rename`.
- uv workspace layout: `truestill-core` (library) and `truestill-cli` (the `truestill` command),
  ready for future packages (desktop/UI) without restructuring the core.
- Concurrent hashing scan with a byte-size pre-filter (`truestill_core.scan`); thread/process
  pool selectable via `--pool`, worker count via `--workers`.
- SQLite catalog schema versioning via `PRAGMA user_version` with ordered, idempotent
  migrations; refuses catalogs written by a newer version.
- `Saved/` category for metadata-stripped social/web images (renamed from `Unsorted/`),
  plus a low-resolution + no-camera-EXIF heuristic that flags likely social saves.
- Two-tier de-duplication: exact (SHA-256) skipped, perceptual (dHash) near-duplicates
  kept-and-flagged so an original is never silently dropped for a look-alike.
- Pluggable `Destination` interface with local and rclone backends.
- Project hygiene: cross-platform CI (Linux/macOS/Windows, Python 3.13), pre-commit
  hooks (ruff + mypy), `py.typed`, package metadata, this changelog.

### Notes
- SHA-256 is the sole content hash (hardware-accelerated via OpenSSL); BLAKE3 is
  deliberately not used, keeping one catalog column and no compiled dependency.
- Dates come from embedded metadata first, filename convention second, `Undated/`
  never from filesystem mtime.

[Unreleased]: https://github.com/dinesh-ad/truestill
