# vaeon - Backlog (approved but unbuilt)

Things that were **decided** but not yet built - captured here so nothing lives only in chat
history. This is not a wishlist of everything possible; only items already agreed, with the
decision context that produced them.

## Approved, not yet built

- **Hash cache (size + mtime keyed).** Approved in the PixSort-extras decision as a re-run
  speedup; never built. mtime is used **only** for change detection, never for date placement
  (that rule is absolute). Today, catalog resume-by-content (`catalog.known_sizes` +
  `seed_rows`) covers re-runs; the cache would additionally skip re-hashing unchanged files
  across runs. Marked convention-not-implemented in `IMPLEMENTATION_STANDARDS.md` §8.
  - **Reference design:** PixSort `backend/pixsort/utils/hash_cache.py` - a small SQLite table
    keyed on `(filepath, file_size, mtime)` → content digest; a lookup validates the file is
    unchanged (size **and** mtime within ~1s) before trusting the cached digest.
  - **Constraints from the PixSort audit (`PixSort/AUDIT_REPORT.md`):** keep **a single cache
    layer** - never a second parallel store (PixSort's dual-store drift was a defect). Invalidate
    an entry on **size OR mtime mismatch**. **Wire cleanup into the run lifecycle** - PixSort
    *defined* `cleanup_stale_entries()` but **never called it anywhere**, so stale rows
    accumulated forever; vaeon must actually invoke pruning as part of a run.
- **GPS-derived per-photo timezone.** Deferred during Takeout Rescue Mode. `--tz` is a single
  fixed offset for the whole run, which cannot correctly date a library that spans timezones;
  the real fix derives each photo's timezone from its GPS. The near-midnight caveat is
  surfaced honestly in the ingest report until this exists.
- **Zip-direct Takeout ingestion.** `vaeon ingest --takeout` takes an already-extracted
  directory today; reading the Takeout `.zip`(s) directly was flagged as a follow-up in the
  Phase-2 spec (deferred to avoid complicating v1).
- **Recognize additional real-world video extensions (l).** The metadata-chain corpus surfaced
  container formats vaeon's `MEDIA_EXTENSIONS` doesn't recognize, so they are skipped (now
  *reported*, not silent). Recognize the ones that are actually common - **`.vob`, `.ts`, `.m2v`,
  and the `.asf` family at minimum** - with the final list driven by **prevalence evidence, not
  the whole corpus zoo** (`.swf`, raw `.hevc`/`.mjpeg` elementary streams are not "photos to back
  up"). Each extension added must have its **category and date handling verified via the corpus
  probe** before inclusion. **Post-launch, demand-driven.**
## Shipped (kept for provenance)

- ~~**`--skip-undated` on organize/ingest (j).**~~ Delivered: default OFF (undateable files still
  copy to `Undated/`); with the flag, they are skipped as `SKIPPED_UNDATED` and **counted + named**
  in the report - never silent. CLI on organize/ingest, plus an app organize toggle.
- ~~**Space-safe move: source reclamation (k).**~~ Delivered as one verify-gated mechanism, two
  surfaces: `organizer.execute(move=True)` / `organize --move` (copy → record → re-verify → delete,
  `MOVE_KEPT` on failure, no zero-copy window) and `reclaim.run_reclaim` / `vaeon reclaim` (dry-run
  default, re-verify-at-delete on a connected drive, typed `delete` confirmation, `--min-copies N`
  with single-copy warning, `reclaim_journal` at schema v9). The copy-only-invariant exception is
  documented in `IMPLEMENTATION_STANDARDS.md §1`. CLI-only in v1 (app surface deferred).

- ~~**Metadata recovery fallback chain - decided on evidence.**~~ A 37-file, 22-format corpus
  test (`docs/metadata-chain-research.md`) showed exiftool already dates every datable file
  (including AVCHD `.mts` and WhatsApp `.mp4`), **no** fallback parser recovered a genuine capture
  date it missed, and naive parsers emit epoch sentinels (1904/1970) that would misfile. Outcome:
  **no parser added**; shipped the never-silent **skipped-file reporting fix** (`scan_source` +
  report); recorded the **sentinel-rejection rule** and ffprobe/schema-v9 reservation as binding
  conventions (`IMPLEMENTATION_STANDARDS.md §1`). The `CreationDate` UTC-vs-local fix shipped
  earlier (`f89fec8`). Remaining follow-on tracked as item (l).
- ~~**Event merge/split.**~~ Delivered in the local web UI's Event review screen (merge/split
  are UI-only capabilities the CLI's name/skip flow lacks), exercised end-to-end through the HTTP
  API against real clustered fixtures. The CLI stays name-or-skip only, by design - a terminal is
  the wrong surface for interactively re-partitioning clusters.
- ~~**Configurable organization structure.**~~ Delivered: `LayoutTemplate` seam + token grammar,
  catalog v7 settings (`layout_template`) + validation, `vaeon config` with 5 presets and live
  preview, and `vaeon migrate-layout` (crash-safe, journaled, catalog v8) plus the app Settings
  screen. Split-era default: a template change affects new files only; migration relocates an
  existing library preview-first. See `docs/org-structure-research.md`.
- ~~**Drive identity + offline catalog + verify.**~~ Delivered: `.vaeon-drive.json` marker,
  catalog v6 (`drives` + `file_copies`), and `vaeon drives`/`where`/`verify`/`status`. See the
  CHANGELOG and `docs/drive-identity-research.md`.

## Product / strategy (parked decisions)

- **Web dedup teaser.** A Pro-tier positioning idea (a lightweight web-facing "find your
  duplicates" hook); not started. Reference stack proven in PixSort's browser mode, all
  **client-side - nothing is uploaded**: `exifr` (image EXIF), `mediainfo.js` (WASM, video
  dates), `hash-wasm` (BLAKE3 hashing in the browser). PixSort's `lib/metadata.ts` and
  `lib/hash.ts` (present under both `frontend/` and `apps-platform/`) are the reference
  implementations to study when we build this.
- **Desktop UI: Tauri vs local-web.** Parked architecture decision. The Rust-backed Tauri path
  informed the SHA-256/no-BLAKE3 hashing choice; the event-review interaction is the feature
  that will ultimately force the decision.
  - **(o) Lessons from the PixSort audit** (`PixSort/AUDIT_REPORT.md`): whatever wraps the UI,
    **one process serves the real UI**, bound to **loopback only**, and there is **never a second
    framework runtime beside the Python core**. PixSort's Electron+Next.js shell ran a whole JS
    runtime alongside the backend - the coupling and bundle weight it caused is exactly what
    vaeon's single-process, server-rendered, no-build local-web UI avoids. A native shell (if ever
    built) wraps that one process; it does not add a second app runtime.

## Ideas / deferred

- **(m) Duplicate-cleanup staging UX.** A **preview → confirm → trash (with restore)** flow for
  removing duplicates - the validated safe-delete pattern (same spirit as `reclaim`'s dry-run +
  typed confirm, but for dedup). Note the real gap PixSort never closed: vaeon's near-duplicate
  review still needs a **visual side-by-side compare** (show the two look-alikes at actual pixels
  so a human decides which to keep) - PixSort had no such compare, and a trash-with-restore is
  only trustworthy once the human can actually *see* what they're removing.
- **(n) "How your dates were determined" honesty stat.** A per-run/library figure in the
  reports/UI showing the **provenance mix** of capture dates - e.g. "82% from embedded EXIF, 11%
  from filename, 5% from Takeout, 2% Undated" (a metadata-accuracy %). vaeon already resolves and
  could persist `date_source` (see the metadata-chain §1b.3 schema-v9 note); surfacing it honestly
  tells a user how much to trust their timeline, in vaeon's report voice.
