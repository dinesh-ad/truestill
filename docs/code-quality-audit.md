# truestill - Code Quality Audit (SonarQube-class)

**Date:** 2026-07-30 | **Scope:** all three packages, `static/`, `scripts/`, `tests/`, hooks, CI
**Method:** measured. Cognitive complexity scored per the SonarSource specification (nesting-weighted,
boolean-sequence collapsed) by an AST scorer run over all 633 functions; duplication by token-shingle
matching; dead code by a definition-vs-reference sweep across `packages`, `scripts`, `tests`, `docs`,
`README.md`, `CHANGELOG.md`; typing gap by an actual `mypy --strict` run.
**Nothing in the repository was modified** - `git status` shows this report as the only new file.
`make check` was run at the start and end of the audit and is green both times: **697 passed, exit 0**.
(The opening run, taken while four analysis processes were running concurrently, reported 696 passed.
Collection was afterwards confirmed at 697 across four consecutive runs, and confirmed identical with
and without this report file present, so the report adds no test. The one-run difference is
unexplained and recorded here rather than smoothed over.)

**What this document is:** a report. Every finding is a proposal awaiting a ruling, not a queued
change. Section 6 is the recommended order once rulings exist.

---

## 0. Reading this report

The repo's own docs are treated as the law being audited against, alongside 2026 industry practice.
Where the code and a doc disagree, the finding is filed **against whichever one is wrong**, and that is
stated explicitly. Where something looks like a defect to a naive tool but is a recorded decision, it is
in **Section 4 (Non-findings)** and should be protected from future "fixers".

Severities:

| | Meaning |
|---|---|
| **CRITICAL** | Correctness or safety risk, or a violation of a binding invariant. |
| **HIGH** | Real maintainability debt or a false contract. Fix before launch. |
| **MEDIUM** | Fix post-launch or opportunistically. |
| **LOW** | Cosmetic. Batch or ignore. |

---

## 1. Findings table

| # | Severity | Location | Metric / evidence | Dimension |
|---|---|---|---|---|
| F0 | **CRITICAL** | `app.js:1208-1216` | undo outcome erased by the next line; the recorded bug's un-fixed twin | H frontend |
| F1 | **CRITICAL** | `verify.py:88` | unguarded `future.result()`; `sha256_file` raises `OSError` | F errors |
| F2 | **HIGH** | `scan.py:144` | same shape; aborts the whole hashing pass | F errors |
| F3 | **HIGH** | `destinations/base.py:91` vs `local.py:81` | ABC declares `DestinationError`, impl raises `OSError` | C structure |
| F4 | **HIGH** | `pyproject.toml:143-154` | `strict` claimed mandatory, not set; 19 errors measured | F typing |
| F5 | **HIGH** | `dedup.py:14` | "0.7s for 10,000 images"; measured 13.5s | E complexity |
| F6 | **HIGH** | `service.py:1368`, `:1441` | only 2 non-test reaches into `Catalog._conn` in the repo | C structure |
| F7 | **HIGH** | `server.py:22-33`, `:458` | contradicts §2 "service.py is the sole bridge" | C layering |
| F8 | **HIGH** | `service.py:2209` -> `:2337-2362` | `list[Any]` through the copy-verify loop | F typing |
| F9 | **HIGH** | `exif.py:207` | cognitive complexity **39** (worst in repo) | A complexity |
| F10 | **HIGH** | `service.py` (whole file) | 2,731 lines, 11 product surfaces, 23 core imports | B unit size |
| F11 | **HIGH** | `test_server.py:560` | guard EXPLAINs a retyped literal, not the real query | I tests |
| F12 | **HIGH** | `test_user_facing_copy.py:41` | prose guard skips itself if its input moves | I tests |
| F13 | **HIGH** | `test_reclaim.py:51` | §1's reclaim-journal clause has no enforcing test | I tests |
| F14 | **MEDIUM** | `migrate.py:596` | cognitive complexity **27**; 4x duplicated tick block | A/B |
| F15 | **MEDIUM** | `layout.py:356-358`, `:396-398` | repair note names the repaired string, not the offender | G naming |
| F16 | **MEDIUM** | `catalog.py:420-1425` | 1,006-line class, 71 methods, 9 concerns, 2 taxonomies | B/C |
| F17 | **MEDIUM** | `server.py:362`, `jobs.py:108` | two dicts that only ever grow | C structure |
| F18 | **MEDIUM** | `cli.py:1184`, `service.py:1523`, `migrate.py:205` | 3 uncached `read_metadata` with no recorded reason | E performance |
| F19 | **MEDIUM** | `layout.py` (whole file) | 949 lines, 7 concerns on one seam | B unit size |
| F20 | **MEDIUM** | `service.py:2518`, `jobs.py:126` | bare `assert` as a runtime gate on external state | F errors |
| F21 | **HIGH** | `fs_browse.py:104`, `:150`, `organize.py:257` | uncaught `PermissionError` -> HTTP 500 on three routes (regraded; see entry) | F errors |
| F22 | **MEDIUM** | `app.js` (39 sites) | four event-wiring disciplines; the majority one is the defect class | H frontend |
| F38 | **HIGH** | `app.js` (13 sites) | job-run skeleton copied 13x, ~250 lines | H frontend |
| F39 | **HIGH** | `app.js:1654`, `:1669` | a Split or Merge silently discards every typed trip name | H/§9 |
| F40 | **MEDIUM** | `app.css:347`, `:530`, `:598` | 2 CSS variables used and never declared; 2 components lose their background | H frontend |
| F41 | **MEDIUM** | `app.js:246-465` (6 sites) | `plural`, named by §9, bypassed inline | H/§9 |
| F42 | **MEDIUM** | `app.js:4` | `esc` does not escape `'`; single-quoted attributes already exist | H frontend |
| F43 | **MEDIUM** | `app.js:1400`, `index.html:120` | primary button that can never be enabled, wired to a no-op | D dead code |
| F44 | **MEDIUM** | `app.js:1365` vs `:1993` | organize never clears its typed confirm; migrate does | H frontend |
| F45 | **MEDIUM** | `app.js:1170`, `:1200` | organize-undo progress bar renders below the viewport | H frontend |
| F46 | **MEDIUM** | `app.js:1781` | move list silently truncated at 200 with no "and N more" | H/§9 |
| F47 | **LOW** | `app.css:499-523`, `tokens.css` | 25-line superseded `.progress` block; 6 unused custom properties | D dead code |
| F23 | **MEDIUM** | 7 sites | `type: ignore` with a code but no reason comment | F typing |
| F24 | **MEDIUM** | `events.py:1-21`, `:237` | the stage PERFORMANCE.md §4 protects says nothing about itself | E complexity |
| F25 | **MEDIUM** | `cleanup.py:17-18` | "Nothing scales with library size" is false of `emptied_directories` | E complexity |
| F26 | **MEDIUM** | `PERFORMANCE.md:21-37` | 0 of 7 new stages got the mandated measured row | E complexity |
| F27 | **MEDIUM** | `DECISIONS.md:136-138`, `BACKLOG.md:951-952` | 3 doc claims falsified by shipped code | docs |
| F28 | **MEDIUM** | tests (7 clusters) | no conftest in 2 of 3 packages; fixture copied up to 7x | I tests |
| F29 | **MEDIUM** | `test_migrate.py` | 1,279 lines; 2 clean cuts already marked by banners | I tests |
| F30 | **MEDIUM** | `service.py` (5 sites) | plan-and-dedup pipeline written out 5 times | C duplication |
| F31 | **LOW** | 4 symbols | exported, never referenced anywhere in the repo | D dead code |
| F32 | **LOW** | `security.py:51` | untyped `__call__` on the security middleware | F typing |
| F33 | **LOW** | `trip_review.py:119`, `:123` | `type: ignore` where the sibling property uses `assert` | G naming |
| F34 | **LOW** | `cli.py:1077-1084` / `:1185-1192` | the only duplicated block in 6,863 logical lines of source | C duplication |
| F35 | **LOW** | `app.css:402` | 1 dead selector of 86 | D dead code |
| F36 | **LOW** | `trips.py:150-151` | correct bound, but the sentence proving it denies the nesting | E complexity |
| F37 | **LOW** | `pyproject.toml:17` | `httpx` deprecated by Starlette's TestClient; warning in every run | deps |

---

## 2. Detailed findings

### F0 - CRITICAL - The recorded `innerHTML` defect exists un-fixed in the organize-undo path

`packages/truestill-app/src/truestill_app/static/app.js:1208-1216`

```
    if (!d.ok) {
      $("org-undo-stage").innerHTML = jobErrorCard(d);
    } else {
      $("org-undo-stage").innerHTML = card(
        `<div class="headline">Restored ${plural(d.summary.restored, "file")}.</div>
         ${organizeUndoSkipped(d.summary.skipped)}`
      );
      loadCustody();
    }
    await refreshOrganizeUndoAffordance();
```

`#org-undo-stage` exists **only** as a child of the card `refreshOrganizeUndoAffordance` writes -
`organizeUndoCard` emits `<div id="org-undo-stage"></div>` at `app.js:1083`. And
`refreshOrganizeUndoAffordance` (`:1087-1096`) reassigns the parent's `innerHTML` in **both** branches:

```
1090    if (!state.ok || !state.armed) { panel.innerHTML = ""; return; }
1094    panel.innerHTML = organizeUndoCard(state);
```

So line 1216 destroys the outcome card written two lines earlier. After a *successful* undo the
journal is consumed, so `armed` is false, `panel.innerHTML = ""` runs, and the user sees **nothing**:
no "Restored 6,000 files.", no skipped list. In the `!d.ok` branch, no error either.

**This is the exact bug `ENGINEERING_STANDARD.md` §2 records as its worked example**, and the
migrate-undo path is the copy that received the fix - with a comment naming the hazard
(`app.js:667-671`):

> `await refreshUndoAffordance(path, panel);`
> `// Prepend the outcome without re-parsing the armed card: assigning panel.innerHTML`
> `// would wipe the Preview onclick refreshUndoAffordance just attached ...`
> `panel.insertAdjacentHTML("afterbegin", summaryHtml);`

The organize-undo twin never got it. It also breaks §9's never-silent rule outright: `undo-organize`
is the reversal for the one feature where §1's safety-asymmetry note says "what is at risk ... is the
**arrangement** of a library whose owner, by definition of the feature, has no backup", and
"`undo-organize` is that gate". The gate runs and then tells the user nothing.

**Not covered by the browser lane.** `tests/e2e/test_ui_regressions.py:233-236` stops at the typed
confirm and never clicks apply - precisely the "UI source assertions are not coverage of a flow" gap
§2 warns about, on the same feature §2's example came from.

**Fix sketch.** Mirror the migrate-undo path exactly: build `summaryHtml` into a local, `await
refreshOrganizeUndoAffordance()`, then `panel.insertAdjacentHTML("afterbegin", summaryHtml)`.
**Cost: ~20 minutes, plus an e2e case that clicks apply and asserts the outcome text (~1h).** The e2e
case is the more important half - the fix without it is one refactor away from regressing again.

### F1 - CRITICAL - `verify_copies` crashes on exactly the failure it exists to detect

`packages/truestill-core/src/truestill_core/verify.py:88`

```
copy = futures[future]
actual = future.result()          # <- re-raises the worker's exception
```

`_hash_path` (`verify.py:47-48`) calls `hashing.sha256_file` (`hashing.py:81-87`), which opens the file
with no exception handling. A present-but-unreadable copy - an unrecoverable read error on a failing
disk, `EIO` on a FUSE/pCloud mount, a mount dropped mid-run, a permission change - passes the
`path.is_file()` check at `verify.py:69` and then raises `OSError` inside the worker. `future.result()`
re-raises it, the `with executor_cls(...)` block unwinds, and `verify_copies` **never returns**. Every
result already computed is discarded.

Consequences traced end to end:

- CLI: `cli.py:518` has no handler. The user gets a traceback. `ENGINEERING_STANDARD.md` §4 Errors:
  "User-facing CLI errors are actionable sentences, not tracebacks."
- App: `service.py:1215` propagates to `jobs.py:174`, which turns it into a terminal SSE error with
  `code="OSError"`. `app.js:105-109` `FRIENDLY_ERRORS` has no entry for it, so the whole verify report
  is replaced by a generic banner. No count, no filename.

**Why this is CRITICAL rather than HIGH.** `verify` exists to catch silent corruption on a drive
(`IMPLEMENTATION_STANDARDS.md` §8: "it re-hashes the copy on the drive to detect bit-rot"). An
unrecoverable read error is one of the two ways a failing disk actually presents. `CopyStatus`
(`verify.py:25-28`) has `VERIFIED`, `MISSING`, `MISMATCH` and no member for "present but unreadable",
so the outcome cannot even be expressed. This breaks two binding rules at once: §4's partial-failure
policy ("one bad file never aborts a batch - it is logged, counted, and reported at the end") and §9's
never-silent rule ("a skipped, refused, degraded or unverifiable outcome is counted and named").

**This is an isolated lapse, not a pattern - which is what makes it credible.** Every neighbouring
site defends correctly: `hashing.perceptual_hash:106` catches `OSError`; `scan._sizes:74-77` and
`scan._mtime_ns:67-68` catch it; `reclaim._verify:109-112` wraps the *same* `sha256_file` call in
`try/except OSError`; `reclaim._safe_size`, `_source_present`, `_is_the_copy_itself` all catch it;
`organizer.execute:1230` catches `(OSError, DestinationError)` per file and records
`ActionStatus.FAILED`; `undo.run_undo:208-210` catches it per file and records `UndoSkip.FAILED`. Two
`future.result()` call sites are the only unguarded ones in the codebase.

**Fix sketch.** Add `CopyStatus.UNREADABLE`, wrap the worker body (or the `future.result()`) in
`except OSError as exc`, record the copy with the error text, and surface the count and names in both
report paths. Note `BrokenProcessPool` for the `pool="process"` path is not an `OSError`.
**Cost: ~2h including the CLI/app report lines and a regression test that injects a read error.**

### F2 - HIGH - `compute_hashes` has the same unguarded shape

`packages/truestill-core/src/truestill_core/scan.py:144`

Identical: `path_str, sha, perceptual = future.result()`. One unreadable file in a source tree aborts
the entire hashing pass, so an organize preview or run over a tree containing a single locked or
unreadable file dies before it reports anything. Graded HIGH rather than CRITICAL because it fails
before any write, so no data is at risk - but `BACKLOG.md` (ss) records this pipeline being run
routinely over a pCloud FUSE mount, which is precisely where `EIO` occurs.

Note the asymmetry inside one module: `scan.py` defends its two `stat` paths (`:67`, `:76`) and leaves
its read path open. **Fix: same shape as F1, ~1h.**

### F3 - HIGH - The `Destination` interface declares a failure contract no backend honours

`packages/truestill-core/src/truestill_core/destinations/base.py:91-94` documents `checksum` as raising
`DestinationError`, and every other optional method on the ABC raises `DestinationError` by default.
The shipped `LocalDestination` does not:

- `checksum` (`local.py:80-81`) - `sha256_file` raises `OSError`
- `relocate` (`local.py:68-75`) - `shutil.copy2` raises `OSError`
- `remove` (`local.py:77-78`), `set_timestamp` (`:39-41`), `list` (`:83-92`), `exists` (`:31-32`) - same

The consequence is a guard that does not guard. `migrate._matches` (`migrate.py:474-483`) exists to
answer "does this copy exist and verify", and catches **only** `DestinationError`:

```
try:
    return destination.checksum(relative) == expected_sha
except DestinationError:
    return False
```

Against the only backend that implements `checksum`, the exception that actually occurs is `OSError`,
which passes straight through. `_apply_move` (`migrate.py:486`) is called from `run_migration:574` with
no per-move handler, so a read error mid-migration aborts the run with a traceback. The journal makes
that *safe* (the module docstring's crash-safety claim holds, and it resumes), but not *honest*.

`organizer.execute:1230` catching `(OSError, DestinationError)` is the tell: the organizer already
works around the gap. The interface documentation is the thing that is wrong.

**Fix sketch.** Either translate in the backend (wrap `LocalDestination`'s bodies so the ABC's contract
becomes true) or amend `base.py`'s docstrings to state that `OSError` is part of the contract and fix
`_matches` plus every other `except DestinationError` to catch both. The first is better: it keeps
`migrate.py` and `organizer.py` free of backend vocabulary, which is `base.py`'s stated purpose.
**Cost: ~3h either way, including tests that inject a read failure per method.**

### F4 - HIGH - `mypy strict` is documented as mandatory and is not configured

`ENGINEERING_STANDARD.md` §4 Typing: "mypy `strict` is mandatory." `pyproject.toml:143-154` sets four
flags (`warn_return_any`, `warn_unused_configs`, `disallow_untyped_defs`, `disallow_incomplete_defs`)
and **not** `strict = true`. `.pre-commit-config.yaml:21` states in a comment "Match the repo's strict
config", which is not accurate.

Measured gap - `mypy --strict` over the same four trees the gate covers:

```
Found 19 errors in 3 files (checked 50 source files)
```

Twelve of the nineteen are `Unused "type: ignore" comment` - suppressions that no longer suppress
anything, invisible today because `warn_unused_ignores` is part of `strict` and is not enabled. One of
them is in shipped app code: `server.py:585`. The rest are `scripts/profile_organize_preview.py`. The
two genuine typing errors are `service.py:722` and `:862` (`typeddict-item` on `NotRequired` keys
spread through `**`), and four are `attr-defined` re-export errors in the profiling script.

This matters more than the error count suggests, because `strict` is what would have caught F23's stale
ignores and would enforce `disallow_any_generics` and `strict_equality` going forward - and because
§7's own standard for this repo is that "the claim and the check agree" (stated there about
`python_version`, and it applies here identically).

**Fix sketch.** Set `strict = true`; fix the two `service.py` errors; delete the 12 stale ignores; add
`__all__` or explicit re-exports for the script's three `scan` imports. Or, if a lower bar is the real
intent, amend `ENGINEERING_STANDARD.md` to name the flags that are actually mandatory. **Cost: ~2h to
close the gap, or 10 minutes to correct the doc. This is a ruling, not an engineering choice.**

### F5 - HIGH - The one justification the complexity rule exists to produce cites the wrong number

`packages/truestill-core/src/truestill_core/dedup.py:14-15`

> "Perceptual lookup is a linear scan ... which makes the matching pass O(n^2) in the number of images.
> **Measured, that is 0.7s for 10,000 images** and still the cheapest thing in the pipeline"

`PERFORMANCE.md:88-94` measures **0.72 s at 2,275** and **13.5 s at 10,000**. The figure was taken from
the wrong row, understating the cost by roughly 19x - and it does so at exactly
`dedup.LINEAR_SCAN_ALARM = 10_000` (`dedup.py:34`), the threshold whose entire purpose
(`PERFORMANCE.md:100-104`) is to reach "the person with 10,000 photos" at the moment they cross it.
That reader is told the thing that just fired costs 0.7 seconds.

This is the single module discharging §6's rule that "anything worse than O(n log n) must say so and
justify the trade", and its justifying measurement contradicts the document it summarises. `BACKLOG.md`
(v) makes the alarm line the unblocking trigger for building the BK-tree, so the wrong number sits
directly in front of the decision it is meant to inform.

**Fix: one line.** "0.72 s at 2,275 images, 13.5 s at 10,000 (`PERFORMANCE.md` §3)". Also drop or
qualify "still the cheapest thing in the pipeline", which is false at 10k. **Cost: 10 minutes.**

### F6 - HIGH - `service.py` is the only non-test code in the repo that reaches into `Catalog._conn`

`packages/truestill-app/src/truestill_app/service.py:1368` and `:1441` execute raw SQL through
`catalog._conn`, a private attribute (`catalog.py:427`). A repo-wide grep for `._conn` outside
`truestill-core/src` returns 11 hits in tests and exactly these two in production code.

`Catalog` already exposes a `stats_*` family built for this screen - `stats_summary` (`catalog.py:866`),
`stats_by_year` (`:903`), `stats_near_duplicate_flagged_count` (`:920`), `stats_undated_samples`
(`:940`) - and `library_stats` calls four of them at `service.py:1435-1439` before hand-rolling two more
against the v12 schema from the app package.

Three consequences: two statements against the catalog schema live outside the package that owns it and
outside `test_catalog.py`'s migration coverage, so a future `_MIGRATIONS` entry can break the app
silently; `_format_counts` (`service.py:1342`) generates a 62-arm `CASE` chain from `MEDIA_EXTENSIONS`
in the app layer; and mypy sees `sqlite3.Row` and checks no column name. (The generated SQL itself was
checked and is correct - this is a layering finding, not a bug report.)

**Fix:** move both queries into `Catalog` as `stats_format_counts()` and `stats_zero_drive_samples()`,
beside their four siblings, with their coverage. **Cost: ~1.5h.**

### F7 - HIGH - §2's "service.py is the sole bridge" is false as written

`IMPLEMENTATION_STANDARDS.md` §2 states the app "Depends on `truestill-core` **only**, never on
`truestill-cli`; `service.py` is the sole bridge." The first clause holds. The second does not:
`server.py:22-33` imports ten symbols directly from core (`Catalog`, `DEFAULT_CATALOG_PATH`,
`EventDecision`, `commit_catalog`, `InvalidEventSettingsError`, `split_candidate`,
`InvalidEverydayDaySettingsError`, `ReviewCard`, `TripDecision`, `TripMergeError`, `commit_trips`,
`merge_review_cards`, `order_review_cards`, `split_trip`), and `server.py:458` opens its own catalog
transaction.

The violation is concentrated in three handlers - `events_merge` (`:401-419`), `events_split`
(`:421-443`) and `events_apply` (`:445-513`, 69 lines) - which carry real domain orchestration in the
transport layer. Every other route in the file is a three-to-five-line shim over `service.*`, so this is
the exception, not the house style, and the seam is already half-built
(`service.review_cards_payload`, `service.proposed_review_cards_payload`).

**This needs a ruling, not an auditor's preference.** Either the three handler bodies move behind
`service` functions (~3h), or §2 is amended to something true - for example "service.py owns all
catalog writes and long-running work; server.py may use core value objects" (15 minutes). §5's
"flag before deviating" says the discrepancy should be surfaced rather than left standing.

### F8 - HIGH - `Any` runs through the backup copy-verify loop

`service.py:2209` declares `_files_missing_on_target(...) -> list[Any]` because `backup_preview`
(`:2272-2276`) unions two row shapes. That `Any` reaches `backup_run`'s copy loop, where every field
access is unchecked:

```
2340:  rel = str(row["relative"])
2344:  want = row["copy_sha256"] or row["sha256"]
2350:  sha256=str(row["sha256"]),
2354:  size=int(row["size"] or 0) or None,
```

This is the loop implementing §1's verify-after-write and §3's dual-hash rule, where `copy_sha256` is
the *verification* identity and `sha256` the *dedup* identity. Swapping them at `:2344`/`:2350` would
type-check silently and corrupt the custody record for every copy written. It is exactly the class of
defect `BACKLOG.md` (ff) was built to eliminate ("dataclasses about to be serialized ... invisible to
mypy precisely because the return type was `Any`"), one screen past where the six slices stopped.

**Fix:** a `@dataclass(frozen=True, slots=True) MissingCopy` with the four fields, built once from
either row source. §4's dataclasses-not-pydantic rule already prescribes the shape. **Cost: ~1.5h.**

### F9 - HIGH - The two worst cognitive-complexity functions

Scored per the SonarSource specification, nested function bodies excluded (they are scored separately):

| Function | Cognitive complexity | Lines |
|---|---|---|
| `exif.read_metadata` (`exif.py:207`) | **39** | 96 |
| `migrate.undo_migration` (`migrate.py:596`) | **27** | 83 (see F14) |

`read_metadata` is one function doing four things: cache-hit partitioning (`:240-253`), progress
seeding (`:255-257`), the exiftool batch loop with two silent-continue error paths (`:265-287`), and
cache write-back (`:295-300`). The `pyproject.toml:72` suppression already concedes it
(`PLR0912`, `PLR0915` waived with the comment "cache-hit vs exiftool branches") - but a suppression
records the debt, it does not discharge it, and 39 is more than twice the 15 threshold.

**Fix sketch.** Three extractions along the seams that already exist: `_partition_by_cache(paths, cache,
force, tags_fp) -> (collected, to_read)`, `_read_chunk(binary, chunk) -> list[record]` (owning the
empty-payload and `JSONDecodeError` paths), `_cache_records(cache, records, tags_fp)`. Expected result:
each part under 10, no behaviour change. **Cost: ~3h with the existing exif tests as the guard.**

### F10 - HIGH - `service.py` has outgrown one module

2,731 lines; 79 top-level functions and 82 top-level classes; **23 `from truestill_core import`
statements**, meaning 23 of core's ~29 modules funnel through one file. Eleven distinct product
surfaces are co-resident (Organize, Organize-undo, Clean-empty, Verify, Drives/Where/At-risk, Stats,
Trips and events, Takeout rescue, Browse, Settings, Migration, Backup). Only six `# ---` section markers
exist, all after line 1,515 - the first 1,514 lines carry no section structure at all.

§2 pins `service.py` as the bridge, so the right shape is a `service/` **package** whose `__init__.py`
re-exports every current name. `server.py` and all twelve app test modules keep working unchanged and
§2's wording stays literally true. Cleanest first cut, verified: `fs_browse.py` from lines
**1759-1913** - the Browse endpoints plus eight TypedDicts, with **zero** `Catalog` usage, depending
only on `read_marker` and `MEDIA_EXTENSIONS`.

Four oversized bodies inside it, each worth its own commit: `organize_run.target` (`:772-870`, 99 lines,
16 responsibilities, and two separate catalog transactions at `:783` and `:856`), `backup_run.target_job`
(`:2310-2377`, 68 lines, containing the copy-verify loop of F8), `library_stats` (`:1428-1512`, 85
lines), `migration_apply.target` (`:2580-2643`, 64 lines, with two near-identical reveal-path loops at
`:2603-2615` and `:2616-2630`).

**Cost: ~1 day for the package skeleton plus the three mechanical modules; ~2 days for the rest;
~10h for the four decompositions. One module per commit, per §5.**

### F11 to F13 - HIGH - Three guards that cannot fail against the bug they name

`ENGINEERING_STANDARD.md` §4: "A fixture that cannot fail against the bug is not a regression test."

**F11 - `packages/truestill-app/tests/test_server.py:560-583.`** The test retypes the production SQL as
a string literal (`:574-577`) and runs `EXPLAIN QUERY PLAN` on **its own copy**, never on what
`catalog.find_copies` executes. Rewrite `find_copies` tomorrow to fetch every row and slice in Python
and this test still passes. Its own docstring claims the opposite: "Asserted against the query plan
rather than by timing, so it cannot pass by being fast on a fixture." It can pass by being wrong.
Separately, `assert "SCAN" in plan or "SEARCH" in plan` matches essentially every non-trivial SQLite
plan. **Fix: expose the query text through a seam, EXPLAIN that, assert on `USING INDEX`. ~1h.**

**F12 - `packages/truestill-app/tests/test_user_facing_copy.py:41-42, 115-116, 126.`** `USER_FACING`
(`:24-30`) is five hard-coded paths derived from `REPO = ...parents[3]`. Each parametrized guard begins
`if not path.exists(): pytest.skip(...)`, with the comment "SECURITY.md and friends are allowed to not
exist yet". Rename or move `app.js` and both guards report **skipped, suite green** - for the exact file
whose defect motivated the module. Move this test file one directory deeper and all five skip.
**Fix: assert `USER_FACING` resolves in its own test; keep the skip only for an explicit `OPTIONAL`
tuple. ~30 min.** (Related, same file: `MALFORMED` is guarded perfectly at `:52-65` - the real defect,
the real repair, and all four look-alikes - while `_BANNED_USER_PHRASES` at `:86-93` has no equivalent
and three of its entries are generic fragments one edit from legitimate copy.)

**F13 - `packages/truestill-core/tests/test_reclaim.py:51.`** `pending_reclaim` appears **once** in the
entire test tree, asserted empty. `record_reclaim` and `clear_reclaim` have **zero** test references.
Delete `catalog.record_reclaim(...)` at `reclaim.py:189` and all fourteen reclaim tests still pass.
`IMPLEMENTATION_STANDARDS.md` §1 states "Every deletion is journalled (`reclaim_journal`, schema v9)
for audit/resume"; that clause has no enforcing test. The contrast is instructive - migration's
equivalent journal has three crash-state reconstructions (`test_migrate.py:149`, `:169`, `:191`).
**Fix: make `unlink` raise a non-`OSError`, assert `pending_reclaim()` names the file. ~1h.**

### F14 - MEDIUM - `undo_migration`: complexity 27, driven by a block written four times

`migrate.py:596-678`. The pair

```
processed += 1
if progress is not None:
    progress(Progress(processed, total, Phase.RESTORING, item))
```

appears at `:646-648`, `:652-654`, `:657-660` and `:674-676`. Four copies of the loop's exit bookkeeping
is most of the 27. A local `def tick()` closure, or restructuring the four `continue` paths through a
`try/finally`, removes the duplication and most of the score without touching the ordering the
docstring's safety argument depends on.

One inconsistency in the same function: `:650` calls `destination.checksum(new_relative)` raw, while
`:664` goes through the guarded `_matches`. Given F3, the raw call is the one that behaves as intended
today; the guarded one is the broken guard. Worth resolving together. **Cost: ~1h.**

### F15 - MEDIUM - A repair note names the repaired string instead of the offending one

`layout.py:356-358`:

```
if _is_reserved(rendered):
    rendered = f"_{rendered}"
    notes.append(f"segment {rendered!r} avoided a Windows reserved name")
```

The reassignment happens first, so the note reads "segment '_CON' avoided a Windows reserved name".
`_CON` is not a reserved name; `CON` was. Identical bug at `layout.py:396-398` (`_trip_segments`) and at
`layout.py:140-142` (`event_folder`), so all three sites are affected.

§9 makes this a first-class defect surface, not a cosmetic one: "A user-supplied name that becomes a
directory is repaired, never trusted and never rejected ... **Every repair is reported.**" The repair
is reported; the report names the wrong string. That is the exact failure mode §9 exists for - eight of
the soak's ten defects were the product describing itself incorrectly. Note the correct pattern is
already in the same file six lines up (`layout.py:131`: `f"event name {name!r} was adjusted to
{cleaned!r}"`, capturing both).

**Fix: bind the original before reassigning. Three one-line changes. Cost: 20 minutes plus a test.**

### F16 - MEDIUM - `Catalog` is a 1,006-line class with 71 methods and two organising schemes

`catalog.py:420-1425`. Concerns, all in one class: schema versioning, key/value settings, the migration
journal (10 methods), the reclaim journal (4), the in-place journal (9), files and dedup seeding, stats
(5), drives and copies (11), events and trips (10).

The sectioning is itself inconsistent: `:485` "layout migration", `:664` "reclaim", `:707` "in-place
relocation journal" are feature-oriented, while `:835` "reads", `:1003` "drives and copies (reads)",
`:1196` "writes" are operation-oriented. Two taxonomies in one class means no method has an obvious
home. The lifecycle methods (`__enter__`, `__exit__`, `close`, `_tx`, `:812-835`) sit in the middle of
the class under no section at all.

`BACKLOG.md` (ee) set the precedent for this kind of split when it moved the catalog-touching layout
trio out to `layout_settings.py`. The cheapest first cut here needs no class change at all: the twelve
module-level schema-migration functions (`_add_*` and `downgrade_v12_to_v11`, `catalog.py:196-398`,
~203 lines) are already free functions and move to a `catalog_schema.py` wholesale.
**Cost: ~2h for the schema extraction; a full repository-per-concern split is a larger, later call.**

### F17 - MEDIUM - Two in-memory dicts that only ever grow

`server.py:362` `sessions: dict[str, EventReviewSession] = {}` - written at `:390`, read at `:365`,
`:410`, `:430`, `:456`, `:517`, `:527`. There is no `del`, no `pop`, no cap, no expiry. Every "Find
trips and events" run leaks a session holding its full card list and day totals for the life of the
process.

`jobs.py:108` `self._jobs: dict[str, Job] = {}` - written at `:137`, never removed. Only `self._occupied`
is cleaned (`:193`). Every finished job is retained with its summary payload, which for organize
includes folder maps and leftover-folder lists.

Two related sharp edges in the same code:
- `sessions[session_id]` is subscripted with no membership check at five sites. A stale session id -
  after a server restart, or a reloaded page - raises `KeyError` and Starlette returns a 500, where the
  file's own `_STALE_BANNER` machinery (`server.py:61-67`) shows the scenario is anticipated elsewhere.
- `JobManager.stream` (`jobs.py:211-221`) blocks on `job.events.get()` with no timeout and no replay of
  the terminal event. Reconnecting SSE to an already-completed job finds an empty queue and pins a
  server thread indefinitely.

`truestill-app` is a long-running local server, so "restart it" is not the whole answer.
**Fix: bound both dicts (LRU or age-based), return a typed "session expired" payload on a miss, and
give `stream` a terminal-event replay or a timeout. Cost: ~3h.**

### F18 - MEDIUM - Three `read_metadata` calls bypass the metadata cache with no recorded reason

`IMPLEMENTATION_STANDARDS.md` §8 records exiftool at **74% of cold pCloud preview wall** and names
exactly two never-cache paths: "Verify is deliberately NOT cached ... Reclaim likewise always
re-hashes." Three call sites are neither, and pass no cache:

| Site | What it is |
|---|---|
| `cli.py:1184` | `truestill ingest` - the Takeout path §8 calls "the feature the launch story leads with" |
| `service.py:1523` | `plan_resolve`, backing the Trips and events review screen |
| `migrate.py:205` | `rederive_rules`, inside migration planning |

The comparison that makes this a finding rather than a nitpick: `service.organize_preview:703` and
`organize_run:783` and `ingest_preview:1693` and `cli._run_pipeline:931` all open
`HashCache.beside(db)` and pass it. So the same library is scanned cached on one screen and uncached on
another, which is the front-end drift §1 introduced `models.date_quality` to prevent, applied to cost
instead of counts.

`migrate.py:205` may be deliberate - a migration preview must write nothing (§5), and a cache write is
arguably a write, though the sidecar is machine-local and explicitly disposable. **That ambiguity is
itself the finding: none of the three carries a comment saying which it is.** Either wire the cache or
state the reason at the site, per §5's "an uncommented deviation is a bug, not a judgement call".
**Cost: ~1h to wire the two clear cases; the `migrate.py` one needs a ruling first.**

### F19 - MEDIUM - `layout.py` carries seven concerns on the one seam that must stay legible

949 lines holding: token grammar and parsing (`:39-53`, `:288-331`), path sanitization including
Windows reserved names, NFC and byte truncation (`:87-98`, `:204-241`), event-folder naming and
collision disambiguation (`:117-198`), the `Placement` router (`:510-534`, `:712-749`), `LayoutScheme`
and presets (`:751-889`), the Everyday day-threshold cluster (`:536-610`, `:611-710`), and preview rows
(`:423-464`).

§2 makes this the file where "there is no way around" the seam, so its legibility is load-bearing.
(ee) already established the precedent for splitting it. Two candidate modules, both cohesive:
`layout_naming.py` (the sanitize/truncate/reserved/event-folder/disambiguate cluster, ~130 lines) and
`everyday_days.py` (the threshold, settings, day-bucket regexes and reconcile reasons, ~175 lines),
leaving `layout.py` as grammar, routing and rendering - which is what its docstring already claims it
is. **Cost: ~3h.**

### F20 - MEDIUM - `assert` used as a runtime gate on external state

`service.py:2518`:

```
def target(progress, cancel) -> MigrationPreviewOk:
    result = migration_preview(path, db, progress=progress, cancel=cancel)
    assert result["ok"] is True  # marker gated above; soft-fail already returned
```

The comment's premise is a time-of-check/time-of-use gap. The marker gate runs at request time
(`:2512`); `target` runs later on a worker thread and `migration_preview` re-reads the marker
(`:2469`). Unplug the drive in between and the assert fires. Traced through: `jobs.py:182` sets
`code="AssertionError"`; `app.js:105-109` has no `FRIENDLY_ERRORS` entry for it; a bare assert has no
message so `str(exc)` is empty, and `app.js:113` renders `friendly || esc(d.error)` - an empty warning
banner. Under `python -O` the assert vanishes and an error payload is returned typed as
`MigrationPreviewOk`.

Every sibling path for the identical condition returns the actionable drive-correction text
(`verify_run:1204`, `propose_events:2397`, `migration_preview:2471`, `migration_armed_state:2689`,
`migration_undo:2707`), and the codebase already knows the right idiom: `migration_apply:2583` and
`backup_run:2320` `raise _not_a_drive(path)`, which **is** in `FRIENDLY_ERRORS`.

Same class, lower risk: `jobs.py:126` `assert held, "jobs.start requires at least one drive"` is a
public-API precondition that disappears under `-O`; `service.py:1594` and `trip_review.py:127` are
genuine invariants but share the `-O` property.

**Fix: `if result["ok"] is not True: raise _not_a_drive(path)`. ~15 min plus an e2e case per §6.**

### F21 - HIGH - A permission-denied folder raised an uncaught `PermissionError` on three routes

> **Corrected 2026-07-30 in the Pass 3 fix, and the correction is the finding.** This entry
> originally graded MEDIUM and read "An error path that tells the user something false": it claimed
> `_device_id` returned `None` for both a missing and an unreadable path, and that both were worded
> "The source folder was not found". **Both halves of that were wrong, and only running the code
> showed it.** The original text is not preserved because it described behaviour the product never
> had; what it got right - that these paths conflate *absent* with *refused* - is kept below.
> The audit's own rule applies to the audit: a claim about behaviour is not established until it
> has been executed.

**What the code actually did.** `Path.exists` and `Path.is_dir` are not total. They swallow `OSError`
only for the "not there" errno family (pathlib's `_ignore_error`: ENOENT, ENOTDIR, EBADF, ELOOP) and
**re-raise everything else, `EACCES` included**. Three app entry points read them as "False means no":

| Site | Call | Consequence |
|---|---|---|
| `service/fs_browse.py:104` | `if not path.is_dir():` | `GET /api/fs/dirs` -> **HTTP 500**; the Browse picker dies |
| `service/fs_browse.py:150` | `is_dir = path.is_dir()` | `GET /api/fs/validate` -> **HTTP 500**; the hint under every folder field |
| `service/organize.py:257` | `if probe.exists():` | `/api/fs/relationship` -> **HTTP 500**, and `_mode_mechanism` on the organize preview path |

Plus two unguarded probes in `fs_roots` (`fs_browse.py:76`, `:80`) on `~/Pictures` and `/media`.

So the "was not found" message was never reached on a permissions failure - the function raised first.
**And it was unreachable for the missing case too:** a path that does not exist resolves through its
nearest existing ancestor, which always stats, so the walk answers rather than returning `None`.
Verified: `_device_id(Path("/nope/nothing/here"))` returned `66311`, the device of `/`. Both error
branches of `filesystem_relationship` were dead strings that had never been shown to anyone.

Browsing into any permission-denied directory - `/root`, another user's home, a locked mount, the
`Crypto Folder` `PROJECT_STATUS.md` §4 fences off - killed the folder picker with a 500.

**The audit's own predicted pattern held.** This entry said of the conflation "that pattern rarely
appears once"; it was three sites plus two probes. Core already had the discipline -
`drive.path_is_usable_dir` wraps its own `is_dir()` for exactly this reason, and
`test_locate_drive_permission_error_returns_empty_not_raise` pins it - so this was five sites that
never received a lesson the codebase had already learned.

**Fixed** by `service/path_probe.py`: a four-state `PathReach` (`DIRECTORY` / `NOT_A_DIRECTORY` /
`MISSING` / `UNREADABLE`) and a `nearest_device` that walks up through *missing* ancestors - the right
answer for a not-yet-created backup folder, which is the normal first-run case - but stops at a
*denied* one rather than borrowing a different folder's device id. `fs_validate` gained an
`unreadable` field so the UI can stop offering "Create it" for a folder that already exists, an offer
whose create fails with the same refusal. Pinned by `tests/test_unreadable_paths.py`, every case
paired against a cry-wolf half and both halves mutation-proven.

Two related items from the original entry, both now closed by the same change: `filesystem_relationship`
walked the tree four times where two suffice, and `_mode_mechanism` collapsed an unstattable path to
`same_filesystem = False`. The second is now reported rather than folded.

### F22 - MEDIUM - Two event-wiring disciplines, and the majority one is the recorded defect class

Measured in `app.js` (2,071 lines, 96 top-level functions):

| Style | Sites |
|---|---|
| `.onclick =` property assignment | 39 |
| `addEventListener` | 15 |
| delegated `document.addEventListener` + `closest("[data-*]")` | 4 |
| inline `onclick="..."` attribute | 1 (`:447`) |

`ENGINEERING_STANDARD.md` §2 records the shipped defect this produces: `panel.innerHTML = summary +
panel.innerHTML` re-parsed an armed card and wiped its handler, so "resume looked present and was dead",
and only the Playwright lane caught it.

**The specific bug is gone - verified.** A scan for `innerHTML +=` and `innerHTML = ...innerHTML` across
all 96 `innerHTML` uses returns **zero** hits. The self-concatenation shape has been eliminated
repo-wide.

**The class is not.** A `.onclick` property assignment does not survive its container being re-rendered;
an inline attribute and a delegated handler do. The code handles this by re-wiring after each render -
`runWhere` (`:1534-1562`) assigns `innerHTML` at `:1555` and then re-wires `prev.onclick`/`next.onclick`
at `:1559-1561`, correctly. But that is correctness by vigilance, and the recorded defect was one lapse
of exactly that vigilance. The structural fix is already proven in the same file at four sites
(`data-use-root`, `data-clean-preview`, `data-open`, `data-stats-action`).

**Fix: convert the handlers attached to dynamically re-rendered markup to the delegated `data-*` pattern
already in use. Not all 39 - only those inside panels that get re-rendered. Cost: ~4h, and it should be
scoped by first listing which panels re-render.** F0 is the confirmed live instance; F39 and the
`withBusy`-on-a-detached-button cases below are the same root cause in different clothes.

### F38 to F47 - The rest of the frontend

**F38 - HIGH - the job-run skeleton is written out thirteen times.** `app.js:595`, `:638`, `:1162`,
`:1193`, `:1319`, `:1366`, `:1469`, `:1592`, `:1756`, `:1804`, `:1851`, `:1979`, `:2022`. Each is the
same eight steps: POST, check `started.ok === false` and render `startRefusedCard`, store the job
handle, `progress.start(label)`, `awaitJob` with an update closure, `progress.stop()`, clear the
handle, render the outcome. Roughly 250 lines. **This is the direct cause of F0** - one of the thirteen
forgot a step the other twelve remember, and nothing could tell you which. Six of the seventeen
functions on the frontend complexity table owe most of their nesting penalty to it.
**Fix: one `runJob({endpoint, body, progress, jobRef, refusedInto, refusedField, label, unit})`
returning the normalized `d`. ~2h; removes ~180 lines and structurally prevents the next F0.**
The nearest pair, `startUndoPreview` (`:593`) and `startUndoApply` (`:636`), are verbatim twins for 22
of their ~40 lines, and `startOrganizeUndoPreview`/`Apply` (`:1160`, `:1191`) are a second copy of that
same pair - a four-way cluster.

**F39 - HIGH - a Split or a Merge silently discards every trip name typed so far.** `evCardHtml`
(`app.js:1654`) emits `<input class="input ev-name" data-i="${i}" placeholder="...">` with no `value=`,
so **the DOM is the only store** for what the user types. `renderCards` (`:1669`) then does
`$("ev-clusters").innerHTML = ...`, which is called on every Split (`:1687`) and Merge (`:1728`).
`$("ev-apply")` reads the names back out of the DOM at `:1734`. Naming is the entire purpose of that
screen. Index shifts after a split mean the values genuinely cannot be replayed positionally - but
that is an argument for telling the user, not for dropping their input in silence, which is §9's
never-silent rule verbatim. **Fix: hoist names onto `evCards[i].name` on `input`, re-emit them as
`value=`, and name any that a split or merge invalidated. ~2h.**

**F40 - MEDIUM - two CSS variables are used and never declared, and two components lose their
background.** Verified: `--surface-raised` (`app.css:347`, `:530`) and `--text-primary` (`:598`) have
**zero** declarations in `app.css` or `tokens.css`. An unresolvable `var()` with no fallback is
invalid at computed-value time, so `background` falls to transparent and `color` inherits. The three
organize-mode option cards (`.org-mode`) and every progress block (`.progress-wrap`) therefore render
with no separation from the page, in both themes - the visual grouping the stylesheet intends is
simply absent. **Fix: declare `--surface-raised` in all three theme blocks and change `:598` to
`var(--text)`. ~20 minutes.**

**F41 - MEDIUM - `plural` is bypassed at six sites.** §9 names it: "`plural(n, word)` in `app.js` -
'1 file', '2 files' - never '1 file(s)'". Inline re-implementations at `app.js:246`, `:247`, `:430`,
`:431`, `:459`, `:465`, each of the form `${nfmt(n)} word${n === 1 ? "" : "s"}` - byte-equivalent to
`plural(n, word)` today. A rule with six un-routed bypasses is a rule that will drift, and §9 exists
because that drift was eight of ten soak defects. **Fix: 15 minutes**, and it also removes about
eleven cognitive-complexity points from `organizeCompletion`.

**F42 - MEDIUM - `esc` does not escape the single quote.** `app.js:4` covers `& < > "` only. Safe
*today* because interpolated attributes happen to use double quotes - but `:1133` and `:1569` already
write single-quoted attributes (`card("<div class='k'>...")`), so the convention is not uniform, and
the first single-quoted attribute carrying an interpolation is an injection. No live hole was found:
every user-controlled string traced (event and trip names, file paths, error messages, search terms,
folder names) does go through `esc`, at 87 sites. **Fix: add `'` to the character class. 2 minutes -
the cheapest risk removal in the codebase.**

**F43 - MEDIUM - a primary button that can never be clicked.** `#org-run`
(`templates/index.html:120`) ships `disabled`, and `app.js` sets `disabled = true` at six further
sites (`:1038`, `:1297`, `:1320`, `:1343`, `:1349`, `:1351`) and **never** sets it `false` - verified
by grep. Its handler is `$("org-run").onclick = guarded(() => {})` (`:1400`), an empty function. The
real call to action is the typed-confirm button `renderOrganizeRunConfirm` builds (`:1050-1073`). So
the Organize screen renders a primary-styled dead control. **Fix: delete both, or repurpose it as the
confirm host. 20 minutes.**

**F44 - MEDIUM - organize never clears its typed confirm after a run; migrate does.** `startMigrateRun`
calls `clearMigrateConfirm()` (`:1974`, called at `:1982`, `:1993`, `:2024`). The organize path clears
`#org-confirm` only *before* a run (`:1037`, `:1321`), never after. `withBusy`'s `finally` restores
`trigger.disabled` to its previous value, so once an organize completes the confirm button is live
again, above the completion card, with `move` still typed in the input. One stray click re-runs it.
The server's `DriveBusy` lock guards concurrent runs, not sequential accidental ones. **Fix: clear
`#org-confirm` after the run. 5 minutes.**

**F45 - MEDIUM - the organize-undo progress bar renders below the viewport.** The migrate and event
flows park the shared `#undo-card` node into their stage (`app.js:611`, `:651`) and return it to
`document.body` afterwards (`:619`, `:659`), because `#undo-card` is a direct child of `<body>` after
`<div class="app">` (`templates/index.html:391`), which is a `min-height:100vh` grid. `startOrganizeUndoPreview`
(`:1170`) and `startOrganizeUndoApply` (`:1200`) call `undoProgress.start(...)` without parking it.
An undo of a large library therefore looks frozen - the same class of defect as `BACKLOG.md` (oo).
**Fix: mirror `:611`/`:619`. 15 minutes.**

**F46 - MEDIUM - the move list is truncated at 200 with no disclosure.** `app.js:1781` renders
`p.moves.slice(0, 200)` under a control that says "Show the moves". `cleanupOfferNote` (`:1108-1110`)
gets this right with "and N more", and the stats samples are honestly labelled "sample". §9's
never-silent rule applies to a truncated list as much as to a skipped file. **Fix: 10 minutes.**

**F47 - LOW - dead CSS.** `.progress`, `.progress .bar`, `.progress .bar > i`, `.progress .meta`
(`app.css:499-523`, 25 lines) match nothing: every progress block in `index.html` uses
`progress-wrap`, whose rules at `:527-600` are a superset. This is the pre-`progress-wrap` version left
behind. `.btn-danger` (`app.css:402-405`) is likewise unreferenced repo-wide. Six custom properties are
declared and never used: `--accent-pressed`, `--danger-subtle`, `--success-subtle`, `--gray-400`,
`--gray-700`, `--space-8`. **Fix: ~20 minutes.** (`--gray-400`'s comment at `tokens.css:40` documents a
deliberate contrast retirement and is worth keeping.)

**Two more, LOW, worth recording rather than acting on:** `withBusy` manages buttons that the wrapped
work destroys (`app.js:1685` holds the Split button while `:1687` replaces its container; same at
`:1162`, `:1193`, `:598`, `:641`), so its documented "always re-enables in `finally`" guarantee is
silently a no-op at those sites and the refusal path removes its own retry affordance; and four async
handlers are wired without `guarded` (`:725`, `:866`, `:888`, `:1456`), so their failures reach the
banner only through the `unhandledrejection` backstop, which skips `hideFatalError()` and can leave a
stale banner up.

### F23 - MEDIUM - Seven `type: ignore` comments with a code but no reason

`ENGINEERING_STANDARD.md` §4: "No `type: ignore` without a reason code **and a comment**." All seven
carry the bracketed code; none carries the prose:

`security.py:51` `[no-untyped-def]` | `migrate.py:375`, `:377` `[arg-type]` | `layout.py:541`
`[call-overload]` | `server.py:585` `[arg-type]` | `cli.py:1288` `[type-arg]` | `trip_review.py:119`,
`:123` `[union-attr]`

`server.py:585` is additionally **stale** - `mypy --strict` reports it as an unused ignore (F4), so it
suppresses nothing. **Fix: add the reason, or remove the ignore where the underlying issue can be fixed
properly (three of them can). Cost: ~1h.**

### F24 to F26 - MEDIUM - The complexity-declaration rule: the habit holds, the rule does not

Compliance was measured across all 31 core modules. Headline: **new code is pricing its complexity
correctly, but not where the rule says to put it, and never in the baseline table.**

- **2 of 31** module docstrings state a complexity (`dedup.py`, `cleanup.py`) - and both carry an
  inaccurate claim (F5, F25).
- **25 function-level** statements exist across 9 modules. Every one checked is arithmetically correct
  except the two flagged. `trips.py:147-151` and `trip_review.py:334-336`, the two newest algorithmic
  modules, carry precise bounds verified against the schema.
- **0 of 7** stages added after 2026-07-27 received the mandated **measured** row in
  `PERFORMANCE.md` §1 (**F26**). `git log` shows the last content commit to that document is `8f77de1`
  (2026-07-27); every module added on 07-28 through 07-30 postdates it. Missing rows: trip detection,
  trip review, migration plan/apply/undo, cleanup, undo, catalog startup. `hash_cache` appears in §1
  prose but has no row.

**F24 - `events.py:1-21` and `:237`.** `PERFORMANCE.md:124-125` explicitly protects this stage: "Event
clustering is O(n log n) - one sort, three linear passes. It is **not the quadratic thing it
resembles**." That fact lives only in the document. Verified true in the code (`:209` one sort;
`:213-217`, `:220-230`, `:234-241` three linear passes; `_boundary_after` medians a constant-width
window). The document anticipates that a reader of this code will misjudge it, and the code offers no
rebuttal. `:237` also slices inside a loop - the classic accidental-quadratic shape - and carries no
comment proving the bound, which §4 requires. **Fix: one docstring line plus one comment. Minutes.**

**F25 - `cleanup.py:17-18`** claims "**O(folders)** in the leftovers ... Nothing scales with library
size." `emptied_directories` (`:91-105`) walks every ancestor of every journal row and sorts, and its
input is one row per migrated file (`cli.py:1345`, `service.py:1004`) - so it is O(moves x depth) +
O(F log F), which is O(n) in the library. The cost is small (pure string work, no reads) and the I/O
half of the claim is correct, but "nothing scales with library size" is the sentence a future optimizer
would trust. **Fix: one line.**

**F36 - `trips.py:150-151`** states "Neither sequence is walked more than once; there is no pass nested
inside another." There are three levels (`:179`, `:182`, `:201`). The stated **O(D)** is nonetheless
correct because `runs` partitions `ordered_days` and `_split_at_year_boundary` partitions each run - so
the bound is right and the sentence proving it is wrong. Ironically it is the clause §4 asks for
("nested iteration carries a comment proving its bound") and it denies the nesting exists.
**Fix: one line.**

### F27 - MEDIUM - Three documented claims falsified by shipped code

All three concern the same feature, `BACKLOG.md` (eee), built 2026-07-30:

1. **`DECISIONS.md:136-138` (D3 ruling 3):** "No in-place-organize E2E. The feature is CLI-only by
   decision ... asserting it through a browser would test a surface that does not exist." The surface
   exists at `templates/index.html:96` (`<input type="radio" name="org-mode" value="inplace">`) and
   `tests/e2e/test_ui_regressions.py:116-131` correctly drives it.
2. **`BACKLOG.md:951`:** "(eee) is that soak demand for in-place + undo - approved to surface, **not
   built yet**." (eee)'s own entry at `BACKLOG.md:298-303` says "**Built 2026-07-30.**" The file
   contradicts itself.
3. **`BACKLOG.md:952`:** "`--move` and `reclaim` remain deferred." `--move` is surfaced at
   `index.html:93` (`value="move"`). Only the `reclaim` half is still accurate - verified, there is no
   reclaim surface in the app.

`DECISIONS.md` has an established form for this (D1's superseded-by header). **Fix: a superseded-by note
on D3 ruling 3 and a correction to the two BACKLOG lines. ~20 minutes.** The docs are what is wrong
here, not the code.

### F28 to F30 - MEDIUM - Test-suite structure

**F28 - No `conftest.py` in two of three packages.** The only two are
`packages/truestill-core/tests/conftest.py` (37 lines, two image fixtures) and `tests/e2e/conftest.py`
(151 lines, well built). That absence is the root cause of every duplication below:

| Cluster | Copies | Drift already present |
|---|---|---|
| `client` TestClient fixture | 7 of 12 app test files | 2 of 7 omit the `x-truestill-token` header |
| SSE-drain helper | 6 copies, 3 names | 3 different terminal-event semantics; one `IndexError`s on empty |
| Catalog seed block | `test_server.py:104-151` and `test_ui_regressions.py:328-375` | **47 lines, differ by exactly one** |
| `record_uploaded` seeding | 31 call sites, 17 files, 7 wrapper helpers | 4 sha strategies |
| `Resolution`/`Decision` builder | 20 sites, 12 files | `CategoryMatch` kwarg order drifted 2 ways |
| stdin-refusal test body | 6 near-identical CLI tests | cosmetic only |
| `skipif(which("exiftool"))` | 21 verbatim copies | 5 use `__import__("shutil")` inline |

**Fix: an app conftest (`token`, `db_path`, `client`, `drain_job`) plus a `resolution(...)` factory and
`seed_copy(...)` in the core conftest. ~7h, mechanical, high leverage.**

**F29 - `test_migrate.py` is 1,279 lines** with 39 tests and **six author-written banner comments that
already declare the seams** (`:138`, `:230`, `:586`, `:707`, `:883`, `:1056`). Two clean cuts, verified
self-contained: `test_migrate_everyday_threshold.py` from `:1056-1279` (7 tests, uses only `_seed`,
`_confirmed_trip`, `plan_migration`) and `test_migrate_undo.py` from `:315-583` (10 tests, owns
`_fingerprint` exclusively - and notably the only large cluster with **no** banner, which is a tell that
it grew unnoticed). Within the file, the (gg) cluster repeats a ~13-line skeleton **7 times**
(~91 duplicated lines) and is the strongest `parametrize` candidate in the suite. **Cost: ~5h.**

**F30 - The plan-and-dedup pipeline is written out five times.** `resolve_scheme` -> `build_rules` ->
`heavy_days_for_organize` -> `plan` -> `DedupIndex.from_catalog_rows` -> `resolve` appears at
`service.py:703-719`, `:783-798`, `:1524-1530`, `:1693-1709` and `cli.py:930-1010`. The copies have
already diverged in ways that are hard to see: `plan_resolve` (`:1524`) opens no `HashCache` (F18), and
`organize_run` calls `pin_existing_layout` where `organize_preview` correctly does not. A sixth stage
lands in five files and nothing fails if it lands in four. **Fix: one `_plan_and_resolve(...)`; the
ordering belongs in core, not in two front-ends. ~4h.**

### F31 to F37 - LOW

**F31 - Four exported symbols with zero references anywhere in the repo** (verified by grep across
`packages`, `scripts`, `tests`, `docs`, `README.md`, `CHANGELOG.md`, and the shipped JS):

| Symbol | Location | Note |
|---|---|---|
| `exif.write_metadata` | `exif.py:93-109` | **the one worth acting on** |
| `Catalog.set_source_path` | `catalog.py:807` | added 2026-07-27 with in-place organize, never wired |
| `Catalog.drive_by_label` | `catalog.py:1019` | |
| `server.app_summary` | `server.py:590` | marked `# pragma: no cover - convenience` |

`write_metadata` is a trap rather than merely dead weight: it is the pre-batching single-file API, and
D4 plus `PERFORMANCE.md` §1 record that one exiftool process per file costs **254.9 ms** against the
batch's 9.3 ms. It is the exact function a future contributor would reach for, and calling it in a loop
silently reintroduces a 27x regression on the one path that modifies bytes the user keeps. If it is
kept for the single-file case, it needs a docstring line pointing at `write_metadata_batch`; otherwise
delete it. **Cost: 30 minutes for all four.**

**F32 - `security.py:51`** - `async def __call__(self, scope, receive, send)` is fully untyped on the
security middleware, suppressed by `# type: ignore[no-untyped-def]`. `starlette.types` supplies
`Scope`, `Receive` and `Send`, and the file already imports `ASGIApp` from it at `:23`. Not a security
hole - `_reject` is fully typed - but it is the one untyped def in the app. **Also dead in the same
file: `Endpoint` (`:75`), zero references. Cost: 15 minutes.**

**F33 - `trip_review.py:119`, `:123`** silence mypy with `# type: ignore[union-attr]` where the sibling
property `count` (`:125-129`) handles the identical union with `assert self.event is not None`. Three
properties, two idioms, one class. The `assert` form is the better one (though see F20 on `-O`); a
`if self.trip is not None: ... return self.event.start.date()` restructure needs neither.
**Cost: 15 minutes.**

**F34 - Duplication in source is essentially nil, with one exception.** A token-shingle scan over
**6,863 logical lines** of source found exactly **one** duplicated 8-line window and three at 5 lines.
The one worth naming: `cli.py:1072-1084` and `cli.py:1181-1192`, the exiftool-plus-destination error
preamble shared by `_cmd_organize` and `_cmd_ingest` (~12 lines). **Cost: 20 minutes.** The others are
`service.py:445-455` vs `:1726-1736` (an 11-line `InferredLocalShift` serializer written twice, for a
TypedDict that already exists at `:393` with no constructor) and `service.py:926-933` vs `:953-960`.

**F35 - One dead CSS selector of 86.** `.btn-danger` (`app.css:402`) is referenced nowhere in `app.js`,
`index.html`, or any Python that emits HTML. Every other declared class resolves. **Cost: 2 minutes.**

**F37 - `pyproject.toml:17`.** Every `make check` run emits
`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2
instead.` A warning that appears in every green run is a warning nobody will read when it matters.
**Fix: migrate the dev dependency, or pin and record the deferral. Cost: ~1h.**

---

## 3. The worst offenders, by measurement

Cognitive complexity, SonarSource specification, nested function bodies scored separately:

| Score | Lines | Location |
|---|---|---|
| **39** | 96 | `truestill-core/src/truestill_core/exif.py:207` `read_metadata` |
| **27** | 83 | `truestill-core/src/truestill_core/migrate.py:596` `undo_migration` |
| **25** | 47 | `truestill-core/src/truestill_core/verify.py:51` `verify_copies` |
| **24** | 67 | `truestill-core/src/truestill_core/scan.py:87` `compute_hashes` |
| **21** | 100 | `truestill-core/src/truestill_core/organizer.py:1135` `execute` |
| **21** | 121 | `truestill-cli/src/truestill_cli/cli.py:917` `_run_pipeline` |
| **20** | 87 | `truestill-core/src/truestill_core/migrate.py:385` `plan_migration` |
| **19** | 101 | `truestill-core/src/truestill_core/trips.py:105` `detect_trips` |
| **18** | 68 | `truestill-app/src/truestill_app/service.py:2310` `backup_run.target_job` |
| **18** | 30 | `truestill-core/src/truestill_core/takeout.py:216` `scan_takeout` |
| **18** | 48 | `truestill-core/src/truestill_core/cleanup.py:205` `run_cleanup` |
| **17** | 28 | `truestill-core/src/truestill_core/layout.py:341` `LayoutTemplate._render` |
| **17** | 46 | `truestill-core/src/truestill_core/events.py:198` `cluster_camera` |
| **16** | 69 | `truestill-core/src/truestill_core/undo.py:107` `plan_undo` |
| **16** | 35 | `scripts/normalize_dashes.py:110` `main` |

**Watch list (10 to 15), 31 functions.** The top of it: `cli._cmd_config` (15), `reclaim.plan_reclaim`
(15), `service.fs_validate` (14), `trip_review.commit_trips` (14), `layout.LayoutTemplate.parse` (14),
`service.fs_roots` (13), `migrate.run_migration` (13), `service.attach_drive` (13),
`migrate._migration_headers` (13).

**Frontend (`app.js`), same scoring rules, nested functions aggregated into the enclosing function as
Sonar does for JS:**

| Score | Location |
|---|---|
| **38** | `app.js:154` `createProgress` - aggregate of 5 nested fns, each individually <= 13 |
| **31** | `app.js:426` `organizeCompletion` - ~11 points are the F41 inline plurals |
| **24** | `app.js:1731` `$("ev-apply").onclick` - saves names *and* drives a second job |
| **22** | `app.js:347` `renderStatsSummary` - 13 of 22 are `\|\| 0` defaults; branch-only ~6 |
| **20** | `app.js:911` `validatePath` - two unrelated state machines in one function |
| **18** | `app.js:1309` `$("org-dedup").onclick` |
| **17** | `app.js:830` `loadCustody` |
| **16** | `app.js:2021` `$("mig-preview").onclick` |
| **15** | `app.js:1359` `startOrganizeRun` |

Eight over 15 in 110 functions. Six of the nine owe most of their nesting penalty to the F38
skeleton; extracting it once is the single largest reduction available.

**Where the metric over-fires, stated honestly.** Four of the above are flagged by the nesting penalty
rather than by genuine difficulty, and I would not act on them: `verify_copies` (25) is 47 clear linear
lines whose score comes almost entirely from a ternary and two conditions sitting inside a `with
executor` block; `scan_takeout` (18) is a 30-line, well-commented two-level walk; `detect_trips` (19) is
~53 lines of body under ~48 lines of docstring; `run_cleanup` (18) is a `try/except/else` inside one
loop. The score is a prompt to look, and I looked. The ones I do stand behind as real are F9's two.

---

## 4. Non-findings - correct, documented, and to be protected from future "fixers"

Anything a naive SonarQube run would flag here, that this repo's context makes right.

1. **`server.create_app` is 500 lines with 45 nested route handlers.** Aggregate score 62. Its **own**
   complexity, excluding nested bodies, is below 10 - it is a factory, not a complex function.
   `pyproject.toml:78-80` waives `PLR0915` with the reason ("each route is a nested handler closing over
   the token/db"), and the closure is real: handlers close over `jobs`, `_db()`, `sessions`,
   `started_fingerprint`. *(The unit-size observation stands separately - 45 handlers in one function
   could become six route-group builders returning `list[Route]` without touching the closure design -
   but "this function is too complex" is a false positive.)*
2. **`catalog._tx` catches bare `Exception` (`catalog.py:831`).** It rolls back and **re-raises**. This
   is the standard transaction idiom, not a swallow.
3. **`jobs.py:174` catches `Exception`.** It is the worker-thread boundary, and §9 requires it: the
   handler exists to convert any failure into a terminal SSE event carrying `code = type(exc).__name__`,
   which is the mechanism `FRIENDLY_ERRORS` matches on. Narrowing it would let an unanticipated
   exception kill the thread silently.
4. **`hashing._register_heif` catches `Exception` (`hashing.py:55`).** §7 mandates it: "Graceful
   degradation is mandatory ... if it ever fails at runtime, `HEIF_AVAILABLE` is `False`". Commented at
   the site.
5. **`Image.MAX_IMAGE_PIXELS` is raised to 300 MP (`hashing.py:34-35`).** A decompression-bomb guard
   deliberately disabled - and correctly so: §7 records that truestill processes the user's own trusted
   local library, not untrusted uploads, and that the guard is a false positive on panoramas and scans.
   Above the ceiling the image is skipped for perceptual hashing and reported, never silently dropped.
6. **`dedup.DedupIndex.check` is O(n^2).** Deliberate, `PERFORMANCE.md` §3 and `BACKLOG.md` (v). Do not
   build the BK-tree until `LINEAR_SCAN_ALARM` fires in a real run. *(The docstring's number is wrong -
   F5 - but the decision is right.)*
7. **`verify` re-reads every byte and never uses the cache.** §8, and `PERFORMANCE.md` §4. Never cache
   it. Same for `reclaim`.
8. **No pydantic, no attrs.** §4: stdlib dataclasses are the right-sized choice absent an untrusted-input
   API boundary. Do not "upgrade" the models.
9. **No build step, no bundler, no framework in `static/`.** D2, D3 and `BACKLOG.md` (o). The 2,071-line
   `app.js` is a deliberate single file. "Split into ES modules with a bundler" is not a valid finding
   here.
10. **`DTZ007` and naive datetimes in `dates.py` / `video_utc.py`.** Waived at `pyproject.toml:82-90`
    with the reason: EXIF timestamps are local wall-clock with no zone, so a naive datetime is correct.
11. **`PLR0911` on `resolve_capture_datetime`.** It is an ordered priority chain of early returns, and
    §1 states "the order *is* the policy, so it reads as data". Collapsing it would hide the policy.
12. **`security.py:63-64` exempts `/static/` from the token check before the Host check.** Commented
    ("inert assets, no data") and correct: those files carry no user data and no token.
13. **`service._take_live_path_hint` writes (`clear_setting`) during a read.** Looks like a dry-run
    violation; it is `BACKLOG.md` (ww)'s ruled behaviour, and it is called only from `list_drives` and
    `library_status`, never from a preview path - so §5's
    `test_drive_preview_endpoints_never_refresh_the_catalog` is not in tension.
14. **`locate_drive` / `path_is_usable_dir` swallow `OSError`.** (ww) again, and pinned by
    `test_stale_path_hints.py`. This is the *intended* soft-fail, distinct from F1's accidental one.
15. **`JobTarget = Callable[..., Any]` (`jobs.py:33`).** Documented at the site: return shapes are
    genuinely heterogeneous across organize/migrate/verify/backup, and the alternative is an
    intersection type jobs cannot enforce.
16. **`test_inventory.py` monkeypatches internal symbols and asserts `calls == {...: 0}`.** It is a
    deliberate mutation check for the "inventory must be cheap" contract, argued in the docstring. There
    is no other way to assert the *absence* of work.
17. **`test_migrate_undo_ui.py` asserts on `app.js` source text.** The file's docstring explicitly
    disclaims flow coverage and points at the Playwright test - a documented §5 deviation. *(The
    assertions themselves are brittle; see the watch item below.)*
18. **21 `skipif(shutil.which("exiftool") is None)` markers.** Environment-conditional, reason still
    true, correctly scoped. These are not disabled tests.
19. **`tests/e2e/test_busy_state.py:83` uses `time.sleep(0.05)`.** Not a browser wait - it is inside a
    monkeypatched server-side function running on the app's worker thread, holding a job open. The
    no-sleeps rule is not violated; there is no `wait_for_timeout` or `time.sleep` in any browser
    interaction anywhere in the lane.
20. **`test_golden_path.py` is one 57-line journey rather than six tests.** D3 ruling 4, with the
    rationale in its own docstring. Do not split it.
21. **`assert set(body[...]) == {...}` key-set pins in the app HTTP tests.** These are (ff)'s deliberate
    TypedDict contract pins, not brittle shape-coupling.
22. **The `sessions` dict and `JobManager` being process-local and single-user.** `BACKLOG.md` (vv)
    records the cross-process gap explicitly as a known limit. F17 is about unbounded *growth*, which
    (vv) does not cover.
23. **`app.js`'s card renderers are not duplicated, despite looking like they should be.**
    `completionCard` (`:310`) is already the shared seam behind `organizeCompletion` (`:426`) and
    `backupCompletion` (`:679`); `evCardHtml` (`:1640`) and `reviewResultCards` (`:1790`) render
    genuinely different objects; `renderCards` (`:1657`) *calls* `evCardHtml` rather than repeating it.
    A reviewer who assumes this cluster is duplicated (as this audit initially did) is wrong.
24. **`tripResultCards` no longer exists.** `IMPLEMENTATION_STANDARDS.md` §9 names it; it was renamed
    to `reviewResultCards`, and `test_user_facing_copy.py:79` actively asserts the old name is
    **absent**. The doc reference is stale but the code is right - fold this into F27's correction
    rather than filing it as a defect.
25. **`prefill` guards against refilling a field mid-keystroke** (`app.js:783`,
    `document.activeElement !== el`). Looks like an unnecessary condition; it is not.
26. **The dark-theme token block mirrors the `prefers-color-scheme` block property for property**
    (`tokens.css:130-156`). Diffed; they match. The light-on-light failure its comment describes is
    genuinely fixed, and the apparent duplication is the fix.

---

## 5. Metrics summary

### Size

| | Source | Files | Tests | Files |
|---|---|---|---|---|
| `truestill-core` | 9,735 | 34 | 8,898 | 44 |
| `truestill-cli` | 1,811 | 4 | 1,357 | 13 |
| `truestill-app` | 3,701 | 6 | 3,036 | 12 |
| `tests/e2e` | - | - | 1,620 | 8 |
| `scripts` | 765 | 6 | - | - |
| `static` + `templates` | 3,517 | 4 | - | - |
| **Total** | **15,247** | **44** | **14,899** | **77** |

Test-to-source ratio **0.98x**. 664 test functions, 696 passing test cases.

### Cognitive complexity (606 functions across the three packages)

| Band | Count | Share |
|---|---|---|
| 0 | 233 | 38% |
| 1 to 4 | 254 | 42% |
| 5 to 9 | 75 | 12% |
| 10 to 15 (watch) | 30 | 5.0% |
| 16 to 25 | 12 | 2.0% |
| over 25 | 2 | 0.3% |

**Functions over 15: 14** (core 12, cli 1, app 1; plus 1 in `scripts`). **80% of all functions score 4
or below.** For context, a typical brownfield codebase of this size carries 5 to 10% over the threshold;
this is 2.3%.

### Largest units

| Metric | Value |
|---|---|
| Largest source file | `service.py`, 2,731 lines |
| Largest core file | `catalog.py`, 1,425 lines |
| Largest class | `Catalog`, 1,006 lines, 71 methods |
| Largest function | `create_app`, 500 lines (45 nested handlers - see non-finding 1) |
| Largest single-purpose function | `cli._run_pipeline`, 121 lines |
| Largest test file | `test_migrate.py`, 1,279 lines |
| Largest JS function | `renderOrganizeResult`, ~108 lines |

### Duplication

| Scope | Result |
|---|---|
| Python source (6,863 logical lines) | **1** duplicated 8-line window; **3** at 5 lines |
| `app.js` (2,071 lines) | **~250 lines** in the 13-copy job-run skeleton (F38), plus 5 smaller clusters |
| Tests (7,729 logical lines) | **15** duplicated 8-line windows across 7 clusters |
| Worst single instance | 47 lines, differing by one, across a package boundary (F28) |

Python source duplication is **approximately 0.1%** - an exceptional result, and the strongest single
signal in this audit. The debt is in the other two: the frontend's job-run skeleton (~12% of `app.js`)
and the test suite, the latter concentrated in the two packages with no `conftest.py`.

### Dead code

| Category | Count |
|---|---|
| Exported Python symbols with zero repo-wide references | **4** of 830 top-level definitions |
| Dead type aliases | **1** (`security.Endpoint`) |
| Dead CSS selectors | **2** of 86 (`.progress` block, 25 lines; `.btn-danger`, 4) |
| CSS custom properties declared and never used | **6** of 56 |
| CSS custom properties **used and never declared** | **2** - a rendering defect, F40 |
| Dead JS functions | **0** of 110 |
| Dead controls | **1** (`#org-run`, F43) |
| `innerHTML +=` / self-concat sites | **0** of 96 `innerHTML` uses |
| Commented-out code (ruff `ERA`, repo-wide; and `static/`) | **0** |
| Stale `type: ignore` (measured by `mypy --strict`) | **12** (1 in shipped code) |
| Skipped or xfail tests | **0** (21 environment-conditional skips) |

### TODO inventory

**Zero.** No `TODO`, `FIXME`, `XXX`, or `HACK` anywhere in `packages/`, `scripts/`, or `tests/`, in
Python, JS, CSS or HTML. This is genuinely unusual and worth protecting - the backlog carries what
would otherwise be scattered in comments.

### Typing

| | |
|---|---|
| `mypy` (repo config) | **clean** |
| `mypy --strict` | **19 errors in 3 files** (12 stale ignores, 2 real, 5 script re-exports) |
| `type: ignore` in source | 7 (all with codes, **0** with reasons) |
| `-> dict[str, Any]` at the service boundary | **0** - (ff)'s claim verified true |
| `os.path.*` in source | **0** - §4's claim verified true |
| Bare `except` | **0** |
| Overbroad `except Exception` | 3, all deliberate and commented |

---

## 6. Grades

Against 2026 industry standard for a product at launch.

| Package | Grade | Basis |
|---|---|---|
| **`truestill-core`** | **A-** | 391 functions, 12 over threshold, ~0.1% duplication, 2 dead symbols, zero TODOs, exceptional documentation-of-why. Held back from A by F1/F2 (the partial-failure policy is stated and not universally applied), F3 (an interface whose failure contract no backend honours), and two 1,000-plus-line units carrying more concerns than one module should. |
| **`truestill-cli`** | **A-** | 1,811 lines, 62 functions, one over threshold, one duplicated block. Thin and faithful to §2's "wires core stages together and owns all interaction". `_run_pipeline` at 121 lines is the only real unit-size complaint, and it is linear. |
| **`truestill-app`** | **B** | The typed boundary (82 TypedDicts, zero `dict[str, Any]`) and the security module are genuinely strong. But `service.py` at 2,731 lines and 11 surfaces is the one place in this repo where structure has visibly lost to accretion, §2's "sole bridge" claim is currently false, `Catalog._conn` is reached from outside core, and two dicts grow without bound. |
| **Frontend (`app.js` / CSS)** | **C+** | Real strengths: 110 functions with zero dead ones, `esc` applied at 87 sites with no live injection found, every §9-binding symbol present and honoured, the `streamJob` seam respected by all 13 consumers, cancelled-says-cancelled at all six terminal sites, and genuinely good accessibility and theming. But this is the one area where the audit found an unfixed CRITICAL (F0), and it is not isolated: the same root cause produces F39 (typed names discarded), the detached-`withBusy` cases, and F45, all traceable to the 13-copy job-run skeleton (F38) and to four coexisting wiring conventions. Two CSS variables are used and never declared (F40), a primary button is permanently dead (F43), and §9's `plural` is bypassed six times (F41). The engine's discipline has not reached this file. |
| **Tests** | **B+** | 664 tests, median 12 lines, zero skips, zero mocks, zero commented-out tests, destructive-path coverage genuinely strong, and every test the contract cites by name resolves. Marked down for three guards that cannot fail against the bug they name (F11 to F13) and for the missing conftest infrastructure in two of three packages. |
| **Build, CI, gates** | **A** | Three-layer gate matrix with each layer owning what only it can see; two prose gates that exist because a real defect was invisible to ruff, mypy and pytest alike; a lockfile-drift gate; a dependency audit that blocks; a commit-msg hook proven by mutation. The `strict` gap (F4) is the one crack. |
| **Documentation** | **A** | Best-in-class. Rejected alternatives are recorded beside chosen ones, measurements are cited rather than asserted, and research records are deliberately not rewritten. Three stale claims (F27) against that volume is a low error rate, but they should still be corrected. |
| **Overall** | **B+** | The Python alone would grade a full band higher. The frontend is the drag, and it is the layer the project's own soak history says defects live in. |

### The three sentences for a new senior hire

1. **The documentation is the codebase's greatest asset and you should read it before you touch
   anything** - the comments explain *why*, cite the contract, and record what was rejected and
   measured, so almost every "obvious improvement" you will think of on day one has already been
   considered and written down, and Section 4 of this audit lists the ones that will most tempt you.
2. **The Python engineering discipline is real and unusually consistent - zero TODOs, ~0.1% source
   duplication, 80% of functions at cognitive complexity 4 or below, four dead symbols in 830 - which
   means the defects that do exist there are isolated lapses in an otherwise uniform practice, not
   systemic rot**; that is why F1 matters so much (two `future.result()` calls are the only unguarded
   ones in a codebase that otherwise defends every single read) and why finding them was worth the
   effort.
3. **That discipline stops at `app.js`, which is where the one unfixed CRITICAL lives and where the
   project's own history says to look** - F0 is the exact bug `ENGINEERING_STANDARD.md` §2 holds up as
   its worked example, fixed in the migrate-undo path with a comment explaining the hazard and never
   applied to the organize-undo twin thirteen copies away, which is precisely what a 13-fold
   duplicated job-run skeleton buys you.

---

## 7. Recommended fix order - CRITICAL and HIGH only

Scoped so each pass can be ruled on and executed independently. Nothing below is started.

### Pass 0 - The two CRITICALs and the cheapest safety fixes. ~4h

1. **F0** `app.js:1208-1216` - mirror the migrate-undo path (`insertAdjacentHTML("afterbegin", ...)`
   after the refresh), **and** add the e2e case that clicks apply and asserts the outcome text. The
   test is the more important half. *(~20 min + ~1h)*
2. **F42** `esc` - add `'` to the character class. *(2 min, and the cheapest risk removal in the repo)*
3. **F40** declare `--surface-raised` in the three theme blocks; `:598` to `var(--text)`. *(~20 min)*
4. **F45**, **F44**, **F43** - park the undo progress node; clear `#org-confirm` after a run; delete
   the dead `#org-run`. *(~40 min total)*

**Why first:** F0 is a live user-facing-truth defect on the reversal path for the feature whose own
contract says the arrangement of an un-backed-up library is what is at stake, and items 2 to 4 are
under an hour combined.

### Pass 1 - Partial-failure policy (CRITICAL + HIGH). ~6h

The three findings that share one root cause: the read path is not defended the way the rest of the
codebase defends every other path.

5. **F1** `verify.verify_copies` - add `CopyStatus.UNREADABLE`, guard `future.result()`, count and name
   in both report surfaces. Regression test injects a read error. *(~2h)*
6. **F2** `scan.compute_hashes` - same shape; a failed file yields `FileHashes(None, None)` and is
   reported. *(~1h)*
7. **F3** `Destination` failure contract - decide translate-in-backend versus widen-the-contract, then
   apply consistently and fix `migrate._matches`. *(~3h)*

**Why here:** F1 is the only *engine* finding where a real user-visible failure is both reachable and
currently unhandled, on the command whose entire purpose is detecting that failure.

### Pass 1b - The frontend structure that produced F0 (HIGH). ~4h

8. **F38** extract one `runJob(...)` and route all thirteen call sites through it. *(~2h)*
9. **F39** hoist trip and event names out of the DOM so a Split or Merge cannot discard them. *(~2h)*
10. **F41** route the six inline plurals through `plural`. *(~15 min)*

**Why immediately after the fix:** F0 was one lapse among thirteen hand-maintained copies. Fixing the
instance without removing the copies leaves the next one exactly as likely.

### Pass 2 - False claims (HIGH). ~4h, mostly rulings

Cheap, and each one currently misleads a reader who trusts the document.

11. **F5** `dedup.py:14` - correct the measurement. *(10 min)*
12. **F27** `DECISIONS.md` D3 ruling 3 superseded-by note; two `BACKLOG.md` line corrections. *(20 min)*
13. **F4** `mypy strict` - **needs a ruling**: enable it and close the 19 errors (~2h), or amend
    `ENGINEERING_STANDARD.md` §4 to name the flags actually mandatory (10 min). Either is defensible;
    the current state is not.
14. **F7** §2 "sole bridge" - **needs a ruling**: move the three `events_*` handler bodies into
    `service` (~3h), or amend §2 (15 min).

### Pass 3 - Typing and safety of the write paths (HIGH). ~4h

15. **F8** `MissingCopy` dataclass through the backup copy-verify loop. *(~1.5h)*
16. **F6** move the two `_conn` queries into `Catalog` beside their four `stats_*` siblings. *(~1.5h)*
17. **F20** replace the `service.py:2518` assert with `raise _not_a_drive(path)`, plus an e2e case.
    *(~30 min)* - carried up from MEDIUM because it is 30 minutes and closes a §9 defect.

### Pass 4 - The guards that cannot fail (HIGH). ~3h

18. **F11** `test_server.py:560` - EXPLAIN the real query. *(~1h)*
19. **F12** `test_user_facing_copy.py` - assert the guard's inputs resolve. *(~30 min)*
20. **F13** `test_reclaim.py` - one test that the reclaim journal is actually written. *(~1h)*

**Why grouped:** these three are the only findings where the suite currently reports green over an
unverified property. Everything else in the test section is maintainability.

### Pass 5 - Unit size (HIGH). ~2 to 3 days, schedule deliberately

21. **F9** decompose `exif.read_metadata` (39) along its three existing seams. *(~3h)*
22. **F10** `service.py` -> `service/` package with a re-exporting `__init__.py`. Start with
    `fs_browse.py` (155 lines, zero `Catalog` coupling) to prove the facade at near-zero risk, then one
    module per commit. *(~1 day for the skeleton and three modules)*
23. **F10** the four oversized bodies inside it, `organize_run.target` first. *(~10h)*

**Do not start Pass 5 during feature work.** It touches the file every app change touches.

---

## 8. What was measured, so it can be re-run

- Cognitive complexity: AST scorer implementing the SonarSource specification (nesting increments for
  `if`/`for`/`while`/`except`/`match`/ternary/lambda/nested-def; boolean-operator sequences collapsed to
  one increment; `elif` flat, `else` +1). Scored both with and without nested function bodies; the
  tables here use the "own" figure, which is the fairer one for factories.
- Duplication: token-shingle hashing over logical lines with comments, blanks and docstrings stripped,
  at window sizes 8 and 5, minimum 200 characters.
- Dead code: every top-level `def`/`class`/method/`UPPER_CONST` indexed, then counted against an
  identifier sweep of `packages`, `scripts`, `tests`, `docs`, `README.md` and `CHANGELOG.md`. Every
  candidate was re-verified with a direct grep before being reported.
- Dead CSS: every declared class matched against class tokens actually *used* - `class="..."`,
  `classList.*()`, `querySelector*()`, `closest()` - across `app.js`, `index.html`, and the one Python
  site that emits HTML (`server.py:61-67`, the stale banner). Substring matching gives a false clean
  bill here: `.progress` looks used because `progress-wrap` contains it. Custom properties were
  checked in both directions, which is what surfaced F40.
- Typing: `mypy --strict` over the four trees the gate covers, diffed against the configured run.
- Gate state: `make check` run before and after. **697 passed, exit 0.** Collection verified stable at
  697 over four runs and identical with and without this file, so the report is inert to the suite.
  `scripts/normalize_dashes.py` reads `git ls-files`, so an untracked report is outside its scope; this
  file was therefore checked for `U+2014` and the mangled `word` + hyphen + space + `word` shape by
  hand, and is clean of both. It will pass `dash-check` once committed.
