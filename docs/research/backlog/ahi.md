# (ahi) THE RECORD-STATE CENSUS COVERS 5 OF 9 MUTATING OPERATIONS.

*Body of backlog entry `(ahi)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahi) THE RECORD-STATE CENSUS COVERS 5 OF 9 MUTATING OPERATIONS.** Filed 2026-08-25 (P72).

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
