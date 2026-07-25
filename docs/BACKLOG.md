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
- **Configurable organization structure.** Presets plus template tokens
  (`{category}/{yyyy}/{mm}`) for the destination layout, with a live preview so the user sees
  where files land before committing. The chosen template is recorded in the catalog. Changing
  the template mid-library must raise an explicit warning and offer an optional migration run
  that relocates existing copies to match. The default stays the current opinionated
  `<Label>/YYYY/MM/` structure — this only unlocks it for users who want a different shape.
  **Priority: first post-UI feature, pre-launch.**
- **Metadata recovery fallback chain (video-date verification).** A full feature, scheduled
  **immediately after the configurable organization structure** above. Today every date comes
  from a single `exiftool` read; some video containers defeat it. Scope, in order:
  1. **Corpus test first.** Assemble real, varied videos — including known-problem formats:
     `.3gp`, `.avi`, WhatsApp-recompressed clips, and old MP4s — and measure where the current
     single `exiftool` read returns *no* date.
  2. **Add only what the corpus proves necessary.** Candidate fallback parsers: `pymediainfo`,
     `hachoir`, `ffprobe`. Each one added must come with a written justification naming a corpus
     file it — and only it — could date. No parser goes in "just in case"; that is how PixSort's
     five-deep chain accreted. Fallbacks fire **only when exiftool finds no date**.
  3. **Provenance per file recorded in the catalog** — which tool supplied the date and from
     which field — so a questionable placement can always be traced back to its source.
  4. **The mtime-never rule stays absolute.** A file that no parser can date goes to `Undated/`,
     never silently placed from filesystem time. (See non-negotiable rule 2 in `docs/CLAUDE.md`.)

  Separately but in the same domain, verified empirically during this investigation: even when
  exiftool *does* return a date, QuickTime container tags (`CreateDate`/`MediaCreateDate`/
  `TrackCreateDate`) are stored in **UTC**, while Apple writes the true local recording moment
  with its offset to `com.apple.quicktime.creationdate` (exiftool tag `CreationDate`). vaeon
  requests the former family and not the latter, so a near-midnight iPhone clip
  (`CreateDate 2023:08:19 20:00:00Z` vs `CreationDate 2023:08:20 01:30:00+05:30`) is misfiled by
  a whole day — a month boundary in the worst case. Requesting `CreationDate` and preferring the
  offset-bearing local tag is a small, dependency-free correctness fix that belongs to this
  feature (or can ship ahead of it). Rationale for the whole feature: the user's firsthand
  experience plus the well-documented community record of multi-field MP4 date chaos.

## Deferred to the desktop UI

- **Event merge/split.** v1 event review is name-or-skip only. Merging and splitting proposed
  clusters were deliberately deferred to the desktop UI — a terminal is the wrong surface for
  interactively re-partitioning clusters.

## Shipped (kept for provenance)

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
