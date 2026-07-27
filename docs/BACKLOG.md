# truestill - Backlog (approved but unbuilt)

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
    accumulated forever; truestill must actually invoke pruning as part of a run.
- **GPS-derived per-photo timezone.** Deferred during Takeout Rescue Mode. `--tz` is a single
  fixed offset for the whole run, which cannot correctly date a library that spans timezones;
  the real fix derives each photo's timezone from its GPS. The near-midnight caveat is
  surfaced honestly in the ingest report until this exists.
- **Zip-direct Takeout ingestion.** `truestill ingest --takeout` takes an already-extracted
  directory today; reading the Takeout `.zip`(s) directly was flagged as a follow-up in the
  Phase-2 spec (deferred to avoid complicating v1).
- **Recognize additional real-world video extensions (l).** The metadata-chain corpus surfaced
  container formats truestill's `MEDIA_EXTENSIONS` doesn't recognize, so they are skipped (now
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
  `MOVE_KEPT` on failure, no zero-copy window) and `reclaim.run_reclaim` / `truestill reclaim` (dry-run
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
  earlier (`01ebaa0`). Remaining follow-on tracked as item (l).
- ~~**Event merge/split.**~~ Delivered in the local web UI's Event review screen (merge/split
  are UI-only capabilities the CLI's name/skip flow lacks), exercised end-to-end through the HTTP
  API against real clustered fixtures. The CLI stays name-or-skip only, by design - a terminal is
  the wrong surface for interactively re-partitioning clusters.
- ~~**Configurable organization structure.**~~ Delivered: `LayoutTemplate` seam + token grammar,
  catalog v7 settings (`layout_template`) + validation, `truestill config` with 5 presets and live
  preview, and `truestill migrate-layout` (crash-safe, journaled, catalog v8) plus the app Settings
  screen. Split-era default: a template change affects new files only; migration relocates an
  existing library preview-first. See `docs/org-structure-research.md`.
- ~~**Drive identity + offline catalog + verify.**~~ Delivered: `.vaeon-drive.json` marker,
  catalog v6 (`drives` + `file_copies`), and `truestill drives`/`where`/`verify`/`status`. See the
  CHANGELOG and `docs/drive-identity-research.md`.

## Product / strategy (parked decisions)

> **Settled stance these sit under:** truestill has **no user accounts and no required telemetry,
> permanently**; Pro is gated by **offline-verified license keys, not a login**. Any Pro-tier item
> below inherits that constraint. Full decision + rationale: `docs/DECISIONS.md` D1
> (binding invariant in `IMPLEMENTATION_STANDARDS.md §1`).

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
    truestill's single-process, server-rendered, no-build local-web UI avoids. A native shell (if ever
    built) wraps that one process; it does not add a second app runtime.

## Ideas / deferred

- **(m) Duplicate-cleanup staging UX.** A **preview → confirm → trash (with restore)** flow for
  removing duplicates - the validated safe-delete pattern (same spirit as `reclaim`'s dry-run +
  typed confirm, but for dedup). Note the real gap PixSort never closed: truestill's near-duplicate
  review still needs a **visual side-by-side compare** (show the two look-alikes at actual pixels
  so a human decides which to keep) - PixSort had no such compare, and a trash-with-restore is
  only trustworthy once the human can actually *see* what they're removing.

  **Binding design constraints, from reviewing PixSort's live duplicate screen:**

  1. **Never auto-select keep/remove by filesystem timestamp.** Observed on real data: PixSort's
     "keep oldest" chose a `(Copy).jpg` to **keep** and the original to **remove**, because the
     mtimes lied - a copy operation had rewritten them. This is the **same lie truestill already
     refuses for dating** (`IMPLEMENTATION_STANDARDS.md` §1: "Dating uses an evidence chain, never
     filesystem mtime"). That invariant currently governs *placement* only; item (m) extends the
     identical distrust to **keep/remove selection**, where being wrong is irreversible rather
     than merely untidy. The corpus already contains this exact shape (`scan-a.jpg` + its
     `(Copy)`), so it is testable on day one.
  2. **Rank by evidence, in this order:** embedded capture date → resolution / bitrate →
     original filename pattern (a `(Copy)`/`(1)`/`-kopie` suffix is evidence *against* being the
     original) → catalog provenance (what truestill already recorded about where each copy came
     from). Every one of these is a property of the *file*, not of the filesystem around it.
  3. **Default to NO pre-selection when the evidence is ambiguous.** A pre-ticked checkbox is a
     recommendation the user will accept without reading; if truestill cannot prove which copy is
     the original, it must say so and select nothing. **A reviewed decision, not a trusted
     heuristic** - and never a heuristic wearing a decision's clothes.
  4. **Staged trash-with-restore, never a permanent delete**, with the two actions labelled by
     consequence - **"Recommended"** vs **"Irreversible"** - so the dangerous one is never the
     path of least resistance. Same spirit as `reclaim`'s typed `delete` confirmation.
  5. **Adopt the honest capability notice pattern**: state plainly what the screen can and cannot
     determine, in place, rather than implying more certainty than the evidence supports. This is
     the never-silent rule applied to a UI surface - the existing precedents are the HEIC
     perceptual-skip notice and the Tier A / Tier B date-quality lines.
- **(n) "How your dates were determined" honesty stat — PRIORITIZED for first post-launch.** A
  per-run/library figure in the reports/UI showing the **provenance mix** of capture dates - e.g.
  "82% from embedded EXIF, 11% from filename, 5% from Takeout, 2% Undated" (a metadata-accuracy %).
  truestill already resolves and could persist `date_source` (see the metadata-chain §1b.3 schema-v9
  note); surfacing it honestly tells a user how much to trust their timeline, in truestill's voice.
  - **Validated by the UI-v2 walkthrough:** the organize result's "**N no date → Undated**" line
    confused a first user — a bare count with no way in. It must be **explorable**: click it to see
    *which* files were undated and *why* no date was found (which tags were checked, whether a
    filename date was tried). Same treatment for the provenance mix — each slice drills to its
    files. This is the concrete first slice of (n) to build first post-launch.
- **(p) "Share safely" — metadata-stripping export. PRO TIER (behind the capability seam).**
  A dedicated **export** action that writes cleaned copies for sharing, so a user can post a photo
  without leaking where they live or what device they use. Market demand is documented (a whole app
  category — CleanShots, ExifStrip, etc.; dating / kids / marketplace / forum use cases; email /
  Slack / Telegram-file preserve EXIF). **Design decisions, recorded now:**
  1. **Export-only, never a library operation.** The user selects files; truestill writes cleaned
     copies to a dedicated **share-export folder**. The organized library and the originals keep
     their full metadata, untouched. A strip control anywhere near the library would contradict
     truestill's metadata-preservation identity and invite accidents — it lives only in this export.
  2. **Complete removal, verified.** `exiftool -all=` on the copy (clears EXIF + XMP + IPTC +
     MakerNotes + embedded thumbnails — the thumbnail is the classic leak); for video, an exiftool
     pass **plus** an ffmpeg container rewrite (`-map_metadata -1`, no re-encode) for the
     `uuid`/`udta` boxes; handle **Live Photo** JPEG+MOV pairs together. Then **re-scan each output**
     and produce a verification report ("0 metadata fields remain") — the never-silent rule applied
     to removal. UI states honestly that cleaning affects the *copies*; the originals still exist
     with their metadata (that is the point).
  3. **Folder protection + lineage.** The share-export folder gets a `.truestill-shared.json` marker;
     the scanner **refuses a marked folder as an organize source** with a clear explanation (so
     dateless cleaned copies are never re-swept into `Undated/`). The catalog records lineage
     (cleaned copy ↔ source hash) so dedup never mistakes a stripped copy for a lost original.
  4. **Modes:** **strip-all** (default) and **GPS-only** — the two the market ships.

  Post-launch build; Pro-tier candidate. Research refs to carry in: the embedded-thumbnail trap,
  the XMP/IPTC/MakerNotes layers, MP4 container metadata boxes, and Live Photo pairing.
- **(q) In-place organize (same-device optimization). Strong candidate for first post-soak.**
  Documented demand: users whose **drive *is* the library** - a pendrive or external HDD as the
  only copy, with no staging space to copy into (Adobe-forum threads request exactly this).
  Today truestill always writes a second copy, which such a user has nowhere to put. Widens the
  addressable audience at low cost on existing machinery. **Final placement decided after soak.**

  **Design (decided):**
  1. **Mechanism: extends `--move`**, the existing opt-in source-deletion exception - never a
     default, same honest destructive labelling. When source and destination share a filesystem,
     use an atomic per-file **rename** instead of copy → verify → delete: zero bytes rewritten,
     no interruption window, and the content hash is unchanged *by definition* (same inode), so
     no re-verify is needed. Cross-device falls back to the existing verified copy → delete path
     automatically.
  2. **Space story:** today's per-file `--move` already needs only one-file peak overhead; rename
     mode needs ~zero. Surface it in the preview - *"in place: files will be moved, not copied"*.
  3. **Cloud tier (later, with the rclone work):** server-side move within a remote for backends
     that support it - **never via mounts**.
  4. **UI:** the destination picker detects same-device and offers *"Organize in place (move
     files)"* behind the explicit opt-in confirm.

  **Engineering notes (verified against the code, 2026-07-27 - read before building):**
  - **`os.rename` silently overwrites on POSIX.** Measured: renaming onto an existing file
     destroyed it with no error (Windows raises instead - the semantics differ by platform). So
     rename mode does **not** inherit the never-overwrite invariant for free. It must route
     through the existing `organizer._free_relative`, which already resolves a collision by
     content hash and numeric suffix, and the guarantee then rests on *that*, not on the syscall.
     Note the TOCTOU window between the check and the rename, and say so in the code.
  - **Treat `st_dev` as a hint, not a gate.** Prefer *try rename, catch `EXDEV`, fall back to
     copy → verify → delete*. Equal-`st_dev` is the common case but not a promise (btrfs
     subvolumes and bind mounts can surprise you), and the fallback path has to exist anyway -
     so letting the kernel decide is both shorter and more correct than predicting it.
  - **Journal on the `migration_journal` shape, not `reclaim_journal`.** `reclaim_journal` is
     `(source_path, sha256, freed_bytes, reclaimed_at)` - an audit record of what was *destroyed*,
     which cannot reverse anything. `migration_journal` is `(sha256, drive_uuid, old_relative,
     new_relative, copy_sha256)` - it records *where things moved*, which is what an undo needs.
     In-place organize should be **reversible**, not merely resumable.
  - **The safety asymmetry to design against.** Every other destructive path in truestill is
     gated on a proven second copy: `reclaim` re-verifies a copy on a connected drive, and
     `--move` re-hashes the destination copy before deleting the source. Rename mode's
     "verification" is trivially satisfied because it is the same inode - so the strongest
     safety gate we have becomes a no-op **exactly in the scenario where the user has the least
     redundancy** (one drive, no backup, by definition of the use case). Nothing here is
     unsound - a rename cannot lose bytes - but the thing at risk shifts from *the data* to
     *the arrangement*: a mis-categorized run rearranges someone's only copy with no undo. The
     reversible journal above is the mitigation, and it is the feature's real safety story
     rather than an implementation detail. The preview must be unusually explicit about this.
