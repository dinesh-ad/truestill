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

- ~~**(q) In-place organize (same-device optimization).**~~ **Delivered.** `organize --in-place`
  moves files by atomic rename when source and destination share a filesystem: no bytes
  rewritten, no zero-copy window, hash unchanged because the inode is. Plain `--move` takes the
  same fast path automatically; `--in-place` *requires* it and refuses a cross-device
  destination rather than silently copying. Typed `move` confirmation, mechanism split in the
  report, empty folders left and reported. `truestill undo-organize` ships with it (catalog
  v10, `inplace_runs` + `inplace_moves`) - reversible, not merely resumable. The `Destination.adopt`
  seam is on the interface, so `migrate-layout` can adopt it later without rework.
  **Two landmines found in the build and fixed with it:** `reclaim` would have deleted the only
  copy of an in-place file (source and drive copy are one inode, so its re-verify gate was a
  tautology), and an undo that left `files` rows behind would have made the library
  un-organizable by re-running dedup against itself. Both pinned by tests. See
  `IMPLEMENTATION_STANDARDS.md` §1. **App UI deliberately deferred** to CLI soak evidence,
  matching `reclaim`'s CLI-only v1.
  - **Still open:** cloud tier (server-side move within a remote, never via mounts) waits for
    the rclone work; a `--prune-empty-dirs` opt-in waits for soak evidence that the folders
    left behind are actually intolerable.
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

- **(r) Analyze-only mode.** An explicit **"Analyze"** entry point (CLI + app) that runs the
  existing dry-run engine and returns a richer **read-only** report: file counts, photo /
  video / audio split with per-extension formats, exact duplicates with the bytes they waste,
  look-alikes with their potential savings, the capture-date range, and the category split.
  Nothing is written and nothing is organized -- it answers *"what is actually in here?"* for
  a user who wants insight before, or instead of, committing to a run.
  - **Free tier by design.** It is the funnel: the moment someone learns something true about
    their own library is the moment the product earns trust. Gating it would gate the
    argument for using truestill at all.
  - **Shares its soul with the web dedup teaser** (parked above): same question, same honest
    answer, one in the terminal or app and one in a browser. Build them knowing that.
  - Most of the data already exists in `service._summarize` and the CLI's decision report;
    this is largely a surfacing and naming job rather than new analysis.
- **(s) Source-folder names as event evidence.** Generalize the Takeout **album → event**
  mapping to plain sources: a meaningful source folder name becomes a **pre-named event
  proposal** in the existing review flow.
  - **The problem, concretely:** an `Olympics/` input folder scatters by capture date today
    and its name -- the single best piece of evidence about what those photos *are* -- is
    discarded. Dates say when; the folder said what.
  - **Filtered against noise:** `DCIM`, `Camera`, `Pictures`, date-pattern directories
    (`2024-06-15`, `20240615`) and similar carry no meaning and must not become event names.
  - **Never auto-applied.** It produces *proposals*; the user confirms, renames or skips, in
    the review flow that already exists. A folder name is evidence, not a decision -- the
    same posture as every other derived label.
  - Reuses `events` + `event_review` machinery; the new part is the evidence source and its
    noise filter.
- **(t) Reflink / copy-on-write fast path.** On filesystems that support it (APFS, btrfs, XFS,
  ReFS) a clone (`FICLONE` / `clonefile`) makes a copy effectively instant and free.
  **Optimization, not correctness** -- `shutil.copy2` already uses `sendfile`/`fcopyfile` fast
  paths today, so this is a further step rather than a missing one, and newer Python is
  growing stdlib support worth waiting for.
  - ⚠ **Recorded caution, to design against before building:** a clone initially **shares
    blocks with the source**. That interacts directly with the independent-verified-copy story
    -- `copy_sha256` would still verify, because the bytes are identical, but "a second copy"
    that shares extents with the first is not the same thing as an independent one for the
    purposes truestill's custody model claims. Two files on one drive sharing blocks survive
    a `verify` and do **not** survive the block going bad. Decide explicitly what a cloned
    copy means for `file_copies`, for the custody count, and for the at-risk banner **before**
    any of it ships; the honest answer may be that clones are fine within a drive but must
    never count toward 3-2-1 redundancy.

## App-surface deferrals (CLI-only for now)

Recorded together because they share one reason: each is a **space-safe or destructive**
operation whose failure mode is unrecoverable, and the QA walkthrough's B2 lesson -- a UI
that reported an outcome it had not produced -- is merely confusing for a copy and permanent
for a move.

- **`organize --move`, `truestill reclaim`, `organize --in-place` + `undo-organize`** stay
  **CLI-only**. GUI demand is to be judged from **soak and launch feedback**, not assumed.
  When one does get a surface, the pre-approved shape is advisory same-device detection plus
  a typed confirmation identical to the CLI's.
- **`{camera_model}` layout token** -- demand **re-confirmed by the user** during the soak
  era. Stays **deferred / Pro-tier candidate** as originally recorded in
  `org-structure-research.md` (§C1 "explicitly NOT v1 tokens"): it needs device metadata
  plumbed into the template render context. Recorded here so the re-confirmation is not lost
  the next time the token list is reviewed.
