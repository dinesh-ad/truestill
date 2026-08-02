# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to adhere to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **An organize *preview* now exits `1` instead of `0` when it could not read one of your
  files.** Read this if you script Truestill: `truestill organize <src> <dst> && next_step` used
  to chain in this case and now stops. That is the intended behaviour, not a side effect - a
  preview exists to predict the run, the run exits `1` on those same files, and a `0` here meant
  the chain continued past a library Truestill could not fully account for. Nothing else about
  the exit codes changed: `1` has always been this CLI's *"finished, but something is wrong"*
  (`verify` uses it for a missing or mismatched copy, `organize --apply` for a failed one,
  `reclaim` for a skipped one), so no new code was introduced. **A preview over a fully readable
  source still exits `0`**, and `--apply` runs are unchanged. If you want the old
  keep-going behaviour, test the code explicitly (`code=$?; [ $code -le 1 ] && next_step`)
  rather than discarding it.
- **`ingest --takeout` is now `ingest --source`.** The old name described the motivating case
  rather than the feature: archive ingestion reads any `.zip`, `.tar`, `.tgz` or `.tar.gz` from
  any source, and every major photo service hands a user a `.zip`. `--source` is format-neutral
  and matches `organize`'s existing `source`. **`--takeout` keeps working, permanently** - it is
  a hidden alias resolving to the same value, not a deprecation, so existing scripts are safe.

### Fixed
- **Truestill will no longer register the same library twice as two different drives.** If a
  drive's marker file went missing - copied to a new machine without it, restored from a backup
  that skipped hidden files - registering that folder used to create a *second* drive identity
  for photos Truestill already knew about. On the command line the new drive then showed **0
  files**, as though the backups had never existed. In the app it was quieter and worse: the new
  drive picked up all the files, and Truestill went on to report *"at least two drive copies"*
  for photos that existed in exactly one place. Registering now **stops and names the drive the
  folder already is**, having checked the file contents rather than just the names. If the drive
  simply moved, `truestill drives --init <folder> --label x --adopt-existing` re-attaches it
  under its original identity; if you really do have two drives holding the same photos,
  `--force-new-identity` registers the second one.
- **An unplugged drive no longer tells you to register it.** Pointing `verify`, `reclaim` or
  `migrate-layout` at a path that is not there said *"isn't a Truestill drive yet - register it
  with `truestill drives --init`"* - the one piece of advice that causes the problem above. It
  now asks whether the drive is plugged in. A folder that *is* there and simply is not a drive
  still gets the register suggestion, unchanged.
- **A photo Truestill could not read is no longer also counted among the ones it says it will
  organize.** The preview said both *"organized (unique): 5"* and *"files that could not be
  read: 2"* about the same seven photos, with the two unreadable ones inside the 5 - a file with
  no hash matches nothing, so it read as new. Every scanned file is now reported in exactly one
  bucket, and the buckets add up to the number of files scanned. **The CLI summary has a new
  `could not be read` line**, printed even when it is zero so the figures can be checked by
  adding them up; the app's *"new - will be organized"* count and the number on the confirm
  button both drop accordingly. Nothing about what a run *does* changed - an unreadable file is
  still attempted and still reported as failed; only the preview stopped promising it.
- **A photo Truestill cannot read is now named, instead of vanishing from the preview.** A file
  that is locked, permission-denied, on a failing disk, or moved away mid-scan produced empty
  hashes - **the same empty hashes** a file gets when the size pre-filter deliberately decides
  not to hash it. Nothing downstream could tell those apart, so on a preview, which copies
  nothing and therefore never reaches the run's "failed" outcome, the file was reported
  **nowhere at all** and the library looked clean. Both the CLI and the app now count these and
  name them one by one, with the reason for each - *permission denied*, *input/output error*,
  *disappeared during the scan* - because those are three different things to do about it. A
  long list is capped and says how many it hid. Unreadable **folders**, which the app has known
  about since the feature shipped but never actually drew on screen, are now displayed too;
  they are still named without a file count, because the number inside a folder that cannot be
  opened is precisely what is unknown.
- **A FAT32 drive can no longer swallow most of a run and then fail the videos.** FAT32 cannot
  store a file of 4 GiB or more, and 4K phone video crosses that routinely. Organize had no
  preflight of any kind, so a library with a few big videos organized nine thousand files and
  *then* failed N of them, one `[Errno 27] File too large` at a time, against a drive reporting
  200 GB free. Organize now checks what the destination can physically hold **before writing
  anything** and refuses, **naming the files that would fail** rather than counting or skipping
  them - a run that quietly omitted exactly the footage the user cared most about, and reported
  success, would be the worse outcome. The errno message itself now names FAT32 as the reason
  instead of passing the raw errno through. Detected from `/proc/mounts` on Linux and
  `GetVolumeInformationW` on Windows; **macOS reports unknown, and unknown never refuses
  anything**. Both the CLI and the app inherit the refusal, and both previews say so up front.
- **An archive holding a file too large for the drive is refused before it is unpacked.** The
  organize preflight above cannot cover this: an archive ingest extracts a staging tree onto the
  destination *first*, so a 5 GB video inside a zip would fail part way through the unpack with
  most of the tree already written. The precheck now names such entries from the archive's own
  headers - free, because the walk that totals the claim already reads every declared size - and
  the extractor's own write, the one path that does not go through the destination backend,
  names EFBIG the same way for a header that under-declares.

### Added
- **Trips**: group multi-day photos into one folder, review and apply on disk.
- **In-place organize (`organize --in-place`)** for libraries that live on the drive itself -
  a pendrive or external HDD with no staging space to copy into. Files are moved by **rename**:
  no bytes are rewritten, no other process ever sees an instant at which the content does not
  exist, and the content hash is unchanged because the inode is. (Surviving a *power cut*
  intact is a property of journalling filesystems; on FAT32/exFAT pendrives the undo journal is
  what makes such a run recoverable.) Plain `--move` now takes the same
  fast path automatically wherever the filesystem allows; `--in-place` additionally *requires*
  it, refusing a cross-device destination rather than quietly consuming space the user said
  they did not have. `--apply` needs a typed `move` confirmation, and the run reports its
  mechanism split ("3 moved by rename · 1 copied across devices").
- **`truestill undo-organize`** - reverse an in-place run, restoring every file to its exact
  prior path. Preview by default, `--apply` to move; `--list` shows recorded runs, and
  `--source-root`/`--dest-root` handle a drive that has remounted elsewhere. It ships *with*
  the feature rather than after it: a rename cannot lose bytes, so what is at risk is the
  *arrangement* of a library whose owner, by definition of this feature, has no second copy.
- Catalog **schema v10**: `inplace_runs` + `inplace_moves`, a **reversible** journal (where
  each file moved) rather than an audit one (what was destroyed).

### Added
- **`truestill migrate-layout`** - move an existing library to a layout you have chosen. Shows
  the full plan first (where every label's files are headed, how many, sample paths, and how
  close the longest path comes to Windows' 260-character limit) and moves nothing until you type
  `move`. Each file is copied, re-hashed at its new home, and only then removed from the old
  one, so there is never a moment when it exists nowhere. An interrupted run resumes.
- **`truestill migrate-layout --undo`** - put a completed migration back. Walks the moves in
  reverse with the same verification going the other way, and **refuses any file that changed
  since the migration**, reporting it rather than overwriting your edit. Available until a later
  migration of the same drive replaces the record.
- **`truestill clean-empty`** - remove the empty folders a migration leaves behind. Scoped to
  folders Truestill itself emptied - it never sweeps your drive - and it shows three lists before
  anything happens: what is empty, what holds only operating-system junk (`.DS_Store`,
  `Thumbs.db` and friends, removed with the folder), and what it is **leaving alone**, naming
  whatever is still inside. Anything it does not recognise keeps its folder. Removals go to the
  trash, and you type `clean` to confirm.
- **`truestill clean-empty --permanent`** - for cloud and network drives, where the trash cannot
  be used at all (there is nowhere on that mount to trash *to*). Trash is still tried first;
  only the folders it refuses are deleted outright, the preview says plainly that this is
  irreversible, and the confirmation is a different phrase - `delete forever` - so the word you
  typed for a recoverable cleanup can never be reused for a permanent one.
- **A browser end-to-end test layer** (`tests/e2e/`, `make e2e`). Playwright via
  `pytest-playwright` against an in-process app server, run in CI as its own chromium-on-ubuntu
  lane. Every UI defect the soak found is pinned as a named regression test, and the whole
  organize → back up → check journey runs as one test because the value is in the handoffs.
  Deliberately outside `make check`: a fresh clone stays green with no browser installed.
- **A hash cache** (`catalog.cache.sqlite`, beside the catalog - never inside it). An unchanged
  file is never read twice: a repeat preview of 2,275 unchanged photos went **15.8s → 4.7s**.
  It caches the perceptual hash as well as SHA-256, which is where nearly all of the win is.
  It can only ever remove work - any mismatch, corruption or unknown schema means hashing from
  scratch - so the answers are identical with it and without it.
- **`truestill --version`**, and the same version in the app footer, read from package metadata.
- **`docs/PERFORMANCE.md`** - the measured baseline per pipeline stage, the two known scaling
  limits with their thresholds, and a list of things a future optimizer should **not** "improve"
  (the size pre-filter above all). It carries one binding rule, referenced from the quality
  gates: every new pipeline stage declares its complexity in *n*, and anything worse than
  O(n log n) must justify itself.
- **A runtime alarm on the one known O(n²).** Perceptual dedup's linear scan is 0.7s at 2,275
  images and deliberately left alone; the first index to pass 10,000 now logs one line saying
  so, rather than leaving the trigger in a document nobody reads.

### Fixed
- **The Backups screen told four kinds of untruth, found in one real backup.** Checking a
  folder that was not a backup drive rendered `NaN verified · NaN missing · NaN changed`; the
  "this isn't a backup yet" state survived the copy that disproved it; the completion had no
  weight; and the drive cards said less than they knew. The NaN was a whole *class* of bug -
  handlers were reading raw job events, so every failure path could produce it - and it is
  fixed at the seam: `streamJob` now normalizes every terminal event before a handler sees it.
- **The golden path was broken at the organize → backup handoff.** Organizing never registered
  its own destination as a drive, so the app rejected the library it had just built. Organize
  destinations and backup targets are now registered on a real run (never on a preview, which
  must stay pure).
- **A path typed into one Backups field had to be typed again in the next.** Known values now
  prefill; Browse is for overriding, not for repeating yourself.
- **Organize reported "uploaded"** - backend vocabulary for an event that did not occur, and a
  quiet contradiction of the promise that files never leave the machine. Outcomes are now
  worded in exactly one place (`models.status_label`), so the CLI and the app cannot drift.
- **A cancelled run claimed there was nothing to organize.** For a 6,000-photo source, that is
  a false statement about the user's own library. Cancellation is now reported as cancellation
  on both the preview and the run paths.
- **Preview blocked the UI and could not be cancelled**; it now runs as a job on the same
  progress/SSE path as every other long operation.
- **`reclaim` can no longer delete the only copy of a file organized in place.** Such a file
  is both the source and the drive copy - one inode - so reclaim's re-verify gate was
  satisfied by the file checking against itself, and it would have deleted content with no
  backup anywhere. Those files are now excluded, and the count is reported rather than
  silently dropped.

### Removed
- **The category-first layout is decommissioned.** The compat machinery that carried existing
  libraries across to year-first - the legacy template constant, the legacy scheme, the
  load-time leniency that let a stored `{category}` template parse, and the "legacy layout"
  framing in Settings - is gone. Both real drives are year-first and verified; there are no
  external users; a bridge kept after the crossing is a path someone can still walk off.
  `{category}` is now valid **only** inside the fixed side-bin shape, which is not user-supplied.
- **The two migration undo records were retired** (The Memory Cabinet and Output, 2,269 journal
  rows each) with an explicit confirm, because after the decommission an undo would have
  succeeded into a state the product could no longer describe: a category-first tree with a
  year-first setting, and no supported way to set a matching layout. `migrate-layout --undo` on
  either drive now answers "no reversible migration exists for this drive". Reversibility itself
  is unchanged - every future migration arms its own record.

### Changed
- **The default folder layout is now year-first.** Photos land in `YYYY/YYYY-MM/`, with ordinary
  shots in a per-month `YYYY-MM - Everyday` bucket and named events in `YYYY-MM-DD - Name`
  beside it. Non-camera sources (Screenshots, WhatsApp, app names) are filed as labelled bins
  *beside* the years - `Screenshots/2024/2024-01/` - never above them. Undated files sit in
  `Undated/` at the root, or `<Label>/Undated/` for a bin.
  - **Months name themselves.** `2025-08`, not a bare `08`, so a folder still says what it is
    once it is copied, searched or attached somewhere away from its parent.
  - **Routing is on evidence, not on the label.** The one rule that identifies a camera photo
    puts it on the timeline; everything else goes to a bin. That keeps working under
    `--by-device`, where the label is the hardware name rather than `Camera`.
  - **An existing library is never reshaped.** A library organized before this change keeps its
    `<Label>/YYYY/MM/` structure, is described as a legacy layout in Settings, and is offered a
    migration it is never forced into.
  - **`{category}` is refused in a timeline template**, so source-above-timeline is structurally
    impossible rather than merely not offered. The side-bin shape is fixed and not editable.
- **Takeout metadata baking is ~27x faster.** Writing a rescued date or location into an
  organized copy spawned one `exiftool` process per file - **254.9 ms/file** measured, almost
  all of it process startup, which is about **7 hours** for a 100,000-file Takeout and 5
  minutes for a 1,200-file one. Writes are now batched (100 files per process, staged and
  baked a chunk at a time): **9.3 ms/file**, staging copy included, or ~15.6 min at 100k.
  The originals are still never touched - the batch bakes staged copies - and a process that
  dies mid-batch is **detected**, with every unconfirmed file reported failed rather than
  counted as organized.
- **The type fence now covers `scripts/`, and the pre-commit hook no longer lies.**
  `scripts/benchmark_hashing.py` imported `truestill.scan` - a module that has never existed
  under that name - and survived two renames that way, because nothing was pointed at it. It
  is repaired (correct import, no dead `sys.path` shim, the corpus read from
  `TRUESTILL_CORPUS` instead of a hard-coded home directory, and one `type: ignore` removed by
  typing the pool properly). Widening the fence also exposed that the pre-commit mypy hook
  inherited `--ignore-missing-imports`, which had been silently answering "fine" for that very
  import; it now runs with `args: []`, resolving workspace packages from source via
  `mypy_path`. That in turn revealed `uvicorn` missing from the hook's dependencies.
- **`[tool.mypy] python_version` and `[tool.ruff] target-version` raised 3.12 → 3.13**, to
  match what all three packages require and what CI actually runs.
- **The custody strip stopped doing 13x more work than it displays.** "Safe in N places" was
  building and sorting every at-risk row and then taking its length; it now counts. 224 ms →
  17.5 ms at 100,000 files, on a query that runs after every operation and on every load.
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
  deliberately not used - one catalog column, no algorithm toggle, and a faster hash would
  optimize ~1% of cold-preview wall (`DECISIONS.md` D8; profiled 2026-07-29).
- Dates come from embedded metadata first, filename convention second, `Undated/`
  never from filesystem mtime.

[Unreleased]: https://github.com/dinesh-ad/truestill
