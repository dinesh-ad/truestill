# (afw) THE OTHER FOUR MUTATING APP RUNS WRITE NO RECORD, AND ONLY ONE OF THEM COULD TODAY.

*Body of backlog entry `(afw)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afw)** Recorded 2026-08-22, split out of `(afu)` **before** it was built rather than
  discovered afterwards. `IMPLEMENTATION_STANDARDS.md` §1 says *"a run that changes the library
  writes down what it did"* - **a run**, not an organize - and `(afu)` carried that to exactly one
  of the app's five.

  ## WHY IT IS A SPLIT AND NOT A SHORTFALL

  ⚠ **Organize is the only app run with a per-file outcome list.** `(afu)` was a wiring change
  because the data was already there; for the rest it is a **design**, and folding them in would
  have put an unanswered partial-failure question inside a move. Measured per surface:

  | run | what it has | why it cannot simply be wired |
  |---|---|---|
  | **organize** | `resolutions` + `results: list[ActionResult]` | ✅ shipped as `(afu)` |
  | **backup** | `copied_names: list[str]` - **successes only** | `_copy_verified_or_raise` **raises**, so the run is fail-fast: on failure the summary is never built and the list dies with it. There is no per-file outcome model to record |
  | **migrate** | `MigrationOutcome`: per-file **plan** (`plan.moves`) plus `resumed`/`migrated` **counts** | no per-file outcome. Its durable per-file state already exists as **`migration_journal`**, which is how it resumes |
  | **bake** | counts | - |
  | **organize_undo** | counts | - |

  Enumerated and pinned: `test_the_app_records_what_a_run_did.py` asserts each of the five as
  writing or not writing **with its reason**, so an absence is recorded rather than merely true.

  ## 🔑 THE QUESTION TO ANSWER FIRST, AND IT IS NOT ABOUT RECORDS

  **`backup_run` is fail-fast, and §1 says the opposite for the ordinary case:**

  > *"Partial-failure policy: one bad file never aborts a batch - it is logged, counted, and
  > reported at the end."*

  §1 states **one** exception - *"a failure that costs the RECORD of work already done"* - and
  backup's raise is not obviously it: a copy that fails leaves the source untouched and the
  earlier copies recorded, which is the ordinary skippable case. ⚠ **So this may be a live §1
  violation rather than a missing record**, and if it is, the record follows from fixing it rather
  than the other way round. **Do not build a record for backup until that is ruled**, or the
  record will faithfully document a policy nobody decided.

  ## NOT DECIDED

  - **Whether migrate should write one at all**, given `migration_journal` already holds per-file
    state durably and survives a crash the record explicitly does not (`(afl)`'s stated limit:
    *"written after execution, so it survives a stop and not a kill"*). A second copy of the same
    facts with weaker guarantees is a cost, not a feature.
  - **Whether count-only runs deserve a record.** A file saying *"12 baked"* answers a question
    the completion screen already answered and adds a file to prune. The argument for one is
    consistency; the argument against is that `(afl)`'s value was **naming what failed**, which a
    count cannot do.
  - **One rolling file per catalog, with a job runner.** The app can have two jobs in flight on
    two drives; `(aaw)`'s lock makes that safe per drive and does not serialise different drives,
    so one rolling `last-run.json` would be overwritten by whichever finished last. A CLI never
    had to answer this. **This is the part to design before any second writer is added**, and
    `(afu)` did not hit it because organize is currently the only writer.

  ## RELATED

  `(afu)` (the surface that shipped, and the enumeration guard), `(afl)` (the record itself),
  `(aaw)` (the per-drive lock that makes the concurrency question answerable), `(aem)`
  (`organize_runs`, which covers the killed run from the other side and is already cross-surface).
