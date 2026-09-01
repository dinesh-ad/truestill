# (ajj) THREE COMMANDS LET A CATALOG WRITE ESCAPE TO THE USER, AND ONLY ONE OF THEM CATCHES IT

*Body of backlog entry `(ajj)`, under **Approved - still to build**. The index is
[`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-09-01 (P171) from `(ajg)`'s own *"what is not established"*: **do `migrate` and `undo`
have the same shape?** Enumerated by reading each loop's handler, the way `_copy_missing`'s was
read - never by collecting defects.

## 🔑 THE ANSWER TO THE ASKED QUESTION IS NO, AND IT IS STRUCTURAL RATHER THAN LUCKY

`(ajg)` was possible because `backup` **re-raises**. The others do not.

| command | how an abort leaves core | what the surface must do |
|---|---|---|
| `backup` | `_copy_missing` catches `Exception`, writes the record, and **re-raises** (wrapped for `OSError`, bare otherwise) | **catch** - and it did not, which was `(ajg)` |
| `migrate-layout --apply` | `run_migration` catches `DestinationError` **per move**, appends to `refused` or sets `stop`, and **returns `AppliedMoves`** | **render** - `_report_migration_shortfall(outcome.stopped, outcome.refused)` |
| `migrate-layout --undo` | the reversal loop catches `DestinationError` the same way and returns `UndoOutcome` | render |
| `undo-organize` | `undo.py` catches `OSError` per step into `UndoSkipped`, stops via `persists_for_the_run`, and returns | render; `UndoError` (pre-flight only) **is** caught |

**So `_cmd_migrate_layout` and `_cmd_migrate_undo` having no `except` at all is CORRECT.** Nothing
raises past those loops for the abort case; the outcome is data. `migrate.py` contains exactly two
`raise` statements - `VerificationFailedError` at `:1098` and `:1489` - and
`VerificationFailedError` **subclasses `DestinationError`**, so both land in the handler two lines
away. `undo.py` raises `UndoError` three times, all pre-flight, all caught.

## ⚠ BUT THE RESIDUAL CLASS IS SHARED, AND NOW ASYMMETRIC

A **catalog write** inside each loop raises `sqlite3.Error`, which is neither a `DestinationError`
nor an `OSError`:

* `migrate`: `_apply_move(catalog, ...)` writes inside the `try` whose only arm is
  `except DestinationError`.
* `undo`: `catalog.forget_organized(...)` is called **after** the `except OSError` block entirely.

**Neither is caught anywhere between there and `main`.** So a locked or unwritable catalog reaches
the user as a traceback on both - `(ajg)`'s shape, in a class `(ajg)` did not measure either.

🔑 **`backup` now catches it and these two do not**, because `cli._BACKUP_STOPS` lists
`sqlite3.Error`. That asymmetry is deliberate for now and is the reason this entry exists rather
than three more arms: `(ajg)` was a **measured** traceback and the `sqlite3` arm cost one word
inside a boundary handler that had to be written anyway. Here there is no boundary handler, no
measured case, and wording a stop for `migrate` means inventing a sentence for a state nothing has
produced. **Adding handlers on a code read alone is the move `(aji)` was deliberately not allowed
to make.**

## WHAT WOULD SETTLE IT

1. **Is it reachable?** `catalog_busy` already exists as a condition with its own wording
   (`CATALOG_BUSY_MESSAGE`, read by `jobs.py`), so a second process holding the catalog is a
   *known* live state - what is unknown is whether it can arrive **mid-loop** rather than at open.
   A test that holds the catalog from another process and starts a migration would answer it in
   one run.
2. **If it is reachable**, the fix is the shape `(ajg)` used: one boundary per surface, the
   enumeration written down, and `is_catalog_busy` / `is_catalog_unwritable` reused for the
   wording so the CLI says what `jobs.py` already says on the app side.

## WHAT IS ESTABLISHED, SO IT IS NOT RE-DERIVED

- `migrate` and `undo` **do not** have `(ajg)`'s measured shape. The null is real and it is the
  answer to the question that was asked.
- Both share one **unmeasured** residual class with the `backup` fix, and the fix already covers
  `backup` alone.
- ⚠ **Nothing here has been run.** Every line above is a read of today's source; no catalog was
  locked and no migration was interrupted.

## RELATED

`(ajg)` (the measured instance, shipped), `(aji)` (the other half of the same reading),
`(agi)` (the persistence predicate all three loops share), `(afe)` (catalog-unwritable wording).
