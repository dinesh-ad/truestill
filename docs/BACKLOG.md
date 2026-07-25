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
- **Metadata recovery fallback chain (video-date verification).** A full feature, scheduled
  **next** (the configurable organization structure it once trailed has shipped — see below).
  Today every date comes from a single `exiftool` read; some video containers defeat it. Scope,
  in order:
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
  offset-bearing local tag is a small, dependency-free correctness fix. **Shipped ahead of the
  feature** (`core(dates)`, commit `f89fec8`): `CreationDate` is now requested and ranked above
  the UTC container tags, converted exactly once, pinned by tests. Rationale for the remaining
  feature: the user's firsthand experience plus the community record of multi-field MP4 chaos.
- **`--skip-undated` on organize/ingest.** Default **OFF** — for backup completeness, files that
  cannot be dated still copy to `Undated/` where they are visible, never dropped. When the flag
  is on, the skipped files are counted **and named** in the end-of-run report; neither posture is
  ever silent about what happened to an undateable file. **Priority: pre-launch, after the
  metadata recovery fallback chain** (which shrinks the undated set first).
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
  when built. **Priority: pre-launch, after the metadata recovery fallback chain.**

## Shipped (kept for provenance)

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
