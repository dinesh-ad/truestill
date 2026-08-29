# (aim) THE SUMMARY PRINTS A PLAN-DERIVED COUNT IN OUTCOME TENSE, BEFORE THE OUTCOME EXISTS.

*Body of backlog entry `(aim)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aim) THE SUMMARY PRINTS A PLAN-DERIVED COUNT IN OUTCOME TENSE, BEFORE THE OUTCOME EXISTS.**
  Filed 2026-08-29 (P141), from code and four prior measurements. **A shape, not a bug list** -
  and it is filed **before** `(aie)` is fixed deliberately, because fixing `(aie)` first would
  delete the fourth instance and leave the shape standing, which is how the first three survived.

  ## THE MECHANISM

  `cli._print_summary(resolutions: list[Resolution])` computes *"organized (unique): N"* from
  `models.partition_for_report` - **the plan**. `cli._print_execution` computes *"N failed"* from
  `ActionStatus` - **the outcome**. Two objects, **no shared arithmetic and no cross-check**.

  🔑 **And the summary is printed BEFORE anything is written, including under `--apply`.**
  `_print_run_reports` runs before `execute(...)` and is called unconditionally; only the per-file
  listings are gated on `--apply`, never the counts. Its own docstring says so - *"before it is
  allowed to write anything … the plan, while the user can still stop it"* - so a number that is
  honest as a **plan** is printed in the **past tense** at the moment the user decides whether the
  run worked. `(abl)` corrected the *listing* headers away from *"would be"* and never reached
  `_print_summary`.

  ## FOUR FILED INSTANCES, FOUR DIFFERENT CAUSES, NONE CONNECTED TO THE OTHERS

  | letter | what the summary said | why it was false |
  |---|---|---|
  | `(aac)` residue 1 | *"organized (unique): 5"* + *"could not be read: 2"* over the same **seven** files | the buckets **overlapped** |
  | `(aer)` | *"files analysed: 3 · organized (unique): 3"* | **scope silently excluded** 18 files in a hidden folder |
  | `(afe)` | *"organized (unique): 3, exit 0"* while **6 files** were on disk | a **duplicate was written**, uncounted |
  | `(aie)` | *"organized (unique): 3"* beside *"3 failed"* | **execution failed after the count was computed** |

  ⚠ **THAT CENSUS IS NOT COMPLETE AND MUST NOT BE READ AS ONE.** Four instances were found because
  four letters happened to be filed; the unit was *what somebody wrote down*. Traced against code,
  the count can diverge by **eight routes inside `organize` alone**, and **two involve no failure
  whatsoever**:

  1. **`--skip-undated`** - a readable, unmatched, undated file is in `buckets.unique` and is never
     copied. `ReportBuckets.will_organize(skip_undated=…)` exists in core to answer exactly this,
     and `_print_summary` **does not call it**.
  2. **User cancel** - every file after the break yields *no `ActionResult` at all*.
  3. a destination/drive health stop · 4. `CatalogWriteError` · 5. a persistent `OSError`
     (`ENOSPC`/`EDQUOT`/`EIO`/`EROFS`) · 6. `RunStoppedError` · 7. a per-file copy failure, which
     is `(aie)` · 8. **`MOVE_KEPT`** - a file that *did* land but whose source-delete failed,
     counted as neither organized nor failed.

  🔑 **ON FOUR OF THOSE ROUTES THE CORRECTING BLOCK NEVER PRINTS.** On a stopped run
  `_stopped_run_exit` returns before `_print_execution`, so the user sees *"organized (unique):
  3"*, one `error:` line, and exit 4 - **the plan number is the only count on screen.** No filed
  letter recorded that, and it is the sharpest form of the shape.

  ## ⚠ THE CLASS IS *NOT* CODEBASE-WIDE, AND SAYING SO IS HALF THE VALUE

  Every command that prints counts was checked, by finding its printing symbol, reading **which
  object the number comes from**, and asking whether the **tense matches the source** - not by
  grepping for a word:

  | command | verdict |
  |---|---|
  | **organize** | ❌ plan number, outcome tense, printed first |
  | **backup** | ✅ *"{n} file(s) **to copy**"* then *"**Copied** {outcome.copied}"* |
  | **reclaim** | ✅ *"{n} file(s) … **would be freed**"* + *"Preview only"* |
  | **verify** | ✅ read-only - the report **is** the outcome, no gap possible |
  | **repoint / migrate** | ✅ `_print_repoint_preview`, a preview by name |
  | **dedup** | n/a - **no such subcommand**, which is `(ail)`'s retired phantom |

  **`organize` is the outlier.** The shape is *a plan-derived number printed in outcome tense*, one
  command does it, and it does it on eight paths.

  ## THE FIX ALREADY EXISTS TWICE IN THIS REPOSITORY - DO NOT DESIGN A THIRD

  - **`backup`'s tense**: the plan number says *"to copy"*, the outcome number says *"Copied"*.
  - **The app's two documents**: `service/organize.py`'s `_completion` reports `len(organized)`
    from `_ORGANIZED_STATUSES` - execution truth - while the plan number lives on a different
    screen as `will_organize`, *"THE NUMBER THE SCREEN PROMISES"*. **The app already solved this;
    the CLI prints both in one scroll with the plan first.**

  ⚠ **`(aac)`'s conservation law is the right shape on the wrong axis**, and this is why it did not
  catch the later three: `new_unique + near_dup + exact_dup + unreadable == files` is asserted over
  `partition_for_report`'s **plan** buckets and pinned by a **preview** tally test. `(aie)` has
  perfectly consistent buckets and then fails during execution. Extending that law from
  plan-consistency to **plan-versus-outcome** is the shape of a guard; it is not proposed here.

  ⚠ **One app caveat to carry**: `MOVE_KEPT` is in neither `_ORGANIZED_STATUSES` nor `failed`, so a
  file can fall out of **both** tallies there too. The app solved the tense, not the completeness.

  ## RELATED

  `(aac)`, `(aer)`, `(afe)`, `(aie)` (the four instances), `(abl)` (the tense correction that
  stopped short of `_print_summary`), `(ain)` (a different orphan on the same mount),
  [`soak-eight-record.md`](../../soak-eight-record.md).
