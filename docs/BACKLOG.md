# vaeon — Backlog (approved but unbuilt)

Things that were **decided** but not yet built — captured here so nothing lives only in chat
history. This is not a wishlist of everything possible; only items already agreed, with the
decision context that produced them.

## Approved, not yet built

- **Hash cache (size + mtime keyed).** Approved in the PixSort-extras decision as a re-run
  speedup; never built. mtime is used **only** for change detection, never for date placement
  (that rule is absolute). Today, catalog resume-by-content (`catalog.known_sizes` +
  `seed_rows`) covers re-runs; the cache would additionally skip re-hashing unchanged files
  across runs. Marked convention-not-implemented in `IMPLEMENTATION_STANDARDS.md` §8.
- **GPS-derived per-photo timezone.** Deferred during Takeout Rescue Mode. `--tz` is a single
  fixed offset for the whole run, which cannot correctly date a library that spans timezones;
  the real fix derives each photo's timezone from its GPS. The near-midnight caveat is
  surfaced honestly in the ingest report until this exists.
- **Zip-direct Takeout ingestion.** `vaeon ingest --takeout` takes an already-extracted
  directory today; reading the Takeout `.zip`(s) directly was flagged as a follow-up in the
  Phase-2 spec (deferred to avoid complicating v1).

## Deferred to the desktop UI

- **Event merge/split.** v1 event review is name-or-skip only. Merging and splitting proposed
  clusters were deliberately deferred to the desktop UI — a terminal is the wrong surface for
  interactively re-partitioning clusters.

## Next feature (agreed direction)

- **Drive identity + offline catalog + verify.** The intended next feature: identify a
  specific destination drive, keep an offline catalog of what already lives on it, and verify
  copies against their `copy_sha256` (the verification-identity hash the dual-hash rule was
  built to enable). Enables safe resume and integrity checks without re-reading the whole
  destination.

## Product / strategy (parked decisions)

- **Web dedup teaser.** A Pro-tier positioning idea (a lightweight web-facing "find your
  duplicates" hook); not started.
- **Desktop UI: Tauri vs local-web.** Parked architecture decision. The Rust-backed Tauri path
  informed the SHA-256/no-BLAKE3 hashing choice; the event-review interaction is the feature
  that will ultimately force the decision.
