# truestill - Backlog (approved but unbuilt)

Things that were **decided** but not yet built - captured here so nothing lives only in chat
history. This is not a wishlist of everything possible; only items already agreed, with the
decision context that produced them.

> **Items (w) and (x) came from a three-report external research synthesis (2026-07-27) whose
> main result was that it changed nothing.** It reviewed the shipped architecture and validated
> it point-for-point; these two are the entire delta, one of them trivial and one of them
> post-launch. That outcome is worth recording as loudly as a finding would have been - an
> external review that produces two small additive items is evidence the recorded decisions
> have been holding, and it is the kind of result that quietly disappears if only the deltas
> get written down.

## Item letters

Letters are **permanent identifiers, not an ordering** - `IMPLEMENTATION_STANDARDS.md` §8 cites
`(u)` by letter, so reusing or renumbering one silently redirects a citation. They are assigned
across *all* sections of this file, not per-section.

**Used: (e)-(z), (aa)-(ff). Next free: (gg).** Check here before assigning - `(u)` and `(v)` were proposed
a second time on 2026-07-27, four hours after they were first taken, because nothing recorded
which letters were spoken for.

Several early letters no longer appear anywhere in this file: their items shipped and the
Shipped entries describe the work rather than repeating the letter. `(e)` and `(h)` are still
cited by name in `drive-identity-research.md` and `org-structure-research.md`. **A letter that
is invisible here is retired, not free.**

## Approved, not yet built

- **(r) Analyze mode - the hash cache half is SHIPPED.** The placement clause fired: a soak run
  previewed an unchanged 2,275-file source twice and re-hashed it both times, so the cache was
  built first. Per the clarified binding, cache-first alone is fine - what the binding forbids
  is shipping Analyze *without* it, and Analyze will now arrive with it already underneath.
  - **Shipped:** `hash_cache.HashCache`, a sidecar `catalog.cache.sqlite`. Measured on
    12 MP-class photos, a repeat preview at 2,275 files went **15.8s -> 4.7s (3.3x)**; the
    remaining 4.7s is exiftool. Invariants in `IMPLEMENTATION_STANDARDS.md` §8.
  - **The measurement that changed the recorded spec:** it said "path+size+mtime -> sha256".
    That alone would have recovered ~5% of the wait - the size pre-filter already spares
    SHA-256 for ~94% of realistic-size files, while the *perceptual* hash runs for every image
    at ~69.8 ms against SHA-256's ~8.5 ms. Caching both is the feature.
  - **Next, on this evidence:** exiftool is now essentially the whole cost of a repeat preview.
    A metadata cache is the natural follow-on and is deliberately a **separate item** - metadata
    feeds *dating*, so a stale row could change where a photo lands, a class of risk the hash
    cache structurally cannot have.
  - **Still to build:** Analyze mode itself.

- **(r, remaining) Analyze mode.** Promoted from
  "ideas" and bound to the previously-standalone hash-cache item, because the pairing is what
  makes either worth building.
  - **Analyze mode.** An explicit **"Analyze"** entry point (CLI + app) that runs the existing
    dry-run engine and returns a richer **read-only** report: file counts, photo / video /
    audio split with per-extension formats, exact duplicates with the bytes they waste,
    look-alikes with their potential savings, the capture-date range, and the category split.
    Nothing is written and nothing is organized -- it answers *"what is actually in here?"* for
    someone who wants insight before, or instead of, committing to a run.
    - **Free tier by design.** It is the funnel: the moment someone learns something true
      about their own library is the moment the product earns trust. Gating it would gate the
      argument for using truestill at all.
    - **Shares its soul with the parked web dedup teaser**: same question, same honest answer,
      one in the terminal or app and one in a browser. Build them knowing that.
  - **Why the cache is not a separate item.** Analyze performs the **full expensive pass** --
    dates, hashes, dedup. Without a cache the natural journey *Analyze → Organize* pays for
    that pass **twice**, which makes the free analysis feel like a tax on organizing rather
    than an invitation to it. With it, the second pass is nearly free, and preview→run and
    repeat batches get faster as a side effect. Shipping Analyze without the cache would ship
    the funnel and the friction in the same release.
  - **Design (unchanged from the original entry).** A small SQLite table keyed on
    `(filepath, file_size, mtime)` → content digest; a lookup validates the file is unchanged
    (size **and** mtime) before trusting the cached digest. Reference implementation to study:
    PixSort `backend/pixsort/utils/hash_cache.py`.
  - **Invariants, restated because they are the whole safety argument:**
    1. **mtime is for invalidation only, never for dating.** The absolute rule
       (`IMPLEMENTATION_STANDARDS.md` §1) is untouched: mtime never influences where a file is
       placed. The cache reads it to ask "did this file change?", which is the one question
       mtime can answer honestly.
    2. **Any size *or* mtime mismatch → hash it fresh.** Never a partial-match heuristic.
    3. **The cache can only ever cost extra work, never produce a wrong answer.** A miss means
       re-hashing; there is no path where a stale entry decides an outcome. If a design choice
       ever trades that away for speed, it is the wrong choice.
    4. **A single cache layer** -- never a second parallel store. PixSort's dual-store drift
       was a defect, not a design.
    5. **Cleanup is wired into the run lifecycle.** PixSort *defined*
       `cleanup_stale_entries()` and **never called it anywhere**, so stale rows accumulated
       forever. Pruning must actually run as part of a run, not merely exist.
  - **Placement:** the **first post-launch wave, alongside (n)**. Earlier if the soak shows
    repeat-run pain at real scale -- that evidence would move it, nothing else needs to.
- **(u) Metadata (exiftool) cache.** Promised by `IMPLEMENTATION_STANDARDS.md` §8 as "tracked
  as a separate later item" and recorded here because that pointer had nothing to point at.
  With the hash cache shipped, **exiftool is essentially the entire cost of a repeat preview**
  (4.7s of the remaining 4.7s at 2,275 files), so this is the next measured win available.
  - **It is deliberately NOT the hash cache with a different table.** The hash cache is safe to
    be wrong because a stale row can only cost a re-read. Metadata feeds **dating**, so a stale
    row could change *where a photo lands* - a class of risk the hash cache structurally cannot
    have. Whatever invalidation this uses must be argued on that basis, not inherited.
  - **Prerequisite for a decision:** state what invalidates a row when an *external* tool edits
    a file's metadata without changing its size (entirely possible - exiftool itself does it),
    and whether size+mtime is honestly sufficient there. If the answer is "not sufficient", the
    correct outcome may be **not to build it**.
  - Blocked on nothing; wants a research pass before a build pass.

- **(v) BK-tree for perceptual dedup - build on the alarm, not before.** The linear scan is
  O(n²) *by decision* (`PERFORMANCE.md` §3): 0.7s at 2,275 images, ~22.6 min at 100k. A BK-tree
  today would be machinery bought before the problem.
  - **The trigger is instrumented, not remembered:** `dedup.LINEAR_SCAN_ALARM = 10_000` logs one
    line the first time an index crosses it. **This item is unblocked when that line appears in
    a real run**, not when someone re-reads this file.
  - Design already settled: BK-tree over Hamming distance, which fits a *fixed small* threshold
    like `DEFAULT_PHASH_THRESHOLD`. VP-tree is the more general metric-space answer and buys
    nothing extra here; LSH is for *approximate* nearest-neighbour at far larger scale and would
    trade away exactness we currently have. `DedupIndex`'s interface was designed for the swap.

- **(w) Self-describing month preset.** ⚠ **Absorbed by the year-first default correction**
  (`docs/default-layout-research.md`) - self-describing months are baked into every shipped
  preset there. Kept until that correction's default flip lands, then closed as delivered-by.
  The original entry follows.

  A folder named
  `2014-08` explains itself when it is copied, searched, sorted or attached somewhere else;
  `08` only means anything while you can still see its parent. Same argument the repo already
  made in the *opposite* direction for the default (`README.md`: the year is the parent, so
  `2026-07` "would just repeat it") - and both are right, because they optimise for different
  moments. The default optimises browsing in place; this optimises the folder travelling alone.
  It is offered as a **preset, not a new default.**
  - **The template engine already supports it - verified, not assumed.** `{yyyy}-{mm}` in one
    segment is an ordinary literal-plus-token construction the parser already accepted.
    Rendered against `layout.LayoutTemplate` today:

    | context | result |
    |---|---|
    | dated | `Camera/2014/2014-08` |
    | undated | `Screenshots/Undated` (the undated-collapse rule holds) |
    | named event | `Camera/2014/2014-08/20140820_lisbon` |

  - **The event variant asked for is unnecessary, and that makes this smaller.** Because of the
    "event append" rule (`layout.py`: when a template has no explicit `{event}` token the event
    folder is appended), `{category}/{yyyy}/{yyyy}-{mm}` and
    `{category}/{yyyy}/{yyyy}-{mm}/{event}` render **identically** for event members - both
    confirmed above. Ship **one** preset. An explicit `{event}` token only earns its place when
    the event folder needs to go somewhere other than last.
  - **Scope is genuinely preset + docs.** `PRESETS` is a plain dict and every consumer reads it
    dynamically: the CLI derives `--preset` choices from `tuple(PRESETS)` and lists
    `PRESETS.items()`; the app serves `dict(PRESETS)` and the Settings dropdown is populated by
    iteration. One dict entry reaches both front-ends with no other code change. Wants a
    rendering test and a name.
  - **State the migration truth in the UI when it ships.** A template change affects **new
    files only**; an existing library is relocated by `truestill migrate-layout` (preview
    first, journalled). Someone switching mid-library will otherwise expect their existing
    folders to rename themselves.
  - **Pre-launch candidate.** Trivial, and it costs nothing to defer.

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

## Pre-launch code-quality pass (from the 2026-07-28 design audit)

Accepted findings from a design-quality audit of `truestill-core` (and `-cli`/`-app` where they
hold logic). The audit's blocker - the layout seam being optional and therefore unreachable from
production - was fixed immediately; these are the rest, deliberately deferred so the layout
correction lands first. Each cites the audit finding that justifies it.

- **(aa) Introduce an `Event` value object** (`start`, `slug`, `name`, `id`). An event is
  currently three parallel dicts that must be kept in sync -
  `assignments: dict[str, tuple[datetime, str]]`, `event_ids: dict[str, int]` and now
  `names: dict[str, str]` - which is the **root cause** of the audit's F1: the human name was
  simply never plumbed, because there was no object to carry it. `event_review.py` had already
  eroded the tuple to `tuple[Any, str]`.
- **(bb) `rule` becomes a `StrEnum`; the router becomes total.** `TIMELINE_RULE = "device"` is
  compared against a bare `str`, and the seven rule names are re-listed by hand in the tests.
  An enum makes the set exhaustive and lets the router be checked for totality.
- **(cc) Collapse `preview()` into `preview_scheme()`.** `preview()` has no production caller
  and duplicates the collision + path-length rule character for character (audit F4). Two copies
  of "is this path risky" will diverge.
- **(dd) Extract `execute()`'s per-file body into named steps.** 180 lines coordinating dedup,
  collision suffixing, baking, rename-vs-copy, catalog recording, journalling and
  move-verify-delete. Its own ruff suppressions (`PLR0912`/`PLR0913`/`PLR0915`) admit it. It is
  the hardest code in the repo to change safely **and** it is the path that writes user bytes.
- **(ee) Move the pin out of `layout.py`.** `pin_existing_layout` is catalog lifecycle, not
  layout; it lives there only because it needed a `CatalogLike` Protocol invented to dodge an
  import cycle - and that Protocol is the tell. Retire it with the move.
- **(ff) Typed payloads at the app boundary.** `service.py` returns `dict[str, Any]` 27 times.
  This is not theoretical: the `dict(PRESETS)` regression - dataclasses about to be serialized
  into the API - was invisible to mypy precisely because the return type was `Any`.

**Not doing, and why:** the audit found no inheritance-for-reuse and no deep hierarchies
anywhere (the only inheritance is `Destination` -> `Local`/`Rclone`, a genuine is-a), so there is
no composition refactor to schedule.

## Shipped (kept for provenance)

- ~~**Browser end-to-end test layer.**~~ **Delivered** (`9be7529`, `0103454`). Playwright via
  `pytest-playwright` against an in-process app server, run in CI as its own chromium-on-ubuntu
  lane. Every UI bug the soak era found is now a **named regression test**, the golden path is
  one journey rather than six set-up tests, and the "a clean runtime install pulls no browser"
  claim is itself tested. Rules in `IMPLEMENTATION_STANDARDS.md` §6; scope rulings and the
  Playwright-over-Docker rationale in `DECISIONS.md` D2/D3.
- ~~**Performance audit + its convictions.**~~ **Delivered** (`1e458df`, `39d889a`, `8f77de1`).
  Measured every pipeline stage, then fixed only what evidence convicted: the per-file exiftool
  write (255ms → 9.3ms/file) and the custody strip's row-building count (224ms → 17.5ms at
  100k). The O(n²) perceptual scan was **deliberately not fixed** - it became item (v) with a
  runtime alarm. Baseline, rule and the do-not-touch list in `PERFORMANCE.md`.
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

  **Quality ranking - the layer that makes the review worth doing (research-grounded).**
  Within each near-duplicate group, rank the candidates by objective quality signals and use
  that ranking to power the side-by-side review's **default suggestion**.

  - **Never auto-action.** Constraint 3 above stands unchanged: a ranking produces a
    *suggestion*, and where the evidence is weak it must still suggest nothing. Ranking makes
    the human's decision cheaper; it does not make it for them.
  - **Why this is the value, from the literature.** Representative-photo-selection and
    burst-quality-assessment work (the PhotoCluster lineage through current blur/quality
    assessment research) consistently finds that in de-duplication and burst review the
    bottleneck is **review effort, not judgement**: people know which photo they want once
    they see the pair, and give up long before they finish looking. A good ranked default is
    therefore the feature -- it turns "review 400 pairs" into "confirm 400 defaults, correct
    a few". Presenting an unranked pile is what makes duplicate review get abandoned.
  - **Signals, cheapest first:** sharpness (Laplacian variance and similar classical focus
    measures), exposure sanity, and resolution -- plus the evidence truestill already has from
    constraint 2: original-vs-recompressed, and the copy-suffix filename pattern as *negative*
    evidence.
  - **Classical metrics first, zero ML dependencies.** They are cheap, explainable in one
    sentence to a user, and defensible in a UI that promises honesty about what it can
    determine. A learned model is only ever a justified later step, against measured
    inadequacy of the simple metrics -- and it would have to earn its dependency against the
    same policy every other dependency does (`IMPLEMENTATION_STANDARDS.md` §7).
  - **Positioning:** this is what makes (m) the **Pro-tier crown feature alongside (p)**. The
    safe-delete flow is the table stakes; knowing which copy to keep is the part worth paying
    for.
- **(n) "How your dates were determined" honesty stat - PRIORITIZED for first post-launch.** A
  per-run/library figure in the reports/UI showing the **provenance mix** of capture dates - e.g.
  "82% from embedded EXIF, 11% from filename, 5% from Takeout, 2% Undated" (a metadata-accuracy %).
  truestill already resolves and could persist `date_source` (see the metadata-chain §1b.3 schema-v9
  note); surfacing it honestly tells a user how much to trust their timeline, in truestill's voice.
  - **Validated by the UI-v2 walkthrough:** the organize result's "**N no date → Undated**" line
    confused a first user - a bare count with no way in. It must be **explorable**: click it to see
    *which* files were undated and *why* no date was found (which tags were checked, whether a
    filename date was tried). Same treatment for the provenance mix - each slice drills to its
    files. This is the concrete first slice of (n) to build first post-launch.
- **(p) "Share safely" - metadata-stripping export. PRO TIER (behind the capability seam).**
  A dedicated **export** action that writes cleaned copies for sharing, so a user can post a photo
  without leaking where they live or what device they use. Market demand is documented (a whole app
  category - CleanShots, ExifStrip, etc.; dating / kids / marketplace / forum use cases; email /
  Slack / Telegram-file preserve EXIF). **Design decisions, recorded now:**
  1. **Export-only, never a library operation.** The user selects files; truestill writes cleaned
     copies to a dedicated **share-export folder**. The organized library and the originals keep
     their full metadata, untouched. A strip control anywhere near the library would contradict
     truestill's metadata-preservation identity and invite accidents - it lives only in this export.
  2. **Complete removal, verified.** `exiftool -all=` on the copy (clears EXIF + XMP + IPTC +
     MakerNotes + embedded thumbnails - the thumbnail is the classic leak); for video, an exiftool
     pass **plus** an ffmpeg container rewrite (`-map_metadata -1`, no re-encode) for the
     `uuid`/`udta` boxes; handle **Live Photo** JPEG+MOV pairs together. Then **re-scan each output**
     and produce a verification report ("0 metadata fields remain") - the never-silent rule applied
     to removal. UI states honestly that cleaning affects the *copies*; the originals still exist
     with their metadata (that is the point).
  3. **Folder protection + lineage.** The share-export folder gets a `.truestill-shared.json` marker;
     the scanner **refuses a marked folder as an organize source** with a clear explanation (so
     dateless cleaned copies are never re-swept into `Undated/`). The catalog records lineage
     (cleaned copy ↔ source hash) so dedup never mistakes a stripped copy for a lost original.
  4. **Modes:** **strip-all** (default) and **GPS-only** - the two the market ships.

  Post-launch build; Pro-tier candidate. Research refs to carry in: the embedded-thumbnail trap,
  the XMP/IPTC/MakerNotes layers, MP4 container metadata boxes, and Live Photo pairing.

- **(x) XMP sidecar export for user-generated context.** Post-launch, demand-driven. Trip and
  event names are the one thing in a truestill library the *user* created rather than the files
  carrying it - so they are the one thing that is currently lost if someone stops using
  truestill. Writing them to standard XMP sidecars makes them portable to Lightroom, digiKam,
  Immich and anything else that reads XMP.
  - **Why it fits the identity rather than diluting it.** The promise is a library you can
    still read without the tool. That already holds for *files* (ordinary folders, ordinary
    names, full metadata). It does **not** yet hold for the context the user added on top.
    This closes that gap, and it is the no-lock-in argument taken to its own conclusion: the
    exit path should be complete, not partial.
  - **Sidecars, never in-place edits, by default.** Writing into originals contradicts §1;
    a sidecar sits beside the file and can be deleted with no trace. The scoped Takeout bake
    stays the only path that modifies content, and it stays scoped.
  - **Open questions for the research pass**, none of them blocking today: which XMP fields
    carry an "event" honestly across readers, whether sidecars belong beside the organized copy
    or the source, and what happens on re-export when a user has renamed an event.
  - **This is export, not a second source of truth.** The catalog stays authoritative;
    re-importing user context from sidecars is a separate question and is *not* part of this
    item.
  - **Virtual views, albums-as-first-class-objects and faces remain out of scope**, unchanged -
    see "Consciously out of scope" below and the composition stance recorded there. Portable
    *context* is not the same request as a gallery.
- **(y) Optional photo / video split - default TOGETHER, and pair-aware or not at all.**
  Post-layout-correction. An opt-in that separates standalone videos into their own top-level
  branch, leaving photos on the timeline.
  - **The default stays together**, because a chronological timeline is the thing the layout
    correction exists to produce and splitting media types cuts across it. This is a preference,
    not an improvement.
  - ⚠ **The constraint that makes or breaks it: a naive split destroys Live / Motion Photos.**
    An iPhone Live Photo is a **pair** - a `.HEIC`/`.JPG` still plus a `.MOV` sharing a content
    identifier - and a Samsung Motion Photo is the same idea. A split that routes by extension
    sends the still to `Photos/` and its motion half to `Videos/`, silently dismembering an asset
    the user thinks of as one thing. This failure is documented in Apple's own asset model and
    has been reported repeatedly against Immich; it is not hypothetical.
  - **Therefore: the pair moves together, and only a STANDALONE video goes to `Videos/`.** A
    `.MOV` that is the motion half of a Live Photo is not a video for this purpose.
  - **Depends on asset pairing**, which truestill does not have yet - matching a still to its
    motion half (content identifier where present, else name + timestamp + duration heuristics).
    That dependency is the real work; the split itself is a routing branch once pairing exists.
    **Do not build the split first and pair later** - shipping it in that order is shipping the
    dismemberment.
  - Fits the existing router as a third axis (`LayoutScheme` already routes on rule, then on
    evented), so the mechanism is understood; it is blocked on evidence, not on design.

- **(z) Optional source / device manifest - catalog-first, hash-keyed.**
  Post-layout-correction, opt-in, **local-only** (no network, D1 unchanged). Answers "what
  device and which app did this file come from?" across a library.
  - **Catalog-first, keyed by content hash.** The catalog already keys everything on `sha256`,
    which is what makes the record survive a rename, a move, a re-layout and an in-place
    organize. A path-keyed record would be wrong the first time `migrate-layout` ran.
  - ⚠ **The JSON is a GENERATED EXPORT, never a loose per-file sidecar.** Per-file sidecars
    orphan the moment a file is renamed or moved - the exact failure the hash key exists to
    avoid - and they would also scatter truestill-named artifacts across a user's drive, which
    §3.1 keeps to a single marker file. Export on demand; regenerate rather than maintain.
  - **The data is largely already known:** device from EXIF `Make`/`Model` (the `device` rule
    already reads them), platform/app from the derived category, and both are already recorded
    per file. This is mostly a query and a serializer, not new extraction.
  - **Opt-in** because it is a reporting feature, not part of custody; nothing about placement
    or verification should depend on it.
  - Open question for the research pass: whether it persists a `device` column (a schema
    version) or derives on demand from stored metadata - decide on measured query cost, not
    taste.

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

## Consciously out of scope (recorded with reasons)

Not "not yet" -- decided **against**, so the question does not get re-litigated every time a
neighbouring product ships one. Each would be a reasonable feature in a different product.

- **Face recognition / people albums.**
- **Semantic AI search** ("photos of a beach at sunset").
- **Auto-generated Memories / highlight reels.**

**Why all three, together:** they are one class -- **ML infrastructure** -- and adopting any of
them changes what truestill *is*. Each needs models shipped or downloaded, a vector store or
embedding index beside the catalog, GPU-or-slow inference, and a retraining/refresh story; that
is a permanent tax on every install, and it lands squarely against the lean, local, no-network,
minimal-dependency identity recorded in `ENGINEERING_STANDARD.md` §1 and
`IMPLEMENTATION_STANDARDS.md` §7. It is also **Immich's and Ente's territory**, where they are
strong and mature: competing there means being a worse version of a server product, while the
thing truestill does that they do not -- custody of files you can still read without it -- goes
unfinished.

The honest framing for a user who wants these: run truestill for organizing and custody, and a
gallery server for browsing and search. They compose. That answer is better than a shallow
imitation of both.
