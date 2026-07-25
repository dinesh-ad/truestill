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
- **Recognize additional real-world video extensions (l).** The metadata-chain corpus surfaced
  container formats vaeon's `MEDIA_EXTENSIONS` doesn't recognize, so they are skipped (now
  *reported*, not silent). Recognize the ones that are actually common — **`.vob`, `.ts`, `.m2v`,
  and the `.asf` family at minimum** — with the final list driven by **prevalence evidence, not
  the whole corpus zoo** (`.swf`, raw `.hevc`/`.mjpeg` elementary streams are not "photos to back
  up"). Each extension added must have its **category and date handling verified via the corpus
  probe** before inclusion. **Post-launch, demand-driven.**
- **`--skip-undated` on organize/ingest.** Default **OFF** — for backup completeness, files that
  cannot be dated still copy to `Undated/` where they are visible, never dropped. When the flag
  is on, the skipped files are counted **and named** in the end-of-run report; neither posture is
  ever silent about what happened to an undateable file. **Priority: pre-launch (next).**
- **Space-safe move: source reclamation.** Two surfaces over one mechanism, so organizing a large
  library does not require 2× disk space:
  - `--move` on `organize` — per file: copy → hash-verify the destination copy → **only then**
    delete the source. Interruption-safe and verification-gated: a failed verify never deletes.
  - `vaeon reclaim` — a standalone command that deletes only source files whose destination
    copies are **catalog-verified**, with its own dry-run preview reporting the count and the
    space that would be freed.

  Both require an explicit flag **and** a confirmation worded with honest destructive-action
  language. This is a **documented, contained exception to the copy-only invariant**, scoped
  exactly like the Takeout metadata-write path — update `IMPLEMENTATION_STANDARDS.md` accordingly
  when built. **Priority: pre-launch (with `--skip-undated`).**

## Shipped (kept for provenance)

- ~~**Metadata recovery fallback chain — decided on evidence.**~~ A 37-file, 22-format corpus
  test (`docs/metadata-chain-research.md`) showed exiftool already dates every datable file
  (including AVCHD `.mts` and WhatsApp `.mp4`), **no** fallback parser recovered a genuine capture
  date it missed, and naive parsers emit epoch sentinels (1904/1970) that would misfile. Outcome:
  **no parser added**; shipped the never-silent **skipped-file reporting fix** (`scan_source` +
  report); recorded the **sentinel-rejection rule** and ffprobe/schema-v9 reservation as binding
  conventions (`IMPLEMENTATION_STANDARDS.md §1`). The `CreationDate` UTC-vs-local fix shipped
  earlier (`f89fec8`). Remaining follow-on tracked as item (l).
- ~~**Event merge/split.**~~ Delivered in the local web UI's Event review screen (merge/split
  are UI-only capabilities the CLI's name/skip flow lacks), exercised end-to-end through the HTTP
  API against real clustered fixtures. The CLI stays name-or-skip only, by design — a terminal is
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
  **client-side — nothing is uploaded**: `exifr` (image EXIF), `mediainfo.js` (WASM, video
  dates), `hash-wasm` (BLAKE3 hashing in the browser). PixSort's `lib/metadata.ts` and
  `lib/hash.ts` (present under both `frontend/` and `apps-platform/`) are the reference
  implementations to study when we build this.
- **Desktop UI: Tauri vs local-web.** Parked architecture decision. The Rust-backed Tauri path
  informed the SHA-256/no-BLAKE3 hashing choice; the event-review interaction is the feature
  that will ultimately force the decision.
