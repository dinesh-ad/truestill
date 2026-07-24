# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to adhere to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- uv workspace layout: `vaeon-core` (library) and `vaeon-cli` (the `vaeon` command),
  ready for future packages (desktop/UI) without restructuring the core.
- Concurrent hashing scan with a byte-size pre-filter (`vaeon_core.scan`); thread/process
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

[Unreleased]: https://github.com/dinesh-ad/vaeon
