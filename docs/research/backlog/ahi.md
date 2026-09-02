# (ahi) TWO OF TEN MUTATING OPERATIONS WRITE NO RUN RECORD, AND THE CENSUS IS KEYED BY MODULE, NOT BY THE OPERATION A ROUTE DECLARES.

*Body of backlog entry `(ahi)`, under **Internal / tooling**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahi) TWO OF TEN MUTATING OPERATIONS WRITE NO RUN RECORD, AND THE CENSUS IS KEYED BY MODULE, NOT BY THE OPERATION A ROUTE DECLARES.** Filed 2026-08-25 (P72).

  ## ⚠ CORRECTED 2026-09-02 (P191) - READ THIS BEFORE THE MEASUREMENT BELOW

  Ten mutating operations, not nine (`rename`, `(aix)`); the census holds **six** module rows and
  **four** entry-point rows; **two** remain, `archive unpack` (`service/takeout.py:archive_ingest_run`)
  and `clean empty` (`service/clean_empty.py:clean_empty_apply`) - each confirmed `False` by the
  guard's own `_reaches_a_record`. `service/migrate.py` writes no record itself and records on both
  paths through core, so the sentence below about it is true of the module and misleading about
  the operation. Three operation strings have no row keyed as their route declares them:
  `undo organize`, `set dates`, `trip apply`. **The shipped undo record has no behavioural test**
  - `git grep '"migrate undo"' -- packages` hits `migrate.py` only. Neither remaining operation
  has a durable per-file store (the staging journal in `archive_extract.py:_write_journal` holds a
  root and part names; `cleanup.py` never touches a catalog), so each record is the only account.
  **Ruled 2026-09-02 by the maintainer: clean-empty's record NAMES THE FOLDERS**, and
  `plan.removable` minus failures over-claims - an already-gone folder is neither removed nor
  failed - so `cleanup.py:CleanupOutcome` must carry the names. The original measurement follows.

  ## MEASURED

  `test_the_app_records_what_a_run_did.py`'s `MUTATING_RUNS` holds five rows: organize, backup,
  migrate, bake, organize_undo. Enumerated from `server.py` by **AST** - every call with
  `mutating=True`, reading the `operation=` beside it - there are **nine**:

  | in the census | absent from it |
  |---|---|
  | organize, backup, migrate, bake, undo organize | **trip apply**, **archive unpack**, **clean empty**, **undo** (migrate's) |

  And none of `service/trips.py`, `service/clean_empty.py` or `service/migrate.py` calls a record
  entry point - checked, 0 hits each.

  ## ⚠ P69'S OWN DOCSTRING PREDICTED THIS, WORD FOR WORD

  > *"a new mutating service that writes no record cannot be detected, because nothing in this
  > codebase declares the set of mutating services. `server.py`'s `mutating=True` marks routes,
  > not modules, and the operation strings do not map onto file names."*

  It was written as an honestly stated limit. It is now a **measured gap**: four operations
  outside the census that exists precisely to make an absence visible. That is the same hand-list
  blind spot `cli-app-parity.md` carries, occurring inside the guard written against that class.

  ## THE RELATIONSHIP TO `(ahj)`

  `(ahj)`'s nine-row declared table would **subsume** this: once every `mutating=True` operation
  must have a row, the four missing here cannot stay missing. Building `(ahj)` first and letting
  it carry this is likely cheaper than filling this table and then replacing it - but that is a
  ruling, not a foregone conclusion, and it is why both are filed rather than merged.

  ## ⚠ THE UNDO HALF SHIPPED 2026-08-29 (P139) - TWO REMAIN

  `migrate.undo_migration` wrote nothing; it now calls `_record_undo_migration` on the applied
  path, with `kind="migrate undo"` and the `undid_run_id` of the run it reversed, so the pair a
  reader needs together is connected. **Ranked first of the three deliberately**: every other
  record says a run moved files, so without this one the newest thing the history describes is a
  state the disk is no longer in.

  🔑 **It carries per-file detail, and that is `(agm)`'s bake question answered the OTHER WAY.**
  Bake writes a line and no detail because `file_copies.date_baked_at` is a permanent per-copy
  timestamp. A migration's per-file store is `migration_journal`, and
  `Catalog.start_migration_run` **deletes the previous run's journal for that drive** - retention
  ONE - so a second migration erases the only other account of what the reversal put back. Entries
  are failures-only, matching the forward path's `(afd)` ruling on the same data shape.

  ⚠ **AND THE GUARD IS WHY THIS SURVIVED, SO IT WAS FIXED FIRST.**
  `test_the_app_records_what_a_run_did.py`'s floor named `("trips", "clean_empty", "takeout")` and
  was **wrong in both directions**: `trip apply` RECORDS - its route reaches
  `service/migrate.py::migration_apply` then `_record_migration` - so it was never in this entry's
  remaining set; while the operation that genuinely wrote nothing was **invisible**, because
  `_wires_a_record` asked about a MODULE and `service/migrate.py` records on the forward path. The
  guard now asks per **entry point** (`ENTRY_POINTS`, `_reaches_a_record`), a bounded call-graph
  walk. **Reproduced to prove it**: with the record deleted, the old module-granular question still
  answers `True` for `migrate`.

  ⚠ **A limit of the fixed guard, stated rather than discovered later**: it sees a CALL, not
  whether the branch runs. A first mutation that disabled the call with `and False` survived it;
  deleting the call is what it catches. Static reachability cannot answer the other question, and
  the behavioural half is `test_migrate.py`'s undo tests.

  **`archive unpack` and `clean empty` remain**, declared `False` in the guard with their reasons
  rather than left invisible. Each needs its own judgement about what its line says and what
  detail it honestly holds - they are not this fix repeated, because neither has a durable
  per-file store to reason from the way migrate's journal gave one here.
