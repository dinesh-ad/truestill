# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to adhere to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
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
