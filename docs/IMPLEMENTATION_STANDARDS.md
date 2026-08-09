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
| **Copy-only - never move or delete user files, except the scoped, opt-in exceptions below.** | `organizer.execute` uploads via `LocalDestination.upload` (`shutil.copy2`) / `RcloneDestination.upload` (`rclone copyto`). `rclone` uses `copyto`, never `sync`. The only code paths that remove a source from where the user left it are `organizer._move_source` (`--move`), `reclaim.run_reclaim` (`truestill reclaim`), and the rename path `LocalDestination.adopt` (`--in-place`) - all scoped exactly like the Takeout write path (below). |

**Folder removal (feature `clean-empty`), the only path that deletes a directory.** truestill
deletes a folder **only** when all four hold: **(a)** it emptied that folder itself, proven by
the migration journal - never a drive sweep; **(b)** the folder contains nothing, or only entries
named in `cleanup.JUNK_NAMES` or zero-byte files - unknown is never junk; **(c)** the user
confirmed a preview listing every folder and every leftover file by name, with a typed word; and
**(d)** it goes to the OS trash where the platform allows, and a trash refusal leaves the folder
in place rather than being downgraded to a permanent delete. This makes the never-delete rule
*explicit* rather than weakening it: the four conditions are the whole permission.

**An absent trash backend is treated as a refusal** (clarified 2026-08-04, and it is a
clarification because condition (d) already said what should happen and named only the refusal
that reaches it). `cleanup.run_cleanup` consulted `permanent` **only** where trash was tried and
said no; where `trash_backend()` returned `None` the flag was never read and removal was
unconditional - so "this drive would not accept it" and "this computer has no trash" produced
opposite outcomes for a user who cannot tell the two apart, and the destructive one was the one
that required no decision from anybody. Both now leave the folder in place and report it by name
with `cleanup.NO_TRASH_REASON`, so **permanent mode below is the only way any folder is ever
destroyed**, which is what makes the typed word match the outcome on every path without the
outcome having to be inferred from a flag. Pinned by
`test_no_trash_backend_is_a_refusal_not_a_licence_to_destroy`, whose cry-wolf half
(`test_permanent_still_removes_when_there_is_no_trash_at_all`) holds permanent mode open for the
mounts it was written for.

**Permanent mode (`clean-empty --permanent`), for mounts with no trash.** A cloud or network
mount has nowhere to trash *to* (`gio`: "Unable to trash file across filesystem boundaries"), so
condition (d) can be impossible to satisfy. In that case, and **only** in that case, removal may
be permanent - under three further conditions: trash is still **tried first** and permanent
applies per folder, exactly to the ones it refused; the preview states plainly that removal is
irreversible on this mount **before** asking; and the confirm is a **distinct phrase**,
`delete forever`, never the `clean` a user typed for a recoverable removal. Removal uses
**`rmdir` semantics** - only the named junk is unlinked, then the directory must be empty - so a
folder that gained a file between the preview and the confirm cannot be removed *by
construction* rather than by a re-check that could race. Pinned by
`test_permanent_removal_cannot_delete_a_folder_that_gained_a_file` and
`tests/test_clean_empty_cli.py`.
Enforced by `cleanup.plan_cleanup` / `cleanup.run_cleanup`; pinned by `tests/test_cleanup.py`.

**Source-relocation exceptions (features k and q), all opt-in:**

- **`organizer.execute(move=True)` (`--move`).** Deletes a source **only** after its just-written
  destination copy re-hashes to the recorded `copy_sha256`. Ordering is copy → record → re-verify
  → delete, so no interruption leaves a window with zero copies; any verify/delete failure keeps
  the source and reports `MOVE_KEPT`. Only under `apply=True`.
- **`reclaim.run_reclaim` (`truestill reclaim`).** Deletes a source **only** after re-hashing a
  destination copy on a **currently-connected** drive at delete time (never trusts a stale
  `last_verified`). Dry-run is the default; `--apply` additionally requires a typed `delete`
  confirmation. `--min-copies N` (default 1) gates on recorded redundancy; single-copy outcomes
  are warned. Every deletion is journalled (`reclaim_journal`, schema v9) for audit/resume.
- **`LocalDestination.adopt` (`--in-place`, and `--move`'s same-filesystem fast path).** Moves a
  source by **rename**: nothing is copied, nothing is deleted, and no other process ever
  observes an instant at which the content does not exist - strictly safer than
  copy-then-delete, which is why plain `--move` uses it automatically wherever the filesystem
  allows. **That guarantee is against concurrent observers, not against a power cut.** A rename
  survives a crash intact only where the filesystem journals its metadata (ext4, APFS, NTFS,
  btrfs); FAT32 and exFAT journal nothing, so a power loss mid-rename can orphan the entry. On
  those drives the `inplace_moves` journal is what makes the run recoverable, and it is the
  thing to rely on - not the rename. `--apply` additionally requires
  a typed `move` confirmation. Every rename is journalled (`inplace_runs` / `inplace_moves`,
  schema v10) and reversed by `truestill undo-organize`.

All are **off by default**. The first two never touch a source whose content is not proven
present at the destination; the third does not need that proof, because it never has two
copies to compare - the file *is* the copy.

> **The safety asymmetry of the rename path, and what answers it.** `--move` and `reclaim` are
> both gated on a *proven second copy*. A rename cannot be gated that way: it produces one
> inode, so any verification is a file checking itself. What is at risk therefore shifts from
> the **data** (a rename cannot lose bytes) to the **arrangement** - a mis-categorized run has
> rearranged the only copy of a library whose owner, by definition of the feature, has no
> backup. **`undo-organize` is that gate**, which is why it shipped with the feature rather
> than after it. Two consequences are binding:
> - `reclaim` must never offer a file whose source *is* the drive copy
>   (`reclaim._is_the_copy_itself`), or the re-verify gate becomes a tautology and reclaim
>   deletes the only copy. Pinned by `test_reclaim_refuses_a_file_organized_in_place`.
> - Undo must clear the catalog rows it reverses (`catalog.forget_organized`), or the content
>   still looks organized and the next run skips every restored file as an exact duplicate.
>   Pinned by `test_undo_clears_the_catalog_so_a_reorganize_works`.
| **Copies are byte-identical to the source EXCEPT the scoped Takeout write.** | The normal path uploads the source bytes unchanged, preserves the source's atime/mtime exactly, then applies the resolved capture timestamp to the **destination copy** through `Destination.set_timestamp`. It must never stamp `decision.source`: besides violating copy-only, changing source mtime invalidates that file's hash-cache entry. An adopt/relocate is deliberately different - ownership of that inode is transferring, so it is stamped before the rename or verified cross-device fallback. The only byte-changing exception is `organizer._upload_with_metadata_write`, reached **only** when an `IngestContext` carries a write (Takeout ingestion). Staging and baking belong to `organizer._MetadataBaker`, which copies each file to a temp path and bakes a **chunk at a time** via `exif.write_metadata_batch` (lossless, no pixel re-encode). A bake that exiftool does not confirm raises `organizer.MetadataBakeError`, and the file is reported FAILED rather than uploaded unbaked. Performance contract in §8. |
| **Categorization is evidence-derived - no hardcoded taxonomy.** | `categorize.build_rules` is an ordered rule chain; labels are plain `str` (there is no `Category` enum in `models.py`). New sources are added as a `NAME_PATTERNS` row, a `CAMERA_NAME_PATTERNS` row (§4 - the two tables are deliberately separate), or derived from the `Software`/device rules. |
| **Dating uses an evidence chain, never filesystem mtime.** | `dates.resolve_capture_datetime`. Capture mtime is only ever *written* to an uploaded destination copy (`Destination.set_timestamp`), a staged Takeout copy, or a file being adopted/relocated (`organizer._apply_timestamp`); a pure-copy source is preserved exactly. Filesystem mtime is never *read* for placement. |
| **Every source file is accounted for - none silently dropped.** | `organizer.scan_source` partitions a source into `media` / `documents` / `unrecognized` / `exiftool_backups`; the CLI end-of-run report (`_print_skipped`) and the app organize summary (`service._skipped_summary`) surface the skipped buckets. Exiftool `*_original` sidecars are refused as primary media at scan (including under `--all-files`) and reported as **exiftool backup**, never as a bare extension count. Nothing is discarded without appearing in a report. |
| **Your photo data never leaves your machine.** No telemetry, no usage beacon, no phone-home in the CLI, core, or app, and **nothing about a library** - not filenames, not counts, not hashes - is ever transmitted. An **account is required at activation** (`DECISIONS.md` D5, which supersedes D1): one-time, email-verified against a self-hosted licensing server, after which the app holds a signed local token and runs fully offline. Usage is otherwise measured externally and in aggregate. Any future crash reporting must be opt-in, off by default, self-hosted, transparent, and post-launch only. | No network path in the product transmits user activity or library content; the capability seam (`§2`) gates on the local token. **Unbuilt** - post-launch, and the licensing server needs its own design pass first. |

**Dating tier order (current), from `dates.resolve_capture_datetime`:**

- **An edit time is never a capture date.** `ModifyDate` and `FileModifyDate` are refused
  permanently (`dates.REFUSED_DATE_TAGS`), alongside filesystem mtime. They record when a file
  was last written, not when it was taken - a photo cropped in 2024 carries a 2024 `ModifyDate`
  beside a 2014 `DateTimeOriginal` - and they are present *precisely* when `DateTimeOriginal` is
  absent, so a chain that treated "any date beats none" would reach for them exactly where they
  are least trustworthy. Probed on the real library: of the files with no `DateTimeOriginal`,
  **every one** carried a `ModifyDate`. Pinned by
  `test_edit_times_are_never_consulted_for_placement`; survey in
  `docs/date-layering-gap-check.md`.
- **A messenger filename is never a capture date.** `IMG-20250804-WA0020.jpg` carries the day
  the file was *delivered*, not the day it was taken - forward a 2015 photo today and the name
  says today. Files whose only date is a messenger convention (`categorize.is_messenger_filename`,
  reusing `NAME_PATTERNS`) go to `Undated/`. **Screenshot filename stamps are still trusted**:
  they share the `YYYYMMDD` pattern but not its meaning, so the refusal is scoped to the
  convention, never the pattern. `dates._filename_capture_date`; pinned by
  `tests/test_messenger_dates.py`; rationale in `docs/messenger-dates-research.md`.
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

> **Schema note (repeatedly moved - read the current line, not the reservation).** This policy
> originally reserved catalog **schema v9** for persisted date **provenance** (`date_tool`,
> `date_field`). v9 shipped as `reclaim_journal`; the note was then updated to reserve v10, and
> **v10 shipped as `inplace_runs` + `inplace_moves`**; the note was updated again to reserve
> v11, and **v11 shipped as `migration_runs`** (completed-migration reversibility); **v12 then
> shipped as `trips` + `trip_days`**. The `files` table still has no date-source column.
>
> The reservation keeps moving because a *reserved* version number is not a reservation - it is
> a guess about which feature ships next, and the feature that actually ships takes the number.
> **Do not reserve a version again, and this note will not name one.** `DateSource` is already
> resolved per file and already aggregated per run by `models.date_quality` and the two report
> surfaces; only the *library-wide* figure (`SHIPPED.md` item `(n)`) needs a column, and it takes
> whatever version is free on the day it is built - whichever number that turns out to be.

---

## 2. Architecture contract

- **uv workspace**, three packages (root `pyproject.toml` `[tool.uv.workspace]`):
  - `packages/truestill-core/` - the pure library. The clustering core (`events.py`) does **no
    I/O** and takes no filesystem/interaction dependencies; it operates on passed-in data.
  - `packages/truestill-cli/` - the thin CLI (`truestill organize` / `truestill ingest`), which wires
    core stages together and owns all interaction (prompts, printing).
  - `packages/truestill-app/` - the local web UI (`truestill-app`). Depends on
    `truestill-core` **only**, never on `truestill-cli`. **`service/` is where state and work
    cross the boundary**, with exactly one exception, named rather than glossed: every catalog
    access in `truestill-app` goes through `service/` **except the startup inspection** -
    `__main__.py` calls `catalog_startup.inspect_catalog`, which opens a `Catalog` to read
    `count()` and `list_drives()` for the launch banner before any route exists. `server.py`
    itself constructs no `Catalog` and holds no transaction. **This rule is about
    `truestill-app`:** `truestill-cli` opens its own catalogs throughout, which is its job and
    not a violation of anything here.
    `server.py` does reach into core directly for four names, and that is allowed because none
    of them is state or work: `InvalidEventSettingsError` and `InvalidEverydayDaySettingsError`
    (turned into HTTP replies), `ReviewCard` (a value type) and `default_catalog_path` (the
    default `--db`, resolved per call inside `create_app`).
    **Pinned by `packages/truestill-app/tests/test_app_core_import_boundary.py`**, which parses
    every app module outside `service/` and fails on a core import with no recorded
    justification - and on a justification for an import that no longer happens. The allow-list
    lives in that test, one line of reasoning per symbol, `inspect_catalog`'s exception included.
    Two earlier wordings failed here and both are worth remembering: "`service.py` is the sole
    bridge" was false because `server.py` imports those four, and its replacement - "every
    catalog read and write goes through `service/`" - was false because of the startup
    inspection above. A universal is the tempting shape and the fragile one; **the exception is
    part of the rule**, and a list kept by hand is what drifted three times before this one was
    made executable.
  - Further packages (e.g. a native shell) slot **beside** these without restructuring the core.
- **One layout seam, and no way around it.** Every placement decision renders through
  `layout.LayoutScheme.render`, which calls `layout.classify(rule, context)` - **the one
  router**, total and exhaustive over `layout.Placement` (a `StrEnum`: `SIDE_BIN`, `EVERYDAY`,
  `EVENT_DAY`, `TRIP_DAY` - a day inside a named multi-day trip, `trip-grouping-research.md` §2,
  §13.2 - and `DAY_BUCKET` - a heavy un-evented Everyday day, `adaptive-day-folder-research.md`).
  `classify` keys on the **rule** (`CategoryMatch.rule`, timeline vs side bin), then trip,
  event, then the caller-supplied `heavy_day` flag - never counts or opens a catalog itself. A
  trip-claimed day takes precedence over an event unconditionally, so `context.event` is never
  consulted once `context.trip` is set. `LayoutScheme.of` is the **build-time exhaustiveness
  gate**: adding a `Placement` member fails `mypy --strict` there (`assert_never`) until every
  scheme-construction site says what template that shape gets - demonstrated for `TRIP_DAY` and
  again for `DAY_BUCKET`: removing its `case` arm alone made mypy fail at exactly that line.
  **What that gate cannot reach, and the rule that covers it: ask timeline membership with
  `layout.TIMELINE_RULES`, never by comparing against `TIMELINE_RULE`.** `assert_never` forces a
  new `RuleName` member to be handled inside `classify`; it cannot force the callers that ask
  *"is this file on the timeline?"* for themselves - event clustering, migration routing and
  headers, trip placement, heavy-day counting, placement. There were seven, each an equality, and
  missing one when a rule joins the timeline would land a file there while silently excluding it
  from event naming or trip placement. `TIMELINE_RULE` stays the value to **construct** with
  (`migrate` maps a route back to it, the layout samples render with it); only the membership
  question is a set. Enforced by `test_timeline_rules_membership.py`, which reads every source
  file under `packages/*/src`. **The set holds `DEVICE` and `CAMERA_FILENAME`** (§4), so it is
  no longer true that membership equals equality - the same test now pins the stronger and
  durable rule instead: over **every** `RuleName`, membership in `TIMELINE_RULES` agrees with
  what `classify` does with it. Those are the two edits a new timeline rule needs, in two
  files, and each is exactly what would be forgotten without the other.
  `plan`, `build_relative` and `apply_events` take a **`LayoutScheme`, never a bare template**,
  and a library that has chosen nothing gets `layout.DEFAULT_SCHEME` - the **year-first**
  default (`DEFAULT_PRESET = PRESETS["year-month-event"]`), which is the shape §4 describes.
  *(This line read "the legacy layout expressed as a scheme" until 2026-08-01. That was true
  only before the flip: the legacy scheme was the default while the bridge existed, and
  `legacy-decommission-research.md` removed it on 2026-07-28. §2 and §4 contradicting each other
  on the product's most visible default is the kind of drift a reader cannot resolve from the
  document alone.)*
  There is deliberately no template-only path: an optional seam is a
  branch, and the branch had already silently switched routing off for every production run.
  - **One resolution entry point.** `layout_settings.resolve_scheme` is the only way to ask what
    layout a catalog is on; `layout.scheme_from_string` is the only interpretation of a stored
    template, and it parses through the same strict door as Settings - there is no load-time
    leniency, so `{category}` is rejected everywhere except inside the fixed side-bin shape,
    which is not user-supplied.
    Runs, previews and the Settings screen all come through them, which is what makes
    `test_a_run_and_a_preview_of_the_same_layout_agree` (every shipped preset) hold.
  - **Migration renders through the same seam** (`migrate.plan_migration` takes a
    `LayoutScheme`). The catalog stores a *label*, not the rule an organize run routes by, so
    `migrate.label_routes` bridges the two: labels only a screenshot/messenger/fallback rule can
    produce are routed deterministically, and everything else is **ambiguous by construction**
    (`Camera` is the device rule's default *and* a possible `Software` value; `--by-device` makes
    any label possible). Ambiguous labels are resolved per file by re-reading metadata for
    **those labels only** (`migrate.rederive_rules`), and are never silently routed. Pinned by
    `test_a_migration_and_an_organize_run_agree_under_the_same_layout`.
  - **Migrations are reversible until superseded.** A completed migration's journal rows are
    **kept**, not deleted, and `migrate.undo_migration` walks the newest run's moves in reverse
    with the forward run's discipline: relocate back, **re-hash at the restored path, and only
    then remove the migrated copy**. A failed verify raises and leaves both the file and its
    journal row intact, so an interrupted undo resumes exactly as an interrupted migration does.
    A file that no longer hashes to what the migration recorded is **refused and reported**, never
    clobbered - someone edited it since, and putting the old path back would discard that work.
    Retention is bounded by supersession: the next migration of the same drive clears the
    previous record, so exactly one run's worth exists per drive and the only record ever dropped
    is one a newer migration has already made meaningless. Catalog `file_copies` rows are updated
    per reversed move, so `verify` passes against disk afterwards. Schema **v11**
    (`migration_journal.run_id` / `completed_at`, plus `migration_runs`).
  - **The unmapped direction is the safe one.** A label with no decision is treated as a side
    bin: a file kept beside the years stays findable and fixable, while one wrongly hoisted onto
    the timeline is mixed into the photo record.
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
- **Schema versioned via `PRAGMA user_version`.** Current: **`CURRENT_SCHEMA_VERSION = 18`**.
  Migrations are ordered, idempotent functions in `_MIGRATIONS`; a catalog newer than the code
  is refused (`CatalogVersionError`). Migration coverage tested in `tests/test_catalog.py`.
- **A migration is not a transaction, and three conventions are what make that safe.** Measured
  2026-08-02: interrupting v17 after its third `ALTER TABLE` left three of five columns
  committed, because DDL autocommits under Python's legacy transaction control. Nothing was lost
  because (1) `user_version` is bumped **after** the migration function returns, so a partial
  upgrade leaves the *old* version and re-runs rather than being skipped; (2) every migration is
  **idempotent**, so the re-run completes it; and (3) **no migration performs a backfill** - DDL
  commits while DML rolls back, so a crash between them would commit the column, lose the data,
  and then have the column guard skip the retry. **Do not add a backfill to a migration, and do
  not remove a guard, without reading `tests/test_migration_safety.py` first** - it pins all
  three, and a backfill is the case that would force an explicit transaction. Transaction
  control is pinned at the connect call to today's `LEGACY_TRANSACTION_CONTROL`, so a future
  Python default cannot change when writes commit; adopting the new semantics is a separate
  decision.
- **Table inventory (v15 - the last migration that adds a table; v16 and v17 add only
  columns, and v18 only drops an index):**
  `files`, `albums`, `file_albums`, `events`, `skipped_clusters`, `drives`, `file_copies`,
  `settings`, `migration_journal`, `reclaim_journal`, `inplace_runs`, `inplace_moves`,
  `migration_runs`, `trips`, `trip_days`, `date_confirmations`.
  v13, v14 and v16 add no table: they are the columns `files.date_source`, `files.date_tag`
  (the tier, and the evidence behind it) and `file_copies.date_baked_at`.
- **Migration ledger:** v2 `size`, v3 `original_name`, v4 event tables (`events` +
  `skipped_clusters` + `files.event_id`), v5 Takeout (`files.copy_sha256` + `albums` +
  `file_albums`), v6 drive identity (`drives` + `file_copies`), v7 key/value `settings`
  (first use: the layout template), v8 `migration_journal` (crash-safe layout migration),
  v9 `reclaim_journal` (audit/resume for `truestill reclaim` deletions), v10 `inplace_runs` +
  `inplace_moves` (**reversible** journal for rename-based relocation), v11 `migration_runs` +
  `migration_journal.run_id`/`completed_at` (makes a **completed** migration reversible, not
  merely resumable), v14 `files.date_tag` (the winning tag, or the container/rung/offset for an
  inferred video time - the evidence the honesty view shows), v13 `files.date_source` (the resolver's tier, persisted at last - see
  `docs/date-provenance-design.md`; pre-existing rows stay **NULL**, which means "not recorded"
  and is deliberately distinct from any real tier), v12 `trips` + `trip_days` (multi-day trips, identity is the **row**
  - `trips.id` - never a membership hash; `trip_days.day` is a primary key, so a day belongs to
  at most one trip). v12 is also the first **schema-level down-migration** in this codebase
  (`downgrade_v12_to_v11`, testing/rollback only - no runtime path calls it) and introduces the
  first **declared foreign key** (`trip_days.trip_id REFERENCES trips(id)`), which is why
  `Catalog.__init__` now sets `PRAGMA foreign_keys = ON` per connection - SQLite does not
  enforce a `REFERENCES` clause unless that pragma is set, and without it the FK fixture would
  have passed for the wrong reason. v15 `date_confirmations` (human date confirmations, in their
  **own table keyed on content** rather than a column on `files`: `forget_organized` deletes the
  `files` row when an undo removes the last copy, so a column would have been deleted by the
  first `undo-organize` - exactly the failure `(ii)` (`SHIPPED.md`) exists to prevent. Keyed on `sha256`,
  because content identity survives rename, migrate, re-layout and in-place organize where a
  path does not). v16 `file_copies.date_baked_at` (whether a confirmed date reached that copy's
  bytes - a date only truestill knows is not the same promise as a date any other tool will
  read). **v16's flag is on `file_copies`, not on `date_confirmations`, deliberately:** a
  confirmation is per *content* and a bake changes *one drive's copy*, so putting it on the
  confirmation would let a photo baked on the laptop count as baked for a backup drive that
  never receives it - the same per-content / per-drive confusion behind the `copy_sha256` and
  `relative` findings, caught before v16 shipped. v17 `files.camera_make` / `camera_model` /
  `lens_model` / `gps_latitude` / `gps_longitude` (the camera and the coordinates, which were
  read on every run and discarded - `Make`/`Model`/`LensModel` decide the Camera category and
  the coordinates feed the event jump-cut, and none of them was written anywhere durable.
  **All five tags were already being requested from exiftool**, so this is a column and not a
  pass: `tags_fingerprint` is unchanged and no cached metadata is invalidated. Coordinates are
  signed decimal degrees; **NULL means the file carries no location and 0.0 means the equator
  or the prime meridian**, which is why the reader tests `isinstance` rather than truthiness -
  exiftool returns integer `0` there and `0` is falsy. No backfill: a pre-v17 row keeps NULLs,
  because recovering the values means re-reading the file and that is a decision of its own).
  v18 **drops** `idx_files_sha256` - the first migration that removes rather than adds.
  `files.sha256` is `NOT NULL UNIQUE`, so SQLite already maintains `sqlite_autoindex_files_1`
  over exactly that column; the explicit index was a second B-tree on the same key, costing
  **196 KB and one extra write per insert** for nothing a query needed. Measured on two clean
  copies rather than by dropping it in place: every query touching `files.sha256` was planned
  both ways, the three that chose it moved to the autoindex, and `library_status` - the only full
  scan among them - ran **0.844 ms with and 0.848 ms without**. *An in-place drop first suggested
  a 1.7x slowdown; that was the freed pages, not the plan.*
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
| **Creating** a marker, unlike upgrading one, happens automatically where the user's action already implies it: **both surfaces** write one at an organize destination, and the app also at a backup target - only on a real run, previews stay pure. Registering is what makes the folder verifiable, findable and countable toward 3-2-1; without it the app rejected the library it had just built. **The CLI was the outlier until 2026-08-05**: it read a marker and never created one, so `truestill organize` into an ordinary folder wrote `files` rows with no `file_copies` row - in the dedup index, so a re-run skips them forever, and outside custody, so `verify`, `status` and `where` could not see them. Same operation, two outcomes, decided by which surface the user picked. **Pre-existing rows are not repaired by the fix** - see `BACKLOG.md`. | `service.attach_drive`, `service.organize_run`, `cli._register_destination`. Pinned by `test_the_golden_path_organize_then_back_up` and `test_organize_registers_the_destination.py`. |
| **Identity is copied verbatim** - `uuid`, `label`, `created` unchanged. Re-minting a uuid would orphan every recorded copy in `file_copies` and under-report the custody count. | `drive.upgrade_marker`. Pinned by `test_upgrade_preserves_identity_verbatim_and_keeps_the_legacy_file`. |
| **The legacy file is retained, never deleted.** Deleting on a user drive is what §1 copy-only forbids; keeping it (~100 bytes) means an older build and a current build agree on identity. | `drive.upgrade_marker` writes only. Pinned by the same test. |
| **Canonical wins if both exist and diverge** - a documented precedence, never a merge. | `drive.existing_marker_path` order. Pinned by `test_canonical_wins_when_both_markers_exist_and_diverge`. |
| **Marker filenames are never hardcoded in messages.** User-facing text interpolates `MARKER_NAME`. | `cli.py` f-strings and `drive.py`, which owns the constant; asserted via `MARKER_NAME` in `test_migrate_cli` / `test_reclaim_cli` / `test_drive_cli`. **The app is not a site for this rule:** `MARKER_NAME` appears nowhere in `truestill-app`, because the marker filename never reaches a screen - the app names drives by label. This row used to cite `service.py`, which is both the wrong package and no longer a file. |

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
- **Folder structure (year-first, default since 2026-07-28).** The timeline is the drive root;
  categories are labelled **side bins beside the years, never above them**:

  | | Path |
  |---|---|
  | Camera, un-evented | `YYYY/YYYY-MM/YYYY-MM - Everyday/` |
  | Camera, named event | `YYYY/YYYY-MM/YYYY-MM-DD - <Name>/` |
  | Non-camera (side bin) | `<Label>/YYYY/YYYY-MM/` |
  | Undated, timeline | `Undated/` (at the root) |
  | Undated, side bin | `<Label>/Undated/` |

  Months name themselves (`2014-08`, not `08`) so a folder still says what it is once copied
  away from its parent. The `Everyday` bucket keeps ordinary photos from sitting loose among a
  month's event folders. The side-bin shape is **fixed and not user-editable**, and `{category}`
  is rejected in a timeline template at input (§2), so category-first and category-last are
  structurally impossible rather than merely unavailable.
- **A library is never silently reshaped.** On an explicit write path,
  `layout_settings.pin_existing_layout` records the current default when a library has already
  placed files but has no stored layout. Future default changes therefore apply only to new
  libraries; an existing tree changes only through an explicit migration. The pin knows nothing
  about any particular shape.
- **Event placement:** a named Camera event's folder is `YYYY-MM-DD - <Name>` under its month,
  carrying the **human name** the user typed (path-safe per §9), not a slug. A legacy library
  falls back to `YYYYMMDD_<slug>` only when no name was recorded. A cluster straddling a month boundary is consolidated
  under its **start** month (`organizer.apply_events`; pinned by
  `test_apply_events_consolidates_cross_month_under_start_month`).
- **Category set** (derived, ordered; `categorize.build_rules`): screenshot-by-metadata →
  screenshot-by-name → messenger/app filename conventions → editing `Software` →
  capture device (`Camera`, or per-device with `--by-device`) → capture filename convention →
  `Saved/`.
- **A capture convention is evidence; a timestamp is not.** A device that names its own files
  `IMG_YYYYMMDD_HHMMSS` / `VID_YYYYMMDD_HHMMSS` has signed them, so those reach `Camera` even
  with no `Make`/`Model` to read (`categorize.CAMERA_NAME_PATTERNS`, `rule_camera_filename`).
  **The predicate is the convention, never a bare embedded date** - a film saved from the web
  carries a `CreateDate` too, and `IMG_1234.JPG` is a counter, not a capture record. The table
  is **separate from `NAME_PATTERNS` and must stay separate**: that one also drives
  `is_messenger_filename`, which makes the date chain *refuse* a filename as a capture date, so
  an entry added there would cost these files the dates they do have. Pinned in
  `test_camera_filename_convention.py`, cry-wolf half included.
  - **Blank device tags are not a device-rule bug**, and this rule is not compensating for one.
    Every rule reads tags through `categorize._text`, so absent, `None`, `""` and whitespace are
    one state at the only place that decides - `rule_device` correctly declines all four,
    because a present-but-empty `Make` asserts nothing. Pinned in the same file, structurally as
    well as behaviourally, so a rule growing its own `metadata.get` is caught.
  - **Two rules now reach the timeline, so `layout.TIMELINE_RULES` and `layout.classify` must
    agree** - see §2. `test_timeline_rules_membership.py` asserts that agreement over every
    `RuleName`, which is the check that makes a third one safe to add.
- **Evidence beats filename.** The filename conventions **stand down when the file names the
  camera that took it** (`categorize.capture_device_model` - `Model`, or `SamsungModel`; a
  `Make`, a date or a coordinate alone is not a device). A photo sent as a document keeps its
  EXIF, and truestill already dates that file from it, so categorising it by its name was one
  chain contradicting the other. **The stand-down condition is exactly the condition under which
  the capture-device rule fires**, read from one function by both, so no metadata shape falls
  through every rule to `Saved/`. The order above is unchanged: deferring touches only files
  carrying capture evidence, where a reordering would move every convention at once.
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
| **A relocation is gated on an explicit typed word, never a default-yes.** `--apply` is permission to *ask*, not permission to move: `migrate-layout` prints the plan and requires the exact word `move`; anything else (including a bare Enter) aborts with nothing moved. The app Settings migrate path uses the same gate via `typedConfirm` with word `move` after preview (never a one-click Move). Every migration or Trips & events preview is a read: neither the CLI nor the app may write anything at all, not even refresh a connected drive's label or `last_seen`. | `cli._cmd_migrate_layout`, `static/app.js` `renderMigrateTypedConfirm`, `service.migration_preview`, `service.propose_events`; pinned by `test_a_preview_moves_nothing_and_writes_nothing`, `test_without_the_typed_confirm_nothing_moves`, `test_settings_migrate_uses_typed_confirm_move`, and `test_drive_preview_endpoints_never_refresh_the_catalog`. |
| **The Everyday day-folder threshold is a per-catalog setting, default 40.** Un-evented days over the threshold get `{yyyy}-{mm}-{dd} - Everyday`; under stay in the monthly bucket. Changing the setting must warn that existing files do not move until migrate, with a route to Settings → Rearrange your library (`#settings-migrate`; the name is `layout.MIGRATE_CARD_NAME`, not retyped). | `layout.EverydayDaySettings` / `EVERYDAY_DAY_THRESHOLD_KEY`; `service.set_everyday_day_settings`; pinned by `test_everyday_day_threshold_change_is_honoured_and_warns_to_migrate`. |
| **Never push without being asked.** | Convention - not yet enforced. |
| **Real-library corpus fence (2026-07-30; the cloud half ended 2026-08-08).** Test / profile / soak against **only** the maintainer's stated pair: source `TruestillLibrary/Input`, destination `TruestillLibrary/Output`. `Input/Testing-new` stays out - single copy, uncatalogued. **The cloud mount is gone.** The client was uninstalled on 2026-08-08 and the mountpoint removed, so The Memory Cabinet, `<cloud mount>/2015` and everything under `Crypto Folder/` no longer exist on this machine and cannot be reached by any means. **The fence is kept rather than deleted, because its reason outlives the paths:** that material was the maintainer's real photographs, and a fence over someone's own library is not repealed by the library becoming temporarily unreachable. If any of it returns, OFF LIMITS returns with it. If a task appears to need it, STOP and ask. | Convention - human process; recorded in `PROJECT_STATUS.md` §4. |
| **Commit identity / no-AI-trailer** - no `Co-Authored-By` trailer, no Anthropic/Claude email or signature in history. | **Enforced:** `scripts/check_commit_msg.py` via the `commit-msg` pre-commit hook (`.pre-commit-config.yaml`, id `no-ai-coauthor`). Activate: `uv run pre-commit install --hook-type commit-msg`. |

---

## 6. Quality gates

- **`make check`** = `ruff check .` (lint) + `ruff format --check` + `mypy` on the three
  `src` trees + `pytest` (`Makefile`).
- **`ruff format --check`** is also a separate gate in CI (and `make format` applies it).
- **`dash-check`** = `scripts/normalize_dashes.py --check`, in `make check` and in pre-commit.
  See the prose convention below.
- **`redirect-check`** = `scripts/check_redirect_artifacts.py`, in `make check` and in
  pre-commit. Refuses repo-root filenames that are bare numbers (`10.0`) or ISO dates
  (`2024-03-24`) - the shape left by pasting ``> 25.9`` / ``-> 2024-03-24`` into a shell.

### 6.1 The prose convention: hyphens, not em-dashes

**Repo prose and source use the ASCII hyphen.** This is the maintainer's house style and it is settled;
do not reintroduce `U+2014`, and do not "restore" the em-dashes in an existing document.

The rule has one detail that matters more than the preference itself, because getting it wrong
shipped a defect:

- **The replacement preserves spacing.** An em-dash with whatever whitespace hugs it becomes
  exactly `" - "`. It must **never** produce `word-<space>word` - a hyphen glued to the
  preceding word with a space only after it. That is not a style; it is mangled prose.
  (The bad pattern is spelled `<space>` throughout this section on purpose: written literally,
  it would be "repaired" by the very sweep it documents.)
- **User-facing surfaces are excluded outright:** `truestill_app/static/`,
  `truestill_app/templates/`, `CHANGELOG.md`, `README.md`, `SECURITY.md`. **UI typography is a
  choice, not a sweep target**, and those files are prose a user reads rather than prose we
  maintain.
- **`scripts/normalize_dashes.py` is the tool.** `--check` reports, `--apply` rewrites. Use it
  rather than a hand-rolled `sed`; that is what caused the damage.
- **The allowlist is explicit and must not silently grow.** Genuine suspended hyphens
  (`Camera- and app-generated`) are the same *shape* as the damage (`photos-<space>and, worse`), and no
  regex over English separates them - the first attempt protected the one real case in the repo
  along with eleven damaged ones. Add a literal, with its file, when a real one appears.
- **`packages/truestill-app/tests/test_user_facing_copy.py`** guards the shipped strings against
  `word-<space>word` independently of the sweep.

**Where it came from, so nobody hunts for an in-repo mechanism again:** on 2026-07-28 a
repo-wide sweep run from **the maintainer's own editor, outside the repo**, replaced every `U+2014` and
consumed the leading space with it - 61 sites, including two in the web UI's backup banner. There
is **no git filter, no hook, no script in this repository that does this**; that was checked
exhaustively before anything was changed. Ruff, mypy and pytest were all green throughout, which
is the point of the gate: **no other gate we have can see prose.**
- **The fence covers `scripts/` too.** `ruff check .` is repo-wide (packages, `tests/e2e/`,
  `scripts/` - the last with its own per-file ignores, because a benchmark script's `print`
  *is* its output), and **mypy covers `packages/*/src/` plus `scripts/`**. Tests stay out.
  - **Why scripts are in the fence, from the evidence:** `scripts/benchmark_hashing.py` sat
    outside it and imported `truestill.scan` - a module that has never existed under that
    name. It survived `vaeon` → `vaeon_core` → `truestill_core` untouched, silently broken,
    because nothing ever checked it. A script that imports the core is real code.
  - **`mypy_path` in `pyproject.toml` resolves workspace packages from source**, so mypy gives
    the same answer under `uv run` as inside pre-commit's isolated environment.
  - **The pre-commit hook overrides its upstream `args`.** `mirrors-mypy` defaults to
    `--ignore-missing-imports --scripts-are-modules`; the first is what let the broken import
    above pass a hook that appeared to be checking it. Set to `args: []`, which is only safe
    because of `mypy_path`. Stub gaps are handled **per module** in `[[tool.mypy.overrides]]`,
    never by a blanket flag - a flag that hides one missing stub hides every missing import.
- **CI** (`.github/workflows/ci.yml`) has **two jobs**:
  - **`check`** - matrix **{ubuntu, macos, windows} × Python 3.13**; steps = sync (`--locked`)
    → ruff (lint) → ruff (format --check) → mypy → pytest → **dependency audit** (Linux only);
    exiftool installed per-OS.
  - **`e2e`** - the browser lane, chromium on ubuntu (below). **A separate job, not a matrix
    entry**, so a browser-layer failure is distinguishable at a glance and never masks a Python
    one.
  - The CI mypy step, `make typecheck` and `.pre-commit-config.yaml` all cover the same three
    `src` trees - **keep the three in step with each other.**
- **The lockfile must be current.** CI syncs with **`uv sync --all-packages --group dev
  --locked`**, which fails if `uv.lock` has drifted from the `pyproject.toml` manifests
  instead of silently re-resolving. `uv.lock` is the source of truth for what ships (§7), so
  drift means CI has quietly stopped testing the real dependency set. Regenerate with
  `uv lock` and commit it.
- **Dependency audit.** `pip-audit` runs against the **locked** set
  (`uv export --no-emit-workspace` → `uvx pip-audit -r …`), Linux-only because it reads a
  lockfile rather than the installed tree, so all three runners would produce the same answer.
  **Findings block the build** - a vulnerable dependency is a defect, not a warning.
  - **Accepting an advisory is allowed, but never silently.** Add `--ignore-vuln <ID>` to the
    CI step with an adjacent comment giving **the reason and the advisory link**, so every
    accepted risk is visible in review and in `git blame`. An audit that passes because
    something was quietly suppressed is worse than no audit.
  - **KNOWN BLIND SPOT: the audit sees PyPI distributions, not the native libraries inside
    them.** `pip-audit` is given a locked requirements list, so it reads `pillow-heif==1.5.0`
    and nothing else. That wheel bundles ~26 MB of C libraries - libheif, libde265, x265 - and
    **a CVE against one of those is invisible to this gate**: measured 2026-08-02, the audit
    input contains **zero** mentions of libheif, libde265 or x265. The audit can report a clean
    build while shipping a vulnerable decoder, and this is the decoder that reads **untrusted
    user media**, which is the whole of our threat surface.
    - **Checked 2026-08-02 and the answer was clean**, so this is a recorded gap rather than a
      live exposure - see the `pillow-heif` row in §7 for the bundled versions and how to read
      them at runtime. A negative result is recorded here so the next person does not re-derive
      it, and so the gap outlives the good news.
    - **Closed as far as it can be from inside the repo (2026-08-02).** §7.1 records the
      bundled versions and `test_bundled_native_versions.py` pins them two ways: the record must
      equal what the wheel actually ships, and what ships must be at or above a recorded security
      floor. The audit still cannot see native libraries - that is `pip-audit`'s scope, not
      something we can change - but a wheel upgrade can no longer move the decoder silently, and
      a reviewer meets the versions without knowing to look for them.
  - **Current ignore list: empty.** First run (2026-07-27) was clean: 28 runtime packages and
    40 including dev, zero known vulnerabilities. That pair is kept as the **dated record of
    that run**, not as a live figure. Measured again 2026-08-01 via
    `uv export --no-emit-workspace`: **14 runtime packages** (`--no-dev`, i.e. what a buyer
    installs) and **86 including dev**. The two pairs are **not directly comparable** - the
    method behind the 2026-07-27 figures was not recorded - so the current numbers are given
    with theirs rather than overwriting them. The dev set grew with the browser lane and the
    packaging probes; the runtime set is small because most of its weight is `scipy` and
    `pywavelets`, which are two packages and ~90 MB.
- **Complexity is declared, not discovered.** Every new pipeline stage states its complexity
  in *n* in its module docstring, and anything worse than O(n log n) must say so and justify
  the trade; new stages get a **measured** row in the baseline table. The rule, the baseline
  and the non-findings live in [`PERFORMANCE.md`](PERFORMANCE.md) §2 - this is the gate that
  points at it, so a reviewer has one place to check the claim against.
- **`uv build --all-packages`** must produce clean wheels for **all three packages**
  (`make build`); `truestill-core` ships `py.typed`.
- **Browser end-to-end** (`tests/e2e/`, `make e2e`): Playwright via `pytest-playwright`, run in
  CI as its own **chromium-on-ubuntu** lane. It exists because every UI bug the soak era found
  lived in client-side JavaScript - a layer pytest cannot reach and manual checking cannot
  regression-pin. Rules:
  - **Deliberately outside `testpaths`**, so a fresh clone runs `make check` green with no
    browser installed. E2E is explicit opt-in (`make e2e-install`, then `make e2e`).
  - **Assertions are on text a user reads**, not element ids. Every bug it pins was a wrong or
    stale *string*; an id-based assertion would have caught none of them.
  - **Auto-waiting assertions only. No sleeps** - hard waits are the dominant flake source.
  - **No retries.** A retry-until-green browser suite launders the nondeterminism this lane
    exists to expose. A test failing non-deterministically is **quarantined and filed with its
    trace**, never retried (threshold: 3 failures in 10 consecutive runs).
  - **Traces and video are kept on failure only** and uploaded as a CI artifact, so a red run
    arrives with a replay rather than a guess.
  - **Fixtures are generated, never committed.** Media files do not belong in git whatever
    their provenance; `tests/e2e/conftest.py` builds exactly the corpus each test needs.
  - **Scope, honestly.** E2E owns user-visible truth. Engine logic - dating, dedup, layout,
    drive-marker rules, reclaim/undo, migrations - stays owned by the fast cross-OS Python
    tests and must not be re-asserted through a browser. `__main__.py` (port selection, arg
    parsing, browser launch) is bypassed by the in-process harness and remains uncovered.
  - **Playwright is dev-group only.** A clean install of the shipped wheels pulls no browser;
    pinned by `tests/e2e/test_dependency_gating.py`, which checks the resolver output rather
    than trusting the manifests.
- **Browser × OS matrix is deferred on purpose.** The Python matrix already owns OS
  differences; this lane owns client truth, which for a no-build vanilla-JS app is uniform
  enough that a full grid would buy coverage we have no evidence we need. Revisit **on
  evidence** - a real cross-browser bug - and not before.
- **Test counts are never hardcoded** as a done-ness signal - they change. Assert behaviour,
  not totals.

---

## 7. Dependency inventory

Runtime deps must justify themselves against stdlib. **This inventory is whole-product**: it
covers the declared runtime dependencies of all three packages, because its subject is what the
buyer installs, not what any one package happens to own. Pinned by
`test_dependency_inventory.py`, which fails when a declared runtime dep has no row here. Current
state:

| Dependency | Why it exists (vs stdlib) |
|---|---|
| `imagehash>=4.3.2` (`truestill-core`) | Perceptual dHash for near-duplicate detection; requires image decoding, which the stdlib cannot do. |
| `pillow>=12.3.0` (`truestill-core`) | Image decoding backing imagehash and cheap dimension reads. **Large-image policy:** truestill processes the user's own local library (trusted), not untrusted uploads, so Pillow's ~89 MP decompression-bomb guard is a false positive on legitimate large photos (panoramas/scans). `hashing.MAX_PERCEPTUAL_PIXELS` raises `Image.MAX_IMAGE_PIXELS` to **300 MP** deliberately; above it a pathological image is **skipped for perceptual hashing** (SHA-256 exact dedup still applies) and the bomb *warning* is suppressed locally so **no raw Pillow warning reaches the terminal**. (Immich/PhotoPrism avoid this entirely via libvips streaming.) |
| `pillow-heif>=1.5.0` (`truestill-core`) | Registers a HEIF opener so Pillow can decode **HEIC/HEIF** (the iPhone-default format since 2017), enabling their perceptual near-dup dedup. **Graceful degradation is mandatory:** `hashing._register_heif` guards the import; if it ever fails at runtime, `HEIF_AVAILABLE` is `False`, SHA-256 exact dedup still applies to HEIC, and the run **reports** that HEIC perceptual hashing was skipped - never a silent drop. TIFF-based RAW (CR2/NEF/DNG/…) needs no plugin (Pillow's TIFF decoder content-sniffs it); container-based RAW (CR3, RAF) is exact-dedup-only. **It bundles native code, so its version is two questions, not one** - the wheel version above, and the C libraries inside it. Those are recorded and pinned separately, immediately below this table. |
| `numpy>=2.5.1` (`truestill-core`) | The packed perceptual match in `dedup.py`: hashes are stored as a `uint64` array and compared with one vectorised XOR + `np.bitwise_count` per incoming file. **Measured, not assumed:** the stdlib per-pair form (`(int(a,16) ^ int(b,16)).bit_count()`) cost 263-269 ns/pair, flat in n, which is 147 s at 33,457 images and 2,996 s at 150,000; packed, the same work is 0.5 s and 8.9 s (291x / 338x). There is no stdlib array primitive that does this - `array`/`memoryview` still loop in Python, and the parsing, not the XOR, was the bill. **It was already installed** (imagehash imports it at module level), so this adds no download; what changed is that we now `import numpy` ourselves, and §7's rule is that what we import, we declare - a transitive dependency we call directly is one imagehash could bound or drop and break us silently. **Deliberately one-vs-many:** `scipy.spatial.distance.pdist` and sklearn's `pairwise_distances` materialise the full matrix (~560M entries at 33,457, ~11.2B at 150,000) and work on unpacked vectors, so both are slower *and* unbounded in memory for a match that is incremental by nature. |
| `send2trash>=2.1.0` (`truestill-core`) | The OS trash, which the stdlib does not expose at all - `shutil.rmtree` is precisely the thing §1's folder-removal rule exists to avoid. **It was an optional import until 2026-08-04, and the optionality was the defect, not the saving.** `cleanup.trash_backend` probed for it and fell back to the `gio` binary, returning `None` when neither was present; `run_cleanup` then removed folders **outright** on that path. `gio` is a GLib tool, so "neither present" was the ordinary state of Windows and macOS - the platforms D9 launches on - which made a silent permanent delete the default there and a recoverable one a Linux-desktop accident. Declaring it removes the state rather than documenting it. Cheap by every measure that usually argues against a dependency: one `py3-none-any` pure-Python wheel (`Root-Is-Purelib: true`), **BSD-3-Clause**, and **no required dependencies of its own** - `pywin32` and `pyobjc` are `nativelib` extras we do not take, so Windows reaches the Recycle Bin through `ctypes` to `SHFileOperationW` and Linux uses GIO when present and its own freedesktop implementation otherwise. It also removes a packaging question rather than deferring one: an import inside a `try` is what a bundler's static analysis misses, so `(aad)` would have had to discover it as a missing hidden import. |
| `platformdirs>=4.11.0` (`truestill-core`) | The three OS conventions for user data and cache directories, which the stdlib does not expose. The alternative is hand-rolling XDG (with its `XDG_DATA_HOME` / `XDG_CACHE_HOME` overrides), `~/Library/Application Support` vs `~/Library/Caches`, and `%APPDATA%` vs `%LOCALAPPDATA%` - each with edge cases we would rediscover as bug reports on machines we do not have. Pure Python, no dependencies of its own, two calls used; the de facto standard for this (Black, pip, pipx). Getting it wrong is not cosmetic: a wrong data directory is where someone's custody record goes missing. Full argument at `app_paths.py`. |
| `starlette>=1.3.1` (`truestill-app`) | The smallest well-tested ASGI: routing, SSE, static files and background tasks. `http.server` is synchronous and would mean hand-rolling all four, which is where a local server gets fragile. **Not FastAPI**, which wraps Starlette plus Pydantic - §4 disallows Pydantic for internal models and a single-user local app needs none of the OpenAPI/validation weight. Rationale in `docs/ui-v1-research.md` §B1/§C4. |
| `uvicorn>=0.51.0` (`truestill-app`) | The ASGI server that runs Starlette. There is no ASGI server in the stdlib. |
| `scipy` + `pywavelets` (**transitive, via imagehash - never imported**) | Not chosen; **imported by nothing truestill runs.** imagehash declares both as hard `Requires-Dist` with **no extras split** (`Provides-Extra: None`), so every install pulls them: measured **81 MB scipy + 8.6 MB PyWavelets = ~90 MB**. They back `phash` (`scipy.fftpack`) and `whash` (`pywt`), both imported *lazily inside those functions*; truestill defaults to `dhash`, and a `dhash` call in a clean process loads neither (verified: `scipy in sys.modules` is `False` after computing one). `numpy` is genuinely required - imagehash imports it at module level, and since 2026-08-02 truestill imports it directly too, so it has **its own row above** and is no longer part of this transitive note. **There is no way to exclude them at the dependency layer**; the only levers are a bundler `--exclude-module` at packaging time or vendoring, and the first belongs to `(aad)`. Recorded because an installer for non-technical users carries this weight for a code path it never executes. |
| `exiftool` (external **binary**, not a pip dep) | The only tool that reads photo EXIF, **video container tags**, and vendor MakerNotes (e.g. the screenshot marker) through one interface, and the writer used for the scoped Takeout bake. A pip EXIF library would cover photos only. |
| **DejaVu Sans Mono 2.37** (bundled **asset**, not a pip dep) | Book + Bold, `truestill-app/static/fonts/`, **661 KB**. The old stack named five faces and none exists on a stock Linux box, so the product's type signature - every path, count and hash, and the wordmark heading them - was whatever the OS happened to resolve: SF Mono on macOS, Consolas on Windows, DejaVu here. Chosen on measurement: best separation of confusable glyph pairs in three of four at 13px, widest coverage at 3,322 codepoints. **IBM Plex Mono was eliminated** - no U+26A0/U+25AA/U+25AB, so the custody pips and warning mark fell back to Times New Roman *inside the custody line*. **Never subset** (coverage is why it won; a subset renders non-ASCII filenames as tofu) and **never `local()`** (hands rendering back to the machine's own copy). Shipped byte-for-byte upstream, so the Vera modification clause is not reached. |
| `truestill-cli` runtime deps | Only `truestill-core` (workspace source). |

### 7.1 Bundled native libraries (the part `pip-audit` cannot see)

`pillow-heif` is a wheel with C libraries inside it - about 26 MB of them - and **the dependency
audit does not know they exist**: it is handed a locked requirements list, reads
`pillow-heif==1.5.0`, and stops (§6). So the versions that actually decode a user's photos are
recorded here, where a release review meets them, and pinned by
`packages/truestill-core/tests/test_bundled_native_versions.py`.

Deliberately **not** a markdown table: `test_dependency_inventory.py` treats every `|` row in §7
as an inventory entry, and a second table here would quietly widen what that guard accepts.

- **`libheif`** - shipped **1.23.1**, security floor **1.22.1**. The one with a CVE history that
  reaches us, and the only one with a clean version accessor.
- **`libde265`** - shipped **1.1.1**. The HEVC decoder libheif delegates to.
- **`x265`** - shipped **4.2**. The HEVC encoder; we never encode HEIC, so it is carried, not used.

**Read them at runtime, never inferred from the wheel version:**
`pillow_heif.libheif_version()` for the first, `pillow_heif.libheif_info()` for all three.

**The floor is a security statement, not a preference.** 1.22.1 is where the 2026 libheif
advisory cluster was fixed - CVE-2026-32740 (heap overflow in grid-tile compositing),
CVE-2026-32814 (uninitialised memory disclosed from corrupt grid images), CVE-2026-49271 (OOB
read in the uncompressed decoder) and neighbours, closed across 1.22.0 and 1.22.1. Checked
2026-08-02: we ship 1.23.1, above all of them, **not affected**. This matters more here than for
a pure-Python dependency because libheif is what parses **untrusted user media** - the one thing
this product does to files it did not create.

SHA-256 (`hashlib`), SQLite (`sqlite3`), concurrency (`concurrent.futures`), and all path/date
work are **stdlib** - no dependency. **BLAKE3 is deliberately absent** - not because of a
compile story (the `blake3` wheels are prebuilt for typical users), but because SHA-256 is
already ~1% of cold-preview wall after the size pre-filter while exiftool is ~74%
(`docs/preview-performance-profile.md`), and because the catalog keeps one hash column with no
algorithm toggle. Full rationale: `DECISIONS.md` **D8**.

**Version policy:** `requires-python` = **`>=3.13` for all three packages**. Lower-bound + lock;
`uv.lock` is the single source of truth; no blind upper-pins; updates via periodic
`uv lock --upgrade` review.

> **A floor means tested-at, not thought-to-work.** Every `>=` bound must name the version the
> suite actually runs against, and moves when the lock moves. The floors had drifted years below
> reality - `starlette>=0.40` while every test ran on 1.3.1, `pillow>=10.0.0` against 12.3.0 -
> which is a claim of compatibility that had never once been demonstrated: a resolver picking the
> minimum would hand a user an untested application, and the first report would come from that
> user. `packages/truestill-core/tests/test_dependency_floors.py` compares every declared floor
> against `uv.lock` and fails on drift, so a dependency upgrade that leaves its floor behind is
> caught at the moment it stops being true.
>
> **There is deliberately no floor-resolution CI lane.** Resolving and testing at the minimum
> would be a second matrix to maintain for a configuration nobody is asked to run. The honest
> fix is to stop claiming support for it, not to start testing it.

> **The checker floors match the declaration.** `[tool.mypy] python_version` and
> `[tool.ruff] target-version` are both **3.13**, raised on 2026-07-27 from a stale 3.12 that
> predated the floor change below. They are checker *floors*, so the mismatch was harmless -
> but a config that claims 3.12 while every package requires 3.13 is a false statement about
> what is being verified, and the point of this section is that the claim and the check agree.
>
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
- **Hash cache** (`hash_cache.HashCache`, wired through `scan.compute_hashes`). An unchanged
  file is never read twice. Measured on 12 MP-class photos: a repeat preview at 2,275 files
  goes from **15.8s to 4.7s (3.3x)**, and cold-cache overhead is +1.5%.
  - **It lives beside the catalog** (`catalog.cache.sqlite`), never inside it. Rows are keyed
    by absolute path, and §3.1 already establishes that identity is never a path - machine-
    local, disposable, high-churn data does not belong in the record of which drive holds the
    only copy of someone's photos. Delete the file and nothing is lost but time.
  - **It caches the perceptual hash as well as SHA-256, and that is the point.** Measured
    per file at 12 MP: perceptual (a full Pillow decode) ~69.8 ms against ~8.5 ms for SHA-256,
    and the size pre-filter already spares SHA-256 for ~94% of realistic-size files while the
    perceptual hash runs for every image. Caching SHA-256 alone would have recovered ~5% of
    the wait rather than nearly all of it.
  - **A hit requires size AND `st_mtime_ns` to match exactly** - integer nanoseconds, never a
    float comparison or a tolerance window. Any mismatch means hashing fresh.
  - **mtime is read for change detection only, never for dating.** The §1 rule is untouched:
    `dates.resolve_capture_datetime` does not consult the filesystem. Pinned by
    `test_mtime_never_reaches_dating`.
  - **It can only remove work, never change an answer.** A miss, a mismatch, a corrupt file or
    an unknown schema all mean full hashing; a cache is rebuilt rather than migrated. A row
    written when the pre-filter skipped SHA-256 is **not** served to a later run that needs one
    (`test_a_row_without_a_sha_is_not_served_to_a_run_that_needs_one`) - serving it would hand
    back a null hash and break exact dedup.
  - **One layer**, and **cleanup runs on every run** rather than being defined and never called
    (the PixSort mistake), bounded so it cannot become a stat storm.
  - **A caller that computes only SOME of a file's hashes must open the cache `writable=False`**
    (added 2026-08-03 for Analyze's tier 2a, which wants SHA-256 without the perceptual hash;
    **`service/drives._copy_hash` was found violating it on 2026-08-07** - it opened
    `HashCache.beside` and wrote `perceptual=None` for every file with no prior row, so
    attaching a drive silently switched off near-duplicate detection for its files. Measured:
    `near_dup=1` without an attach, `near_dup=0` after one, no message either way.
    **The rule was already enforced at the only door that checks it** - `compute_hashes` raises
    on the pairing - and `_copy_hash` called `cache.put` directly and went round it, which is
    the shape to look for: a guard on the shared path and a caller that does not use it).
    `perceptual` is nullable and carries **two meanings in one value** - *"not an image"* and
    *"not computed"* - and `get` has a `need_sha` parameter precisely because `sha256` has the
    same ambiguity, with **no `need_perceptual` counterpart**. A partially-hashed row would come
    back as a hit on the next organize preview and **silently delete near-duplicate detection**
    for those files. Reading is safe; only writing poisons, so read-only keeps every hit and
    removes the hazard. **Enforced by SQLite** (`mode=ro`), not by agreement: writes raise, the
    file is never created, and pruning - itself a write - does not run. Pinned by
    `test_hash_cache_readonly.py`, including that the connection itself refuses a write.
    **Closed 2026-08-07 at cache schema v3**, after the ambiguity produced a second live
    defect: `read_metadata` writes a row for a path nothing has hashed, and `_cmd_organize`
    closes that cache before `_run_pipeline` opens a fresh one, so the metadata-only rows
    became hits **within one command** - measured on the real library as 2,221 of 2,239
    image rows with no perceptual hash and an organize preview reporting `look-alikes: 0`
    as though it had looked. A guard on `put_metadata` cannot be written correctly, because
    `read_metadata` does not know whether anybody hashed the file. `perceptual_computed`
    records whether a pass ran, `get` takes `need_perceptual`, and `put` **requires** the
    flag rather than defaulting it - a default is the guess the column exists to end.
    The version bump rebuilds the cache, which is also the repair; a targeted delete was
    measured against it and saved 18 rows of 2,239.
  - **Verify is deliberately NOT cached.** It re-hashes the copy on the drive to detect
    bit-rot, and silent corruption changes content without changing size or mtime. Verify
    always reads the bytes. Reclaim likewise always re-hashes.
  - **Every other reader caches, and that list is now closed.** `organize` preview/run, Takeout
    `ingest`, and **migration re-derivation** (`migrate.rederive_rules`) all pass a `HashCache`.
    Re-derivation was the exception until 2026-07-31, by omission rather than decision: it cost a
    measured **12.2 s on every preview** of a 2,224-file drive, forever, because nothing was
    cached (audit F18; `PERFORMANCE.md` §1.1 carries the before/after). **Caching on a preview
    does not violate §5.** That rule's two guards assert on the drive tree and the catalog bytes;
    the sidecar is deliberately neither, and `service.organize_preview` has always written it on
    a preview path. If a future reader is added uncached, the reason belongs at the call site -
    an unexplained exception here is what F18 was.
  - **exiftool results ARE cached in the same sidecar** (path + size + ``mtime_ns`` + a
    fingerprint of ``REQUESTED_TAGS``). Profiled 2026-07-29: exiftool was **74%** of cold
    cloud-mount preview wall. A warm second pass must make **zero** exiftool subprocess calls
    (`test_warm_second_read_makes_zero_exiftool_calls`). Known limit: some tools edit tags
    without bumping mtime (IMatch-class); callers pass ``force=True`` /
    ``--refresh-metadata`` / the app checkbox to bypass. An expanded tag set changes the
    fingerprint so old rows miss rather than partially answer. See `DECISIONS.md` is not
    required here - the contract is this bullet + `hash_cache.py` module docs.
- **Concurrency for I/O-bound batches** via a worker pool (`scan.compute_hashes`, thread or
  process, benchmarked default = thread).
- **Metadata writes are batched** (`exif.write_metadata_batch`, `WRITE_BATCH_SIZE = 100`).
  One exiftool process per file cost **254.9 ms/file** measured, ~98% of it process startup -
  about 7 hours at 100k files on the feature the launch story leads with. Batched: **9.3
  ms/file**, staging copy included, so ~15.6 min at 100k.
  - **The batch bakes a staged copy, never the source.** That is what makes it safe to batch:
    a process that dies mid-batch can only leave a temp file half-written, and the user's
    original is untouched by construction.
  - **Silence is failure, never success.** exiftool prints one summary line per operation, in
    order; a short reply means the process stopped early, and every file past that point is
    reported **failed** rather than assumed baked. Pinned by
    `test_a_process_that_dies_mid_batch_is_detected` and
    `test_a_partial_batch_failure_reports_each_file_truthfully`.
  - **Written with `-m` but deliberately not `-q`:** quiet suppresses the per-file summary
    that is the only thing tying a batched result back to its file.
  - **`WRITE_BATCH_SIZE` is the peak scratch footprint** of an ingest (chunk x file size),
    which is why it is 100 rather than the reader's 200.
- **No accidental O(n²).** The perceptual dedup is a linear scan per file, documented in
  `dedup.py` and **priced rather than assumed**: the pair count is quadratic, the per-pair cost
  is not the problem. Any nested library iteration must carry a comment proving its bound.
  - **The remedy was vectorisation, not a tree, and that was settled by measurement**
    (2026-08-02). Hashes are packed to `uint64` once at registration and compared with one
    XOR + `np.bitwise_count` per incoming file: 147 s -> 0.5 s at 33,457 images. A BK-tree
    prunes only ~85% at threshold 5 and lost by 89x at 150,000, so `(v)` is closed refused,
    not deferred. See [`PERFORMANCE.md`](PERFORMANCE.md) §3.0 and `SHIPPED.md` `(v)`.
  - **`LINEAR_SCAN_ALARM` was removed with that change and this clause used to name it.** It
    warned at 10,000 images that matching had become the slow path; that is false of the packed
    scan, and there is no larger n to re-aim it at. Recorded rather than deleted because a
    contract that named a symbol for a day after the symbol went is the failure `(aan)` is
    filed to catch.
- **The custody strip counts, it does not list.** `Catalog.single_copy_count()` answers *how
  many files sit on exactly one drive* with a `COUNT(*)`; it used to build and sort every
  at-risk row via `single_copy_shas()` and take `len()` of it - **224 ms to 17.5 ms at 100k**,
  on a query that runs after every operation and on every load. That measurement is unchanged
  and still true of the method. The listing form still exists for the screen that shows the
  names, and `test_single_copy_count_matches_the_listing` holds the two answers together.
  - **Corrected 2026-08-05: this row used to say the method answers the "safe in N places"
    question. It did not.** That sentence was written against `len(drives-with-any-copy)` - a
    per-drive count under a per-file claim - and `single_copy_count` was computed on the same
    request and dropped. The strip is now per-file and risk-first: `Catalog.custody_floor()`
    returns the weakest file's copy count plus the no-copy and one-copy tallies in one grouped
    query, and the sentence is written against those. **`single_copy_count` alone could not have
    carried it either**: it reads `FROM file_copies`, so a `files` row with no copy at all is in
    neither bucket, which is the most exposed state a file can be in. Pinned by
    `tests/e2e/test_custody_strip.py`.

---

## 9. User-facing truth contract

Recorded because the soak test's defects landed **here rather than in the engine**: not one file
was mis-placed or lost, and what failed was the product describing itself incorrectly. That makes
the user-facing string a first-class defect surface with its own rules, not presentation polish.
The section **accumulated** rather than arriving whole: the soak pass opened it, and rules have
been added since by the feature work that needed them - path-component safety, the proposal size
floor, and the trip/event duration wording each brought their own. The per-defect list from that
first pass was not kept, and no rule here depends on it.

| Rule | Enforced by |
|---|---|
| **One source of outcome wording.** An `ActionStatus` is never rendered from its raw enum value; `models.status_label` is the only place an outcome is worded, so the CLI and the app cannot drift. | `models._STATUS_LABELS` + `models.status_label`. Pinned by `test_organizer.py` importing `_STATUS_LABELS`. |
| **No backend vocabulary reaches a user.** "Uploaded" is honest *inside* the code (`Destination.upload` covers rclone remotes) and false on screen: it names an event that did not occur and contradicts the promise that files never leave the machine. "Organized" is true of every backend. | The `_STATUS_LABELS` map; pinned by `test_a_finished_organize_says_organized_and_never_uploaded`. |
| **A user-supplied name that becomes a directory is repaired, never trusted and never rejected.** Illegal characters replaced, trailing dots/spaces trimmed (Windows drops them silently), **NFC-normalized** so one name typed on two platforms is one directory, capped at **255 bytes** (not characters) on a character boundary, and Windows reserved stems defused case-insensitively and with any extension. Every repair is reported. | `layout._sanitize_value`, `layout.event_folder`; `tests/test_filename_safety.py`; rationale in `docs/filename-safety-research.md`. |
| **Two events that would render one folder are disambiguated before anything is written, and the folder the preview names is the folder that is used.** Not a filesystem constraint - truestill created it by making event folders readable - so truestill detects it, at preview time, with a numeric suffix that keeps the user's name rather than a hash that destroys it. The second clause is not decoration: until `(abv)` the suffix was computed, reported and discarded, so the preview named a folder nothing was ever placed in. | `layout.disambiguate_event_folders` decides it; `layout._decided_folder` is the single seam through which all three render sites spell an event or trip folder. Pinned by `test_the_preview_note_describes_the_folder_that_is_actually_used` - which asserts the note and the path **together**, because `test_two_events_that_sanitize_to_one_folder_are_disambiguated` pins only what the helper computes and stayed green throughout the defect. |
| **The Trips & events size floor is a per-catalog setting, default 8.** Lower values expose more small suggestions; higher values hide them and must be an explicit user choice. `events.EventSettings` is the frozen typed accessor: it reads the existing key/value table once per proposal run, resolves an unset value through `DEFAULT_MIN_FILES`, and rejects malformed stored data with an actionable Settings message rather than coercing or leaking a `ValueError`. Its resolved value reaches the same `cluster_camera(min_files=...)` call that gates both trip and standalone-event proposals. | `events.EventSettings` / `EVENT_MIN_FILES_KEY`; `service.event_settings` / `set_event_settings` / `propose_events`; `trip_review.assemble_trip_review`; pinned by `test_event_min_files_setting_changes_proposals_and_unset_keeps_default` and `test_invalid_stored_event_min_files_is_actionable`. |
| **Trip/event proposals are largest-first, with one derived small-event disclosure.** "Small" is a threshold-adjacent standalone event below the first doubling of the configured floor (`count < 2 * min_files`), never a `TripProposal`; at the default 8 the exclusive limit is 16, leaving the OnePoll/Mixbook ~23-photo mean occasion (see `adaptive-day-folder-research.md`) visible above the collapsed band. One summary line names the hidden count, photo range and date span. There is no second collapsed tier. Split is the primary per-card correction; Merge remains available but visually secondary. | `trip_review.order_review_cards` / `is_small_event`; `service.collapsed_event_summary`; `static/app.js` `renderCards`; pinned by `test_review_order_and_small_set_are_derived_and_trips_never_collapse` and the app HTTP proposal fixtures. |
| **Trip duration says active days; every result retains its TRIP/EVENT kind.** A Sep 13-16 proposal with photos on Sep 13, 15 and 16 spans four calendar dates but contains **3 active days**; the card must say exactly that, never the ambiguous "3 days". Proposal, naming, move-preview and completion copy use trip/event as a pair, and each completion row carries and renders its typed kind rather than putting events under a `trips` key. | `service.ReviewCardPayload.active_days` / `AppliedReviewGroupPayload.kind`; `static/app.js` `evCardHtml` / `reviewResultCards`; pinned by `test_bridged_trip_reports_active_days_not_calendar_span`, `test_trip_duration_names_active_days_not_calendar_span`, and the apply-to-disk HTTP fixtures. |
| **Counts are grammatical.** `plural(n, word)` in `app.js` - "1 file", "2 files" - never "1 file(s)" and never a bare number glued to a noun. | `static/app.js` `plural`; pinned by `test_a_finished_copy_splits_photos_and_videos_without_form_letter_grammar`. |
| **A terminal job event is normalized once, at the seam.** `streamJob` converts every SSE terminal event into `{ok, status, error, code, summary}` before any handler sees it. Handlers read `summary.*`; a *failed* job carries `message` at the top level and an empty summary. Handing raw events to handlers is what rendered `NaN verified · NaN missing · NaN changed`. | `static/app.js` `streamJob` vs `jobs.py`'s `done`/`error` events. Pinned by the Backups regression tests. |
| **Errors are matched on an exception *name*, never on message text.** `FRIENDLY_ERRORS` keys off `type(exc).__name__` (surfaced as `code`), so rewording a message cannot silently disable its guidance. | `jobs.py` sets `code`; `app.js` `FRIENDLY_ERRORS`. |
| **Truestill never creates a folder on a filesystem that is not the one the run started on.** A cloud FUSE mount that drops under load leaves its mountpoint as an ordinary empty directory: writes into it *succeed*, and because every write path calls `mkdir(parents=True, exist_ok=True)` first, Truestill would **rebuild the whole library tree on the local disk** and fill it. Observed on a real migration, 2026-08-03. The signal is the destination root's **`st_dev`**, latched on the first sighting - not the mount table, which the same migration found lying (a dead mount lingers with no process behind it and lists nothing), and not the drive marker, which a destination that was never a registered drive does not have. `None` counts as a *changed* answer, not as no opinion. The baseline latches on first sight rather than at construction, so organizing into a folder Truestill is about to create still works. **This closes `--move` too**: the delete is strictly downstream of the write, so blocking the write means `_move_source` is never reached - and a mount that drops *after* a good upload makes `checksum` raise, which already keeps the source. | `destinations/base.DestinationDevice`; `LocalDestination._make_parent`, the single door all three of its creating paths use; `service/backup.py`'s copy loop, which does its own `mkdir`. Pinned by `test_vanished_mountpoint.py`, including that the backup guard runs *before* the create. |
| **A destination-relative path is checked for containment before any backend joins it onto a root, and the check is lexical.** `Path.__truediv__` **replaces** its left side when the right is absolute, and an f-string join carries `..` through untouched, so neither join defends its own root. The rule refuses three shapes - absolute, drive-qualified/anchored, and any `..` component - reading both POSIX and Windows flavours regardless of host, because a path built on Linux may be written to a drive read on Windows. **It deliberately does not use `resolve()` + `is_relative_to()`**, the usual remedy: `resolve()` follows symlinks, so a library with a year folder symlinked onto a second disk would resolve outside its own root and be falsely refused. The relative path is generated by truestill from a filesystem walk, never supplied by an untrusted caller, so the question is "could this string escape a join" and is answerable without touching the disk. | `destinations/base.check_contained`, called from `LocalDestination._full` - the one place that backend turns a relative path into a real one, so `exists`/`upload`/`set_timestamp`/`adopt`/`relocate`/`remove` are all covered by one guard. Pinned by `test_destination_containment.py`, including the symlinked-subfolder case that a `resolve()`-based check would break. |
| **A catalog another process holds is a refusal on both surfaces, discriminated by SQLite's error code and never by its message.** Two truestill processes wanting the catalog is ordinary, not a fault: SQLite serialises writers, so nothing is corrupted, and the loser must say so in a sentence instead of a traceback. `SQLITE_BUSY`/`SQLITE_LOCKED` alone qualify - a disk I/O error or a corrupt schema keeps its traceback, because "wait for the other operation to finish" sends a user to wait out a fault that never clears. The CLI exits **`5`**, its own code, so a script can tell *retry* from `2` (a usage error, never valid later) and from `1` (the run finished and the library has a problem). The wording is **one string in core** - the CLI and the app cannot word it differently. | `truestill_core/catalog_busy.py` (`is_catalog_busy`, `CATALOG_BUSY_MESSAGE`, `CATALOG_BUSY_CODE`); `cli.main`'s single seam; `jobs.py`'s terminal-event branch. Pinned by `test_catalog_busy_refusal.py` (two real processes) and `test_catalog_busy_job_refusal.py`, both with a cry-wolf half. |
| **A cancelled run says cancelled.** Never "nothing to organize here" - that is a false negative about the user's own library, and it shipped once for 6,000 photos. | `d.status === "cancelled"` handled on both the preview and run paths. |
| **Never-silent, restated for screens.** A skipped, refused, degraded or unverifiable outcome is *counted and named*, never folded into a success total or dropped. Existing precedents: the Tier A / Tier B date lines (§1), the HEIC perceptual-skip notice (§7), the skipped-extension buckets, and an unconfirmed metadata bake (§8). | Per-feature; each cites its own test. |
| **A source truestill could not read is named on both surfaces, and a preview that found one exits `1`.** *"Could not read this file"* and *"correctly did not hash this file"* must never share a representation - they did, as `FileHashes(None, None)`, and an unreadable file was therefore invisible in a preview, which attempts no copy and so never reaches the run's `FAILED`. `UnreadableReason` carries the fact and `models.unreadable_label` words it, so the CLI and the app cannot drift. **The preview exit code is part of the rule**: predicting with `0` a run that will exit `1` makes `organize && next_step` chain past a library truestill could not account for. **Files carry a count and folders do not** - for a folder the number inside is exactly what could not be read, so stating one would invent it. **The reported buckets are disjoint and exhaustive**: an unreadable file is counted in its own bucket and no other (it has no hash, so it used to read as new *and* be reported unreadable), and `new_unique + near_dup + exact_dup + unreadable == files` - so a category added later that forgets to be disjoint fails a test rather than double-counting. | `models.UnreadableReason` / `unreadable_label`; `scan._probe_readability` (**over every path, ahead of the hash-cache split** - `stat` succeeds on an unreadable file, so a stale-cache hit would otherwise skip it); `cli._print_unreadable`; `service/organize._unreadable_files`; `static/app.js` `renderUnreadable`; `models.partition_for_report` (**not** `Resolution.should_upload`, which drives the *plan* - the run still attempts an unreadable file, and preflight must still size it). Pinned by `test_unreadable_files_are_named.py`, `test_unreadable_files_report.py`, `test_unreadable_files_payload.py`, `test_report_buckets.py`, `test_preview_tally_is_disjoint.py`, `test_summary_tally_is_disjoint.py` and `tests/e2e/test_unreadable_sources_are_visible.py`. |
| **A duplicate count says *where the twin is*, on every surface that shows the count.** *"2,057 duplicates, skipped"* is true and answers nothing a person is asking: **already in your library** means the source copies are redundant and can go, **earlier in this batch** says nothing about the library at all. `duplicate_explain` had drawn that distinction per match since it was written - its own comment says it "is never collapsed into 'a duplicate'" - and the *counts* collapsed it anyway, which is the same counted-but-not-named gap that module was built to close. **The split is computed over every match, never over the displayed sample** (`DUPLICATE_SAMPLE_LIMIT` caps `shown` at 200; a split taken from it would read `200` on a large library and look entirely plausible). **A zero bucket prints no line** - never-silent is about what happened, not about what did not. **An unrecognised origin token is counted, not dropped**, so the parts always sum to the whole; `origin_phrase` may degrade such a token for display, a count may not. `DuplicateOrigin` names the vocabulary the engine has always written, so no compared or displayed token changed when it arrived. | `models.DuplicateOrigin`; `duplicate_explain.split_by_origin` / `describe_split` / `ORIGIN_HEADLINE`; `cli._print_duplicate_origins` (preview, EXECUTED tally, and Analyze's deep pass - which seeds no catalog rows, so an unqualified count there implies the opposite of the truth); `service/organize._duplicate_report`; `static/app.js` `dupOrigins`. Pinned by `test_duplicate_origin_split.py`, `test_duplicate_origin_is_named.py`, `test_duplicate_matches_are_named.py` and `tests/e2e/test_duplicate_matches_are_named.py`. |
| **A move says which files it did not take, and where they still are.** A file already in the library is skipped and its original left alone - right, and it was silent, so the source came back PARTIALLY emptied with no explanation for what is still in it. Worse, the empty-folder offer that follows names the folders the move DID empty and drops the occupied ones (`plan_cleanup`), so the app tidied around the leftovers without mentioning them. **Two sentences, because they answer different questions**: the preview says what will happen while the user can still change their mind, the result says what to do now and is the only place the leftovers are explained after the fact. **The folder is named** - "3 files remain" is weaker than "3 files remain in D/E", and the payload carries it. **`remain` is read from the disk**, one `stat` per skipped duplicate: "never deleted by this run" is not "still there". **FAILED is excluded** - it means the opposite thing, and folding the two would tell a user their photo may be lost when it is safely stored. **Copy mode says nothing**: the originals always stay, which is what the mode is called. | `left_behind.files_left_in_source` / `describe_left_behind` / `will_remain_line`; `cli._print_will_remain` / `_print_left_in_source`; `service/leftover_cleanup.left_in_source_from_results`; `static/app.js` `leftInSourceNote` / `willRemainNote`. Pinned by `test_left_behind.py`, `test_move_says_what_it_left.py`, `test_overlapping_organize_runs.py` and `tests/e2e/test_the_move_says_what_it_left.py`. |
| **A preview that finds almost everything already in the library says so, names WHICH library, and points at rearranging.** Someone re-pointing organize at their own folder is not asking to organize - they are asking how the library is ARRANGED, and re-copying cannot answer that. **Naming the library is the hard half**: `matched_path` is `files.source_path`, where content was first read from and deliberately never repointed, so it names the user's old folder; only `file_copies` keyed by `(sha256, drive_uuid)` knows where a copy sits, and the preview never asked it. Without that, the pointer offers to rearrange a drive holding none of these files - Stage 1's two-destination case exactly. **Two drives yield two names and no prefill**; picking the first would reintroduce the failure the query was added to prevent. **Reach stays three-valued** - a library that is "not plugged in" is not one that is gone, and one whose "location is not known yet" is neither. **A match with no copy row is counted as unplaced**, and with no library to name there is no button, because a button that lands nowhere is worse than the sentence alone. **THRESHOLD: `already_in_library / files >= 0.8` AND `already_in_library >= 20`.** 0.8 rather than a near-100% gate, which would stay silent exactly when the user is most active - they have usually added a few photos since; below 0.8 a real minority is new and organizing IS the right action. **20 is judgement, not measurement, and is the first number to tune** - it exists only so 3-of-3 does not read as "most of your library". **It SUBSUMES the move-preview line rather than stacking**: both open on the same count, and two of them reads as the app repeating itself; the "they stay where they are" tail survives the merge. The wording says "will not change how they are arranged", never "nothing will happen" (files WILL be organized), and never "instead" (the user may want both). | `Catalog.drives_holding` / `placed_shas` (no index added - `PRIMARY KEY (sha256, drive_uuid)` leads with sha256; asserted by EXPLAIN QUERY PLAN); `service/organize._matched_drives`; `static/app.js` `willRemainNote` / `pointsAtRearranging` / `rearrangeNote`; `layout.MIGRATE_CARD_NAME`. Pinned by `test_drives_holding.py`, `test_the_preview_names_the_drive.py`, `test_the_rearrange_card_name.py` and `tests/e2e/test_the_preview_points_at_rearranging.py`. |
| **Every long write watches the ground, and one builder decides whether it can.** Three loops copy for minutes at a time and only one goes through `execute`: `migrate.run_migration` (`LocalDestination.relocate` is a `copy2`, so a layout change **rewrites every byte of the library**) and the app's `backup_run` have their own. All three build their watcher through `run_health.watcher_for`, which takes a local root and a catalog path and returns `None` unless it has both - three copies of "is this worth watching" is how one of them ends up with a different answer. **What the two extra loops gain is the space half, and only that**, which this repo states rather than implies: both already call `DestinationDevice` per file (backup directly, migrate through `_make_parent`), and that **fails closed on the first bad reading**, so it is strictly stricter than a periodic three-strike watch. Migrate had **no free-space check at all**; backup had one on `disk_usage(target)` - the *remote's* free space on a mounted drive, while the disk that fills is this computer's. **Neither loop pays a new `stat`**: backup's rows already carry `size`, and `copies_for_migration` was already fetching its row and merely did not select `fc.size`. **The stop follows each surface's own established shape** rather than being forced into one: migrate returns it on `MigrationOutcome.stopped`, because a half-finished migration has *done* something (`migrated`, plus a journal that makes the rest replayable) and raising would discard that along with the reason; backup raises `ValueError`, because that loop already stops that way for an unverifiable copy and a second mechanism would be a second thing to keep in step. | `run_health.watcher_for`; `migrate._largest_move_ahead`, `Move.size`, `MigrationOutcome.stopped`; `service/backup._stop_if_ground_moved`, `_largest_copy_ahead`. Pinned by `test_long_writes_watch_the_ground.py` and `test_backup_watches_the_ground.py`. |
| **A long run watches the ground under it, and `execute` is the one place that arranges it.** `_refuse_impossible_destination` already records why: the CLI and the app both call `execute`, so a check either surface has to remember is one the other silently lacks. So `execute` builds the `RunHealth` itself and takes no watcher from its caller. **Two things must be true before it watches anything.** The destination must have a **local root** - `Destination.local_root()` returns `None` by default and stands down completely, the same bargain `preflight` makes, because a remote has no device id to lose and a guess on its behalf can only stop work that would have succeeded. And a **catalog** must be present to supply the local probe: the disk that fills is the one the cloud client caches to, never the destination, and substituting the destination would rebuild the very mistake this guard corrects. **The check sits after the skips and immediately before the write**, so a run whose remaining work is all duplicates is never stopped for want of space it will not use. **The stop is a `FAILED` result, not a new `ActionStatus`** - nothing type-checks exhaustiveness over that enum, so a new member is a set of call sites to be found by hand, and `FAILED` already means exactly *this file is not in your library, here is the message*. **The honest limit:** files after the stop are unattempted and absent from the results, the shape `cancel` has always had; the wording carries the remedy. **One `stat` pass, not two** - the refusal returns the sizes it gathered and the run's suffix-maximum is built from them (`PERFORMANCE.md` §3.1: a second pass over a FUSE library is the whole tier-0 budget again). | `Destination.local_root` / `LocalDestination.local_root`; `organizer._ground_watch`, `_watcher`, `_largest_still_ahead`, `_health_stop`; `run_health.RunHealth`. Pinned by `test_execute_watches_the_ground.py` and `test_run_health.py`. |
| **A watcher never treats an absence as its baseline.** `RunHealth._baseline_device` is `None` until a real device is seen. It used to be whatever the first reading gave, and a `None` there carried two meanings at once - *not yet established* and *the device id is None*. The visible consequence was not silence but the opposite: every later `None` compared **equal** and read healthy, and the moment the drive did answer its real id compared **unequal**, so the watcher struck three times and stopped a run whose drive was working. `DestinationDevice` already latched on first real sighting; the two differ in what they do afterwards, not in what counts as a baseline. Until one is latched the watcher stands down - the guard detects the ground *moving*, and a destination that never answered is reported by the write itself, per file, with the real `OSError`, which **names the file**. | `run_health.RunHealth._check_device`. Pinned by `test_a_drive_that_answers_late_does_not_get_a_healthy_run_stopped`. |
| **Results go to stdout, progress goes to stderr, and a completed tier is flushed before the next one starts.** `truestill analyze <path> > report.txt` must leave a clean, parseable report in the file while the terminal still shows the run - the split git and docker use. **Progress is not a result**: the counter, the phase name and the per-file pace all belong on stderr, and every number a reader would keep belongs on stdout. **TTY detection is required, not cosmetic**: `\r` rewrites one line on a terminal and is *stored* in a file, so the same code path left one padded 60-column counter per file - 127 KB of unreadable scrollback on a 32,628-file run. A non-terminal gets no carriage return, no padding, and a throttled cadence, because without `\r` to overwrite with, one line per file is the same flood in a new shape. **And the flush is what makes the ordering real**: Python block-buffers stdout when it is not a terminal, so a correctly-ordered report still arrives all at once at exit - measured, the redirect file stays empty for the whole of the slow tier. The throttle uses its own clock, never the report's elapsed-time `_CLOCK`, which tests drive with a fixture yielding an exact number of readings. | `cli._stderr_is_terminal`, `_end_of_tier`, `_progress_printer` (the one home for all five progress call sites), `_PROGRESS_CLOCK`, `_PROGRESS_INTERVAL_SECONDS`; `_cmd_analyze` / `_analyze_deep` flush points. Pinned by `test_analyze_streams_each_tier.py`. |
| **A hidden file or folder is skipped, and also counted and named.** The skip stays - `.Trash`, `.thumbnails`, `.git`, `.Spotlight-V100` and AppleDouble `._` files are exactly what must not be swept into a library, and a flag that pulled them all in would be a footgun aimed at the thing the product protects. **The defect was the silence.** A dot-file had no bucket at all, so `.picasa.ini` - real user metadata - vanished from a census that claims to say what is in a folder; worse, a hidden *directory* was pruned before the walk descended, so **a user with photos inside one saw no acknowledgement whatever**. **Files are counted, folders are named without a count**, the same asymmetry `unreadable_dirs` already carries and for the same reason: the walk never went in, so any number would be invented - and counting would mean descending `.git` on every scan. **Hidden files are counted by NAME, not extension**: `.DS_Store` has no suffix by `Path`'s rules, so an extension census reads `(no ext)` and teaches nothing. **Our own marker is its own group** - folded into the user's tally, every scan of an organized drive reports a hidden file they did not create and cannot act on; dropped, the number stops matching `ls -a`. Marker names are **imported from `drive`**, never retyped. | `organizer.HIDDEN_LABEL`, `TRUESTILL_MARKER_LABEL`, `_MARKER_NAMES`, `SourceScan.hidden` / `.markers` / `.hidden_dirs`, `skipped_extension_counts`; `cli._print_inventory_skipped`; `service/organize._skipped_summary` (an alias, see below); `static/app.js` `renderSkippedDetails`. Pinned by `test_hidden_files_are_accounted_for.py` and `tests/e2e/test_unreadable_sources_are_visible.py`. |
| **One vocabulary, one home: the skipped-census groups are produced once and rendered generically.** Three copies of this list existed - core's `_skipped_extension_counts`, a **verbatim duplicate** in the app service, and a hand-written group list in `app.js` - so adding a group would have left two surfaces silently short. That is the same drift `test_layout_scheme.ALL_RULES` and `check_product_name.SUBCOMMANDS` each produced once already, and it is now the third instance. The app service calls core; `renderSkippedDetails` renders **whatever groups the payload carries**. A group with nothing in it is **absent, not zero** - never-silent is about what happened, not about what did not. **Group keys are snake_case payload keys and are not the same strings as the human labels inside them** (`exiftool_backups` the key, `exiftool backup` the row); collapsing the two renamed a key under three call sites before the existing tests caught it. | `organizer.skipped_extension_counts` (the one producer), `service/organize._skipped_summary`, `static/app.js` `renderSkippedDetails`. Pinned by `test_exiftool_original_backups.py` and the browser test above. |
| **An empty result states the bar it applied, and a feature is named for what it accepts, not for what motivated it.** Two failures with one shape - a sentence that describes the code's *neighbourhood* instead of its rule. **Trips** said *"needs enough camera photos taken close together"*: that describes within-day clustering while wearing the name of a trip, and there are two rules stacked here, not one - a day qualifies on photos taken in one stretch (`cluster_camera`, `min_files`), and a TRIP is two or more such days **in a row** (`detect_trips`). A four-day trip is not "close together". And *"enough"* stated no number while that number is a field on the Settings screen of the same product, so somebody two photos short and somebody two hundred short read the same sentence. The floor now rides the **proposal** payload (not the shared review payload: propose is the only path that can render an empty screen) and the sentence names the Settings control by the label it really has. The two silent exclusions are named too - `camera_copies_for_events` filters `category = 'Camera' AND captured_at IS NOT NULL`, and either alone explains an empty screen on a library full of pictures. **Import** was headed *"Import from Google Photos"* while `ingest` reads any folder and any archive from any source; SHIPPED's (jj) scope correction says every user-facing string was audited, and this heading plus the Stats button pointing at it are the two it missed. The guard keys on the **shape** `Import from <Capital>`, so a different vendor fails the same way, and it deliberately spares the placeholder: Takeout may be named as an example, and `takeout.py` / `scan_takeout` / the sidecar parsing are Google's own format and keep the name. | `service/trips.ProposedReviewCardsPayload.min_files`; `static/app.js` `evEmptyState` / `EV_MIN_FILES_SETTING`; `templates/index.html` Import header; `test_user_facing_copy.SERVICE_SCOPED_IMPORT`. Pinned by `test_the_trips_screen_knows_its_threshold.py`, `test_user_facing_copy.py` and `tests/e2e/test_trips_and_import_on_the_pattern.py`. |
| **A summing block sums, on Import too.** The identity `files == kept + dup_collapsed + unreadable` is guaranteed by `ingest_preview` and stated on the field that carries it - and the screen showed kept, duplicates, dates-recovered and undated as one column under *"N files found"*. The last two are counted over `kept`, so they double-counted against it; `unreadable`, the bucket that makes the identity hold, **reached no surface at all**. Same defect as Organize's tally (`ab0a76a`), one screen over, found by putting the screen on the pattern rather than by a new report. A zero bucket is omitted rather than rendered as a zero row, and the sum holds without it; the two date facts are stated as properties of what will be imported; reclaimed space rides the duplicates label rather than floating as a fifth number. | `service/takeout.IngestPreviewSummary`; `static/app.js` `rcRenderSummary`. Pinned by `tests/e2e/test_trips_and_import_on_the_pattern.py`. |
| **The text-size preference ADJUSTS the reader's own default and never replaces it.** `tokens.css` declared no root font-size and said why - "the root is the user's" - and ended "which is why there is no font-size setting in the product". That held against an *absolute* setting only. The case it did not cover is wanting text **smaller** than the browser default, where zoom is a poor answer because it scales the layout with the type. So the steps are **percentages** (87.5% / 112.5%) and **medium declares no rule at all**: the absence of a declaration is the mechanism, and `100%` would look equivalent while making medium a value the app asserts rather than one it declines to. A reader whose own default is 24px gets 27px on Large, never 18. **Bounded on purpose** - a larger multiplier compounds on a default that is already raised, which is the state this setting is most likely to be used in; 27px is therefore the largest root the app can be asked for, past the 24px the type-scale tests already prove. **Nothing but type moves**: `--sidebar-width` (232/64px), `--icon-size` (16px), `--space-*` and the 720px media query stay px, so the setting moves exactly the lever a raised browser default already moves and nothing else. **Where the claim is settled matters**: a browser test cannot raise the root except by an inline style, which beats the stylesheet, so such a test reads back its own input and passes for an absolute implementation too - the percentage is asserted in the declaration instead. Values are normalised **server-side on both directions**; an unrecognised stored value resolves to medium rather than reaching the root as an invalid `font-size` the browser drops silently. | `service/organize.TEXT_SIZE_KEY` / `TEXT_SIZES` / `_normalize_text_size`; `/api/text-size/settings`; `static/tokens.css` `:root[data-text-size]`; `static/app.js` `applyTextSize` / `loadTextSize`. Pinned by `test_text_size_setting.py` (service) and `tests/e2e/test_text_size_setting.py`. |
| **Settings is a shelf, not a task screen, and its card order is load-bearing.** Recorded because it was asked and the answer is a deliberate no: the lifecycle pattern (one form, one run, one result) describes a surface with **one job**, and Settings holds five cards with five unrelated ones. Correcting an earlier description of my own - it does have run blocks and result states, **two of each**: Rearrange and the date bake are complete preview -> typed confirm -> run -> undo flows that already use the shared run block. Nothing was bent to fit; the pattern's *components* reach this screen, its *lifecycle* does not, and forcing one would mean inventing a result for "Settings", which is not a thing that runs. **Rearrange sits directly under Folder layout**: that card decides how new files are laid out and this one brings the existing library to that layout, so the two are one thought - and it is the answer to the most-asked question in this space, which is not something to file third under a trip-suggestion number field. **The order is pinned by a test because the copy encodes it**: `EVERYDAY_DAY_THRESHOLD_MIGRATE_WARNING` says "below", a claim about DOM order that nothing else connects to the DOM. | `templates/index.html` `#screen-settings` card order; `layout.EVERYDAY_DAY_THRESHOLD_MIGRATE_WARNING`. Pinned by `tests/e2e/test_settings_is_a_shelf_not_a_task_screen.py`. |
| **A dropped CSS declaration is invisible to every non-browser gate.** A stray `*/` ended a comment in `tokens.css` two lines early; CSS error recovery swallowed the declaration below it and `--text-xs` stopped existing. `ruff`, `mypy`, `ruff format` and 1802 pytest cases all stayed green - none of them reads a stylesheet - and the existing token guard passed too, because an **empty** value does not end in `px`. What noticed was two unrelated browser tests, by three pixels of top-bar height. A missing token is not a smaller token: it is no rule, so the element inherits, which is how a 12px label silently became body size. Every step of the scale is now asserted to RESOLVE, not merely to be non-px. | `static/tokens.css`; pinned by `test_every_step_of_the_scale_actually_resolves` in `tests/e2e/test_type_scale_follows_the_browser_default.py`. |
| **The layout is keyed to CSS pixels, and the column is capped by what sits in it.** Measured on the maintainer's own three monitors via mutter's `GetCurrentState`, because a panel's native resolution is not what CSS sees: the laptop is 1920 CSS px at dPR 1.00, the **BenQ 4K runs at scale 1.25 so it is 3072 CSS px**, not 3840, and the Dell QHD is 2560 at dPR 1.00. With the content column capped at 1080 that left 144 / 464 / **720px of dead page each side** - the last two read as a broken layout. **The ceiling is 1600px and is defended by content, not by a round number**: the widest real element is a Find row carrying a full event-folder path, measured at ~1030px natural width, which the old cap only just cleared and a longer event name would not. **The residual gutter at 3072 is the answer, not a shortfall** - filling that width with one column puts a 2400px-wide text input on screen; the column is capped, the page is not, and past that the remedy is the third column (the panel), which now scales `clamp(320px, 20vw, 440px)`. Its **floor stays 320** because the 1336px panel threshold was derived from it. **`devicePixelRatio` is never read**: CSS px are dPR-independent by definition, so a window dragged between monitors changes the viewport (which fires the `resize` the catalog-path fit already listens to) and nothing else. The widely-copied `body.zoom = 1 / devicePixelRatio` remedy is refused - it would undo the user's own scaling, the same failure the text-size setting was built to avoid. | `static/app.css` `.screen` max-width, `--panel-width`; no JS. Pinned by `tests/e2e/test_large_viewports.py`. |
| **Fluid type stops at a fixed frame.** The type scale is `clamp()` with **rem floor and ceiling** - a px clamp is fluid and dead to the root, which would silently undo both a raised browser default and the text-size setting. Only the middle term carries `vw`. **And `vw` is the wrong question inside the rail**: it asks how wide the window is, while the rail is 232px (or 64px) at every window size, so letting rail text grow with the viewport made the custody path truncate *more* on the bigger monitor. The rail redeclares the tokens at their floor - still rem, so the root still reaches it; only the `vw` term is dropped. Container queries are deliberately **not** used: one declaration at the container that owns the exception already says "the rail is a fixed frame". **`.metrics` stays two-up**, tried and reverted in the same commit: `auto-fit` always leaves a width band where three of four fit and the fourth wraps alone, and at any minimum that band lands inside the 1080-1700px range this app is used at - including a rotated QHD at 1440. | `static/tokens.css` `--text-*`; `static/app.css` `.sidebar` token floor, `.metrics`. Pinned by `tests/e2e/test_large_viewports.py` and `test_metrics_go_two_up_rather_than_wrapping_three_and_one`. |
| **One byte count, one formatter, one unit.** The same 1,997 photos read "5.2 GB" in the panel and "4.9 GB" on Stats. Not a units disagreement - **`library_status` summed `total_size` across every drive**, so backing a library up made it report as bigger, and the gap was exactly the backup drive. "Your library" is DISTINCT CONTENT; a second copy is custody, which is what `places` and `single_copy` beside it are for. The formatter existed three times (once in JS, twice inline as `f"{n / 1024**3:.1f} GB"`) and is now `truestill_core.units.format_bytes`, mirrored in JS the way `plural` is, with a parity test over one table. **Decimal**, because the number gets compared against a drive's advertised capacity and against GNOME Files / macOS Finder, all decimal; 1024-based labelled "GB" is ~7% low at that scale. The FAT32 "4 GB" limit keeps its own literal - it is a domain constant, not a formatted size. | `units.format_bytes`; `Catalog.total_content_bytes`; `service/drives.library_status`; `static/app.js` `fmtBytes`. Pinned by `test_units.py`, `test_library_bytes_count_content_not_copies.py`, `tests/e2e/test_one_byte_formatter.py`. |
| **An engineering annotation is never a user-facing string.** Stats rendered *"Query cost: O(n) aggregate SQL over catalog tables; grouped rollups only.."* where a description belongs - double full stop included, because the payload value already ended in one. The payload key is gone rather than merely unrendered: a key nothing may display invites the next reader to display it. Checked as a **class** - a guard scans every service payload literal for cost/plan prose, so this cannot recur quietly while leaving docstrings and comments free to say it. | `service/stats.py`; pinned by `test_no_service_payload_ships_engineering_prose`. |
| **A tab older than the server says so.** `_static_fingerprint` warned only that the SERVER was older than the files on disk. The app is one page - screen switches never reload it - so a tab open across an upgrade keeps running old JS and a new control **silently fails to exist**: no error, nothing to click, no way to learn to reload. That is what "the text-size setting does nothing" looks like from the user's side. The server stamps its fingerprint on every response and the page compares it with the one baked into its HTML, so the check **costs no request**: no polling, no timer, no endpoint. Said once, because the header rides every response. | `server.StampStaticFingerprint`; `static/app.js` `noticeIfPageIsStale`. Pinned by `tests/e2e/test_the_page_knows_it_is_out_of_date.py`. |
| **One fact is stated once per moment.** The rail's custody line and the resting panel both said "1,836 files in only one place", simultaneously, in different words. **The rail keeps it**: it is ambient, on every screen, while the panel is not rendered below 1336px - so the panel is the copy that can vanish without the fact going with it. Same rule on Backups: with a single drive "Your library" and that drive are necessarily the same set, so the total appears **only once a second drive exists** and can disagree with it. | `static/app.js` `renderRestingPanel` / `loadDrives`. Pinned by `test_screen_pass_2026_08.py` and `test_palette_and_resting_panel.py`. |
| **Known values prefill; Browse is for overriding.** A path the user has already given - or that the app already recorded - is never asked for a second time. | `service` path hints (`LIBRARY_PATH_HINT` / `BACKUP_PATH_HINT`), `app.js` `prefill`. Pinned by `test_prefill_never_proposes_copying_the_library_onto_itself`. |

**Why the browser lane owns this and pytest cannot.** Every rule above is a property of
rendered text. `tests/e2e/` therefore asserts on **the words a user reads**, never on element
ids - an id-based assertion would have passed for every one of the defects that produced
these rules, because each was a wrong or stale *string* in an element that existed and
rendered. See §6.
