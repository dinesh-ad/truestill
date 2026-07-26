# truestill - Implementation Standards (the binding contract)

The truestill-specific rules, stated as checkable facts against this repo. This contract
**overrides** [`ENGINEERING_STANDARD.md`](ENGINEERING_STANDARD.md) on any conflict. Every
rule cites where it is enforced - a source symbol, a hook, a CI step, or a test - or is
marked **convention - not yet enforced** (a human-process rule with no automated gate).

Paths are workspace-relative. Symbols are cited over line numbers, which drift.

---

## 1. Product invariants

| Invariant | Enforced by |
|---|---|
| **Original quality is the top priority.** Media pixels are never re-encoded. | The pipeline only copies bytes; the sole content write is metadata-only (see below). |
| **Copy-only - never move or delete user files, except the two scoped, opt-in exceptions below.** | `organizer.execute` uploads via `LocalDestination.upload` (`shutil.copy2`) / `RcloneDestination.upload` (`rclone copyto`). `rclone` uses `copyto`, never `sync`. The only code paths that delete a **source** are `organizer._move_source` (`--move`) and `reclaim.run_reclaim` (`truestill reclaim`) - both scoped exactly like the Takeout write path (below). |

**Source-deletion exceptions (feature k), both opt-in and verify-gated:**

- **`organizer.execute(move=True)` (`--move`).** Deletes a source **only** after its just-written
  destination copy re-hashes to the recorded `copy_sha256`. Ordering is copy → record → re-verify
  → delete, so no interruption leaves a window with zero copies; any verify/delete failure keeps
  the source and reports `MOVE_KEPT`. Only under `apply=True`.
- **`reclaim.run_reclaim` (`truestill reclaim`).** Deletes a source **only** after re-hashing a
  destination copy on a **currently-connected** drive at delete time (never trusts a stale
  `last_verified`). Dry-run is the default; `--apply` additionally requires a typed `delete`
  confirmation. `--min-copies N` (default 1) gates on recorded redundancy; single-copy outcomes
  are warned. Every deletion is journalled (`reclaim_journal`, schema v9) for audit/resume.

Both are **off by default**, never touch a source whose content is not proven present at the
destination, and are the *only* sanctioned deletions of user source data.
| **Copies are byte-identical to the source EXCEPT the scoped Takeout write.** | Normal path uploads the source unchanged. The only exception is `organizer._upload_with_metadata_write`, reached **only** when an `IngestContext` carries a write (Takeout ingestion); it stages a temp copy, bakes metadata losslessly via `exif.write_metadata` (no pixel re-encode), and never touches the source. |
| **Categorization is evidence-derived - no hardcoded taxonomy.** | `categorize.build_rules` is an ordered rule chain; labels are plain `str` (there is no `Category` enum in `models.py`). New sources are added as a `NAME_PATTERNS` row or derived from the `Software`/device rules. |
| **Dating uses an evidence chain, never filesystem mtime.** | `dates.resolve_capture_datetime`. mtime is only ever *written* (`organizer._apply_timestamp` sets mtime from the resolved capture date); it is never *read* for placement. |
| **Every source file is accounted for - none silently dropped.** | `organizer.scan_source` partitions a source into `media` / `documents` / `unrecognized`; the CLI end-of-run report (`_print_skipped`) and the app organize summary (`service._skipped_summary`) count the two skipped buckets by extension. Nothing is discarded without appearing in a report. |
| **No user accounts and no required telemetry - permanently.** No login, no install/user identifier, no phone-home, no usage beacon in the CLI, core, or app. The "your files never leave your machine" promise holds *inside* the product. Usage is measured only externally and in aggregate (PyPI/GitHub stats, Plausible-class cookieless site analytics, payment-provider purchase records). Pro is gated by **offline-verified license keys**, not a login. Any future crash reporting must be opt-in, off by default, self-hosted, transparent, and post-launch only. | No network path in the product transmits user activity; the capability seam (`§2`) is key-verified locally. Full rationale (Audacity 2021 precedent) in `docs/DECISIONS.md` D1. |

**Dating tier order (current), from `dates.resolve_capture_datetime`:**

- Default: **sane embedded EXIF** → **Takeout `photoTakenTime`** (`TAKEOUT`) → **Takeout
  `creationTime`** (`TAKEOUT_UPLOAD`, approximate) → **filename convention** (`FILENAME`) →
  **none** (`NONE` → `Undated/`, or `REJECTED_SENTINEL` when a date was found and refused).
- The tiers are an ordered tuple of `dates._Candidate`, not nested branches - the order *is*
  the policy, so it reads as data.
- `--prefer-takeout-dates` flips the first two (`photoTakenTime` above EXIF).
- "Sane" EXIF = parseable and year in `[1900, 2100]`; outside that, a Takeout date wins.
  Sentinel rejection does **not** rely on this window - see the two-tier policy below.
- Takeout times are epoch-UTC, converted to local wall-clock **exactly once**
  (`takeout.local_naive`); `--tz ±HH:MM` supplies the offset.

**Implausible-date policy (binding, for any current or future date source).** Two tiers, and the
distinction between them is the point: one kind of bad date is *never* real, the other *can* be.

| | **Tier A - hard sentinels** | **Tier B - suspect camera defaults** |
|---|---|---|
| Values | `1904-01-01T00:00:00` (ISO-BMFF/QuickTime), `1970-01-01T00:00:00` (Unix), all-zero `0000…` | **Exactly midnight** on `2000-01-01`, `1999-12-31`, `1980-01-01` |
| Policy | **Auto-reject, always** - fall through to the next tier | **Accept and flag** - file by the date, count it for review |
| Why | An unset field, not an early date. Naive parsers (hachoir, pymediainfo) report these as real, which would misfile clips to 1904/1970 - strictly worse than `Undated/`. | These are the dates a camera falls back to when its clock battery dies, but a photo really can be taken on 2000-01-01. Rejecting would be guessing. Exact midnight is the discriminator. |
| Enforced by | `dates.HARD_SENTINELS` + `dates.is_hard_sentinel`, applied to **every** tier inside `dates.resolve_capture_datetime` (not just EXIF - a zero-epoch is not a date whichever field carried it); `0000…` still drops in `dates.parse_exif_datetime`. | `dates.SUSPECT_DEFAULT_DAYS` + `dates.is_suspect_default`, surfaced as `Decision.suspect_default`. |
| Pinned by | `tests/test_date_sentinels.py`, incl. `test_sentinel_rejection_does_not_depend_on_the_sanity_window` | `tests/test_date_sentinels.py`, incl. `test_filename_dates_are_never_flagged_as_camera_defaults` |

**Tier A is independent of the sanity window, deliberately.** `dates._MIN_SANE_YEAR` / `_MAX_SANE_YEAR`
(**1900-2100**) is a *plausibility* filter, not a sentinel filter. The floor was 1990 and was the
only thing rejecting 1904/1970, which made it unsafe to lower - and it needed lowering, because
scanned negatives and slides carry genuine pre-1990 dates that were silently landing in `Undated/`.
Tier A now rejects on value, so the window is free to be generous. A test pins that independence;
do not delete it.

**Never-silent disclosure (binding).** Neither tier may be folded into a plain "undated" count.
- A Tier A rejection resolves to **`DateSource.REJECTED_SENTINEL`**, not `DateSource.NONE` - the
  file still goes to `Undated/`, but the report can say a date was *found and refused* rather
  than implying the file never had one.
- Both counts come from the single shared helper **`models.date_quality`**, used by the CLI
  (`cli._print_date_quality`, `cli._print_ingest_report`) and the app (`service._summarize`,
  `service.ingest_preview`) so the two front-ends cannot drift.

See `docs/metadata-chain-research.md` for the corpus evidence behind Tier A.

**Fallback-parser policy (convention - no parser is currently a dependency).** exiftool is the
sole date reader. A container-parsing fallback (pymediainfo / hachoir / ffprobe) is added **only**
when a real corpus shows a file it - and only it - can *correctly* date; hachoir is disqualified
(reports EXIF `ModifyDate` as capture). On the evidence to date the designated front-runner, if
one is ever justified, is **ffprobe** (the only sentinel-safe parser observed). When that happens,
the fallback slots into `resolve_capture_datetime` between embedded-EXIF and the filename tier.

> **Schema note.** This policy originally reserved catalog **schema v9** for persisted date
> **provenance** (`date_tool`, `date_field`). v9 shipped as `reclaim_journal` instead, and the
> `files` table still has no date-source column - so **the next free version is v10**, and that
> is where provenance lands. `DateSource` is already resolved per file and already aggregated
> per run by `models.date_quality` and the two report surfaces; only the *library-wide* figure
> (BACKLOG item (n)) needs the column.

---

## 2. Architecture contract

- **uv workspace**, three packages (root `pyproject.toml` `[tool.uv.workspace]`):
  - `packages/truestill-core/` - the pure library. The clustering core (`events.py`) does **no
    I/O** and takes no filesystem/interaction dependencies; it operates on passed-in data.
  - `packages/truestill-cli/` - the thin CLI (`truestill organize` / `truestill ingest`), which wires
    core stages together and owns all interaction (prompts, printing).
  - `packages/truestill-app/` - the local web UI (`truestill-app`). Depends on
    `truestill-core` **only**, never on `truestill-cli`; `service.py` is the sole bridge.
  - Further packages (e.g. a native shell) slot **beside** these without restructuring the core.
- **Destinations behind an interface.** `destinations/base.py::Destination` (ABC:
  `exists`/`upload`/`list`/`describe`). Implementations: `LocalDestination`,
  `RcloneDestination`. Nothing in organize/dedup logic names a specific backend. Relative
  paths are POSIX across all backends (enforced: `LocalDestination.list` returns `.as_posix()`;
  regression-tested cross-OS in CI).
- **Capability seam for Pro-tier candidates** (`--events`, `--map-albums`, Takeout ingestion
  are the candidates). **Convention - not yet enforced:** there is no licensing/tier code in
  the repo today; these are gated only by CLI flags. Keep them cleanly separable so a seam can
  be introduced without forking core logic.

---

## 3. Data contract (catalog)

- **Single SQLite file**, stdlib `sqlite3` (`catalog.py::Catalog`). No server.
- **Schema versioned via `PRAGMA user_version`.** Current: **`CURRENT_SCHEMA_VERSION = 9`**.
  Migrations are ordered, idempotent functions in `_MIGRATIONS`; a catalog newer than the code
  is refused (`CatalogVersionError`). Migration coverage tested in `tests/test_catalog.py`.
- **Table inventory (v9):** `files`, `albums`, `file_albums`, `events`, `skipped_clusters`,
  `drives`, `file_copies`, `settings`, `migration_journal`, `reclaim_journal`.
- **Migration ledger:** v2 `size`, v3 `original_name`, v4 event tables (`events` +
  `skipped_clusters` + `files.event_id`), v5 Takeout (`files.copy_sha256` + `albums` +
  `file_albums`), v6 drive identity (`drives` + `file_copies`), v7 key/value `settings`
  (first use: the layout template), v8 `migration_journal` (crash-safe layout migration),
  v9 `reclaim_journal` (audit/resume for `truestill reclaim` deletions).
- **Dual-hash rule.** `files.sha256` is the **source** (pre-write) hash - the **dedup
  identity**. `files.copy_sha256` is the organized copy's **post-write** hash - the
  **verification identity** (equal to `sha256` for the byte-identical normal pipeline; differs
  after a Takeout metadata write). Any future copy-verification compares against
  `copy_sha256`, never `sha256`. Recorded by `catalog.record_uploaded`.

### 3.1 On-disk drive marker (and legacy-name compatibility)

The drive marker is the **only** truestill-named artifact ever written to a user's drive.
Migration and reclaim journals live in the local catalog, not on the drive. The catalog's
`drives` / `file_copies` tables key on the marker **`uuid`**, never on its filename - so the
`vaeon` → `truestill` rename needed no schema change and no catalog migration.

| Rule | Enforced by |
|---|---|
| **Canonical name is `.truestill-drive.json`** - the only name any code path writes. | `drive.MARKER_NAME`; `drive.write_marker` writes `marker_path()` only. Pinned by `test_new_drives_only_ever_get_the_canonical_name`. |
| **Legacy names stay readable.** `.vaeon-drive.json` (pre-rename) resolves normally. | `drive.LEGACY_MARKER_NAMES` + `drive.existing_marker_path`, consumed by `read_marker`. Pinned by `test_legacy_only_drive_is_still_readable`. |
| **A read never writes.** `read_marker` runs on every app filesystem browse and on preview/dry-run paths; silently upgrading there would break the dry-run invariant (§5) and touch read-only mounts. | `drive.read_marker` has no write path. Pinned by `test_reading_a_legacy_drive_never_writes`. |
| **Upgrading is explicit.** Only `write_marker` / `create_marker` / `upgrade_marker`, or `truestill drives --migrate-marker ROOT`. | `cli._migrate_marker`. Pinned by `test_drives_migrate_marker_upgrades_a_legacy_drive`. |
| **Identity is copied verbatim** - `uuid`, `label`, `created` unchanged. Re-minting a uuid would orphan every recorded copy in `file_copies` and under-report the custody count. | `drive.upgrade_marker`. Pinned by `test_upgrade_preserves_identity_verbatim_and_keeps_the_legacy_file`. |
| **The legacy file is retained, never deleted.** Deleting on a user drive is what §1 copy-only forbids; keeping it (~100 bytes) means an older build and a current build agree on identity. | `drive.upgrade_marker` writes only. Pinned by the same test. |
| **Canonical wins if both exist and diverge** - a documented precedence, never a merge. | `drive.existing_marker_path` order. Pinned by `test_canonical_wins_when_both_markers_exist_and_diverge`. |
| **Marker filenames are never hardcoded in messages.** User-facing text interpolates `MARKER_NAME`. | `cli.py` / `service.py` f-strings; asserted via `MARKER_NAME` in `test_migrate_cli` / `test_reclaim_cli`. |

Retiring the legacy name is a **future, opt-in** step (a flag that removes it after a
successful upgrade), never automatic.

---

## 4. Filename & organization contract

- **Copy filename:** `YYYYMMDD_HHMMSS_<original>` (date-only when the time is unknown), from
  the same date evidence used for placement (`naming.dated_filename`). Originals are never
  renamed.
- **Exact-stamp suppression:** the prefix is added **only** when that exact stamp is not
  already in the name - so date-embedded names (screenshots) are not double-dated and re-runs
  never stack a prefix; any mismatch keeps the authoritative prefix. Pinned in
  `tests/test_naming.py` (incl. real screenshot/WhatsApp cases). Disable with `--no-rename`.
- **Folder structure:** `<Label>/YYYY/MM/` (bare two-digit month). Undated → `<Label>/Undated/`.
- **Event placement:** named Camera events become `<Label>/YYYY/MM/YYYYMMDD_<slug>/`. A cluster
  straddling a month boundary is consolidated under its **start** month
  (`organizer.apply_events`; pinned by `test_apply_events_consolidates_cross_month_under_start_month`).
- **Category set** (derived, ordered; `categorize.build_rules`): screenshot-by-metadata →
  screenshot-by-name → messenger/app filename conventions → editing `Software` →
  capture device (`Camera`, or per-device with `--by-device`) → `Saved/`.
- **`Saved/` heuristic:** a no-camera-EXIF image under `_SOCIAL_MAX_PIXELS` (2 MP) is flagged a
  likely social/web save (`categorize.rule_saved_heuristic`); true unknowns also fall to
  `Saved/` (`rule="fallback"`). No Instagram/Facebook-style categories - undetectable
  post-strip, so not created.

---

## 5. Process contract

| Rule | Status |
|---|---|
| **Staged/gated workflow** - no new stage without explicit user confirmation. | Convention - not yet enforced (human process). |
| **Flag before deviating** - surface a spec/engineering conflict before implementing; never silently comply or silently deviate. | Convention - not yet enforced. |
| **Research-first for every feature** - mine the issue trackers of tools that fought the same battle; write findings down. | Convention; exemplar: `docs/takeout-format.md`. |
| **One fix per commit** - focused, reviewable commits. | Convention - visible in git history. |
| **Dry-run before real runs** - planning writes nothing; `--apply` is the only writing path. | Enforced: `organizer.execute(apply=...)`; CLI defaults to dry run. |
| **Never push without being asked.** | Convention - not yet enforced. |
| **Commit identity / no-AI-trailer** - no `Co-Authored-By` trailer, no Anthropic/Claude email or signature in history. | **Enforced:** `scripts/check_commit_msg.py` via the `commit-msg` pre-commit hook (`.pre-commit-config.yaml`, id `no-ai-coauthor`). Activate: `uv run pre-commit install --hook-type commit-msg`. |

---

## 6. Quality gates

- **`make check`** = `ruff check .` (lint) + `ruff format --check` + `mypy` on **all three**
  `src` trees + `pytest` (`Makefile`).
- **`ruff format --check`** is also a separate gate in CI (and `make format` applies it).
- **CI** (`.github/workflows/ci.yml`): matrix **{ubuntu, macos, windows} × Python 3.13**; steps
  = sync → ruff (lint) → ruff (format --check) → mypy → pytest; exiftool installed per-OS.
  The mypy step and `.pre-commit-config.yaml` both cover all three packages - keep the three
  in step with each other.
- **`uv build --all-packages`** must produce clean wheels for **all three packages**
  (`make build`); `truestill-core` ships `py.typed`.
- **Test counts are never hardcoded** as a done-ness signal - they change. Assert behaviour,
  not totals.

---

## 7. Dependency inventory

Runtime deps must justify themselves against stdlib. Current state:

| Dependency | Why it exists (vs stdlib) |
|---|---|
| `imagehash>=4.3.1` (`truestill-core`) | Perceptual dHash for near-duplicate detection; requires image decoding, which the stdlib cannot do. |
| `pillow>=10.0.0` (`truestill-core`) | Image decoding backing imagehash and cheap dimension reads. **Large-image policy:** truestill processes the user's own local library (trusted), not untrusted uploads, so Pillow's ~89 MP decompression-bomb guard is a false positive on legitimate large photos (panoramas/scans). `hashing.MAX_PERCEPTUAL_PIXELS` raises `Image.MAX_IMAGE_PIXELS` to **300 MP** deliberately; above it a pathological image is **skipped for perceptual hashing** (SHA-256 exact dedup still applies) and the bomb *warning* is suppressed locally so **no raw Pillow warning reaches the terminal**. (Immich/PhotoPrism avoid this entirely via libvips streaming.) |
| `pillow-heif>=0.16.0` (`truestill-core`) | Registers a HEIF opener so Pillow can decode **HEIC/HEIF** (the iPhone-default format since 2017), enabling their perceptual near-dup dedup. **Graceful degradation is mandatory:** `hashing._register_heif` guards the import; if it ever fails at runtime, `HEIF_AVAILABLE` is `False`, SHA-256 exact dedup still applies to HEIC, and the run **reports** that HEIC perceptual hashing was skipped - never a silent drop. TIFF-based RAW (CR2/NEF/DNG/…) needs no plugin (Pillow's TIFF decoder content-sniffs it); container-based RAW (CR3, RAF) is exact-dedup-only. |
| `exiftool` (external **binary**, not a pip dep) | The only tool that reads photo EXIF, **video container tags**, and vendor MakerNotes (e.g. the screenshot marker) through one interface, and the writer used for the scoped Takeout bake. A pip EXIF library would cover photos only. |
| `truestill-cli` runtime deps | Only `truestill-core` (workspace source). |

SHA-256 (`hashlib`), SQLite (`sqlite3`), concurrency (`concurrent.futures`), and all path/date
work are **stdlib** - no dependency. **BLAKE3 is deliberately absent** (SHA-256 is hardware-
accelerated and doubles as the dedup + verification hash without a compiled dep).

**Version policy:** `requires-python` = **`>=3.13` for all three packages**. Lower-bound + lock;
`uv.lock` is the single source of truth; no blind upper-pins; updates via periodic
`uv lock --upgrade` review.

> Core declared `>=3.12` until 2026-07-27. It was **not** a 3.12 incompatibility - core was
> verified importing and running correctly on 3.12.13 - it was an **untested claim**, since CI
> only ever ran 3.13. The floor was raised so the declaration matches what is actually
> exercised. If a real user needs 3.12 (Ubuntu 24.04 LTS ships it as system Python), lowering
> it back is cheap: add a CI job that installs `truestill-core` alone on 3.12 and runs its
> tests, then drop the floor. Do not assume incompatibility from the `>=3.13`.

---

## 8. Performance law (checkable)

- **Stream, never slurp.** `hashing.sha256_file` reads in `1 MiB` chunks; no whole-media read.
- **Size pre-filter is law.** SHA-256 is computed only for files whose byte size collides
  in-scan or with a catalogued size (`scan._needs_sha`); unique-size files skip the read.
- **One disk pass per file per run.** Re-runs skip already-processed content via catalog resume
  (`catalog.known_sizes` seeds the pre-filter; `catalog.seed_rows` seeds the dedup index).
  *A per-path mtime hash cache is **convention - not yet implemented**; catalog resume-by-content
  currently serves the re-run case.*
- **Concurrency for I/O-bound batches** via a worker pool (`scan.compute_hashes`, thread or
  process, benchmarked default = thread).
- **No accidental O(n²).** The perceptual dedup is a linear scan per file, documented in
  `dedup.py` as acceptable at current scale with a BK-tree noted as the drop-in for growth.
  Any nested library iteration must carry a comment proving its bound.
